# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2017 TeMPO Consulting
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

import os
import time
import pooler
import uuid
import configparser
import shutil

import tools
import threading
from tools.translate import _
from osv import fields, osv
from datetime import datetime
import logging

TRUE_LIST = (True, 'True', 'true', 'TRUE', 'Yes', 'YES', 'yes')

class instance_auto_creation(osv.osv):
    _name = "instance.auto.creation"
    _description = "Instance auto creation"

    _columns = {
        'start_date': fields.datetime('Instance creation start date'),
        'state': fields.selection([
            ('draft', 'Draft'),
            ('msf_profile_installation', 'Installation of module \'msf_profile\' in progress...'),
            ('msf_profile_installed', 'Module \'msf_profile\' installed.'),
            ('sync_so_installation', 'Installation of module \'sync_so\' in progress...'),
            ('sync_so_installed', 'Module \'sync_so\' installed.'),
            ('update_client_installation', 'Installation of module \'update_client\' in progress...'),
            ('update_client_installed', 'Module \'update_client\' installed.'),
            ('sync_client_web_installation', 'Installation of module \'sync_client_web\' in progress...'),
            ('sync_client_web_installed', 'Module \'sync_client_web\' installed.'),
            ('language_installation', 'Installation of the language localisation in progress...'),
            ('language_installed', 'Language installed.'),
            ('register_instance', 'Register the instance into the SYNC_SERVER...'),
            ('instance_registered', 'Instance registered.'),
            ('waiting_for_validation', 'Waiting for validation on SYNC_SERVER side (re-check every 5 minutes) ...'),
            ('instance_validated', 'Instance validated on SYNC_SERVER side.'),
            ('backup_configuration', 'Backup configuration...'),
            ('backup_configured', 'Backup configured.'),
            ('start_init_sync', 'Start intial synchronisation, this may take a lot of time...'),
            ('end_init_sync', 'Init sync finished !'),
            ('reconfigure', 'Do reconfigure...'),
            ('reconfigure_done', 'Reconfigure done.'),
            ('import_files', 'Start importing files ...'),
            ('files_imported', 'Files import done.'),
            ('partner_configuration', 'Start configuration of internal partner...'),
            ('partner_configuration_done', 'Internal partner configuration done.'),
            ('done', 'Instance creation done.')], 'State', readonly=True),
        'progress': fields.float('Progress', readonly=True),
        'error': fields.text('Error', readonly=True),
        'message': fields.text('Message', readonly=True),
        'resume': fields.text('Resume', readonly=True),
        'dbname': fields.char('Database name', size=256, readonly=True),
    }

    _defaults = {
        'start_date': lambda *a: time.strftime("%Y-%m-%d %H:%M:%S"),
        'state': lambda *a: 'draft',
        'progress': lambda self, cr, uid, c: 1/float(len(self._columns['state'].selection)-1),
        'resume': lambda *a: ''.join((_('Empty database creation in progress...\n'), _('%s: Empty database created.\n') % time.strftime("%Y-%m-%d %H:%M:%S"))),
    }

    def write(self, cr, uid, ids, vals, context=None):

        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        # each time a write is done, add a line in the resume
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        state = vals.get('state')
        if state:
            previous_state = self.read(cr, uid, ids[0], ['state'], context=context)['state']
            if previous_state != state:
                get_sel = self.pool.get('ir.model.fields').get_selection
                current_state_label = get_sel(cr, uid, self._name, 'state', state, context=context)
                line_to_add = '%s: %s\n' % (current_time, current_state_label)

                resume = self.read(cr, uid, ids[0], ['resume'], context=context)['resume']
                resume += line_to_add
                vals['resume'] = resume

        if 'progress' not in vals and vals.get('state') and state != previous_state:
            # if progress is not passed, increment it at each state change
            progress = self.read(cr, uid, ids[0], ['progress'],
                                 context=context)['progress']
            nb_state = len(self._columns['state'].selection) - 3  # remove draft and done
            one_step_percentage = 1/float(nb_state)
            progress += one_step_percentage
            vals['progress'] = progress

        # prevent to go more the 100%
        if vals.get('progress', 0) >= 1 or state == 'done':
            vals['progress'] = 1
            vals['state'] = 'done'

        res = super(instance_auto_creation, self).write(cr, uid, ids, vals,
                                                        context=context)
        cr.commit()
        return res

    def check_sync_server_registration_validation(self, cr, uid, context=None):
        entity_obj = self.pool.get('sync.client.entity')
        entity = entity_obj.get_entity(cr, uid, context=context)
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.entity")

        # call a method decorated with @check_validated to ensure that the
        # entity has been validated by the sync_server
        validated = False
        message = ''
        creation_id = self.search(cr, uid, [('dbname', '=', cr.dbname)], context=context)
        if not creation_id:
            return False
        creation_id = creation_id and creation_id[0]
        current_state = self.read(cr, uid, creation_id, ['state'])['state']
        try:
            validated, message = proxy.is_validated(entity.identifier)
        except Exception as e:
            if 'AccessDenied' in e.value:
                # try to reconnect automatically:
                synchro_serv = self.pool.get('sync.client.sync_server_connection')
                connection_ids = synchro_serv.search(cr, uid, [])
                connection = False
                if connection_ids:
                    connection_state = synchro_serv.read(cr, uid, connection_ids[0], ['state'])['state']
                    if connection_state == 'Disconnected':
                        connection = synchro_serv.connect(cr, uid, connection_ids)
                if connection and current_state in ('start_init_sync', 'end_init_sync', 'reconfigure', 'reconfigure_done', 'done'):
                    validated = True
                else:
                    message = _('The instance is not connected to the SYNC_SERVER')
            else:
                message = e.value
            self.write(cr, uid, creation_id, {'error': message}, context=context)
        else:
            self.write(cr, uid, creation_id,
                       {'error':''},
                       context=context)

        if not validated:
            return False

        # registration validated ! The crontab can be desactivated
        cron_obj = self.pool.get('ir.cron')
        cron_ids = cron_obj.search(cr, uid,
                                   [('function', '=', 'check_sync_server_registration_validation')],
                                   context=context)
        if cron_ids:
            cron_obj.write(cr, uid, cron_ids, {'active': False}, context=context)
        if current_state == 'waiting_for_validation':
            self.write(cr, uid, creation_id,
                       {'state': 'instance_validated', 'error':''},
                       context=context)
        creation_obj = self.pool.get('instance.auto.creation')
        create_thread = threading.Thread(target=creation_obj.background_install_after_registration,
                                         args=(cr.dbname, uid, creation_id))
        create_thread.start()
        create_thread.join(1)

        return True

    def background_install(self, cr, pool, uid, creation_id, context=None):
        if context is None:
            context = {}

        try:
            creation_state = self.read(cr, uid, creation_id, ['state'], context=context)['state']

            config_file_name = 'uf_auto_install.conf'
            config_file_path = os.path.join(tools.config['root_path'], '..', 'UFautoInstall', config_file_name)
            config = configparser.ConfigParser()
            config.read(config_file_path)
            config_dict =  {x:dict(config.items(x)) for x in config.sections()}

            skip_msf_profile = skip_sync_so = skip_update_client = skip_sync_client_web = skip_language = skip_all_modules = skip_register = False
            if creation_state == 'draft':
                pass
            elif creation_state == 'msf_profile_installed':
                skip_msf_profile = True
            elif creation_state == 'sync_so_installed':
                skip_sync_so = True
            elif creation_state == 'update_client_installed':
                skip_update_client = True
            elif creation_state == 'sync_client_web_installed':
                skip_sync_client_web = True
            elif creation_state in ('language_installed', 'register_instance'):
                skip_all_modules = skip_language = True
            elif creation_state in ('instance_registered',
                                    'waiting_for_validation', 'instance_validated',
                                    'backup_configuration', 'backup_configured',
                                    'start_init_sync', 'end_init_sync', 'reconfigure',
                                    'reconfigure_done', 'import_files', 'file_imported', 'done') :
                skip_all_modules = skip_language = skip_register = True
            else:
                # this is not a state we can restart from
                # this mean there was probably a crash during the creation and
                # it is safer to create a new one.
                error_message = self.read(cr, uid, creation_id, ['error'], context=context)['error']
                if error_message and 'It is not possible to restart' not in error_message:
                    error_message = 'It is not possible to restart the auto-creation from this state. It is safer to delete the database and recreate a new one. Last error message was: %s.' % error_message
                raise osv.except_osv(_("Error!"), error_message)

            if creation_state != 'draft':
                # this is a restart of an existing autocreation.
                # errase previous errors
                self.write(cr, uid, creation_id, {'error': ''}, context=context)

            # module installation
            module_obj = pool.get('ir.module.module')
            if not skip_all_modules:
                upgrade_obj = pool.get('base.module.upgrade')
                for module_name in ['msf_profile', 'sync_so', 'update_client', 'sync_client_web']:
                    if locals().get(('skip_%s' % module_name), False):
                        continue
                    self.write(cr, 1, creation_id,
                               {'state': '%s_installation' % module_name}, context=context)
                    module_id = module_obj.search(cr, 1, [('name', '=', module_name)])
                    module_obj.button_install(cr, 1, module_id)
                    upgrade_obj.upgrade_module(cr, 1, None, None)
                    self.write(cr, 1, creation_id,
                               {'state': '%s_installed' % module_name}, context=context)

            # install language
            if not skip_language:
                self.write(cr, 1, creation_id,
                           {'state': 'language_installation'}, context=context)
                lang = config_dict['instance'].get('lang')
                if lang:
                    lang_obj = pool.get('res.lang')
                    lang_id = lang_obj.search(cr, uid, [('code', '=', lang)])
                    if lang_id:
                        lang_obj.write(cr, uid, lang_id, {'translatable': True})
                        mod_ids = module_obj.search(cr, uid, [('state', '=', 'installed')])
                        module_obj.button_update_translations(cr, uid, mod_ids, lang)
                self.write(cr, 1, creation_id,
                           {'state': 'language_installed'}, context=context)

            if skip_register:
                # try to connect
                synchro_serv = pool.get('sync.client.sync_server_connection')
                ids = synchro_serv.search(cr, uid, [])
                if ids:
                    synchro_serv.connect(cr, uid, ids)

            if not skip_register:
                # register instance
                self.write(cr, 1, creation_id,
                           {'state': 'register_instance'}, context=context)
                sync_vals = {
                    'protocol': config_dict['instance'].get('sync_protocol'),
                    'host': config_dict['instance'].get('sync_host'),
                    'port': config_dict['instance'].get('sync_port'),
                    'database': config_dict['instance'].get('sync_server'),
                    'login': config_dict['instance'].get('sync_user'),
                    'password': config_dict['instance'].get('sync_pwd'),
                }

                # get new pool after module installation
                db, pool = pooler.get_db_and_pool(cr.dbname)
                cr.commit()
                cr.close()
                cr = db.cursor()
                synchro_serv = pool.get('sync.client.sync_server_connection')
                ids = synchro_serv.search(cr, uid, [])
                if ids:
                    synchro_serv.write(cr, uid, ids, sync_vals)
                else:
                    ids = [synchro_serv.create(cr, uid, sync_vals)]
                cr.commit()
                synchro_serv.connect(cr, uid, ids)

                # use the instance name if defined else, the database name
                instance_name = config_dict['instance'].get('instance_name') or cr.dbname
                # find the parent_id:
                oc = config_dict['instance'].get('oc').lower()
                data = {
                    'name': instance_name,
                    'parent': config_dict['instance'].get('parent_instance'),
                }

                # search the current entity
                entity_obj = pool.get('sync.client.entity')
                entity_id = entity_obj.search(cr, uid, [])
                instance_identifier = False
                if entity_id:
                    entity_data = entity_obj.read(cr, uid, entity_id[0])
                    entity_obj.write(cr, uid, entity_id[0], data)
                    instance_identifier = entity_data['identifier']
                else:
                    instance_identifier = str(uuid.uuid1())
                    data['identifier'] = instance_identifier
                    entity_obj.create(cr, uid, data)
                wiz_data = {'email': 'www', 'oc': oc}
                wizard = pool.get('sync.client.register_entity')
                wizard_id = wizard.create(cr, uid, wiz_data)
                wizard.next(cr, uid, wizard_id)
                # Group state
                wizard.group_state(cr, uid, wizard_id)

                group_obj = pool.get('sync.client.entity_group')
                group_name_list = config_dict['instance'].get('group_names')
                group_ids = group_obj.search(cr, uid, [('name', 'in', group_name_list)], context=context)
                wizard.write(cr, uid, wizard_id, {'group_ids': [(6, 0, group_ids)]}, context=context)

                # Register instance
                wizard.validate(cr, uid, wizard_id)
                self.write(cr, 1, creation_id,
                           {'state': 'instance_registered'}, context=context)

                if config_dict['instance'].get('auto_valid') and config_dict['instance'].get('sync_host') in ('localhost', '127.0.0.1') and instance_identifier:
                    proxy = pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.entity")
                    ent_ids = proxy.search([('name', '=', instance_name), ('identifier', '=', instance_identifier)])
                    proxy.validate_action(ent_ids)


            # create a cron job to check that the registration has been validated on the server side
            cron_obj = pool.get('ir.cron')
            cron_vals = {
                'name': 'Check if SYNC_SERVER validates the registration',
                'active': True,
                'interval_number': 5,
                'interval_type': 'minutes',
                'numbercall': -1,
                'doall': False,
                'nextcall': time.strftime('%Y-%m-%d %H:%M:%S'),
                'model': 'instance.auto.creation',
                'function': 'check_sync_server_registration_validation',
            }
            cron_ids = cron_obj.search(cr, uid,
                                       [('function', '=', 'check_sync_server_registration_validation'),
                                        ('active', 'in', ('t', 'f'))],
                                       context=context)
            if cron_ids:
                cron_obj.write(cr, uid, cron_ids, cron_vals, context=context)
            else:
                cron_obj.create(cr, uid, cron_vals, context=context)
            current_state = self.read(cr, uid, creation_id, ['state'])['state']
            if current_state == 'instance_registered':
                self.write(cr, 1, creation_id,
                           {'state': 'waiting_for_validation'}, context=context)
        except Exception as e:
            logging.getLogger('autoinstall').error('Auto creation error: %s' % tools.misc.get_traceback(e))
            self.write(cr, 1, creation_id,
                       {'error': '%s' % e}, context=context)

        finally:
            cr.commit()
            cr.close()


    def background_install_after_registration(self, dbname, uid, creation_id, context=None):
        cr = None
        try:
            db, pool = pooler.get_db_and_pool(dbname)
            cr = db.cursor()
            skip_reconfigure = False
            creation_state = self.read(cr, uid, creation_id, ['state'], context=context)['state']
            skip_init_sync = skip_backup_config = skip_reconfigure = skip_import_files = False
            if creation_state == 'end_init_sync':
                skip_init_sync = True
            elif creation_state in ('backup_configured', 'reconfigure'):
                skip_init_sync = skip_backup_config = True
            elif creation_state in ('reconfigure_done', 'import_files'):
                skip_init_sync = skip_backup_config = skip_reconfigure = True
            elif creation_state in ('start_init_sync', 'instance_validated'):
                pass  # it is allowed to restart this state
            else:
                # this is not a state we can restart from
                # this mean there was probably a crash during the creation and
                # it is safer to create a new one.
                error_message = self.read(cr, uid, creation_id, ['error'], context=context)['error'] or 'no error stored'
                if 'It is not possible to restart' not in error_message:
                    error_message = 'It is not possible to restart the auto-creation from this state. It is safer to delete the database and recreate a new one. Last error message was: %s.' % error_message
                raise osv.except_osv(_("Error!"), error_message)

            config_file_name = 'uf_auto_install.conf'
            config_file_path = os.path.join(tools.config['root_path'], '..', 'UFautoInstall', config_file_name)
            config = configparser.ConfigParser()
            config.read(config_file_path)
            config_dict =  {x:dict(config.items(x)) for x in config.sections()}

            if not skip_init_sync:
                entity_obj = self.pool.get('sync.client.entity')
                sync_status = entity_obj.get_status(cr, uid)
                if sync_status == 'Syncing...':
                    # keep going
                    pass
                elif sync_status.startswith('Last Sync: Ok'):
                    self.write(cr, 1, creation_id,
                               {'state': 'end_init_sync'}, context=context)
                elif sync_status == 'Connected' or sync_status.startswith('Last Sync:'):
                    # start/restart the init sync (very long)
                    self.write(cr, 1, creation_id,
                               {'state': 'start_init_sync'}, context=context)
                    entity_obj.sync(cr, uid)
                    self.write(cr, 1, creation_id,
                               {'state': 'end_init_sync'}, context=context)
                else:
                    raise osv.except_osv(_("Error!"), 'Impossible to perform the sync. Sync status is \'%s\'.' % sync_status)

            if not skip_backup_config:
                self.write(cr, 1, creation_id,
                           {'state': 'backup_configuration'}, context=context)
                backup_obj = self.pool.get('backup.config')
                backup_id = backup_obj.search(cr, uid, [], context=context)
                backup_vals = {
                    'name': config_dict['backup'].get('auto_bck_path'),
                    'beforemanualsync': config_dict['backup'].get('auto_bck_beforemanualsync') in TRUE_LIST,
                    'aftermanualsync': config_dict['backup'].get('auto_bkc_aftermanualsync') in TRUE_LIST,
                    'beforepatching': config_dict['backup'].get('auto_bck_beforepatching') in TRUE_LIST,
                    'beforeautomaticsync': config_dict['backup'].get('auto_bck_beforeautomaticsync') in TRUE_LIST,
                    'afterautomaticsync': config_dict['backup'].get('auto_bck_afterautomaticsync') in TRUE_LIST,
                    'scheduledbackup': config_dict['backup'].get('auto_bck_scheduledbackup', True) in TRUE_LIST,
                }
                backup_obj.write(cr, uid, backup_id, backup_vals, context=context)

                # update automatic backup cron job
                vals = {
                    'active': config_dict['backup'].get('auto_bck_scheduledbackup', True) in TRUE_LIST,
                    'interval_number': config_dict['backup'].get('auto_bck_interval_nb'),
                    'interval_type': config_dict['backup'].get('auto_bck_interval_unit'),
                }
                if config_dict['backup'].get('auto_bck_next_exec_date'):
                    vals['nextcall'] = config_dict['backup'].get('auto_bck_next_exec_date')

                auto_backup = self.pool.get('ir.model.data').get_object(cr, uid, 'sync_client', 'ir_cron_automaticsyncbackup')
                cron_obj = self.pool.get('ir.cron')
                if auto_backup:
                    backup_id = auto_backup.id
                    cron_obj.write(cr, uid, backup_id, vals, context=context)
                self.write(cr, 1, creation_id,
                           {'state': 'backup_configured'}, context=context)

            if not skip_reconfigure:
                # sync to get the parent prop instance if it has been recently added
                self.pool.get('sync.client.entity').sync(cr, uid)
                if creation_state != 'reconfigure':
                    self.write(cr, 1, creation_id,
                               {'state': 'reconfigure'}, context=context)

                country_code = config_dict['reconfigure'].get('address_country')
                country_id = False
                if country_code:
                    country_obj = self.pool.get('res.country')
                    country_ids = country_obj.search(cr, uid, [('code', '=ilike', country_code)])
                    if country_ids:
                        country_id = country_ids[0]

                state_code = config_dict['reconfigure'].get('address_state')
                state_id = None
                if state_code:
                    state_obj = self.pool.get('res.country.state')
                    state_ids = state_obj.search(cr, uid, [('code', '=', state_code)])
                    if state_ids:
                        state_id = state_ids[0]

                if config.has_option('reconfigure', 'import_commitments'):
                    import_commitments = config.getboolean('reconfigure', 'import_commitments')
                else:
                    import_commitments = True

                if config.has_option('reconfigure', 'previous_fy_dates_allowed'):
                    previous_fy_dates_allowed = config.getboolean('reconfigure', 'previous_fy_dates_allowed')
                else:
                    previous_fy_dates_allowed = False

                if config.has_option('reconfigure', 'customer_commitment'):
                    customer_commitment = config.getboolean('reconfigure', 'customer_commitment')
                else:
                    customer_commitment = False

                if config.has_option('reconfigure', 'payroll_ok'):
                    payroll_ok = config.getboolean('reconfigure', 'payroll_ok')
                else:
                    payroll_ok = True

                if config.has_option('reconfigure', 'delivery_process'):
                    delivery_process = config_dict['reconfigure'].get('delivery_process')
                else:
                    delivery_process = 'complex'

                base_wizards = {
                    'base.setup.config': {
                        'button' : 'config',
                    },
                    'unifield.setup.configuration': {
                        'import_commitments': import_commitments,
                    },
                    'payroll.setup': {
                        'payroll_ok': payroll_ok,
                    },
                    'delivery.process.setup': {
                        'delivery_process': delivery_process,
                    },
                    'base.setup.company': {
                        'street': config_dict['reconfigure'].get('address_street'),
                        'street2': config_dict['reconfigure'].get('address_street2'),
                        'zip': config_dict['reconfigure'].get('address_zip'),
                        'city': config_dict['reconfigure'].get('address_city'),
                        'phone': config_dict['reconfigure'].get('address_phone'),
                        'email': config_dict['reconfigure'].get('address_email'),
                        'website': config_dict['reconfigure'].get('address_company_website'),
                        'contact_name': config_dict['reconfigure'].get('address_contact_name'),
                        'account_no': config_dict['reconfigure'].get('address_account'),
                    },
                    'res.config.view': {
                        'name': "auto_init",
                        'view': 'extended',
                    },
                    'sale.price.setup': {
                        'sale_price': 0.10,
                    },
                    'stock.location.configuration.wizard': {
                        'location_type': 'internal',
                        'location_usage': 'stock',
                        'location_name': 'Test Location',
                        'button': 'action_stop',
                    },
                    'currency.setup': {
                        'functional_id': config_dict['reconfigure'].get('functional_currency').lower(),
                    },
                    'previous.fy.dates.setup': {
                        'previous_fy_dates_allowed': previous_fy_dates_allowed,
                    },
                    'customer.commitment.setup': {
                        'customer_commitment': customer_commitment,
                    },
                    'esc_line.setup': {
                        'esc_line': config.has_option('reconfigure', 'activate_international_invoices_lines') and config.getboolean('reconfigure', 'activate_international_invoices_lines')
                    },
                    'fixed.asset.setup': {
                        'fixed_asset_ok': config.has_option('reconfigure', 'activate_fixed_asset') and config.getboolean('reconfigure', 'activate_fixed_asset')
                    },
                    'signature.setup': {
                        'signature': config.has_option('reconfigure', 'activate_electronic_validation') and config.getboolean('reconfigure', 'activate_electronic_validation')
                    },
                }
                base_wizards['base.setup.company']['country_id'] = country_id
                if state_code:
                    base_wizards['base.setup.company']['state_id'] = state_id

                model = 'msf_instance.setup'
                while model != 'ir.ui.menu':
                    # skip account.installer if no parent_name providen (typically: HQ instance)
                    if model == 'msf_instance.setup':
                        instance_id = self.pool.get('msf.instance').search(cr,
                                                                           uid, [('code', '=', config_dict['instance']['prop_instance_code'])])
                        if not instance_id:
                            error_message = ('No prop. instance \'%s\' found. Please check it has been created on the HQ and sync, then restart the auto creation process from scratch.') % config_dict['instance']['prop_instance_code']
                            raise osv.except_osv(_("Error!"), error_message)
                        else:
                            instance_id = instance_id[0]

                        self.pool.get('res.company').write(cr, uid, [1], {'instance_id': instance_id})
                        wiz_obj = self.pool.get(model)
                        wizard_id = wiz_obj.create(cr, uid, {'instance_id': instance_id})
                        answer = wiz_obj.action_next(cr, uid, [wizard_id])
                    else:
                        data = dict(base_wizards.get(model, {}))
                        button = data.pop('button', 'action_next')
                        wiz_obj = self.pool.get(model)
                        wizard_id = wiz_obj.create(cr, uid, data)
                        answer = getattr(wiz_obj, button)(cr, uid, [wizard_id])
                    model = answer.get('res_model', None)

                # sync to send the prop instance modifications
                self.pool.get('sync.client.entity').sync(cr, uid)
                self.write(cr, 1, creation_id,
                           {'state': 'reconfigure_done'}, context=context)

            cr.commit()
            if not skip_import_files:
                self.write(cr, 1, creation_id,
                           {'state': 'import_files'}, context=context)
                import_path = os.path.join(tools.config['root_path'], '..', 'UFautoInstall', 'import')
                file_to_import = []
                for file_name in os.listdir(import_path):
                    if file_name.endswith('.imported'):
                        continue
                    if not '.csv' in file_name:
                        raise osv.except_osv(_("Error!"), 'Only CSV file can be imported. \'%s\' is not a CSV extension.' % file_name)
                    if file_name == 'account.analytic.journal.csv':
                        file_to_import.insert(0, file_name)
                    else:
                        file_to_import.append(file_name)
                for file_name in file_to_import:
                    model_to_import = file_name.split('.csv')[0]
                    model_obj = self.pool.get(model_to_import)
                    processed, rejected, headers = model_obj.import_data_from_csv(cr, uid, os.path.join(import_path, file_name), with_commit=False)
                    if rejected:
                        raise osv.except_osv(_("Error!"), "Import file %s\n %s" % (file_name, "\n".join(["Line: %s %s" % (x[0], x[2]) for x in rejected])))
                    cr.commit()
                    os.rename(os.path.join(import_path, file_name), os.path.join(import_path, '%s.imported' %file_name))
                self.write(cr, 1, creation_id,
                           {'state': 'files_imported'}, context=context)

            # internal partner configuration
            self.write(cr, 1, creation_id,
                       {'state': 'partner_configuration'}, context=context)
            partner_obj = self.pool.get('res.partner')
            local_market_id = partner_obj.search(cr, uid, [('ref', '=', 'LOCAL')])
            if len(local_market_id) != 1:
                raise osv.except_osv(_("Error!"), 'There should be one and only one partner with reference \'LOCAL\' (Local Market), found %d.' % len(local_market_id))
            account_obj = self.pool.get('account.account')
            account_receivable = config_dict['partner'].get('external_account_receivable')
            account_receivable_id = account_obj.search(cr, uid, [('code', '=', account_receivable)])[0]
            account_payable = config_dict['partner'].get('external_account_payable')
            account_payable_id = account_obj.search(cr, uid, [('code', '=', account_payable)])[0]
            vals = {
                'property_account_receivable': account_receivable_id,
                'property_account_payable': account_payable_id,
            }
            partner_obj.write(cr, uid, local_market_id, vals)
            instance_partner_id = partner_obj.search(cr, uid, [('name', '=', config_dict['instance'].get('instance_name'))])
            if len(instance_partner_id) != 1:
                raise osv.except_osv(_("Error!"), 'There should be one and only one partner with name \'%s\', found %d.' % (config_dict['instance'].get('instance_name'), len(instance_partner_id)))
            account_receivable = config_dict['partner'].get('internal_account_receivable')
            account_receivable_id = account_obj.search(cr, uid, [('code', '=', account_receivable)])[0]
            account_payable = config_dict['partner'].get('internal_account_payable')
            account_payable_id = account_obj.search(cr, uid, [('code', '=', account_payable)])[0]
            vals = {
                'property_account_receivable': account_receivable_id,
                'property_account_payable': account_payable_id,
            }
            partner_obj.write(cr, uid, instance_partner_id, vals)
            cr.commit()
            self.write(cr, 1, creation_id,
                       {'state': 'partner_configuration_done'}, context=context)

            # company configuration
            instance_id = self.pool.get('msf.instance').search(cr,
                                                               uid, [('code', '=', config_dict['instance']['prop_instance_code'])])
            company_obj = self.pool.get('res.company')
            company_id = company_obj.search(cr, uid, [('instance_id', '=', instance_id)])
            if len(company_id) != 1:
                raise osv.except_osv(_("Error!"), 'There should be one and only one company with proprietary instance \'%s\', found %d.' % (config_dict['instance']['prop_instance_code'], len(instance_partner_id)))

            vals = {}
            if config_dict['company']['scheduler_range_days']:
                vals['schedule_range'] = float(config_dict['company']['scheduler_range_days'])

            account_property_dict = {  # config_file_property_name : unifield property name
                'salaries_default_account': 'salaries_default_account',
                'default_counterpart': 'counterpart_hq_entries_default_account',
                'reserve_profitloss_account': 'property_reserve_and_surplus_account',
                'rebilling_intersection_account': 'import_invoice_default_account',
                'intermission_counterpart': 'intermission_default_counterpart',
                'revaluation_account': 'revaluation_default_account',
                'counterpart_bs_debit_balance': 'ye_pl_cp_for_bs_debit_bal_account',
                'counterpart_bs_crebit_balance': 'ye_pl_cp_for_bs_credit_bal_account',
                'credit_account_pl_positive': 'ye_pl_pos_credit_account',
                'debit_account_pl_positive': 'ye_pl_pos_debit_account',
                'credit_account_pl_negative': 'ye_pl_ne_credit_account',
                'debit_account_pl_negative': 'ye_pl_ne_debit_account',
                'default_cheque_account': ['cheque_debit_account_id', 'cheque_credit_account_id'],
                'default_bank_account': ['bank_debit_account_id', 'bank_credit_account_id'],
                'default_cash_account': ['cash_debit_account_id', 'cash_credit_account_id'],
            }

            for config_file_prop, unifield_prop in list(account_property_dict.items()):
                account = config_dict['company'].get(config_file_prop)
                account_id = account_obj.search(cr, uid, [('code', '=', account)])
                account_id = account_id and account_id[0] or False
                if account_id:
                    if isinstance(unifield_prop, str):
                        unifield_prop = [unifield_prop]
                    for uf_prop in unifield_prop:
                        vals[uf_prop] = account_id

            if config.has_option('company', 'additional_allocation'):
                vals['additional_allocation'] = config.getboolean('company', 'additional_allocation')

            if vals.get('ye_pl_cp_for_bs_debit_bal_account') and vals.get('ye_pl_cp_for_bs_credit_bal_account'):
                vals['has_move_regular_bs_to_0'] = True

            if vals.get('ye_pl_pos_credit_account') and vals.get('ye_pl_ne_debit_account'):
                vals['has_book_pl_results'] = True

            company_obj.write(cr, uid, company_id, vals)

            # configure cost center for FX gain loss
            if config.has_option('accounting', 'cost_center_code_for_fx_gain_loss') and  config_dict['accounting'].get('cost_center_code_for_fx_gain_loss'):
                self.pool.get('ir.config_parameter').set_param(cr, 1, 'INIT_CC_FX_GAIN', config_dict['accounting'].get('cost_center_code_for_fx_gain_loss'))

            cr.commit()
            # send imported data and configuration
            self.pool.get('sync.client.entity').sync(cr, uid)

            if config_dict.get('autosync'):
                auto_sync_cron = self.pool.get('ir.model.data').get_object(cr, uid, 'sync_client', 'ir_cron_automaticsynchronization0')
                if auto_sync_cron:
                    auto_sync_data = {
                        'active': config_dict['autosync'].get('active', True) in TRUE_LIST,
                        'interval_number': config_dict['autosync'].get('interval_nb'),
                        'interval_type': config_dict['autosync'].get('interval_unit'),
                    }
                    if config_dict['autosync'].get('next_exec_date'):
                        auto_sync_data['nextcall'] = config_dict['autosync'].get('next_exec_date')
                    self.pool.get('ir.cron').write(cr, uid, auto_sync_cron.id, auto_sync_data, context=context)

            if config_dict.get('stockmission'):
                cron_id = self.pool.get('ir.model.data').get_object(cr, uid, 'mission_stock', 'ir_cron_stock_mission_update_action')
                if cron_id:
                    scheduler_data = {
                        'active': config_dict['stockmission'].get('active', True) in TRUE_LIST,
                        'interval_number': config_dict['stockmission'].get('interval_nb'),
                        'interval_type': config_dict['stockmission'].get('interval_unit'),
                    }
                    if config_dict['stockmission'].get('next_exec_date'):
                        scheduler_data['nextcall'] = config_dict['stockmission'].get('next_exec_date')
                    self.pool.get('ir.cron').write(cr, uid, cron_id.id, scheduler_data, context=context)

            if config_dict.get('silentupgrade') and config_dict['silentupgrade'].get('hour_from') and config_dict['silentupgrade'].get('hour_to'):
                synchro_serv = pool.get('sync.client.sync_server_connection')
                ids = synchro_serv.search(cr, uid, [])
                if ids:
                    from_mx = datetime.strptime(config_dict['silentupgrade']['hour_from'], '%H:%M')
                    to_mx = datetime.strptime(config_dict['silentupgrade']['hour_to'], '%H:%M')
                    sync_vals = {
                        'automatic_patching_hour_from': from_mx.hour + from_mx.minute/60.,
                        'automatic_patching_hour_to': to_mx.hour + to_mx.minute/60.,
                        'automatic_patching': config_dict['silentupgrade'].get('active', True) in TRUE_LIST
                    }
                    try:
                        cr.commit()
                        synchro_serv.write(cr, uid, ids, sync_vals)
                    except:
                        cr.rollback()
                        logging.getLogger('autoinstall').warn('Unable to set Silent Upgrade, please check the silent upgrade and auto sync times')


            self.write(cr, 1, creation_id,
                       {'state': 'done'}, context=context)
            time.sleep(6)  # before to delete to let the web get the last
            # informations
            # rename auto configuration folder
            config.set('instance', 'sync_pwd', '')
            config.set('instance', 'admin_password', '')
            config_fp = open(config_file_path, 'w')
            config.write(config_fp)
            config_fp.close()
            shutil.move(config_file_path, "%s-%s" % (config_file_path, time.strftime('%Y%m%d-%H%M')))

        except Exception as e:
            cr.rollback()
            logging.getLogger('autoinstall').error('Auto creation error: %s' % tools.misc.get_traceback(e))
            self.write(cr, 1, creation_id,
                       {'error': '%s' % e}, context=context)

        finally:
            if cr:
                cr.commit()
                cr.close()


instance_auto_creation()
