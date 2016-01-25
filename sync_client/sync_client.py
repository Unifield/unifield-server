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
import sys
import os
import hashlib
import traceback
from psycopg2 import OperationalError

import logging
from sync_common import sync_log, get_md5, check_md5

from threading import Thread, RLock, Lock
import pooler

import functools

MAX_EXECUTED_UPDATES = 500
MAX_EXECUTED_MESSAGES = 500


class SkipStep(StandardError):
    pass


class BackgroundProcess(Thread):

    def __init__(self, cr, uid, method, context=None):
        super(BackgroundProcess, self).__init__()
        self.context = context
        self.uid = uid
        self.db, pool = pooler.get_db_and_pool(cr.dbname)
        try:
            entity = pool.get('sync.client.entity')
            # Lookup method to call
            self.call_method = getattr(entity, method)
            # Check if we are not already syncing
            entity.is_syncing(raise_on_syncing=True)
            # Check if connection is up
            if not pool.get('sync.client.sync_server_connection').is_connected:
                raise osv.except_osv(_("Error!"), _("Not connected: please try to log on in the Connection Manager"))
            # Check for update
            if hasattr(entity, 'upgrade'):
                up_to_date = entity.upgrade(cr, uid, context=context)
                if not up_to_date[0]:
                    cr.commit()
                    raise osv.except_osv(_('Error!'), _(up_to_date[1]))
        except BaseException, e:
            logger = pool.get('sync.monitor').get_logger(cr, uid, context=context)
            logger.switch('status', 'failed')
            if isinstance(e, osv.except_osv):
                logger.append(e.value)
                raise
            else:
                error = "%s: %s" % (e.__class__.__name__, tools.ustr(e))
                logger.append(error)
                raise osv.except_osv(_('Error!'), error)

    def run(self):
        cr = self.db.cursor()
        try:
            self.call_method(cr, self.uid, context=self.context)
            cr.commit()
        except:
            pass
        finally:
            cr.close(True)


def sync_subprocess(step='status', defaults_logger={}):
    def decorator(fn):

        @functools.wraps(fn)
        def wrapper(self, cr, uid, *args, **kwargs):
            context = kwargs['context'] = kwargs.get('context') is not None and dict(kwargs.get('context', {})) or {}
            logger = context.get('logger')
            logger.switch(step, 'in-progress')
            logger.write()
            try:
                res = fn(self, self.sync_cursor, uid, *args, **kwargs)
            except osv.except_osv, e:
                logger.switch(step, 'failed')
                raise
            except BaseException, e:
                # Handle aborting of synchronization
                if isinstance(e, OperationalError) and e.message == 'Unable to use the cursor after having closed it':
                    logger.switch(step, 'aborted')
                    self.sync_cursor = None
                    raise
                logger.switch(step, 'failed')
                error = "%s: %s" % (e.__class__.__name__, getattr(e, 'message', tools.ustr(e)))
                self._logger.exception('Error in sync_process at step %s' % step)
                logger.append(error, step)
                raise
            else:
                logger.switch(step, 'ok')
                if isinstance(res, (str, unicode)) and res:
                    logger.append(res, step)
            finally:
                # gotcha!
                logger.write()
            return res
        return wrapper
    return decorator

def sync_process(step='status', need_connection=True, defaults_logger={}):
    is_step = not (step == 'status')

    def decorator(fn):

        @functools.wraps(fn)
        def wrapper(self, cr, uid, *args, **kwargs):

            # First, check if we can acquire the lock or return False
            sync_lock = self.sync_lock
            if not sync_lock.acquire(blocking=False):
                raise already_syncing_error

            # Lock is acquired, so don't put any code outside the try...catch!!
            res = False
            context = kwargs['context'] = kwargs.get('context') is not None and dict(kwargs.get('context', {})) or {}
            try:
                # more information to the logger
                def add_information(logger):
                    entity = self.get_entity(cr, uid, context=context)
                    if entity.session_id:
                        logger.append(_("Update session: %s") % entity.session_id)

                # get the logger
                logger = context.get('logger')
                make_log = logger is None

                # we have to make the log
                if make_log:
                    # get a whole new logger from sync.monitor object
                    context['logger'] = logger = \
                        self.pool.get('sync.monitor').get_logger(cr, uid, defaults_logger, context=context)
                    context['log_sale_purchase'] = True

                    # create a specific cursor for the call
                    self.sync_cursor = pooler.get_db(cr.dbname).cursor()

                    if need_connection:
                        # Check if connection is up
                        if not self.pool.get('sync.client.sync_server_connection').is_connected:
                            raise osv.except_osv(_("Error!"), _("Not connected: please try to log on in the Connection Manager"))
                        # Check for update (if connection is up)
                        if hasattr(self, 'upgrade'):
                            # TODO: replace the return value of upgrade to a status and raise an error on required update
                            up_to_date = self.upgrade(cr, uid, context=context)
                            cr.commit()
                            if not up_to_date[0]:
                                raise osv.except_osv(_("Error!"), _("Cannot check for updates: %s") % up_to_date[1])
                            elif 'last' not in up_to_date[1].lower():
                                logger.append( _("Update(s) available: %s") % _(up_to_date[1]) )
                    else:
                        context['offline_synchronization'] = True

                    # more information
                    add_information(logger)

                # ah... we can now call the function!
                logger.switch(step, 'in-progress')
                logger.write()
                res = fn(self, self.sync_cursor, uid, *args, **kwargs)
                self.sync_cursor.commit()

                # is the synchronization finished?
                if need_connection and make_log:
                    entity = self.get_entity(cr, uid, context=context)
                    proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.entity")
                    proxy.end_synchronization(entity.identifier, self._hardware_id)
            except SkipStep:
                # res failed but without exception
                assert is_step, "Cannot have a SkipTest error outside a sync step process!"
                logger.switch(step, 'null')
                logger.append(_("ok, skipped."), step)
                if make_log:
                    raise osv.except_osv(_('Error!'), _("You cannot perform this action now."))
            except osv.except_osv, e:
                logger.switch(step, 'failed')
                if make_log:
                    logger.append( e.value )
                    add_information(logger)
                raise
            except BaseException, e:
                # Handle aborting of synchronization
                if isinstance(e, OperationalError) and e.message == 'Unable to use the cursor after having closed it':
                    if make_log:
                        error = "Synchronization aborted"
                        logger.append(error, 'status')
                        self._logger.warning(error)
                        raise osv.except_osv(_('Error!'), error)
                    else:
                        logger.switch(step, 'aborted')
                        self.sync_cursor = None
                        raise
                logger.switch(step, 'failed')
                error = "%s: %s" % (e.__class__.__name__, getattr(e, 'message', tools.ustr(e)))
                if is_step:
                    self._logger.exception('Error in sync_process at step %s' % step)
                    logger.append(error, step)
                if make_log:
                    self._logger.exception('Error in sync_process at step %s' % step)
                    add_information(logger)
                    raise osv.except_osv(_('Error!'), error)
                raise
            else:
                logger.switch(step, 'ok')
                if isinstance(res, (str, unicode)) and res:
                    logger.append(res, step)
            finally:
                # gotcha!
                if make_log:
                    all_status = logger.info.values()
                    if 'ok' in all_status and step == 'status' and logger.info.get(step) in ('failed', 'aborted'):
                        try:
                            self.pool.get('backup.config').exp_dump_for_state(cr, uid, 'after%ssync' % context.get('sync_type', 'manual'), context=context)
                        except Exception, e:
                            self._logger.exception("Can't create backup %s" % tools.ustr(e))
                sync_lock.release()
                if make_log:
                    logger.close()
                    if self.sync_cursor is not None:
                        self.sync_cursor.close(True)
                else:
                    logger.write()
            return res

        return wrapper
    return decorator

already_syncing_error = osv.except_osv(_('Already Syncing...'), _('OpenERP can only perform one synchronization at a time - you must wait for the current synchronization to finish before you can synchronize again.'))

def get_hardware_id():
        mac = []
        if sys.platform == 'win32':
            for line in os.popen("ipconfig /all"):
                if line.lstrip().startswith('Physical Address'):
                    mac.append(line.split(':')[1].strip().replace('-',':'))
        else:
            for line in os.popen("/sbin/ifconfig"):
                if line.find('Ether') > -1:
                    mac.append(line.split()[4])
        mac.sort()
        hw_hash = hashlib.md5(''.join(mac)).hexdigest()
        logging.getLogger('sync.client').info('Hardware identifier: %s' % (hw_hash,))
        return hw_hash


class Entity(osv.osv):
    """ OpenERP entity name and unique identifier """
    _name = "sync.client.entity"
    _description = "Synchronization Instance"
    _logger = logging.getLogger('sync.client')
    _hardware_id = get_hardware_id()

    def _auto_init(self,cr,context=None):
        res = super(Entity, self)._auto_init(cr, context=context)
        if not self.search(cr, 1, [], limit=1, order='NO_ORDER', context=context):
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
        return self.search(cr, uid,[(1, '=', 1)], context=context, count=True) == 1

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

        # used to determine which sync rules to use
        # UF-2531: moved this from the RW module to the general sync module
        'usb_instance_type': fields.selection((('',''),('central_platform','Central Platform'),('remote_warehouse','Remote Warehouse')), string='USB Instance Type'),
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

    def get_entity(self, cr, uid, context=None):
        ids = self.search(cr, uid, [], context=context)
        return self.browse(cr, uid, ids, context=context)[0]

    def _get_entity(self, cr):
        """
        private method to get entity with uid = 1
        """
        ids = self.search(cr, 1, [])
        return self.browse(cr, 1, ids)[0]

    def generate_uuid(self):
        return str(uuid.uuid1())

    def get_uuid(self, cr, uid, context=None):
        return self.get_entity(cr, uid, context=context).identifier

    def __init__(self, *args, **kwargs):
        self.renew_lock = Lock()
        self._renew_sync_lock()
        self.aborting = False
        super(Entity, self).__init__(*args, **kwargs)

    def _renew_sync_lock(self):
        if not self.renew_lock.acquire(False):
            raise StandardError("Can't acquire renew lock!")
        try:
            self.sync_lock = RLock()
        finally:
            self.renew_lock.release()

    @sync_process('data_push')
    def push_update(self, cr, uid, context=None):
        """
            Push Update
        """
        context = context or {}
        logger = context.get('logger')
        entity = self.get_entity(cr, uid, context)

        if entity.state not in ('init', 'update_send', 'update_validate'):
            raise SkipStep

        cont = False
        if cont or entity.state == 'init':
            updates_count = self.create_update(cr, uid, context=context)
            cr.commit()
            cont = updates_count > 0
            self._logger.info("Push data :: Updates created: %d" % updates_count)
        if cont or entity.state == 'update_send':
            updates_count = self.send_update(cr, uid, context=context)
            cr.commit()
            cont = True
            self._logger.info("Push data :: Updates sent: %d" % updates_count)
            if logger:
                logger.info['nb_data_push'] = updates_count
        if cont or entity.state == 'update_validate':
            server_sequence = self.validate_update(cr, uid, context=context)
            cr.commit()
            if server_sequence:
                self._logger.info(_("Push data :: New server's sequence number: %d") % server_sequence)
        return True

    @sync_subprocess('data_push_create')
    def create_update(self, cr, uid, context=None):
        context = context or {}
        updates = self.pool.get(context.get('update_to_send_model', 'sync.client.update_to_send'))

        def prepare_update(session):
            updates_count = 0
            for rule_id in self.pool.get('sync.client.rule').search(cr, uid, [('type', '!=', 'USB')], context=context):
                updates_count += sum(updates.create_update(
                    cr, uid, rule_id, session, context=context))
            return updates_count

        entity = self.get_entity(cr, uid, context)
        session = str(uuid.uuid1())
        updates_count = prepare_update(session)
        if updates_count > 0:
            self.write(cr, uid, [entity.id], {'session_id' : session})
        return updates_count
        #state init => update_send

    @sync_subprocess('data_push_send')
    def send_update(self, cr, uid, context=None):
        context = context or {}
        logger = context.get('logger')
        updates = self.pool.get(context.get('update_to_send_model', 'sync.client.update_to_send'))

        max_packet_size = self.pool.get("sync.client.sync_server_connection")._get_connection_manager(cr, uid, context=context).max_size
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
        entity = self.get_entity(cr, uid, context=context)

        def create_package():
            return updates.create_package(cr, uid, entity.session_id, max_packet_size)

        def send_package(ids, packet):
            context={'md5': get_md5(packet)}
            res = proxy.receive_package(entity.identifier, self._hardware_id, packet, context)
            if not res[0]:
                raise Exception, res[1]
            updates.write(cr, uid, ids, {'sent' : True}, context=context)
            return (len(packet['load']), len(packet['unload']))

        # get update count
        max_updates = updates.search(cr, uid, [('sent','=',False)], count=True, context=context)
        if max_updates == 0:
            return 0

        imported, deleted = 0, 0
        logger_index = None
        res = create_package()
        while res:
            imported_package, deleted_package = send_package(*res)
            imported += imported_package
            deleted += deleted_package
            if logger:
                if logger_index is None: logger_index = logger.append()
                logger.replace(logger_index, _("Update(s) sent: %d import update(s) + %d delete update(s) on %d update(s)") % (imported, deleted, max_updates))
                logger.write()
            res = create_package()

        if logger and (imported or deleted):
            logger.replace(logger_index, _("Update(s) sent: %d import update(s) and %d delete update(s) = %d total update(s)") \
                                         % (imported, deleted, (imported + deleted)))

        #state update_send => update_validate
        return imported + deleted

    def validate_update(self, cr, uid, context=None):
        context = context or {}
        updates = self.pool.get(context.get('update_to_send_model', 'sync.client.update_to_send'))

        entity = self.get_entity(cr, uid, context)
        session_id = entity.session_id
        update_ids = updates.search(cr, uid, [('session_id', '=', session_id)], context=context)
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
        res = proxy.confirm_update(entity.identifier, self._hardware_id, session_id, {'md5': get_md5(session_id)})
        if not res[0]:
            raise Exception, res[1]
        updates.sync_finished(cr, uid, update_ids, context=context)
        self.write(cr, uid, entity.id, {'session_id' : ''}, context=context)
        #state update validate => init
        return res[1]

    def set_rules(self, cr, uid, context=None):
        entity = self.get_entity(cr, uid, context)
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
        res = proxy.get_model_to_sync(entity.identifier, self._hardware_id)
        if not res[0]:
            raise Exception, res[1]
        check_md5(res[2], res[1], _('method set_rules'))
        self.pool.get('sync.client.rule').save(cr, uid, res[1], context=context)

    @sync_process('data_pull')
    def pull_update(self, cr, uid, recover=False, context=None):
        """
            Pull update
        """
        context = context or {}

        logger = context.get('logger')
        entity = self.get_entity(cr, uid, context=context)
        if entity.state not in ('init', 'update_pull'):
            raise SkipStep

        if entity.state == 'init':
            self.set_last_sequence(cr, uid, context=context)
        sync_server_obj = self.pool.get("sync.client.sync_server_connection")
        max_packet_size = sync_server_obj._get_connection_manager(cr, uid, context=context).max_size

        # UTP-1177: Retrieve the message ids and save into the entity at the Server side
        proxy = sync_server_obj.get_connection(cr, uid, "sync.server.sync_manager")
        res = proxy.get_message_ids(entity.identifier, self._hardware_id)
        if not res[0]: raise Exception, res[1]

        updates_count = self.retrieve_update(cr, uid, max_packet_size, recover=recover, context=context)
        self._logger.info("::::::::The instance " + entity.name + " pulled: " + str(res[1]) + " messages and " + str(updates_count) + " updates.")
        updates_executed = self.execute_updates(cr, uid, context=context)
        if updates_executed == 0 and updates_count > 0:
            self._logger.warning("No update to execute, this case should never occurs.")

        self._logger.info("Pull data :: Number of data pull: %s" % updates_count)
        if logger:
            logger.info['nb_data_pull'] = updates_count
        return True

    def set_last_sequence(self, cr, uid, context=None):
        entity = self.get_entity(cr, uid, context=context)
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
        res = proxy.get_max_sequence(entity.identifier, self._hardware_id)
        if res and res[0]:
            check_md5(res[2], res[1], _('method get_max_sequence'))
            self._logger.info("Pull data :: Last sequence: %s" % res[1])
            return self.write(cr, uid, entity.id, {'max_update' : res[1]}, context=context)
        elif res and not res[0]:
            raise Exception, res[1]
        return True

    @sync_subprocess('data_pull_receive')
    def retrieve_update(self, cr, uid, max_packet_size, recover=False, context=None):
        context = context or {}
        logger = context.get('logger')
        updates = self.pool.get(context.get('update_received_model', 'sync.client.update_received'))

        entity = self.get_entity(cr, uid, context)
        last_seq = entity.update_last
        max_seq = entity.max_update
        offset = (0, entity.update_offset)
        offset_recovery = entity.update_offset
        last = (last_seq >= max_seq)
        updates_count = 0
        logger_index = None
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
        while not last:
            res = proxy.get_update(entity.identifier, self._hardware_id, last_seq, offset, max_packet_size, max_seq, recover)
            if res and res[0]:
                if res[1]: check_md5(res[3], res[1], _('method get_update'))
                increment_to_offset = 0
                for package in (res[1] or []):
                    updates_count += updates.unfold_package(cr, uid, package, context=context)

                    if logger and updates_count:
                        if logger_index is None: logger_index = logger.append()
                        logger.replace(logger_index, _("Update(s) received: %d") % updates_count)
                        logger.write()
                    if package:
                        increment_to_offset = package['offset'][1]
                        offset = (package['update_id'], 0)

                offset_recovery += increment_to_offset
                self.write(cr, uid, entity.id, {'update_offset' : offset_recovery}, context=context)
                last = res[2]
            elif res and not res[0]:
                raise Exception, res[1]
            cr.commit()

        self.write(cr, uid, entity.id, {'update_offset' : 0,
                                        'max_update' : 0,
                                        'update_last' : max_seq}, context=context)
        cr.commit()
        return updates_count

    @sync_subprocess('data_pull_execute')
    def execute_updates(self, cr, uid, context=None):
        context = context or {}
        logger = context.get('logger')
        updates = self.pool.get(context.get('update_received_model', 'sync.client.update_received'))
        # get instance prioritiies
        priorities_stuff = None
        if not context.get('offline_synchronization'):
            proxy = self.pool.get("sync.client.sync_server_connection")\
                .get_connection(cr, uid, "sync.server.entity")
            priorities_stuff = proxy.get_entities_priorities()

        # Get a list of updates to execute
        # Warning: execution order matter
        update_ids = updates.search(cr, uid, [('run', '=', False)], order='sequence_number, rule_sequence, id asc', context=context)
        update_count = len(update_ids)
        if not update_count: return 0

        try:
            if logger: logger_index = logger.append()
            done = []
            imported, deleted = 0, 0
            while update_ids:
                to_do, update_ids = update_ids[:MAX_EXECUTED_UPDATES], update_ids[MAX_EXECUTED_UPDATES:]
                messages, imported_executed, deleted_executed = \
                    updates.execute_update(cr, uid,
                        to_do,
                        priorities=priorities_stuff,
                        context=context)
                imported += imported_executed
                deleted += deleted_executed
                # Do nothing with messages
                done += to_do
                if logger:
                    logger.replace(logger_index, _("Update(s) processed: %d import updates + %d delete updates on %d updates") \
                                                 % (imported, deleted, update_count))
                    logger.write()
                # intermittent commit
                if len(done) >= MAX_EXECUTED_UPDATES:
                    done[:] = []
                    cr.commit()
        finally:
            cr.commit()

            if logger:
                if imported or deleted:
                    logger.replace(logger_index, _("Update(s) processed: %d import updates + %d delete updates = %d total updates") % \
                                                 (imported, deleted, imported+deleted))
                else:
                    logger.pop(logger_index)
                notrun_count = updates.search(cr, uid, [('run','=',False)], count=True, context=context)
                if notrun_count > 0: logger.append(_("Update(s) not run left: %d") % notrun_count)
                logger.write()
        return update_count

    @sync_process('msg_push')
    def push_message(self, cr, uid, context=None):
        """
            Push message
        """
        context = context or {}
        entity = self.get_entity(cr, uid, context)
        logger = context.get('logger')
        if entity.state not in ['init', 'msg_push']:
            raise SkipStep

        if entity.state == 'init':
            self.create_message(cr, uid, context=context)
            cr.commit()

        nb_msg = self.send_message(cr, uid, context=context)
        cr.commit()

        self._logger.info("Push messages :: Number of messages pushed: %d" % nb_msg)
        if logger:
            logger.info['nb_msg_push'] = nb_msg
        return True

    @sync_subprocess('msg_push_create')
    def create_message(self, cr, uid, context=None):
        context = context or {}
        messages = self.pool.get(context.get('message_to_send_model', 'sync.client.message_to_send'))

        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
        uuid = self.pool.get('sync.client.entity').get_entity(cr, uid).identifier

        res = proxy.get_message_rule(uuid, self._hardware_id)
        if res and not res[0]: raise Exception, res[1]
        check_md5(res[2], res[1], _('method get_message_rule'))
        self.pool.get('sync.client.message_rule').save(cr, uid, res[1], context=context)

        rule_obj = self.pool.get("sync.client.message_rule")

        messages_count = 0
        for rule in rule_obj.browse(cr, uid, rule_obj.search(cr, uid, [('type', '!=', 'USB')], context=context), context=context):
            messages_count += messages.create_from_rule(cr, uid, rule, None, context=context)
        return messages_count

    @sync_subprocess('msg_push_send')
    def send_message(self, cr, uid, context=None):
        context = context or {}
        logger = context.get('logger')
        messages = self.pool.get(context.get('message_to_send_model', 'sync.client.message_to_send'))

        max_packet_size = self.pool.get("sync.client.sync_server_connection")._get_connection_manager(cr, uid, context=context).max_size
        uuid = self.pool.get('sync.client.entity').get_entity(cr, uid, context=context).identifier
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
        messages_max = messages.search(cr, uid, [('sent','=',False)], count=True, context=context)

        messages_count = 0
        logger_index = None
        while True:
            packet = messages.get_message_packet(cr, uid, max_packet_size, context=context)
            if not packet:
                break
            messages_count += len(packet)
            res = proxy.send_message(uuid, self._hardware_id, packet, {'md5': get_md5(packet)})
            if not res[0]:
                raise Exception, res[1]
            messages.packet_sent(cr, uid, packet, context=context)
            if logger and messages_count:
                if logger_index is None: logger_index = logger.append()
                logger.replace(logger_index, _("Message(s) sent: %d/%d") % (messages_count, messages_max))
                logger.write()

        if logger and messages_count:
            logger.replace(logger_index, _("Message(s) sent: %d") % messages_count)
        return messages_count
        #message_push => init

    @sync_process('msg_pull')
    def pull_message(self, cr, uid, recover=False, context=None):
        """
            Pull message
        """
        context = context or {}
        logger = context.get('logger')
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")

        entity = self.get_entity(cr, uid, context=context)
        if recover:
            proxy.message_recover_from_seq(entity.identifier, self._hardware_id, entity.message_last)

        if not entity.state == 'init':
            raise SkipStep

        self.get_message(cr, uid, context=context)
        # UTP-1177: Reset the message ids of the entity at the server side
        proxy.reset_message_ids(entity.identifier, self._hardware_id)
        msg_count = self.execute_message(cr, uid, context=context)
        self._logger.info("Pull message :: Number of messages pulled: %s" % msg_count)
        if logger:
            logger.info['nb_msg_pull'] = msg_count
        return True

    @sync_subprocess('msg_pull_receive')
    def get_message(self, cr, uid, context=None):
        context = context or {}
        logger = context.get('logger')
        messages = self.pool.get(context.get('message_received_model', 'sync.client.message_received'))

        entity = self.get_entity(cr, uid, context)
        last_seq = entity.update_last
        messages_count = 0
        logger_index = None

        max_packet_size = self.pool.get("sync.client.sync_server_connection")._get_connection_manager(cr, uid, context=context).max_size
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
        instance_uuid = entity.identifier
        while True:
            res = proxy.get_message(instance_uuid, self._hardware_id,
                    max_packet_size, last_seq)
            if not res[0]: raise Exception, res[1]

            packet = res[1]
            if not packet: break
            check_md5(res[2], packet, _('method get_message'))

            messages_count += len(packet)
            messages.unfold_package(cr, uid, packet, context=context)
            data_ids = [data['id'] for data in packet]
            res = proxy.message_received(instance_uuid, self._hardware_id, data_ids, {'md5': get_md5(data_ids)})
            if not res[0]: raise Exception, res[1]
            cr.commit()

            if logger and messages_count:
                if logger_index is None: logger_index = logger.append()
                logger.replace(logger_index, _("Message(s) received: %d") % messages_count)
                logger.write()
        return messages_count

    @sync_subprocess('msg_pull_execute')
    def execute_message(self, cr, uid, context=None):
        context = context or {}
        logger = context.get('logger')
        messages = self.pool.get(context.get('message_received_model', 'sync.client.message_received'))

        # Get the whole list of messages to execute
        # Warning: order matters
        message_ids = messages.search(cr, uid, [('run','=',False)], order='id asc', context=context)
        messages_count = len(message_ids)
        if messages_count == 0: return 0

        try:
            if logger: logger_index = logger.append()
            messages_executed = 0
            while message_ids:
                to_do, message_ids = message_ids[:MAX_EXECUTED_MESSAGES], message_ids[MAX_EXECUTED_MESSAGES:]
                messages.execute(cr, uid, to_do, context=context)
                messages_executed += len(to_do)
                if logger is not None:
                    logger.replace(logger_index, _("Message(s) processed: %d/%d") % (messages_executed, messages_count))
                    logger.write()
                # intermittent commit
                cr.commit()
        finally:
            cr.commit()
            if logger is not None:
                logger.replace(logger_index, _("Message(s) processed: %d") % messages_count)
                notrun_count = messages.search(cr, uid, [('run', '=', False)], count=True, context=context)
                if notrun_count > 0: logger.append(_("Message(s) not run left: %d") % notrun_count)
                logger.write()
                # UTP-1200: Update already the sync_id to the logger lines for FO/PO
                logger.update_sale_purchase_logger()
        return messages_count

    def sync_threaded(self, cr, uid, recover=False, context=None):
        """
            SYNC process : usefull for scheduling
        """
        BackgroundProcess(cr, uid,
            ('sync_recover_withbackup' if recover else 'sync_withbackup'),
            context).start()
        return True

    def sync_manual_threaded(self, cr, uid, recover=False, context=None):
        BackgroundProcess(cr, uid,
            ('sync_manual_recover_withbackup' if recover else 'sync_manual_withbackup'),
            context).start()
        return True

    @sync_process()
    def sync_recover(self, cr, uid, context=None):
        """
        Call both pull_all_data and recover_message functions - used in manual sync wizard
        """
        self.pull_update(cr, uid, recover=True, context=context)
        if context is None:
            context = {}
        context['restore_flag'] = True
        self.pull_message(cr, uid, recover=True, context=context)
        return True

    @sync_process()
    def sync_recover_withbackup(self, cr, uid, context=None):
        """
        Call both pull_all_data and recover_message functions - used in manual sync wizard
        """
        if context is None:
            context = {}
        context['sync_type'] = 'automatic'
        #Check for a backup before automatic sync
        self.pool.get('backup.config').exp_dump_for_state(cr, uid, 'beforeautomaticsync', context=context)
        self.sync_recover(cr, uid, context=context)
        #Check for a backup after automatic sync
        self.pool.get('backup.config').exp_dump_for_state(cr, uid, 'afterautomaticsync', context=context)
        return {'type': 'ir.actions.act_window_close'}

    @sync_process()
    def sync_manual_recover_withbackup(self, cr, uid, context=None):
        """
        Call both pull_all_data and recover_message functions - used in manual sync wizard
        """
        if context is None:
            context = {}
        context['sync_type'] = 'manual'
        #Check for a backup before automatic sync
        self.pool.get('backup.config').exp_dump_for_state(cr, uid, 'beforemanualsync', context=context)
        self.sync_recover(cr, uid, context=context)
        #Check for a backup after automatic sync
        self.pool.get('backup.config').exp_dump_for_state(cr, uid, 'aftermanualsync', context=context)
        return {'type': 'ir.actions.act_window_close'}

    @sync_process()
    def sync(self, cr, uid, context=None):
        if context is None:
            context = {}
        # US_394: force synchronization lang to en_US
        context['lang'] = 'en_US'
        logger = context.get('logger')
        self._logger.info("Start synchronization")
        self.set_rules(cr, uid, context=context)
        self.pull_update(cr, uid, context=context)
        self.pull_message(cr, uid, context=context)
        self.push_update(cr, uid, context=context)
        self.push_message(cr, uid, context=context)
        self._logger.info("Synchronization succesfully done")
        if logger:
            logger.info['nb_msg_not_run'] = self.pool.get('sync.client.message_received').search(cr, uid, [('run', '=', False)], count=True)
            logger.info['nb_data_not_run'] = self.pool.get('sync.client.update_received').search(cr, uid, [('run', '=', False)], count=True)
        return True

    @sync_process()
    def sync_withbackup(self, cr, uid, context=None):
        """
        Call both pull_all_data and recover_message functions - used in manual sync wizard
        """
        if context is None:
            context = {}
        context['sync_type'] = 'automatic'
        #Check for a backup before automatic sync
        self.pool.get('backup.config').exp_dump_for_state(cr, uid, 'beforeautomaticsync', context=context)
        self.sync(cr, uid, context=context)
        #Check for a backup after automatic sync
        self.pool.get('backup.config').exp_dump_for_state(cr, uid, 'afterautomaticsync', context=context)
        return {'type': 'ir.actions.act_window_close'}

    @sync_process()
    def sync_manual_withbackup(self, cr, uid, context=None):
        """
        Call both pull_all_data and recover_message functions - used in manual sync wizard
        """
        #Check for a backup before automatic sync
        if context is None:
            context = {}
        context['sync_type'] = 'manual'
        self.pool.get('backup.config').exp_dump_for_state(cr, uid, 'beforemanualsync', context=context)
        self.sync(cr, uid, context=context)
        #Check for a backup after automatic sync
        self.pool.get('backup.config').exp_dump_for_state(cr, uid, 'aftermanualsync', context=context)
        return {'type': 'ir.actions.act_window_close'}

    def get_upgrade_status(self, cr, uid, context=None):
        return ""

    # Check if lock can be acquired or not
    def is_syncing(self, raise_on_syncing=False):
        acquired = self.sync_lock.acquire(blocking=False)
        if not acquired:
            if raise_on_syncing:
                raise already_syncing_error
            return True
        self.sync_lock.release()
        self.aborting = False
        return False

    def get_status(self, cr, uid, context=None):
        if not self.pool.get('sync.client.sync_server_connection').is_connected:
            return "Not Connected"

        if self.is_syncing():
            if self.aborting:
                return "Aborting..."
            return "Syncing..."

        monitor = self.pool.get("sync.monitor")
        last_log = monitor.last_status
        if last_log:
            return "Last Sync: %s at %s, Not run upd: %s, Not run msg: %s" \
                % (_(monitor.status_dict[last_log[0]]), last_log[1], last_log[2], last_log[3])
        return "Connected"

    def interrupt_sync(self, cr, uid, context=None):
        if self.is_syncing():
            #try:
            #    self._renew_sync_lock()
            #except StandardError:
            #    return False
            self.aborting = True
            self.sync_cursor.close(True)
        return True

Entity()


class Connection(osv.osv):
    """
        This class handle connection with the server of synchronization
        Keep the username, uid on the synchronization

        Question for security issue it's better to not keep the password in database

        This class is also a singleton

    """
    _logger = logging.getLogger('sync.client.sync_server_connection')

    def _auto_init(self,cr,context=None):
        res = super(Connection, self)._auto_init(cr, context=context)
        if not self.search(cr, 1, [], limit=1, order='NO_ORDER', context=context):
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
        return super(Connection, self).unlink(cr, uid, ids, context=context)

    _name = "sync.client.sync_server_connection"
    _description = "Connection to sync server information and tools"
    _rec_name = 'host'

    _columns = {
        'active': fields.boolean('Active'),
        'host': fields.char('Host', help='Synchronization server host name', size=256, required=True),
        'port': fields.integer('Port', help='Synchronization server connection port'),
        'protocol': fields.selection([('xmlrpc', 'XMLRPC'), ('gzipxmlrpc', 'compressed XMLRPC'), ('xmlrpcs', 'secured XMLRPC'), ('gzipxmlrpcs', 'secured compressed XMLRPC'), ('netrpc', 'NetRPC'), ('netrpc_gzip', 'compressed NetRPC')], 'Protocol', help='Changing protocol may imply changing the port number'),
        'database' : fields.char('Database Name', size=64),
        'login':fields.char('Login on synchro server', size=64),
        'uid': fields.function(_get_uid, string='Uid on synchro server', readonly=True, type='char', method=True),
        'password': fields.function(_get_password, fnct_inv=_set_password, string='Password', type='char', method=True, store=False),
        'state' : fields.function(_get_state, method=True, string='State', type="char", readonly=True, store=False),
        'max_size' : fields.integer("Max Packet Size"),
        'timeout' : fields.float("Timeout"),
        'netrpc_retry' : fields.integer("NetRPC retry"),
        'xmlrpc_retry' : fields.integer("XmlRPC retry"),
    }

    _defaults = {
        'active': True,
        'host' : 'sync.unifield.net',
        'port' : 8070,
        'protocol': 'netrpc_gzip',
        'login' : 'admin',
        'max_size' : 500,
        'database' : 'SYNC_SERVER',
        'timeout' : 600.0,
        'netrpc_retry' : 10,
        'xmlrpc_retry' : 10,
    }

    def _get_connection_manager(self, cr, uid, context=None):
        ids = self.search(cr, uid, [], context=context)
        if not ids:
            raise osv.except_osv('Connection Error', "Connection manager not set!")
        return self.browse(cr, uid, ids, context=context)[0]

    def connector_factory(self, con):
        if con.protocol == 'xmlrpc':
            connector = rpc.XmlRPCConnector(con.host, con.port, timeout=con.timeout, retry=con.xmlrpc_retry)
        elif con.protocol == 'gzipxmlrpc':
            connector = rpc.GzipXmlRPCConnector(con.host, con.port, timeout=con.timeout, retry=con.xmlrpc_retry)
        elif con.protocol == 'gzipxmlrpcs':
            connector = rpc.GzipXmlRPCSConnector(con.host, con.port, timeout=con.timeout, retry=con.xmlrpc_retry)
        elif con.protocol == 'xmlrpcs':
            connector = rpc.SecuredXmlRPCConnector(con.host, con.port, timeout=con.timeout, retry=con.xmlrpc_retry)
        elif con.protocol == 'netrpc':
            connector = rpc.NetRPCConnector(con.host, con.port, timeout=con.timeout, retry=con.netrpc_retry)
        elif con.protocol == 'netrpc_gzip':
            connector = rpc.GzipNetRPCConnector(con.host, con.port, timeout=con.timeout, retry=con.netrpc_retry)
        else:
            raise osv.except_osv('Connection Error','Unknown protocol: %s' % con.protocol)
        return connector

    def connect(self, cr, uid, ids=None, context=None):
        if getattr(self, '_uid', False):
            return True
        try:
            con = self._get_connection_manager(cr, uid, context=context)
            sync_args = {
                'client_name': cr.dbname,
                'server_name': con.database,
            }
            self._logger.info('Client \'%(client_name)s\' attempts to connect to sync. server \'%(server_name)s\'' % sync_args)
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

        self._logger.info('Client \'%(client_name)s\' succesfully connected to sync. server \'%(server_name)s\'' % sync_args)
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
        con = self._get_connection_manager(cr, uid, context=context)
        sync_args = {
            'client_name': cr.dbname,
            'server_name': con.database,
        }
        if not self.pool.get('sync.client.entity').interrupt_sync(cr, uid, context=context):
            self._logger.warning('Error during the disconnection of client \'%(client_name)s\'' % sync_args)
            return False
        self._uid = False
        self._logger.info('Client \'%(client_name)s\' succesfully disconnected from the sync. server \'%(server_name)s\'' % sync_args)
        return True

    def action_disconnect(self, cr, uid, ids, context=None):
        self.disconnect(cr, uid, context=context)
        return {}

    def write(self, *args, **kwargs):
        # reset connection flag when data changed
        self._uid = False
        return super(Connection, self).write(*args, **kwargs)

    def change_host(self, cr, uid, ids, host, proto, context=None):
        if host in ('127.0.0.1', 'localhost'):
            return self.change_protocol(cr, uid, ids, host, proto, context=context)
        return {}

    def change_protocol(self, cr, uid, ids, host, proto, context=None):
        xmlrpc = 8069
        xmlrpcs = 8071
        netrpc = 8070
        if host in ('127.0.0.1', 'localhost'):
            xmlrpc = tools.config.get('xmlrpc_port')
            xmlrpcs = tools.config.get('xmlrpcs_port')
            netrpc = tools.config.get('netrpc_port')
        ports = {
            'xmlrpc': xmlrpc,
            'gzipxmlrpc': xmlrpc,
            'xmlrpcs': xmlrpcs,
            'gzipxmlrpcs': xmlrpcs,
            'netrpc': netrpc,
            'netrpc_gzip': netrpc,
        }
        if ports.get(proto):
            return {'value': {'port': ports[proto]}}
        return {}

    _sql_constraints = [
        ('active', 'UNIQUE(active)', 'The connection parameter is unique; you cannot create a new one')
    ]

Connection()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
