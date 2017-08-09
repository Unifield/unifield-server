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

import time
import pooler
import uuid

from tools.translate import _
from osv import fields, osv, orm

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
            ('wating_for_validation', 'Waiting for validation on SYNC_SERVER side...'),
            ('instance_validated', 'Instance validated on SYNC_SERVER side.'),
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
            nb_state = len(self._columns['state'].selection) - 2  # remove draft and done
            one_step_percentage = 1/float(nb_state)
            progress += one_step_percentage
            vals['progress'] = progress

        # prevent to go more the 100%
        if vals.get('progress', 0) >= 1:
            vals['progress'] = 1
            vals['state'] = 'done'

        return super(instance_auto_creation, self).write(cr, uid, ids, vals,
                context=context)

    def check_sync_server_registration_validation(self, cr, uid, context=None):
        #self.pool.get('sync.client.entity').sync(cr, uid)
        entity_obj = self.pool.get('sync.client.entity')
        entity = entity_obj.get_entity(cr, uid, context=context)
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.entity")

        # call a method decorated with @check_validated to ensure that the
        # entity has been validated by the sync_server
        validated = False
        message = ''
        creation_id = self.search(cr, uid, [('dbname', '=', cr.dbname)], context=context)
        try:
            validated, message = proxy.is_validated(entity.identifier)
        except Exception as e:
            if 'AccessDenied' in e.value:
                message = _('The instance is not connected to the SYNC_SERVER')
            else:
                message = e.value
            self.write(cr, uid, creation_id, {'error': message}, context=context)
            cr.commit()
        else:
            self.write(cr, uid, creation_id,
                       {'error':''},
                       context=context)

        if not validated:
            return False

        # registration validated ! The crontab can be desactivated
        cron_obj = self.pool.get('ir.cron')
        cron_ids = cron_obj.search(cr, uid,
                                   [('name', '=', 'Check if SYNC_SERVER validates the registration')],
                                   context=context)
        if cron_ids:
            cron_obj.write(cr, uid, cron_ids, {'active': False}, context=context)
        self.write(cr, uid, creation_id,
                   {'state': 'instance_validated', 'error':''},
                   context=context)
        cr.commit()
        return True

    def background_install(self, cr, pool, uid, creation_id, lang, sync_login, sync_pwd, sync_host, sync_port, sync_protocol, sync_server, oc, group_name_list, parent_instance, context=None):
        if context is None:
            context = {}

        try:
            creation_state = self.read(cr, uid, creation_id, ['state'], context=context)['state']
            if creation_state != 'draft':
                # errase previous errors
                self.write(cr, uid, creation_id, {'error': ''}, context=context)
            skip_msf_profile = skip_sync_so = skip_update_client = skip_sync_client_web = skip_language = False
            if creation_state == 'language_installed':
                skip_msf_profile = skip_sync_so = skip_update_client = skip_sync_client_web = skip_language = True

            # module installation
            module_obj = pool.get('ir.module.module')
            upgrade_obj = pool.get('base.module.upgrade')
            for module_name in ['msf_profile', 'sync_so', 'update_client', 'sync_client_web']:
                if locals().get(('skip_%s' % module_name), False):
                    continue
                module_id = module_obj.search(cr, 1, [('name', '=', module_name)])
                module_obj.button_install(cr, 1, module_id)
                self.write(cr, 1, creation_id,
                           {'state': '%s_installation' % module_name}, context=context)
                upgrade_obj.upgrade_module(cr, 1, None, None)
                self.write(cr, 1, creation_id,
                           {'state': '%s_installed' % module_name}, context=context)
                cr.commit()

            # install language
            if not skip_language:
                self.write(cr, 1, creation_id,
                           {'state': 'language_installation'}, context=context)
                cr.commit()
                if lang:
                    lang_obj = pool.get('res.lang')
                    lang_id = lang_obj.search(cr, uid, [('code', '=', lang)])
                    if lang_id:
                        lang_obj.write(cr, uid, lang_id, {'translatable': True})
                        mod_ids = module_obj.search(cr, uid, [('state', '=', 'installed')])
                        module_obj.button_update_translations(cr, uid, mod_ids, lang)
                self.write(cr, 1, creation_id,
                           {'state': 'language_installed'}, context=context)
                cr.commit()

            # register instance
            self.write(cr, 1, creation_id,
                       {'state': 'register_instance'}, context=context)
            cr.commit()
            sync_vals = {
                'protocol': sync_protocol,
                'host': sync_host,
                'port': sync_port,
                'database': sync_server,
                'login': sync_login,
                'password': sync_pwd,
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

            data = {
                'name': cr.dbname,
                'identifier': str(uuid.uuid1()),
                'oc': oc,
                'parent': parent_instance,
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
            group_ids = group_obj.search(cr, uid, [('name', 'in', group_name_list)], context=context)
            wizard.write(cr, uid, wizard_id, {'group_ids': [(6, 0, group_ids)]}, context=context)

            # Register instance
            wizard.validate(cr, uid, wizard_id)
            self.write(cr, 1, creation_id,
                       {'state': 'instance_registered'}, context=context)
            cr.commit()

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
                                       [('name', '=', 'Check if SYNC_SERVER validates the registration')],
                                       context=context)
            if cron_ids:
                cron_obj.write(cr, uid, cron_ids, cron_vals, context=context)
            else:
                cron_obj.create(cr, uid, cron_vals, context=context)
            self.write(cr, 1, creation_id,
                       {'state': 'wating_for_validation'}, context=context)
            cr.commit()


            # delete the configuration file
        except Exception as e:
            self.write(cr, 1, creation_id,
                        {'error': '%s' % e}, context=context)

        finally:
            cr.commit()
            cr.close()


instance_auto_creation()
