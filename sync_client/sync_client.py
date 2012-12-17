# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import osv
from osv import fields
from osv import orm
from tools.translate import _

import socket
import rpc
import uuid
import tools
import time
import sys
import traceback

import logging
from sync_common.common import sync_log

from threading import Thread, RLock
import pooler
from datetime import datetime

import functools

class SkipStep(StandardError):
    pass

class BackgroundSynchronisation(Thread):

    def __init__(self, dbname, uid, context):
        super(BackgroundSynchronisation, self).__init__()
        self.dbname = dbname
        self.uid = uid
        self.context = context

    def run(self):
        db, pool = pooler.get_db_and_pool(self.dbname)
        cr = db.cursor()
        try:
            pool.get('sync.client.entity').sync(cr, self.uid, self.context)
            cr.commit()
        except:
            pass
        finally:
            cr.close()

class entity(osv.osv):
    """ OpenERP entity name and unique identifier """
    _name = "sync.client.entity"
    _description = "Synchronization Instance"
    
    _logger = logging.getLogger('sync.client')

    def _auto_init(self,cr,context=None):
        res = super(entity,self)._auto_init(cr,context=context)
        if not self.search(cr, 1, [], context=context):
            self.create(cr, 1, {'identifier' : self.generate_uuid()}, context=context)
        return res
    
    def _get_state(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for entity in self.browse(cr, uid, ids, context=context):
            session_id = entity.session_id
            max_update = entity.max_update
            msg_send = int(entity.message_to_send)
            upt_send = int(entity.update_to_send)
            if not any([session_id, max_update, msg_send, upt_send]):
                res[entity.id] = 'init'
            elif not any([session_id, max_update, upt_send]) and msg_send:
                res[entity.id] = 'msg_push'
            elif not any([max_update, msg_send]) and upt_send and session_id:
                res[entity.id] = 'update_send'
            elif not any([max_update, msg_send, upt_send]) and session_id:
                res[entity.id] = 'update_validate'
            elif not any([session_id, msg_send, upt_send]) and max_update:
                res[entity.id] = 'update_pull'
            else:
                res[entity.id] = 'corrupted'
        return res
    
    def _get_nb_message_send(self, cr, uid, ids, name, arg, context=None):
        nb = self.pool.get('sync.client.message_to_send').search_count(cr, uid, [('sent', '=', False), ('generate_message', '=', False)], context=context)
        return self._encapsulate_in_dict(nb, ids)
    
    def _get_nb_update_send(self, cr, uid, ids, name, arg, context=None):
        nb = self.pool.get('sync.client.update_to_send').search_count(cr, uid, [('sent', '=', False)], context=context)
        return self._encapsulate_in_dict(nb, ids)
    
    def _encapsulate_in_dict(self, value, ids):
        res= {}
        for id in ids:
            res[id] = value 
        return res
   
    def _entity_unique(self,cr,uid,ids,context=None):     
        return self.search(cr, uid,[(1, '=', 1)],context=context,count=True) == 1
    
    _columns = {
        'name':fields.char('Instance Name', size=64, readonly=True),
        'identifier':fields.char('Identifier', size=64, readonly=True), 
        'parent':fields.char('Parent Instance', size=64, readonly=True),
        'update_last': fields.integer('Last update', required=True),
        'update_offset' : fields.integer('Update Offset', required=True, readonly=True),
        'message_last': fields.integer('Last message', required=True),
        'email' : fields.char('Contact Email', size=512, readonly=True),
        
        'state' : fields.function(_get_state, method=True, string='State', type="char", readonly=True),
        'session_id' : fields.char('Push Session Id', size=128),
        'max_update' : fields.integer('Max Update Sequence', readonly=True),
        'message_to_send' : fields.function(_get_nb_message_send, method=True, string='Nb message to send', type='integer', readonly=True),
        'update_to_send' : fields.function(_get_nb_update_send, method=True, string='Nb update to send', type='integer', readonly=True),
    }
    
    _constraints = [
        (_entity_unique,_('The Instance is unique, you cannot create a new one'), ['name','identifier'])
    ]

    _defaults = {
        'name' :  lambda self, cr, uid, c={}: cr.dbname,
        'update_last' : 0,
        'update_offset' : 0,
        'message_last' : 0,
    }
    
    state_prefix = {
        'data_pull' : 'Pull Update',
        'msg_pull' : 'Pull Message',
        'data_push' : 'Push Update',
        'msg_push' : 'Push Message',
    }

    def get_entity(self, cr, uid, context=None):
        ids = self.search(cr, uid, [], context=context)
        return self.browse(cr, uid, ids, context=context)[0]
    
    def generate_uuid(self):
        return uuid.uuid1().hex
        
    def get_uuid(self, cr, uid, context=None):
        return self.get_entity(cr, uid, context=context).identifier

    def __init__(self, *args, **kwargs):
        self.sync_lock = RLock()
        super(entity, self).__init__(*args, **kwargs)

    def sync_process(step='status', is_step=None):
        is_step = not (step == 'status')

        def decorator(fn):

            @functools.wraps(fn)
            def wrapper(self, cr, uid, context=None, *args, **kwargs):

                # First, check if we can acquire the lock or return False
                if not self.sync_lock.acquire(blocking=False):
                    raise osv.except_osv('Already Syncing...', 'OpenERP can only perform one synchronization at a time - you must wait for the current synchronization to finish before you can synchronize again.')

                # Lock is acquired, so don't put any code outside the try...catch!!
                try:
                    # are we creating a new log line?
                    make_log = not getattr(self, 'log_id', False)
                    
                    # we have to make the log
                    if make_log:
                        # let's make the private log cursor
                        self.log_cr = pooler.get_db(cr.dbname).cursor()
                        self.log_cr.autocommit(True)

                        # Init log dict for sync.monitor
                        self.log_info = {
                            'error' : '',
                            'status' : 'in-progress',
                            'data_pull' : 'null',
                            'msg_pull' : 'null',
                            'data_push' : 'null',
                            'msg_push' : 'null',
                        }
                        # already create the log to get the id early
                        self.log_id = self.pool.get('sync.monitor').create(self.log_cr, uid, self.log_info, context=context)

                        # Check if connection is up
                        con = self.pool.get('sync.client.sync_server_connection')
                        con.connect(cr, uid, context=context)
                        # connect() raise an osv.except_osv if something goes wrong
                        # Check for update (if connection is up)
                        if hasattr(self, 'upgrade'):
                            # TODO: replace the return value of upgrade to a status and raise an error on required update
                            up_to_date = self.upgrade(cr, uid, context=context)
                            if not up_to_date[0]:
                                raise osv.except_osv(_("Error!"), _("Revision Update Failed: %s") % up_to_date[1])
                            elif 'last' not in up_to_date[1].lower():
                                self.log_info['error'] += "Revision Update Status: " + up_to_date[1]

                    # update log line
                    self.pool.get('sync.monitor').write(self.log_cr, uid, [self.log_id], self.log_info, context=context)

                    # ah... we can now call the function!
                    res = fn(self, cr, uid, *args, **kwargs)
                except SkipStep:
                    # res failed but without exception
                    assert is_step, "Cannot have a SkipTest error outside a sync step process!"
                    self.log_info[step] = 'null'
                    self.log_info['error'] += "%s: Not a valid state, skipped.\n" % self.state_prefix[step]
                    if make_log:
                        raise osv.except_osv(_('Error!'), "You cannot perform this action now.")
                except osv.except_osv, e:
                    self.log_info[step] = 'failed'
                    if not is_step:
                        self.log_info['error'] += e.value
                    raise
                except BaseException, e:
                    self.log_info[step] = 'failed'
                    error = unicode(e)
                    if is_step:
                        self._logger.exception('Error in sync_process at step %s' % step)
                        self.log_info['error'] += "%s: %s\n" % (self.state_prefix[step], error)
                    if make_log:
                        raise osv.except_osv(_('Error!'), error)
                    else:
                        raise
                else:
                    self.log_info[step] = 'ok'
                    if isinstance(res, (str, unicode)) and res:
                        if is_step:
                            self.log_info['error'] += "%s: %s\n" % (self.state_prefix[step], res)
                        else:
                            self.log_info['error'] += res + "\n"
                finally:
                    # if we created the log, we close it
                    if make_log:
                        self.log_info['status'] = self.log_info[step]
                        self.log_info['end'] = fields.datetime.now()
                    # update the log
                    self.pool.get('sync.monitor').write(self.log_cr, uid, [self.log_id], self.log_info, context=context)
                    # if we created the log, we close it
                    if make_log:
                        self.log_id = False
                        self.log_cr.close()
                    # gotcha!
                    self.sync_lock.release()
                return res

            return wrapper
        return decorator

    def last_log_status(self, cr, uid, context=None):
        if not hasattr(self, 'log_info'):
            monitor = self.pool.get("sync.monitor")
            monitor_ids = monitor.search(cr, uid, [], context=context, limit=1, order='sequence_number desc')
            if monitor_ids:
                self.log_info = monitor.read(cr, uid, monitor_ids, context=context)[0]
            else:
                self.log_info = {}
        return self.log_info
       
    """
        Push Update
    """
    @sync_process('data_push')
    def push_update(self, cr, uid, context=None):

        context = context or {}
        entity = self.get_entity(cr, uid, context)
        
        if entity.state not in ['init', 'update_send', 'update_validate']: 
           raise SkipStep
    
        cont = False
        if cont or entity.state == 'init':
            self.create_update(cr, uid, context=context)
            cr.commit()
            cont = True
            self._logger.info("init")
        if cont or entity.state == 'update_send':
            self.send_update(cr, uid, context=context)
            cr.commit()
            cont = True
            self._logger.info("sent update")
        if cont or entity.state == 'update_validate':
            self.validate_update(cr, uid, context=context)
            cr.commit()
            self._logger.info("validate update")

        return True

    
    def create_update(self, cr, uid, context=None):
        entity = self.get_entity(cr, uid, context)
        
        def set_rules(id):
            proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
            uuid = entity.identifier
            res = proxy.get_model_to_sync(uuid)
            if res and res[0]:
                self.pool.get('sync.client.rule').save(cr, uid, res[2], context=context)
                self.write(cr, uid, [id], {'session_id' : res[1]})
            elif res and not res[0]: raise Exception, res[1]
            return True
        
        def prepare_update(id):
            session_id = self.browse(cr, uid, id, context=context).session_id
            ids = self.pool.get('sync.client.rule').search(cr, uid, [], context=context)
            for rule_id in ids:
                self.pool.get('sync.client.update_to_send').create_update(cr, uid, rule_id, session_id, context=context)
        
        set_rules(entity.id)
        prepare_update(entity.id)
        return True
        #state init => update_send
        
    def send_update(self, cr, uid, context=None):
        entity = self.get_entity(cr, uid, context=context)
        def send_package(id):
            uuid = entity.identifier
            session_id = self.browse(cr, uid, id, context=context).session_id
            max_packet_size = self.pool.get("sync.client.sync_server_connection")._get_connection_manager(cr, uid, context=context).max_size
            res = self.pool.get('sync.client.update_to_send').create_package(cr, uid, session_id, max_packet_size)
            if res:
                ids = res[0]
                packet = res[1]
                
                proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
                res = proxy.receive_package(uuid, packet, context)
                if res and res[0]:
                    self.pool.get('sync.client.update_to_send').write(cr, uid, ids, {'sent' : True}, context=context)
                elif res and not res[0]:
                    raise Exception, res[1]
                return True
            return False
        
        send_more = True
        i = 0
        while send_more:
            if i % 20 == 0:
                self._logger.debug("send package %s" % i)
            send_more = send_package(entity.id)
            i += 1
        #state update_send => update_validate
        return True

    def validate_update(self, cr, uid, context=None):
        entity = self.get_entity(cr, uid, context)
        session_id = entity.session_id
        update_obj = self.pool.get('sync.client.update_to_send')
        update_ids = update_obj.search(cr, uid, [('session_id', '=', session_id)], context=context)
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
        res = proxy.confirm_update(entity.identifier, session_id, context)
        if res and res[0]:
            update_obj.sync_finished(cr, uid, update_ids, context=context)
            self.write(cr, uid, entity.id, {'session_id' : ''}, context=context)
        elif res and not res[0]:
            raise Exception, res[1]
        #state update validate => init 
        return True
    
    
    """
        Pull update
    """
    @sync_process('data_pull')
    def pull_update(self, cr, uid, recover=False, context=None):
        
        context = context or {}
        entity = self.get_entity(cr, uid, context)
        
        if entity.state not in ['init', 'update_pull']: 
            raise SkipStep
        
        if entity.state == 'init': 
            self.set_last_sequence(cr, uid, context)
        
        self.retrieve_update(cr, uid, recover=recover, context=context)
        cr.commit()

        res = self.pool.get('sync.client.update_received').execute_update(cr, uid, context=context)
        cr.commit()
        return res
    

    def set_last_sequence(self, cr, uid, context=None):
        entity = self.get_entity(cr, uid, context)
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
        res = proxy.get_max_sequence(entity.identifier, context)
        if res and res[0]:
            return self.write(cr, uid, entity.id, {'max_update' : res[1]}, context=context)
        elif res and not res[0]:
            raise Exception, res[1]

        return True

    def retrieve_update(self, cr, uid, recover=False, context=None):
        entity = self.get_entity(cr, uid, context)
        last = False
        last_seq = entity.update_last
        max_packet_size = self.pool.get("sync.client.sync_server_connection")._get_connection_manager(cr, uid, context=context).max_size
        max_seq = entity.max_update
        offset = entity.update_offset
        #Already up-to-date
        if last_seq >= max_seq:
            last = True
        while not last:
            proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
            res = proxy.get_update(entity.identifier, last_seq, offset, max_packet_size, max_seq, recover, context)
            if res and res[0]:
                nb_upate = self.pool.get('sync.client.update_received').unfold_package(cr, uid, res[1], context=context)
                last = res[2]
                if res[1]:
                    offset = res[1]['offset']
                    self.write(cr, uid, entity.id, {'update_offset' : offset}, context=context)
            elif res and not res[0]:
                raise Exception, res[1]
        
        return self.write(cr, uid, entity.id, {'update_offset' : 0, 
                                        'max_update' : 0, 
                                        'update_last' : max_seq}, context=context) 



    """
        Push message
    """
    @sync_process('msg_push')
    def push_message(self, cr, uid, context=None):

        context = context or {}
        entity = self.get_entity(cr, uid, context)
        
        if entity.state not in ['init', 'msg_push']: 
            raise SkipStep
        
        if entity.state == 'init':
            self.create_message(cr, uid, context)
            cr.commit()
        self.send_message(cr, uid, context)
        cr.commit()

        return True
        
    def create_message(self, cr, uid, context=None):
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
        uuid = self.pool.get('sync.client.entity').get_entity(cr, uid, context=context).identifier
        res = proxy.get_message_rule(uuid)
        if res and not res[0]: raise Exception, res[1]
        self.pool.get('sync.client.message_rule').save(cr, uid, res[1], context=context)
        
        rule_obj = self.pool.get("sync.client.message_rule")
        rules_ids = rule_obj.search(cr, uid, [], context=context)
        for rule in rule_obj.browse(cr, uid, rules_ids, context=context):
            self.pool.get("sync.client.message_to_send").create_from_rule(cr, uid, rule, context=context)
            
        return True
    
    def send_message(self, cr, uid, context=None):
        max_packet_size = self.pool.get("sync.client.sync_server_connection")._get_connection_manager(cr, uid, context=context).max_size
        uuid = self.pool.get('sync.client.entity').get_entity(cr, uid, context=context).identifier
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
        packet = True
        while packet:
            message_obj = self.pool.get('sync.client.message_to_send')
            packet = message_obj.get_message_packet(cr, uid, max_packet_size, context=context)
            if packet:
                res = proxy.send_message(uuid, packet)
                if res and not res[0]: raise Exception, res[1]
                message_obj.packet_sent(cr, uid, packet, context=context)
        return True
        #message_push => init
        
    
    """ 
        Pull message
    """
    @sync_process('msg_pull')
    def pull_message(self, cr, uid, recover=False, log=None, context=None):

        context = context or {}
        entity = self.get_entity(cr, uid, context)
        if recover:
            proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
            proxy.message_recover_from_seq(entity.identifier, entity.message_last, context)

        if not entity.state in ['init']:
            raise SkipStep
        
        self.get_message(cr, uid, context)
        cr.commit()
        self.execute_message(cr, uid, context)
        cr.commit()

        return True
        
    def get_message(self, cr, uid, context):
        def _ack_message(proxy, uuid, message_uuid):
            res = proxy.message_received(uuid, message_uuids)
            if res and not res[0]:
                raise Exception, res[1]
             
        packet = True
        max_packet_size = self.pool.get("sync.client.sync_server_connection")._get_connection_manager(cr, uid, context=context).max_size
        entity = self.get_entity(cr, uid, context)
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
        while packet:
            res = proxy.get_message(entity.identifier, max_packet_size)
            if res and not res[0]:
                raise Exception, res[1]

            if res and res[1]:
                packet = res[1]
                self.pool.get('sync.client.message_received').unfold_package(cr, uid, packet, context=context)
                message_uuids = [data['id'] for data in packet]
                _ack_message(proxy, entity.identifier, message_uuids)
                
            else:
                packet = False

        return True
            
    def execute_message(self, cr, uid, context):
        return self.pool.get('sync.client.message_received').execute(cr, uid, context=context)


    """
        SYNC process : usefull for scheduling 
    """
    def sync_threaded(self, cr, uid, context=None):
        # Check if connection is up
        self.pool.get('sync.client.sync_server_connection').connect(cr, uid, context=context)
        # Check for update (if connection is up)
        if hasattr(self, 'upgrade'):
            up_to_date = self.upgrade(cr, uid, context=context)
            if not up_to_date[0]:
                cr.commit()
                raise osv.except_osv(_('Error!'), _(up_to_date[1]))
        context = context or {}
        t = BackgroundSynchronisation(cr.dbname, uid, context)
        t.start()
        return True

    @sync_process(is_step=True)
    def sync(self, cr, uid, context=None):
        self.pull_update(cr, uid, context=context)
        self.pull_message(cr, uid, context=context)
        self.push_update(cr, uid, context=context)
        self.push_message(cr, uid, context=context)
        return True
        
    def get_upgrade_status(self, cr, uid, context=None):
        return ""

    # Check if lock can be acquired or not
    def is_syncing(self):
        acquired = self.sync_lock.acquire(blocking=False)
        if not acquired:
            return True
        self.sync_lock.release()
        return False

    def get_status(self, cr, uid, context=None):
        if not self.pool.get('sync.client.sync_server_connection').is_connected:
            return "Not Connected"

        if self.is_syncing():
            return "Syncing..."
        
        last_log = self.last_log_status(cr, uid)
        if last_log:
            status_dict = dict( self.pool.get("sync.monitor")._columns['status'].selection )
            status = status_dict[last_log['status']]
            return "Last Sync: %s at %s" % (status, last_log['end'])

        return "Connected"
   
entity()


class sync_server_connection(osv.osv):
    """
        This class handle connection with the server of synchronization
        Keep the username, uid on the synchronization 
        
        Question for security issue it's better to not keep the password in database
           
        This class is also a singleton
        
    """     

    def _auto_init(self,cr,context=None):
        res = super(sync_server_connection,self)._auto_init(cr,context=context)
        if not self.search(cr, 1, [], context=context):
            self.create(cr, 1, {}, context=context)
        return res
    
    def _is_connected(self):
        return getattr(self, '_uid', 0) > 0
    
    is_connected = property(_is_connected)

    def _get_state(self, cr, uid, ids, name, arg, context=None):
        return dict.fromkeys(ids, "Connected" if getattr(self, '_uid', False) else "Disconnected")

    def _get_password(self, cr, uid, ids, field, arg, context):
        return dict.fromkeys(ids, getattr(self, '_password', ''))

    def _set_password(self, cr, uid, ids, field, password, arg, context):
        self._password = password

    def _get_uid(self, cr, uid, ids, field, arg, context):
        return dict.fromkeys(ids, getattr(self, '_uid', ''))

    def unlink(self, cr, uid, ids, context=None):
        self._uid = False
        return super(sync_server_connection, self).unlink(cr, uid, ids, context=context)

    _name = "sync.client.sync_server_connection"
    _description = "Connection to sync server information and tools"
    _rec_name = 'host'

    _columns = {
        'active': fields.boolean('Active'),
        'host': fields.char('Host', help='Synchronization server host name', size=256, required=True),
        'port': fields.integer('Port', help='Synchronization server connection port'),
        'protocol': fields.selection([('xmlrpc', 'XMLRPC'), ('gzipxmlrpc', 'compressed XMLRPC'), ('xmlrpcs', 'secured XMLRPC'), ('netrpc', 'NetRPC'), ('netrpc_gzip', 'compressed NetRPC')], 'Protocol', help='Changing protocol may imply changing the port number'),
        'database' : fields.char('Database Name', size=64),
        'login':fields.char('Login on synchro server', size=64),
        'uid': fields.function(_get_uid, string='Uid on synchro server', readonly=True, type='char', method=True),
        'password': fields.function(_get_password, fnct_inv=_set_password, string='Password', type='char', method=True, store=False),
        'state' : fields.function(_get_state, method=True, string='State', type="char", readonly=True, store=False),
        'max_size' : fields.integer("Max Packet Size"),
    }

    _defaults = {
        'active': True,
        'host' : 'sync.unifield.org',
        'port' : 8070,
        'protocol': 'netrpc_gzip',
        'login' : 'admin',
        'max_size' : 500,
        'database' : 'SYNC_SERVER',
    }
    
    def _get_connection_manager(self, cr, uid, context=None):
        ids = self.search(cr, uid, [], context=context)
        if not ids:
            raise osv.except_osv('Connection Error', "Connection manager not set!")
        return self.browse(cr, uid, ids, context=context)[0]
    
    def connector_factory(self, con):
        if con.protocol == 'xmlrpc':
            connector = rpc.XmlRPCConnector(con.host, con.port)
        elif con.protocol == 'gzipxmlrpc':
            connector = rpc.GzipXmlRPCConnector(con.host, con.port)
        elif con.protocol == 'xmlrpcs':
            connector = rpc.SecuredXmlRPCConnector(con.host, con.port)
        elif con.protocol == 'netrpc':
            connector = rpc.NetRPCConnector(con.host, con.port)
        elif con.protocol == 'netrpc_gzip':
            connector = rpc.GzipNetRPCConnector(con.host, con.port)
        else:
            raise osv.except_osv('Connection Error','Unknown protocol: %s' % con.protocol)
        return connector

    def connect(self, cr, uid, ids=None, context=None):
        if getattr(self, '_uid', False):
            return True
        try: 
            con = self._get_connection_manager(cr, uid, context=context)
            connector = self.connector_factory(con)
            if not getattr(self, '_password', False):
                self._password = con.login
            cnx = rpc.Connection(connector, con.database, con.login, self._password)
            if cnx.user_id:
                self._uid = cnx.user_id
            else:
                raise osv.except_osv('Not Connected', "Not connected to server. Please check password and connection status in the Connection Manager")
        except socket.error, e:
            raise osv.except_osv(_("Error"), _(e.strerror))
        except osv.except_osv:
            raise
        except BaseException, e:
            raise osv.except_osv(_("Error"), _(unicode(e)))
        
        return True

    def action_connect(self, cr, uid, ids, context=None):
        self.connect(cr, uid, ids, context=context)
        return {}
    
    def get_connection(self, cr, uid, model, context=None):
        """
            @return: the proxy to call distant method specific to a model
            @param model: the model name we want to call remote method
        """
        con = self._get_connection_manager(cr, uid, context=context)
        connector = self.connector_factory(con)
        cnx = rpc.Connection(connector, con.database, con.login, con.password, con.uid)
        return rpc.Object(cnx, model)

    def disconnect(self, cr, uid, context=None):
        self._uid = False
        return True
        
    def action_disconnect(self, cr, uid, ids, context=None):
        self.disconnect(cr, uid, context=context)
        return {}

    def write(self, *args, **kwargs):
        # reset connection flag when data changed
        self._uid = False
        return super(sync_server_connection, self).write(*args, **kwargs)

    _sql_constraints = [
        ('active', 'UNIQUE(active)', 'The connection parameter is unique; you cannot create a new one') 
    ]

sync_server_connection()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

