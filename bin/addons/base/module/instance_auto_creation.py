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
import ConfigParser

import tools
import threading
from tools.translate import _
from osv import fields, osv, orm


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
            ('waiting_for_validation', 'Waiting for validation on SYNC_SERVER side...'),
            ('instance_validated', 'Instance validated on SYNC_SERVER side.'),
            ('backup_configuration', 'Backup configuration...'),
            ('backup_configured', 'Backup configured.'),
            ('start_init_sync', 'Start intial synchronisation, this may take a lot of time...'),
            ('end_init_sync', 'Init sync finished !'),
            ('reconfigure', 'Do reconfigure...'),
            ('reconfigure_done', 'Reconfigure done.'),
            #('import_files', 'Start file imoprt...'),
            #('files_imported', 'Files import done.'),
            ('done', 'Done')], 'State', readonly=True),
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
        if isinstance(ids, (int, long)):
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
        if vals.get('progress', 0) >= 1:
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
            config = ConfigParser.ConfigParser()
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

            # XXX
            skip_language = True

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

                # search the current entity
                entity_id = pool.get('sync.client.entity').search(cr, uid, [])

                # find the parent_id:
                oc = config_dict['instance'].get('oc').lower()
                data = {
                    'name': cr.dbname,
                    'identifier': str(uuid.uuid1()),
                    'oc': oc,
                    'parent': config_dict['instance'].get('parent_instance'),
                }
                if entity_id:
                    entity_data = pool.get('sync.client.entity').read(cr, uid, entity_id[0])
                    pool.get('sync.client.entity').write(cr, uid, entity_id[0], data)
                else:
                    pool.get('sync.client.entity').create(cr, uid, data)
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
            skip_backup = skip_reconfigure = False
            creation_state = self.read(cr, uid, creation_id, ['state'], context=context)['state']
            skip_init_sync = skip_backup_config = skip_reconfigure = skip_import_files = False
            if creation_state == 'end_init_sync':
                skip_init_sync = True
            elif creation_state in ('backup_configured', 'reconfigure'):
                skip_init_sync = skip_backup_config = True
            elif creation_state == 'reconfigure_done':
                skip_init_sync = skip_backup_config = skip_reconfigure = True
            elif creation_state == 'start_init_sync':
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
            config = ConfigParser.ConfigParser()
            config.read(config_file_path)
            config_dict =  {x:dict(config.items(x)) for x in config.sections()}

            if not skip_init_sync:
                entity_obj = self.pool.get('sync.client.entity')
                sync_status = entity_obj.get_status(cr, uid)
                if sync_status == 'Syncing...':
                    # keep going
                    pass
                elif sync_status == 'Connected' or sync_status.startswith('Last Sync: In Progress...'):
                    # start/restart the init sync (very long)
                    self.write(cr, 1, creation_id,
                               {'state': 'start_init_sync'}, context=context)
                    self.pool.get('sync.client.entity').sync(cr, uid)
                    self.write(cr, 1, creation_id,
                               {'state': 'end_init_sync'}, context=context)
                elif sync_status.startswith('Last Sync: Ok'):
                    self.write(cr, 1, creation_id,
                               {'state': 'end_init_sync'}, context=context)
                else:
                    raise 'Impossible to perform the sync. Sync status is \'%s\'.' % sync_status

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
                    'scheduledbackup': config_dict['backup'].get('auto_bck_scheduledbackup') in TRUE_LIST,
                }
                backup_obj.write(cr, uid, backup_id, backup_vals, context=context)

                # update automatic backup cron job
                vals = {
                    'active': True,
                    'interval_number': config_dict['backup'].get('auto_bck_interval_nb'),
                    'interval_type': config_dict['backup'].get('auto_bck_interval_unit'),
                }
                auto_backup = self.pool.get('ir.model.data').get_object(cr, uid, 'sync_client', 'ir_cron_automaticsyncbackup')
                cron_obj = self.pool.get('ir.cron')
                if auto_backup:
                    backup_id = auto_backup.id
                    cron_obj.write(cr, uid, backup_id, vals, context=context)
                self.write(cr, 1, creation_id,
                           {'state': 'backup_configured'}, context=context)

            if not skip_reconfigure:
                self.write(cr, 1, creation_id,
                           {'state': 'reconfigure'}, context=context)


                base_wizards = {
                    'base.setup.config' : {
                        'button' : 'config',
                    },
                    'res.config.view' : {
                        'name' : "auto_init",
                        'view' : 'extended',
                    },
                    'sale.price.setup' : {
                        'sale_price' : 0.10,
                    },
                    'stock.location.configuration.wizard' : {
                        'location_type' : 'internal',
                        'location_usage' : 'stock',
                        'location_name' : 'Test Location',
                        'button' : 'action_stop',
                    },
                    'currency.setup' : {
                        #'functional_id' : config_dict['instance'].get('functional_currency').lower(),
                        'functional_id' : 'eur', #config_dict['instance'].get('functional_currency').lower(),
                    },
                }



                model = 'msf_instance.setup'
                while model != 'ir.ui.menu':
                    # skip account.installer if no parent_name providen (typically: HQ instance)
                    if model == 'msf_instance.setup':
                        instance_id = self.pool.get('msf.instance').search(cr, uid, [('instance', '=', cr.dbname)])
                        if not instance_id:
                            error_message = ('No prop. instance \'%s\' found. Please check it has been created on the HQ and sync, then restart the auto creation process from scratch.') % cr.dbname
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

                self.write(cr, 1, creation_id,
                           {'state': 'reconfigure_done'}, context=context)

            if not skip_import_files:
                pass
                #for file_name in file_list_to_import:
                    #model = ...
                    #module = ...
                    #import

            time.sleep(15)  # before to delete to let the web get the last
                            # informations
            # delete the auto configuration folder
            config_file_path = os.path.join(tools.config['root_path'], '..', 'UFautoInstall')
            import shutil
            shutil.rmtree(config_file_path)

        except Exception as e:
            self.write(cr, 1, creation_id,
                        {'error': '%s' % e}, context=context)

        finally:
            if cr:
                cr.commit()
                cr.close()


instance_auto_creation()
