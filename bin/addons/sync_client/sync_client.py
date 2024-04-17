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
from tools.translate import _

import socket
from . import rpc
import uuid
import tools
import sys
import os
import math
import hashlib
import time
import platform
from random import random

from psycopg2 import OperationalError
from psycopg2.extensions import ISOLATION_LEVEL_REPEATABLE_READ, TransactionRollbackError

import logging
from sync_common import get_md5, check_md5
from service.web_services import check_tz

from threading import Thread, RLock, Lock
import pooler

import functools

from sync_common import WHITE_LIST_MODEL
from datetime import datetime, timedelta

from sync_common import OC_LIST_TUPLE
from base64 import b64decode

from msf_field_access_rights.osv_override import _get_instance_level

MAX_EXECUTED_UPDATES = 500
MAX_EXECUTED_MESSAGES = 500


def check_patch_scripts(cr, uid, context=None):
    if pooler.get_pool(cr.dbname).get('patch.scripts').search(cr, uid, [('run', '=', False)], limit=1, context=context):
        return _('PatchFailed: A script during upgrade has failed. Synchronization is forbidden. Please contact your administrator')
    else:
        return ''


class SkipStep(Exception):
    pass


class AdminLoginException(Exception):
    def __init__(self):
        self.value = "Not connected to server. "\
            "You cannot use 'admin' in the config file for "\
            "automatic connection, please use a user dedicated "\
            "to the synchronization or manually connect before "\
            "launching a sync."

    def __str__(self):
        return repr(self.value)


class BackgroundProcess(Thread):

    def __init__(self, cr, uid, method, context=None):
        super(BackgroundProcess, self).__init__()
        self.context = context
        self.uid = uid
        self.db, pool = pooler.get_db_and_pool(cr.dbname)
        connected = True
        try:
            chk_tz_msg = check_tz()
            if chk_tz_msg:
                raise osv.except_osv(_('Error'), chk_tz_msg)
            entity = pool.get('sync.client.entity')
            # Lookup method to call
            self.call_method = getattr(entity, method)
            # Check if we are not already syncing
            entity.is_syncing(raise_on_syncing=True)
            # Check if connection is up
            connection_obj = pool.get('sync.client.sync_server_connection')
            try:
                connection_obj.get_connection_from_config_file(cr, uid, context=context)
            except AdminLoginException as e:
                connected = False
                raise osv.except_osv(_("Error!"), _(e.value))
            if not pool.get('sync.client.sync_server_connection').is_connected:
                connected = False
                raise osv.except_osv(_("Error!"), _("Not connected: please try to log on in the Connection Manager"))
            # Check for update

            if hasattr(entity, 'upgrade'):
                up_to_date = entity.upgrade(cr, uid, context=context)
                if not up_to_date[0]:
                    # check if patchs should be applied automatically
                    connection = pool.get("sync.client.sync_server_connection")
                    sync_type = context and context.get('sync_type', 'manual')
                    automatic_patching = sync_type == 'automatic' and\
                        connection.is_automatic_patching_allowed(cr, uid)
                    if not automatic_patching:
                        cr.commit()
                        raise osv.except_osv(_('Error!'), _(up_to_date[1]))
        except BaseException as e:
            logger = pool.get('sync.monitor').get_logger(cr, uid, context=context)
            logger.switch('status', 'failed')
            if not connected:
                if context is None:
                    context = {}
                keyword = 'manual' in method and 'beforemanualsync' or 'beforeautomaticsync'
                context['logger'] = logger
                try:
                    pool.get('backup.config').exp_dump_for_state(cr, uid, keyword, context=context)
                except osv.except_osv as f:
                    logger.append(f.value)
                del context['logger']
            if isinstance(e, osv.except_osv):
                logger.append(e.value)
                raise
            else:
                error = "%s: %s" % (e.__class__.__name__, e)
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
                chk_tz_msg = check_tz()
                if chk_tz_msg:
                    raise BaseException(chk_tz_msg)
                patch_failed = check_patch_scripts(cr, uid, context=context)
                if patch_failed:
                    raise BaseException(patch_failed)

                res = fn(self, self.sync_cursor, uid, *args, **kwargs)
            except osv.except_osv:
                logger.switch(step, 'failed')
                raise
            except BaseException as e:
                # Handle aborting of synchronization
                if isinstance(e, OperationalError) and str(e) == 'Unable to use the cursor after having closed it':
                    logger.switch(step, 'aborted')
                    self.sync_cursor = None
                    raise
                logger.switch(step, 'failed')
                error = "%s: %s" % (e.__class__.__name__, getattr(e, 'message', e))
                self._logger.exception('Error in sync_process at step %s' % step)
                logger.append(error, step)
                raise
            else:
                logger.switch(step, 'ok')
                if isinstance(res, str) and res:
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
            chk_tz_msg = check_tz()
            if chk_tz_msg:
                raise osv.except_osv(_('Error'), chk_tz_msg)
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

                    # generate a white list of models
                    if self.pool.get('sync.client.rule') and\
                            self.pool.get('sync.client.message_rule'):
                        server_model_white_set = self.get_model_white_list(cr, uid)
                        # check all models are in the hardcoded white list
                        difference = server_model_white_set.difference(WHITE_LIST_MODEL)
                        if difference:
                            msg = 'Warning: Some models used in the synchronization '\
                                'rule are not present in the WHITE_LIST_MODEL: %s'
                            logger.append(_(msg) % ' ,'.join(list(difference)))

                    # create a specific cursor for the call
                    self.sync_cursor = pooler.get_db(cr.dbname).cursor()

                    if need_connection:
                        # Check if connection is up
                        connection_obj = self.pool.get('sync.client.sync_server_connection')
                        if not connection_obj.is_connected:
                            if fn.__name__ == 'sync_manual_withbackup':
                                self.pool.get('backup.config').exp_dump_for_state(cr, uid, 'beforemanualsync', context=context)
                            # try to coonect from the file
                            try:
                                if not connection_obj.get_connection_from_config_file(cr,
                                                                                      uid, context=context):
                                    raise osv.except_osv(_("Error!"), _("Not connected: please try to log on in the Connection Manager"))
                            except AdminLoginException as e:
                                raise osv.except_osv(_("Error!"), _(e.value))
                        # Check for update (if connection is up)
                        if hasattr(self, 'upgrade'):
                            # TODO: replace the return value of upgrade to a status and raise an error on required update
                            up_to_date = self.upgrade(cr, uid, context=context)
                            cr.commit()

                            # check if patchs should be applied automatically
                            connection_module = self.pool.get("sync.client.sync_server_connection")
                            upgrade_module = self.pool.get('sync_client.upgrade')

                            sync_type = context.get('sync_type', 'manual')
                            automatic_patching = sync_type == 'automatic' and\
                                connection_module.is_automatic_patching_allowed(cr, uid)
                            if not up_to_date[0] and not automatic_patching:
                                raise osv.except_osv(_("Error!"), _("Cannot check for updates: %s") % up_to_date[1])
                            elif 'last' not in up_to_date[1].lower():
                                logger.append( _("Update(s) available: %s") % _(up_to_date[1]) )
                                if automatic_patching:
                                    upgrade_module = self.pool.get('sync_client.upgrade')
                                    upgrade_id = upgrade_module.create(cr, uid, {})
                                    upgrade_module.do_upgrade(cr, uid,
                                                              [upgrade_id], sync_type=context.get('sync_type', 'manual'))
                                    raise osv.except_osv(_('Sync aborted'),
                                                         _("Current synchronization has been aborted because there is update(s) to install. The sync will be restarted after update."))
                    else:
                        context['offline_synchronization'] = True

                    # more information
                    add_information(logger)
                patch_failed = check_patch_scripts(cr, uid, context=kwargs.get('context', {}))
                if patch_failed:
                    raise osv.except_osv(_('Error'), patch_failed)

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
                    cr.execute('SHOW server_version')
                    result = cr.fetchone()
                    pg_version = result and result[0] or 'pgversion not found'
                    proxy.set_pg_version(entity.identifier, self._hardware_id,
                                         pg_version)
            except SkipStep:
                # res failed but without exception
                assert is_step, "Cannot have a SkipTest error outside a sync step process!"
                logger.switch(step, 'null')
                logger.append(_("ok, skipped."), step)
                if make_log:
                    raise osv.except_osv(_('Error!'), _("You cannot perform this action now."))
            except osv.except_osv as e:
                logger.switch(step, 'failed')
                if make_log:
                    logger.append( e.value )
                    add_information(logger)
                raise
            except BaseException as e:
                # Handle aborting of synchronization
                if isinstance(e, OperationalError) and str(e) == 'Unable to use the cursor after having closed it':
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
                error = "%s: %s" % (e.__class__.__name__, getattr(e, 'message', e))
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
                if isinstance(res, str) and res:
                    logger.append(res, step)
            finally:
                # gotcha!
                try:
                    if make_log:
                        all_status = list(logger.info.values())
                        if 'ok' in all_status and step == 'status' and logger.info.get(step) in ('failed', 'aborted') and not logger.ok_before_last_dump:
                            # ok_before_last_dump: if backup after sync fails do not generate a new backup
                            try:
                                self.pool.get('backup.config').exp_dump_for_state(cr, uid, 'after%ssync' % context.get('sync_type', 'manual'), context=context)
                            except Exception as e:
                                logger.append("Cannot create backup")
                                self._logger.exception("Can't create backup %s" % tools.ustr(e))
                finally:
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

def generate_new_hwid():
    '''
            @return: the new hardware id
    '''
    logger = logging.getLogger('sync.client')
    mac_list = []
    if sys.platform == 'win32':
        # generate a new hwid with uuid library
        hw_hash = uuid.uuid1().hex
    else:
        for line in os.popen("/sbin/ifconfig"):
            if line.find('Ether') > -1:
                mac_list.append(line.split()[4])
        if not mac_list:
            raise Exception('/sbin/ifconfig give no result, please check it is correctly installed')
        mac_list.sort()
        logger.info('Mac addresses used to compute hardware indentifier: %s' % ', '.join(x for x in mac_list))
        hw_hash = hashlib.md5((''.join(mac_list)).encode('utf8')).hexdigest()
    logger.info('Hardware identifier: %s' % hw_hash)
    return hw_hash

def get_hardware_id():
    logger = logging.getLogger('sync.client')
    if sys.platform == 'win32':
            # US-1746: on windows machine get the hardware id from the registry
            # to avoid hwid change with new network interface (wifi adtapters,
            # vpn, ...)

        import winreg
        sub_key = 'SYSTEM\ControlSet001\services\eventlog\Application\openerp-web-6.0'

        try:
                # check if there is hwid stored in the registry
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub_key,
                                0, winreg.KEY_READ) as registry_key:
                hw_hash, regtype = winreg.QueryValueEx(registry_key, "HardwareId")
                logger.info("HardwareId registry key found: %s" % hw_hash)
        except WindowsError:
            logger.info("HardwareId registry key not found, create it.")

            # generate a new hwid on windows
            hw_hash = generate_new_hwid()

            # write the new hwid in the registry
            try:
                with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, sub_key):
                    pass
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub_key,
                                    0, winreg.KEY_ALL_ACCESS) as registry_key:
                    winreg.SetValueEx(registry_key, "HardwareId", 0, winreg.REG_SZ, hw_hash)
            except WindowsError as e:
                logger.error('Error on write of HardwareId in the registry: %s' % e)
    else:
        hw_hash = generate_new_hwid()
    return hw_hash

class Entity(osv.osv):
    """ OpenERP entity name and unique identifier """
    _name = "sync.client.entity"
    _description = "Synchronization Instance"
    _logger = logging.getLogger('sync.client')
    _hardware_id = get_hardware_id()

    def _auto_init(self, cr, context=None):
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
        'oc': fields.selection(OC_LIST_TUPLE,
                               'Operational Center'), # not required here because _auto_init create
        # before to know from witch OC it is part of
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
        'previous_hw': fields.char('Last HW successfully used', size=128, select=True),
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
            raise Exception("Can't acquire renew lock!")
        try:
            self.sync_lock = RLock()
        finally:
            self.renew_lock.release()

    def get_model_white_list(self, cr, uid):
        '''
        return a set of all models involved in the synchronization process
        '''
        model_field_dict = {}

        # search for model of sync_server.sync_rule
        if self.pool.get('sync_server.sync_rule'):
            rule_module = self.pool.get('sync_server.sync_rule')
            model_field_name = 'model_id'
        else:
            rule_module = self.pool.get('sync.client.rule')
            model_field_name = 'model'
        # TODO JFB RR: remove USB rules from sync / instances
        obj_ids = rule_module.search(cr, uid, [('active', '=', True), ('type', '!=', 'USB')])
        for obj in rule_module.read(cr, uid, obj_ids, [model_field_name, 'included_fields']):
            if obj[model_field_name] not in model_field_dict:
                model_field_dict[obj[model_field_name]] = set()
            model_field_dict[obj[model_field_name]].update(eval(obj['included_fields']))

        # search for model of sync_server.message_rule
        if self.pool.get('sync_server.message_rule'):
            rule_module = self.pool.get('sync_server.message_rule')
            model_field_name = 'model_id'
        else:
            rule_module = self.pool.get('sync.client.message_rule')
            model_field_name = 'model'
        obj_ids = rule_module.search(cr, uid, [('active', '=', True)])
        for obj in rule_module.read(cr, uid, obj_ids, [model_field_name, 'arguments']):
            if obj[model_field_name] not in model_field_dict:
                model_field_dict[obj[model_field_name]] = set()
            model_field_dict[obj[model_field_name]].update(eval(obj['arguments']))

        model_set = set(model_field_dict.keys())

        def get_field_obj(model, field_name):
            model_obj = self.pool.get(model)
            field_obj = None
            if field_name in model_obj._columns:
                field_obj = model_obj._columns[field_name]
            elif field_name in model_obj._inherit_fields:
                field_obj = model_obj._inherit_fields[field_name][2]
            return field_obj


        # for each field corresponding to each model, check if it is a m2m m2o or o2m
        # if yes, add the model of the relation to the model set

        for model, field_list in list(model_field_dict.items()):
            field_list_to_parse = [x for x in field_list if '/id' in x]
            if not field_list_to_parse:
                continue

            for field in field_list_to_parse:
                field = field.replace('/id', '')
                if len(field.split('/')) == 2:
                    related_field, field = field.split('/')
                    field_obj = get_field_obj(model, related_field)
                    related_model = field_obj._obj
                    field_obj = get_field_obj(related_model, field)
                else:
                    field_obj = get_field_obj(model, field)
                if field_obj and field_obj._type in ('many2one', 'many2many', 'one2many'):
                    model_set.add(field_obj._obj)

        # specific cases to sync BAR and FAR
        to_remove = ['ir.ui.view', 'ir.model.fields', 'ir.sequence']
        for f in to_remove:
            if f in model_set:
                model_set.remove(f)

        return model_set

    @sync_process('data_push')
    def push_update(self, cr, uid, context=None):
        """
            Push Update
        """
        context = context or {}
        logger = context.get('logger')
        entity = self.get_entity(cr, uid, context)
        context['lang'] = 'en_US'

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
    def create_update(self, oldcr, uid, context=None):
        cr = pooler.get_db(oldcr.dbname).cursor()
        cr._cnx.set_isolation_level(ISOLATION_LEVEL_REPEATABLE_READ)
        nb_tries = 1
        MAX_TRIES = 10
        while True:
            try:
                context = context or {}
                logger = context.get('logger')
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
                cr.commit()
                cr.close(True)
                return updates_count
            except TransactionRollbackError:
                cr.rollback()
                if nb_tries == MAX_TRIES:
                    msg = _("Unable to generate updates after %d tries") % MAX_TRIES
                    if logger:
                        logger.append(msg)
                        logger.write()
                    self._logger.info(msg)
                    cr.close(True)
                    raise
                msg = _("Unable to generate updates, retrying %d/%d") % (nb_tries, MAX_TRIES)
                if logger:
                    logger.append(msg)
                    logger.write()
                self._logger.info(msg)
                nb_tries += 1
            except:
                cr.rollback()
                cr.close(True)
                raise


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
                raise Exception(res[1])
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
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
        res = proxy.confirm_update(entity.identifier, self._hardware_id, session_id, {'md5': get_md5(session_id)})
        if not res[0]:
            raise Exception(res[1])
        updates.sync_finished(cr, uid, session_id, context=context)
        self.write(cr, uid, entity.id, {'session_id' : ''}, context=context)
        #state update validate => init
        return res[1]

    def set_rules(self, cr, uid, context=None):
        entity = self.get_entity(cr, uid, context)
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
        res = proxy.get_model_to_sync(entity.identifier, self._hardware_id)
        if not res[0]:
            raise Exception(res[1])

        entity.write({'previous_hw': self._hardware_id}, context=context)
        check_md5(res[2], res[1], _('method set_rules'))
        self.pool.get('sync.client.rule').save(cr, uid, res[1], context=context)

    def install_user_rights(self, cr, uid, context=None):
        if not context:
            context = {}

        logger = context.get('logger')
        entity = self.get_entity(cr, uid, context)
        encoded_zip = entity.user_rights_data
        plain_zip = b64decode(encoded_zip)

        self.pool.get('user_rights.tools').load_ur_zip(cr, uid, plain_zip, sync_server=False, logger=logger, context=context)
        return True

    @sync_process('user_rights')
    def check_user_rights(self, cr, uid, context=None):
        if context is None:
            context = {}
        context['lang'] = 'en_US'
        logger = context.get('logger')

        if _get_instance_level(self, cr, uid) != 'hq':
            return True

        entity = self.get_entity(cr, uid, context)
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
        res = proxy.get_last_user_rights_info(entity.identifier, self._hardware_id)
        if not res.get('sum'):
            return True

        first_sync = not entity.user_rights_sum
        to_install = False
        if res.get('sum') != entity.user_rights_sum:
            if logger:
                logger.append(_("Download new User Rights: %s") % res.get('name'))
                logger.write()
            ur_data_encoded = proxy.get_last_user_rights_file(entity.identifier, self._hardware_id, res.get('sum'))
            ur_data = b64decode(ur_data_encoded)
            computed_hash = hashlib.md5(ur_data).hexdigest()
            if computed_hash != res.get('sum'):
                raise Exception('User Rights: computed sum (%s) and server sum (%s) differ' % (computed_hash, res.get('sum')))
            entity.write({'user_rights_name': res.get('name'), 'user_rights_sum': computed_hash, 'user_rights_state': 'to_install', 'user_rights_data': ur_data_encoded})
            to_install = True

        if to_install or entity.user_rights_state == 'to_install':
            if first_sync:
                self.pool.get('sync.trigger.something').create(cr, uid, {'name': 'clean_ir_model_access'})
                # to generate all sync updates
                self.pool.get('sync.trigger.something').delete_ir_model_access(cr, uid)
            self.install_user_rights(cr, uid, context=context)
            entity.write({'user_rights_state': 'installed'})

        cr.commit()
        self.pool.get('ir.ui.menu')._clean_cache(cr.dbname)
        self.pool.get('ir.model.access').call_cache_clearing_methods(cr)
        return True

    @sync_process('get_surveys')
    def get_surveys(self, cr, uid, context=None):
        try:
            cr.execute("SAVEPOINT import_surveys")
            survey_obj = self.pool.get('sync_client.survey')
            logger = context.get('logger')

            entity = self.get_entity(cr, uid, context)
            proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
            last_date = survey_obj.get_last_write(cr, uid)
            res = proxy.get_surveys(entity.identifier, self._hardware_id, last_date)

            results_log = {}
            if res.get('deactivated_ids'):
                cr.execute("update sync_client_survey set active='f', server_write_date=%s where sync_server_id in %s", (res['max_date'], tuple(res['deactivated_ids'])))
                results_log['deactivated'] = cr.rowcount

            for survey_data in res.get('active', []):
                if 'id' in survey_data:
                    survey_data['sync_server_id'] = survey_data['id']
                    del(survey_data['id'])

                    survey_data['active'] = 't'
                    for field in ['included', 'excluded']:
                        list_ids = []
                        if survey_data['%s_group_txt' % field]:
                            list_ids = self.pool.get('res.groups').search(cr, uid, [('name', 'in', survey_data['%s_group_txt' % field].split(','))], context=context)
                        del(survey_data['%s_group_txt' % field])
                        survey_data['%s_group_ids' % field] = [(6, 0, list_ids)]

                    local_id = survey_obj.search(cr, uid, [('sync_server_id', '=', survey_data['sync_server_id']), ('active', 'in', ['t', 'f'])], context=context)
                    if local_id:
                        survey_obj.write(cr, uid, local_id, survey_data, context=context)
                        results_log['updated'] = results_log.setdefault('updated', 0) + 1
                    else:
                        survey_obj.create(cr, uid, survey_data, context=context)
                        results_log['created'] = results_log.setdefault('created', 0) + 1
            if logger and results_log:
                logger.append(_("Survey: %s") % ', '.join(['%d %s' % (x[1], x[0]) for x in results_log.items()]))
                logger.write()

            return True
        except Exception as e:
            cr.execute("ROLLBACK TO SAVEPOINT import_surveys")
            if logger:
                logger.append("Survey error: unable to get surveys")
                logger.write()
            self._logger.error('Survey error: %s' % tools.misc.get_traceback(e))
        else:
            cr.execute("RELEASE SAVEPOINT import_surveys")

    @sync_process('data_pull')
    def pull_update(self, cr, uid, recover=False, context=None):
        """
            Pull update
        """
        context = context or {}
        context['lang'] = 'en_US'
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
        if not res[0]: raise Exception(res[1])

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
            raise Exception(res[1])
        return True

    @sync_subprocess('data_pull_receive')
    def retrieve_update(self, cr, uid, max_packet_size, recover=False, context=None):
        context = context or {}
        logger = context.get('logger')
        updates = self.pool.get(context.get('update_received_model', 'sync.client.update_received'))

        init_sync = not bool(self.pool.get('res.users').get_browse_user_instance(cr, uid))

        entity = self.get_entity(cr, uid, context)
        last_seq = entity.update_last
        total_max_seq = entity.max_update
        offset = (0, entity.update_offset)
        offset_recovery = entity.update_offset
        last = (last_seq >= total_max_seq)
        updates_count = 0
        logger_index = None
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")

        # ask only max_seq_pack sequences to the sync server
        max_seq_pack = max_packet_size

        max_seq = min(last_seq+max_seq_pack, total_max_seq)
        while max_seq <= total_max_seq:
            while not last:
                res = proxy.get_update(entity.identifier, self._hardware_id, last_seq, offset, max_packet_size, max_seq, recover, init_sync)
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
                    raise Exception(res[1])
                cr.commit()

            self.write(cr, uid, entity.id, {'update_offset' : 0,
                                            'max_update' : 0,
                                            'update_last' : max_seq}, context=context)
            cr.commit()
            if max_seq == total_max_seq:
                break
            last = False
            last_seq = max_seq
            offset = (0, 0)
            offset_recovery = 0
            max_seq = min(max_seq+max_seq_pack, total_max_seq)

        trigger_analyze = self.pool.get('ir.config_parameter').get_param(cr, 1, 'ANALYZE_NB_UPDATES')
        nb = 2000
        if trigger_analyze:
            nb = int(trigger_analyze)
        if updates_count >= nb:
            self._logger.info('Begin analyze sync_client_update_received')
            cr.execute('analyze sync_client_update_received')
            self._logger.info('End of analyze')

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
        update_ids = updates.search(cr, uid, [('run', '=', False)], order='sequence_number, is_deleted, rule_sequence, id asc', context=context)
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

        param = self.pool.get('ir.config_parameter')
        if param.get_param(cr, uid, 'exec_set_journal_code_on_aji'):
            # here to process in-pipe AJI on the 1st sync after the release
            self.pool.get('patch.scripts').set_journal_code_on_aji(cr, uid)
            param.set_param(cr, uid, 'exec_set_journal_code_on_aji', '')

        return update_count

    @sync_process('msg_push')
    def push_message(self, cr, uid, context=None):
        """
            Push message
        """
        context = context or {}
        entity = self.get_entity(cr, uid, context)
        logger = context.get('logger')
        context['lang'] = 'en_US'
        if entity.state not in ['init', 'msg_push']:
            raise SkipStep

        if entity.state == 'init':
            self.create_message(cr, uid, context=context)
            cr.commit()

        nb_msg = self.send_message(cr, uid, context=context)
        cr.commit()

        self._logger.info("Push messages :: Number of messages pushed: %d" % nb_msg)
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
        proxy.sync_success(entity.identifier, self._hardware_id)
        if logger:
            logger.info['nb_msg_push'] = nb_msg
        return True

    @sync_subprocess('msg_push_create')
    def create_message(self, cr, uid, context=None):
        context = context or {}
        messages = self.pool.get(context.get('message_to_send_model', 'sync.client.message_to_send'))
        rule_obj = self.pool.get("sync.client.message_rule")

        to_update = {}
        messages_count = 0
        for rule in rule_obj.browse(cr, uid, rule_obj.search(cr, uid, [('type', '!=', 'USB')], context=context), context=context):
            generated_ids, ignored_ids = messages.create_from_rule(cr, uid, rule, None, context=context)
            messages_count += len(generated_ids)
            to_update.setdefault(rule.model, []).extend(generated_ids + ignored_ids)

        for model, ids in to_update.items():
            if ids:
                cr.execute('update ir_model_data set sync_date=NOW() where model=%s and res_id in %s', (model, tuple(ids)))
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
            msg_ids, packet = messages.get_message_packet(cr, uid, max_packet_size, context=context)
            if not packet:
                break
            messages_count += len(packet)
            res = proxy.send_message(uuid, self._hardware_id, packet, {'md5': get_md5(packet)})
            if not res[0]:
                raise Exception(res[1])
            messages.packet_sent(cr, uid, msg_ids, context=context)
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
        context['lang'] = 'en_US'
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")

        entity = self.get_entity(cr, uid, context=context)

        res = proxy.get_message_rule(entity.identifier, self._hardware_id)
        if res and not res[0]: raise Exception(res[1])
        check_md5(res[2], res[1], _('method get_message_rule'))
        self.pool.get('sync.client.message_rule').save(cr, uid, res[1], context=context)

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
            if not res[0]: raise Exception(res[1])

            packet = res[1]
            if not packet: break
            check_md5(res[2], packet, _('method get_message'))

            messages_count += len(packet)
            messages.unfold_package(cr, uid, packet, context=context)
            cr.commit()
            data_ids = [data['sync_id'] for data in packet]
            res = proxy.message_received_by_sync_id(instance_uuid, self._hardware_id, data_ids, {'md5': get_md5(data_ids)})
            if not res[0]: raise Exception(res[1])

            if logger and messages_count:
                if logger_index is None: logger_index = logger.append()
                logger.replace(logger_index, _("Message(s) received: %d") % messages_count)
                logger.write()
        return messages_count

    @sync_subprocess('msg_pull_execute')
    def execute_message(self, cr, uid, context=None):
        context = context or {}
        logger = context.get('logger')
        # force user to user_sync
        uid = self.pool.get('res.users')._get_sync_user_id(cr)

        messages = self.pool.get(context.get('message_received_model', 'sync.client.message_received'))

        # Get the whole list of messages to execute
        # Warning: order matters
        message_ids = messages.search(cr, uid, [('run','=',False)], order='rule_sequence, id', context=context)
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
        if context is None:
            context = {}
        context['sync_type'] = 'automatic'
        BackgroundProcess(cr, uid,
                          ('sync_recover_withbackup' if recover else 'sync_withbackup'),
                          context).start()
        return True

    def sync_manual_threaded(self, cr, uid, recover=False, context=None):
        if context is None:
            context = {}
        context['sync_type'] = 'manual'
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
        # is sync modules installed ?
        for sql_table, module in [('sync_client.version', 'update_client'),
                                  ('so.po.common', 'sync_so')]:
            if not self.pool.get(sql_table):
                raise osv.except_osv('Error', "%s module is not installed ! You need to install it to be able to sync." % module)
        # US_394: force synchronization lang to en_US
        context['lang'] = 'en_US'
        logger = context.get('logger')
        self._logger.info("Start synchronization")

        version_instance_module = self.pool.get('sync.version.instance.monitor')
        version_data = {}
        try:
            backup_config_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'sync_client', 'backup_config_default')[1]
            config_obj = self.pool.get('backup.config')
            version = config_obj.get_server_version(cr, uid, context=context)

            postgres_disk_space = version_instance_module._get_default_postgresql_disk_space(cr, uid)
            unifield_disk_space = version_instance_module._get_default_unifield_disk_space(cr, uid)
            version_data = {
                'version': version,
                'postgresql_disk_space': postgres_disk_space,
                'unifield_disk_space': unifield_disk_space,
                'machine': platform.machine(),
                'platform': platform.platform(),
                'processor': platform.processor(),
            }

            config_data = config_obj.read(cr, uid, backup_config_id, ['backup_type', 'wal_directory', 'ssh_config_dir', 'basebackup_date', 'rsync_date'], context=context)
            del config_data['id']
            version_data.update(config_data)


        except Exception:
            cr.rollback()
            logging.getLogger('version.instance.monitor').exception('Cannot generate instance monitor data')
            # do not block sync
            pass

        try:
            # list VI jobs
            job_details = []
            nb_late = 0
            now = time.strftime('%Y-%m-%d %H:%M:%S')

            dt_format = '%d/%b/%Y %H:%M'
            for auto_job in ['automated.export', 'automated.import']:
                job_obj = self.pool.get(auto_job)
                job_ids = job_obj.search(cr, uid, [('active', '=', True), ('cron_id', '!=', False)], context=context)
                if job_ids:
                    end_time_by_job = {}
                    job_field = "%s_id" % auto_job.split('.')[-1]
                    cr.execute("select "+job_field+", max(end_time) from "+auto_job.replace('.', '_')+"_job where "+job_field+" in %s and state in ('done', 'error') group by "+job_field, (tuple(job_ids), )) # not_a_user_entry
                    for end in cr.fetchall():
                        end_time_by_job[end[0]] = end[1] and time.strftime(dt_format, time.strptime(end[1], '%Y-%m-%d %H:%M:%S'))

                    for job in job_obj.browse(cr, uid, job_ids, fields_to_fetch=['name', 'cron_id', 'last_exec'], context=context):
                        if job.cron_id.nextcall < now:
                            nb_late += 1
                            job_name = '%s*' % job.name
                        else:
                            job_name = job.name

                        job_details.append('%s: %s' % (job_name, end_time_by_job.get(job.id, 'never')))

            version_data['nb_late_vi'] = nb_late
            version_data['vi_details'] = "\n".join(job_details)
            version_instance_module.create(cr, uid, version_data, context=context)
        except Exception:
            cr.rollback()
            logging.getLogger('version.instance.monitor').exception('Cannot generate instance monitor data')
        self.check_user_rights(cr, uid, context=context)
        self.get_surveys(cr, uid, context=context)
        self.set_rules(cr, uid, context=context)
        self.pull_update(cr, uid, context=context)
        self.pull_message(cr, uid, context=context)
        self.push_update(cr, uid, context=context)
        self.push_message(cr, uid, context=context)
        nb_msg_not_run = self.pool.get('sync.client.message_received').search(cr, uid, [('run', '=', False)], count=True)
        nb_data_not_run = self.pool.get('sync.client.update_received').search(cr, uid, [('run', '=', False)], count=True)
        if logger:
            logger.info['nb_msg_not_run'] = nb_msg_not_run
            logger.info['nb_data_not_run'] = nb_data_not_run

        self._logger.info('Not run updates : %d' % (nb_data_not_run, ))
        self._logger.info('Not run messages : %d' % (nb_msg_not_run, ))
        self._logger.info("Synchronization successfully done")
        if self.pool.get('wizard.hq.report.oca').launch_auto_export(cr, uid, context=context):
            if logger:
                logger_index = logger.append()
                logger.replace(logger_index, 'Processing Export to HQ system (OCA) - Not yet exported')
                logger.write()
            self._logger.info('Processing Export to HQ system (OCA) - Not yet exported')
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
        logger = context.get('logger')
        if logger:
            logger.ok_before_last_dump = True
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
        logger = context.get('logger')
        if logger:
            logger.ok_before_last_dump = True
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
        connection_obj = self.pool.get('sync.client.sync_server_connection')
        if not connection_obj.is_connected:
            login, password = connection_obj._info_connection_from_config_file(cr)
            if login == -1 or not login or not password:
                return _("Not Connected")

        if self.is_syncing():
            if self.aborting:
                return _("Aborting...")
            return _("Syncing...")

        monitor = self.pool.get("sync.monitor")
        last_log = monitor.last_status
        if last_log:
            return _("Last Sync: %s at %s, Not run upd: %s, Not run msg: %s") \
                % (_(monitor.status_dict[last_log[0]]), last_log[1], last_log[2], last_log[3])
        return _("Connected")

    def update_nb_shortcut_used(self, cr, uid, nb_shortcut_used, context=None):
        '''
        if the current have used some shorcut, update his counter and last date of use accordingly
        '''
        if context is None:
            context = {}
        if not nb_shortcut_used:
            return True
        user_obj = self.pool.get('res.users')
        current_date = datetime.now()
        previous_nb_shortcut_used = user_obj.read(cr, uid, uid,
                                                  ['nb_shortcut_used'],
                                                  context=context)['nb_shortcut_used']
        total_shortcut_used = previous_nb_shortcut_used + nb_shortcut_used
        user_obj.write(cr, uid, uid, {'last_use_shortcut': current_date,
                                      'nb_shortcut_used': total_shortcut_used,
                                      }, context=context)
        return True

    def display_shortcut_message(self, cr, uid, context=None):
        '''
        return True if the message should be displayed, False otherwize.
        random is used not display all the time the message, but 1 out of 10.
        '''
        if context is None:
            context = {}
        user_obj = self.pool.get('res.users')
        result = user_obj.read(cr, uid, uid,
                               ['nb_shortcut_used',
                                'last_use_shortcut'],
                               context=context)
        if result['nb_shortcut_used'] and result['nb_shortcut_used'] > 100:
            # once the user have used the shortcut a lot of times, do not
            # bother him with warning message
            return False
        if not result['last_use_shortcut']:
            # user have never used the shortcut
            return random() < 0.1
        last_date = result['last_use_shortcut']
        last_date = datetime.strptime(last_date[:19],'%Y-%m-%d %H:%M:%S')
        current_date = datetime.now()
        if current_date - last_date > timedelta(days=1):
            # the user didn't use the shortcut since long time
            return random() < 0.1
        return False

    def interrupt_sync(self, cr, uid, context=None):
        if self.is_syncing():
            #try:
            #    self._renew_sync_lock()
            #except StandardError:
            #    return False
            self.aborting = True
            # US-2306 : before to close the cursor, clear the _get_id caches
            self.pool.get('ir.model.data')._get_id.clear_cache(cr.dbname)
            self.sync_cursor.close(True)
        return True

    def clean_updates(self, cr, uid):
        '''delete old updates older than 6 months
        '''
        nb_month_to_clean = 6

        # delete sync_client_update_received older than 6 month
        cr.execute("""DELETE FROM sync_client_update_received
        WHERE create_date < now() - interval '%s month' AND
        execution_date IS NOT NULL AND run='t'""", (nb_month_to_clean,))
        deleted_update_received = cr.rowcount
        self._logger.info('clean_updates method has deleted %d sync_client_update_received' % deleted_update_received)

        # delete sync_client_update_to_send older than 6 month
        cr.execute("""DELETE FROM sync_client_update_to_send
        WHERE create_date < now() - interval '%s month' AND
        sent_date IS NOT NULL AND sent='t'""", (nb_month_to_clean,))
        deleted_update_to_send = cr.rowcount
        self._logger.info('clean_updates method has deleted %d sync_client_update_to_send' % deleted_update_to_send)

        self._logger.info('Begin analyze sync_client_update_to_send')
        cr.execute('analyze sync_client_update_to_send')
        self._logger.info('End analyze, begin analyze sync_client_update_received')
        cr.execute('analyze sync_client_update_received')
        self._logger.info('End analyze')


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
        'protocol': fields.selection([('xmlrpc', 'XMLRPC'), ('gzipxmlrpcs', 'secured compressed XMLRPC')], 'Protocol', help='Changing protocol may imply changing the port number'),
        'database' : fields.char('Database Name', size=64),
        'login':fields.char('Login on synchro server', size=64),
        'uid': fields.function(_get_uid, string='Uid on synchro server', readonly=True, type='char', method=True),
        'password': fields.function(_get_password, fnct_inv=_set_password, string='Password', type='char', method=True, store=False),
        'state' : fields.function(_get_state, method=True, string='State', type="char", readonly=True, store=False),
        'max_size' : fields.integer("Max Packet Size"),
        'timeout' : fields.float("Timeout"),
        'netrpc_retry' : fields.integer("NetRPC retry"),
        'xmlrpc_retry' : fields.integer("XmlRPC retry"),
        'automatic_patching' : fields.boolean('Silent Upgrade', help="Enable this if you want to automatically install patches during these hours."),
        'automatic_patching_hour_from': fields.float('Upgrade from', size=8, help="Enable upgrade from this time"),
        'automatic_patching_hour_to': fields.float('Upgrade until', size=8, help="Enable upgrade unitl this time"),
    }

    _defaults = {
        'active': True,
        'host' : 'sync.unifield.net',
        'port' : 443,
        'protocol': 'gzipxmlrpcs',
        'login' : 'admin',
        'max_size' : 500,
        'database' : 'SYNC_SERVER',
        'timeout' : 600.0,
        'netrpc_retry' : 10,
        'xmlrpc_retry' : 10,
        'automatic_patching': lambda *a: False,
    }

    def on_change_upgrade_hour(self, cr, uid, ids, automatic_patching_hour_from, automatic_patching_hour_to):
        """ Finds default stock location id for changed warehouse.
        @param warehouse_id: Changed id of warehouse.
        @return: Dictionary of values.
        """
        result = {'value': {}, 'warning': {}}
        values_dict = {
            'automatic_patching_hour_from':automatic_patching_hour_from,
            'automatic_patching_hour_to':automatic_patching_hour_to
        }
        for name, value in list(values_dict.items()):
            if value < 0:
                result.setdefault('value', {}).update({name: 0})
            if value >= 24:
                result.setdefault('value', {}).update({name: 23.98}) # 23.98 == 23h59
        return result

    def is_automatic_patching_allowed(self, cr, uid, date=None, automatic_patching=None,
                                      hour_from=None, hour_to=None, context=None):
        """
        return True if the passed date is in the range of hour_from, hour_to
        False othewise
        If no date is passed as parameter, datetime.today() is used
        """
        connection = self._get_connection_manager(cr, uid)
        if automatic_patching is None:
            automatic_patching = connection.automatic_patching
        if not automatic_patching:
            return False

        if date is None:
            date = datetime.today()
        if isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d %H:%M')

        if not hour_from:
            hour_from = connection.automatic_patching_hour_from
        if not hour_to:
            hour_to = connection.automatic_patching_hour_to

        hour_from_decimal = int(math.floor(abs(hour_from)))
        min_from_decimal = int(round(abs(hour_from)%1+0.01,2) * 60)
        hour_to_decimal = int(math.floor(abs(hour_to)))
        min_to_decimal = int(round(abs(hour_to)%1+0.01,2) * 60)

        from_date = datetime(date.year, date.month, date.day,
                             hour_from_decimal, min_from_decimal)
        to_date = datetime(date.year, date.month, date.day, hour_to_decimal,
                           min_to_decimal)

        # from_date and to_date are not the same day:
        if from_date > to_date:
            # case 1: the from date is in the past
            # ex. it is 3h, from_date=19h, to_date=7h
            if from_date > date:
                from_date = from_date - timedelta(days=1)

            # case 2: the to_date is in the future
            # ex. it is 20h, from_date=19h, to_date=7h
            elif date > to_date:
                to_date = to_date + timedelta(days=1)

        return date > from_date and date < to_date

    def _get_connection_manager(self, cr, uid, context=None):
        ids = self.search(cr, uid, [], context=context)
        if not ids:
            raise osv.except_osv('Connection Error', "Connection manager not set!")
        return self.browse(cr, uid, ids, context=context)[0]

    def connector_factory(self, con):
        # xmlrpc now does gzip by default
        if con.protocol == 'xmlrpc' or con.protocol == 'gzipxmlrpc':
            connector = rpc.XmlRPCConnector(con.host, con.port, timeout=con.timeout, retry=con.xmlrpc_retry)
        elif con.protocol == 'xmlrpcs' or con.protocol == 'gzipxmlrpcs':
            connector = rpc.SecuredXmlRPCConnector(con.host, con.port, timeout=con.timeout, retry=con.xmlrpc_retry)
        elif con.protocol == 'netrpc':
            connector = rpc.NetRPCConnector(con.host, con.port, timeout=con.timeout, retry=con.netrpc_retry)
        elif con.protocol == 'netrpc_gzip':
            connector = rpc.GzipNetRPCConnector(con.host, con.port, timeout=con.timeout, retry=con.netrpc_retry)
        else:
            raise osv.except_osv('Connection Error','Unknown protocol: %s' % con.protocol)
        return connector

    def _info_connection_from_config_file(self, cr):
        login = tools.config.get('sync_user_login')
        if login == 'admin':
            if not self.search_exist(cr, 1, [('host', 'in', ['127.0.0.1', 'localhost'])]):
                login = -1
        return (login, tools.config.get('sync_user_password'))

    def get_connection_from_config_file(self, cr, uid, ids=None, context=None):
        '''
        get credentials from config file if any and try to connect to the sync
        server with them. Return True if it has been connected using this
        credentials, False otherwise
        '''
        logger = logging.getLogger('sync.client')
        if not self.is_connected:
            login, password = self._info_connection_from_config_file(cr)
            if login == -1:
                raise AdminLoginException
            if login and password:
                # write this credentials in the connection manager to be
                # consistent with the credentials used for the current
                # connection and what is in the connection manager
                connection_ids = self.search(cr, 1, [])
                if connection_ids:
                    logger.info('Automatic set up of sync connection credentials')
                    data_to_write = {
                        'login': login,
                        'password': password,
                    }
                    self.write(cr, 1, connection_ids, data_to_write)
                    cr.commit()
                return self.connect(cr, 1, password=password, login=login)
        return False

    def connect(self, cr, uid, ids=None, password=None, login=None, context=None):
        """
        connect the instance to the SYNC_SERVER instance for synchronization
        """
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
                if password is not None:
                    self._password = password
                    con.password = password
                else:
                    self._password = con.login
            if login is None:
                login=con.login
            cnx = rpc.Connection(connector, con.database, login, self._password)
            con._cache = {}
            if cnx.user_id:
                self._uid = cnx.user_id
            else:
                raise osv.except_osv('Not Connected', "Not connected to server. Please check password and connection status in the Connection Manager")
        except socket.error as e:
            raise osv.except_osv(_("Error"), _(e.strerror))
        except osv.except_osv:
            raise
        except BaseException as e:
            raise osv.except_osv(_("Error"), _(str(e)))

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

    def write(self, cr, uid, ids, vals, context=None):
        # reset connection flag when connection data changed
        connection_property_list = [
            'database',
            'host',
            'login',
            'max_size',
            'netrpc_retry',
            'password',
            'port',
            'protocol',
            'timeout',
            'xmlrpc_retry'
        ]

        new_values = vals
        current_values = self.read(cr, uid, ids, list(vals.keys()))[0]
        for key, value in list(new_values.items()):
            if current_values[key] != value and \
                    key in connection_property_list:
                self._uid = False
                break

        # check the new properties match the automatic sync task
        if set(('automatic_patching', 'automatic_patching_hour_from',
                'automatic_patching_hour_to')).issubset(list(vals.keys())) and\
                vals['automatic_patching']:

            try:
                model, auto_sync_id = self.pool.get('ir.model.data').get_object_reference(cr, uid,
                                                                                          'sync_client', 'ir_cron_automaticsynchronization0')
                cron_obj = self.pool.get(model)
                sync_cron = cron_obj.read(cr, uid, auto_sync_id,
                                          ['nextcall','interval_type',
                                           'interval_number',
                                           'active', 'numbercall'],
                                          context=context)
                if not sync_cron['active']:
                    raise osv.except_osv(_('Error!'),
                                         _('Automatic Synchronization must be '
                                           'activated to perform Silent Upgrade'))
                try:
                    cron_obj.check_upgrade_time_range(cr, uid,
                                                      sync_cron['nextcall'], sync_cron['interval_type'],
                                                      sync_cron['interval_number'],
                                                      vals['automatic_patching_hour_from'],
                                                      vals['automatic_patching_hour_to'],
                                                      vals['automatic_patching'], context=context)
                except osv.except_osv:
                    nextcall_time = datetime.strptime(sync_cron['nextcall'],
                                                      '%Y-%m-%d %H:%M:%S').strftime('%H:%M')
                    raise osv.except_osv(_('Error!'),
                                         _('Silent Upgrade time range must include '
                                           'the Automatic Synchronization time (%s)') % nextcall_time)
            except ValueError:
                pass  # the reference don't exists

        return super(Connection, self).write(cr, uid, ids, vals,
                                             context=context)

    def change_host(self, cr, uid, ids, host, proto, context=None):
        if host in ('127.0.0.1', 'localhost'):
            return self.change_protocol(cr, uid, ids, host, proto, context=context)
        return {}

    def change_protocol(self, cr, uid, ids, host, proto, context=None):
        xmlrpc = 8069
        xmlrpcs = 443
        netrpc = 8070
        if host in ('127.0.0.1', 'localhost'):
            xmlrpc = tools.config.get('xmlrpc_port')
            netrpc = tools.config.get('netrpc_port')
            # For xmlrpcs, we keep the default value (443) because this does
            # not make much sense anyway to have SSL over localhost (won't have
            # a valid certificate)
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
