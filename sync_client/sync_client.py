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

import rpc
import uuid
import tools
import time
import sys
import traceback
import logging

from threading import Thread
import pooler
from datetime import datetime

class entity(osv.osv, Thread):
    """ OpenERP entity name and unique identifier """
    _name = "sync.client.entity"
    _description = "Synchronization Instance"
    
    __logger = logging.getLogger('sync.client')


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
        nb = self.pool.get('sync.client.message_to_send').search_count(cr, uid, [('sent', '=', False)], context=context)
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
        'is_syncing' : fields.boolean("Is Currently Syncing?"),
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
    
    def set_syncing(self, cr, uid, status, context=None):
        self.write(cr, uid, self.search(cr, uid, []), {'is_syncing':status}, context=context)

    def generate_uuid(self):
        return uuid.uuid1().hex
        
    def get_uuid(self, cr, uid, context=None):
        return self.get_entity(cr, uid, context=context).identifier

    def _handle_error(self, e):
        try:
            msg = list(e)
            if e[-1] != "\n": e.append("\n")
            return "".join(e)
        except: return str(e) + "\n"

    def stateSync(self, state, log, step, message=None):
        if message:
            error = "%s: %s" % (self.state_prefix[step], message)
            log['error'] = log.get('error', '') + error
        log[step] = state
        return log[step]

    #def _log_error(self, log, e):
    def errorSync(self, e, log, step):
        message = traceback.format_exc()
        error = "%s: %s\n%s" % (self.state_prefix[step], self._handle_error(e), message)
        self.__logger.error(error)
        log['error'] = log.get('error', '') + error
        log[step] = 'failed'
        return log[step]
       
    def startSync(self, cr, uid, log=None, log_id=None, step='status', context=None):
        # Prevent synchronization to be started multiple times
        me = self.get_entity(cr, uid, context)
        if me.is_syncing and log is None:
            return (None, log_id, log)

        # First time we run into startSync()
        if log is None:
            # Init log dict for sync.monitor
            log = {
                'error' : '',
                'status' : 'in-progress',
                'data_pull' : 'null',
                'msg_pull' : 'null',
                'data_push' : 'null',
                'msg_push' : 'null',
            }
            # Check if connection is up
            if not self.pool.get('sync.client.sync_server_connection')._get_connection_manager(cr, uid, context=context).state == 'Connected':
                log['error'] += "Not connected to server. Please check password and connection status in the Connection Manager"
                log['status'] = 'failed'
            # Check for update
            if hasattr(self, 'upgrade'):
                up_to_date = self.upgrade(cr, uid, context=context)
                if not up_to_date[0]:
                    log.update({
                        'end' : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'error' : log['error'] + "Revision Update failed: " + up_to_date[1],
                        'status' : 'failed',
                    })
                    log_id = self.pool.get('sync.monitor').create(cr, uid, log)
                    return (None, log_id, log)
                else:
                    log['error'] += "Revision Update Status: " + up_to_date[1]
        
        if step is not None:
            log[step] = 'in-progress'

        if log_id is None:
            log_id = self.pool.get('sync.monitor').create(cr, uid, log, context=context)
        else:
            self.pool.get('sync.monitor').write(cr, uid, [log_id], log, context=context)
        self.set_syncing(cr, uid, True)
        cr.commit()
        return (('ok' if not log[step] == 'failed' else None), log_id, log)
 
    def stopSync(self, cr, uid, log_id, log, step='status', status=None, context=None):
        if status is not None:
            log[step] = status
        #statuses = [v for k, v in log.iteritems() if k in ('data_push', 'msg_push', 'data_pull', 'msg_pull','status')]
        statuses = [log[k] for k in ('data_push', 'msg_push', 'data_pull', 'msg_pull','status')]
        if 'failed' in statuses or 'in-progress' not in statuses[:-1]:
            # Determine final status
            log.update({'end':datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'status': 'ok' if 'failed' not in statuses  else 'failed'})
            self.set_syncing(cr, uid, False)
        # Update log
        self.pool.get('sync.monitor').write(cr, uid, [log_id], log, context=context)
        cr.commit()
        return log[step] == 'ok'

    """
        Push Update
    """
    def push_update(self, cr, uid, log=None, log_id=None, context=None):
        (status, log_id, log) = self.startSync(cr, uid, log=log, log_id=log_id, step='data_push', context=context)
        if status is None: return False

        context = context or {}
        entity = self.get_entity(cr, uid, context)
        
        if entity.state not in ['init', 'update_send', 'update_validate']: 
            self.stateSync('null', log, 'data_push', message="Not valid state: " + entity.state)
            return False
            #log['error'] += 'Push data: ' + "Not a valid state to push data: " + entity.state
            #log['data_push'] = 'null'
            #return False
        
        try :
            cont = False
            if cont or entity.state == 'init':
                self.create_update(cr, uid, context=context)
                cont = True
                self.__logger.info("init")
            if cont or entity.state == 'update_send':
                self.send_update(cr, uid, context=context)
                cont = True
                self.__logger.info("sent update")
            if cont or entity.state == 'update_validate':
                self.validate_update(cr, uid, context=context)
                self.__logger.info("validate update")
        except Exception, e:
            status = self.errorSync(e, log, 'data_push')

        return self.stopSync(cr, uid, log_id, log, step='data_push', status=status, context=None)
    
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
                self.__logger.debug("send package %s" % i)
            send_more = send_package(entity.id)
            i += 1
        #state update_send => update_validate
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
    
    
    
    """
        Pull update
    """
    def pull_update(self, cr, uid, log=None, log_id=None, context=None, recover=False):
        (status, log_id, log) = self.startSync(cr, uid, log=log, log_id=log_id, step='data_pull', context=context)
        if status is None: return False

        context = context or {}
        entity = self.get_entity(cr, uid, context)
        if entity.state not in ['init', 'update_pull']: 
            self.stateSync('null', log, 'data_pull', message="Not valid state: " + entity.state)
            return False
        
        try:
            if entity.state == 'init': 
                self.set_last_sequence(cr, uid, context)
            self.retrieve_update(cr, uid, recover=recover, context=context)
            cr.commit()
            self.execute_update(cr, uid, context)
        except Exception, e:
            status = self.errorSync(e, log, 'data_pull')
        
        return self.stopSync(cr, uid, log_id, log, step='data_pull', status=status, context=None)
    

    def set_last_sequence(self, cr, uid, context=None):
        entity = self.get_entity(cr, uid, context)
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
        res = proxy.get_max_sequence(entity.identifier, context)
        if res and res[0]:
            return self.write(cr, uid, entity.id, {'max_update' : res[1]}, context=context)
        elif res and not res[0]:
            raise Exception, res[1]

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
                #unfold packet with res[1]
                last = res[2]
                offset += nb_upate
                self.write(cr, uid, entity.id, {'update_offset' : offset}, context=context)
            elif res and not res[0]:
                raise Exception, res[1]
        
        return self.write(cr, uid, entity.id, {'update_offset' : 0, 
                                        'max_update' : 0, 
                                        'update_last' : max_seq}, context=context) 
        
    def execute_update(self, cr, uid, context=None):
        self.pool.get('sync.client.update_received').execute_update(cr, uid, context=context)
             
             
    """
        Push message
    """
    def push_message(self, cr, uid, log=None, log_id=None, context=None):
        (status, log_id, log) = self.startSync(cr, uid, log=log, log_id=log_id, step='msg_push', context=context)
        if status is None: return False

        context = context or {}
        entity = self.get_entity(cr, uid, context)
        
        if entity.state not in ['init', 'msg_push']: 
            self.stateSync('null', log, 'msg_push', message="Not valid state: " + entity.state)
            return False
        
        try:
            if entity.state == 'init':
                self.create_message(cr, uid, context)
            self.send_message(cr, uid, context)
        except Exception, e:
            status = self.errorSync(e, log, 'msg_push')
        
        return self.stopSync(cr, uid, log_id, log, step='msg_push', status=status, context=None)
        
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
    def pull_message(self, cr, uid, log=None, log_id=None, context=None):
        (status, log_id, log) = self.startSync(cr, uid, log=log, log_id=log_id, step='msg_pull', context=context)
        if status is None: return False

        context = context or {}
        entity = self.get_entity(cr, uid, context)

        if not entity.state in ['init']:
            self.stateSync('null', log, 'msg_pull', message="Not valid state: " + entity.state)
            return False
        
        try: 
            self.get_message(cr, uid, context)
            self.execute_message(cr, uid, context)
        except Exception, e:
            status = self.errorSync(e, log, 'msg_pull')
        
        return self.stopSync(cr, uid, log_id, log, step='msg_pull', status=status, context=None)
        
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
        Backup after recovery : set all message after seq as not send, then pull message
    """
    def recover_message(self, cr, uid, context=None):
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
        entity = self.get_entity(cr, uid, context)
        proxy.message_recover_from_seq(entity.identifier, entity.message_last, context)
        return self.pull_message(cr, uid, context=context)

    """
        SYNC process : usefull for scheduling 
    """
    def sync_threaded(self, cr, uid, context=None):
        context = context or {}
        #TODO thread
        self.data = [cr, uid, context]
        Thread.__init__(self)
        self.start()
        return True
    
    def sync(self, cr, uid, context=None):
        context = context or {}

        (status, log_id, log) = self.startSync(cr, uid, context=context)
        #if status is None: return False
        if status is None:
            raise osv.except_osv(_('Error!'), _('Unable to start the synchronization process now!'))
       
        #self.sync_core(cr, uid, log_id, log, context=context)
        self.pull_update(cr, uid, log, log_id, context=context)
        self.pull_message(cr, uid, log, log_id, context=context)
        self.push_update(cr, uid, log, log_id, context=context)
        self.push_message(cr, uid, log, log_id, context=context)
            
        return self.stopSync(cr, uid, log_id, log)
        
    def run(self):
        cr = self.data[0]
        uid = self.data[1]
        context = self.data[2]
        cr = pooler.get_db(cr.dbname).cursor()
        self.sync(cr, uid, context)
        cr.close()
        
    def get_upgrade_status(self, cr, uid, context=None):
        return ""

    def get_status(self, cr, uid, context=None):
        if not self.pool.get('sync.client.sync_server_connection')._get_connection_manager(cr, uid, context=context).state == 'Connected':
            return "Not Connected"
        me = self.get_entity(cr, uid, context)
        if me.is_syncing:
            return "Syncing..."
        monitor = self.pool.get("sync.monitor")
        monitor_ids = monitor.search(cr, uid, [], context=context)
        if monitor_ids:
            last_log = monitor.browse(cr, uid, monitor_ids[0], context=context)
            status = filter(lambda x:x[0] == last_log.status, self.pool.get("sync.monitor")._columns['status'].selection)[0][1] if last_log.status else 'Unknown Status'
            return "Last Sync: %s at %s" % (status, last_log.end)
        else:
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
    
    def _get_state(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for connection in self.browse(cr, uid, ids, context=context):
            ## Make sure we get an integer (xmlrpc bug fixed in 6.1 server)
            res[connection.id] = "Connected" if int(connection.uid) and connection.password else "Disconnected"
        return res
 
    _password = {}
    _uid = {}

    def _get_password(self, cr, uid, ids, field, arg, context):
        return dict.fromkeys(ids, self._password.get(cr.dbname))

    def _set_password(self, cr, uid, ids, field, password, arg, context):
        self._password[cr.dbname] = password

    _name = "sync.client.sync_server_connection"
    _description = "Connection to sync server information and tools"
    _rec_name = 'host'

    _columns = {
        'host': fields.char('Host', help='Synchronization server host name', size=256),
        'port': fields.integer('Port', help='Synchronization server connection port'),
        'protocol': fields.selection([('xmlrpc', 'XMLRPC'), ('gzipxmlrpc', 'compressed XMLRPC'), ('xmlrpcs', 'secured XMLRPC'), ('netrpc', 'NetRPC'), ('netrpc_gzip', 'compressed NetRPC')], 'Protocol', help='Changing protocol may imply changing the port number'),
        'database' : fields.char('Database Name', size=64),
        'login':fields.char('Login on synchro server', size=64),
        'uid': fields.integer('Uid on synchro server', readonly=True),
        'password': fields.function(_get_password, fnct_inv=_set_password, string='Password', type='char', method=True, store=False),
        'state' : fields.function(_get_state, method=True, string='State', type="char", readonly=True, store=False),
        'max_size' : fields.integer("Max Packet Size"),
    }
    
    _defaults = {
        'host' : 'localhost',
        'port' : 8070,
        'protocol': 'netrpc_gzip',
        'login' : 'admin',
        'max_size' : 1000,
    }
    
    def _get_connection_manager(self, cr, uid, context=None):
        ids = self.search(cr, uid, [], context=context)
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
            raise Exception('Unknown protocol: %s' % con.protocol)
        return connector
 
    def connect(self, cr, uid, ids, context=None):
        for con in self.browse(cr, uid, ids, context=context):
            connector = self.connector_factory(con)
            #if not con.password or not con.database or not con.login:
            #    raise osv.except_osv(_('Error !'), _('All the fields in this form are mandatory!'))
            
            cnx = rpc.Connection(connector, con.database, con.login, con.password)
            if cnx.user_id:
                self.write(cr, uid, con.id, {'uid' : cnx.user_id}, context=context)
        self.pool.get('sync.client.entity').set_syncing(cr, uid, False)
        return True
    
    def get_connection(self, cr, uid, model, context=None):
        """
            @return: the proxy to call distant method specific to a model
            @param model: the model name we want to call remote method
        """
        con = self._get_connection_manager(cr, uid, context=context)
        connector = self.connector_factory(con)
        cnx = rpc.Connection(connector, con.database, con.login, con.password, con.uid)
        return rpc.Object(cnx, model)
    
    def disconnect(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'uid' : False}, context=context)
        return True
    
    def _entity_connection(self,cr,uid,ids,context=None):     
        return self.search(cr, uid,[(1, '=', 1)],context=context,count=True) == 1
    
    _constraints = [
        (_entity_connection, _('The connection parameter is unique, you cannot create a new one'), ['host'])
    ]

sync_server_connection()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

