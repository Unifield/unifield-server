# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 OpenERP s.a. (<http://odoo.com>).
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
from osv import osv
from osv import fields
import tools
from datetime import datetime
from tools.translate import _
from updater import get_server_version
import release
import time
import logging

class BackupConfig(osv.osv):
    """ Backup configurations """
    _name = "backup.config"
    _description = "Backup configuration"
    _pg_psw_env_var_is_set = False

    _logger = logging.getLogger('sync.client')

    _columns = {
        'name' : fields.char('Path to backup to', size=254),
        'beforemanualsync':fields.boolean('Backup before manual sync'),
        'beforeautomaticsync':fields.boolean('Backup before automatic sync'),
        'aftermanualsync':fields.boolean('Backup after manual sync'),
        'afterautomaticsync':fields.boolean('Backup after automatic sync'),
        'scheduledbackup':fields.boolean('Scheduled backup'),
        'beforepatching': fields.boolean('Before patching'),
    }

    _defaults = {
        'name' : 'c:\\backup\\',
        'beforemanualsync' : True,
        'beforeautomaticsync' : True,
        'aftermanualsync' : True,
        'afterautomaticsync' : True,
        'beforepatching': False,
    }

    def get_server_version(self, cr, uid, context=None):
        revisions = self.pool.get('sync_client.version')
        if not revisions:
            return release.version or 'UNKNOWN_VERSION'
        current_revision = revisions._get_last_revision(cr, uid, context=context)
        # get the version name from db
        if current_revision and current_revision.name:
            return current_revision.name
        # if nothing found, take it from the unifield-version.txt file
        elif current_revision and current_revision.sum:
            # get the version from unifield-version.txt file
            version_list = get_server_version()
            for version in version_list:
                if current_revision.sum == version['md5sum'] and version['name']:
                    return version['name']
        # in case nothing found, return UNKNOWN_VERSION instead of a wrong name
        return 'UNKNOWN_VERSION'

    def _set_pg_psw_env_var(self):
        if tools.config['db_password'] and not os.environ.get('PGPASSWORD', ''):
            os.environ['PGPASSWORD'] = tools.config['db_password']
            self._pg_psw_env_var_is_set = True

    def _unset_pg_psw_env_var(self):
        if self._pg_psw_env_var_is_set:
            os.environ['PGPASSWORD'] = ''

    def exp_dump_for_state(self, cr, uid, state, context=None, force=False):
        context = context or {}
        logger = context.get('logger')
        if not force:
            bkp_ids = self.search(cr, uid, [(state, '=', True)], context=context)
        else:
            bkp_ids = self.search(cr, uid, [], context=context)

        suffix = ''
        if state == 'beforepatching':
            suffix = '-BP'
        elif state.startswith('before'):
            suffix = '-B'
        elif state.startswith('after'):
            suffix = '-A'

        if bkp_ids:
            if logger:
                logger.append("Database %s backup started.." % state)
                logger.write()
            self.exp_dump(cr, uid, bkp_ids, suffix, context)
            if logger:
                logger.append("Database %s backup successful" % state)
                logger.write()

    def button_exp_dump(self, cr, uid, ids, context=None):
        return self.exp_dump(cr, uid, ids, context=context)

    def exp_dump(self, cr, uid, ids, suffix='', context=None):
        if context is None:
            context = {}
        bkp = self.browse(cr, uid, ids, context)
        if bkp and bkp[0] and bkp[0].name: #US-786 If no path define -> return
            bck = bkp[0]
            try:
                # US-386: Check if file/path exists and raise exception, no need to prepare the backup, thus no pg_dump is executed
                version = self.get_server_version(cr, uid, context=context)
                outfile = os.path.join(bck.name, "%s-%s%s-%s.dump" %
                                       (cr.dbname, datetime.now().strftime("%Y%m%d-%H%M%S"),
                                        suffix, version))
                version_instance_module = self.pool.get('sync.version.instance.monitor')
                postgres_disk_space = version_instance_module._get_default_postgresql_disk_space(cr,
                                                                                                 uid)
                unifield_disk_space = version_instance_module._get_default_unifield_disk_space(cr,
                                                                                               uid)
                vals = {'version': version,
                        'backup_path': outfile,
                        'postgresql_disk_space': postgres_disk_space,
                        'unifield_disk_space': unifield_disk_space,
                        }

                version_instance_module.create(cr, uid, vals, context=context)

                bkpfile = open(outfile,"wb")
                bkpfile.close()
            except Exception, e:
                # If there is exception with the opening of the file
                if isinstance(e, IOError):
                    error = "Backup Error: %s %s. Please provide the correct path or deactivate the backup feature." %(e.strerror, e.filename)
                else:
                    error = "Backup Error: %s. Please provide the correct path or deactivate the backup feature." % e
                self._logger.exception('Cannot perform the backup %s.' % error)
                raise osv.except_osv(_('Error! Cannot perform the backup.'), error)
            finally:
                cr.commit()

            res = tools.pg_dump(cr.dbname, outfile)

            # check the backup file
            error = None
            if res:
                error = "Couldn't dump database : pg_dump return an error for path %s." % outfile
            elif not os.path.isfile(outfile):
                error = 'The backup file could not be found on the disk with path %s' % outfile
            elif not os.stat(outfile).st_size > 0:
                error = 'The backup file should be bigger that 0 (actually size=%s bytes)' % os.stat(outfile).st_size
            if error:
                self._logger.exception('Cannot perform the backup %s.' % error)
                raise osv.except_osv(_('Error! Cannot perform the backup.'), error)
            return "Backup done"
        raise osv.except_osv(_('Error! Cannot perform the backup'), "No backup path defined")

    def scheduled_backups(self, cr, uid, context=None):
        bkp_ids = self.search(cr, uid, [('scheduledbackup', '=', True)], context=context)
        if bkp_ids:
            self.exp_dump(cr, uid, bkp_ids, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        toret = super(BackupConfig, self).write(cr, uid, ids, vals, context=context)
        backups = self.browse(cr, uid, ids, context=context)
        #if context:
        #    for backup in backups:
        #        if not os.path.isdir(backup.name):
        #            raise osv.warning(_('Error'), _("The selected path doesn't exist!"))
        if backups and backups[0]:
            #Find the scheduled action
            ircron_model = self.pool.get('ir.cron')
            cron_ids = ircron_model.search(cr, uid, ([('name', '=', 'Automatic backup'), ('model', '=', 'backup.config'), '|', ('active', '=', True), ('active', '=', False)]), context=context)
            crons = ircron_model.browse(cr, uid, cron_ids, context=context)
            for cron in crons:
                if cron.active != backups[0].scheduledbackup:
                    ircron_model.write(cr, uid, [cron.id,], {'active': backups[0].scheduledbackup}, context=context)
        return toret

BackupConfig()

class ir_cron(osv.osv):
    _name = 'ir.cron'
    _inherit = 'ir.cron'

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        toret = super(ir_cron, self).write(cr, uid, ids, vals, context=context)
        crons = self.browse(cr, uid, ids, context=context)
        if crons and crons[0] and crons[0].model=='backup.config':
            #Find the scheduled action
            bkp_model = self.pool.get('backup.config')
            bkp_ids = bkp_model.search(cr, uid, (['|', ('scheduledbackup', '=', True), ('scheduledbackup', '=', False)]), context=context)
            bkps = bkp_model.browse(cr, uid, bkp_ids, context=context)
            for bkp in bkps:
                if crons[0].active != bkp.scheduledbackup:
                    bkp_model.write(cr, uid, [bkp.id,], {'scheduledbackup': crons[0].active}, context=context)
        return toret

ir_cron()

class backup_download(osv.osv):
    _name = 'backup.download'
    _order = "mtime desc, id"
    _description = "Backup Files"

    _columns = {
        'name': fields.char("File name", size=128, readonly=True),
        'path': fields.text("File path", readonly=True),
        'mtime': fields.datetime("Modification Time", readonly=True),
    }

    def _get_bck_path(self, cr, uid, context=None):
        res = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'sync_client', 'backup_config_default')
        path = self.pool.get('backup.config').read(cr, uid, res[1], ['name'], context=context)
        if path['name'] and os.path.isdir(path['name']):
            return path['name']
        return False

    def populate(self, cr, uid, context=None):
        if context is None:
            context = {}

        all_bck_ids = self.search(cr, uid, [], context=context)
        all_bck = {}
        for bck in self.read(cr, uid, all_bck_ids, ['path'], context=context):
            all_bck[bck['path']] = bck['id']
        path = self._get_bck_path(cr, uid, context)
        if path:
            for f in os.listdir(path):
                if f.endswith('.dump'):
                    full_name = os.path.join(path, f)
                    if os.path.isfile(full_name):
                        stat = os.stat(full_name)
                        #US-653: Only list the files with size > 0 to avoid web side error
                        if stat.st_size:
                            data = {'mtime': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))}
                            if full_name in all_bck:
                                self.write(cr, uid, [all_bck[full_name]], data, context=context)
                                del all_bck[full_name]
                            else:
                                data.update({'name': f, 'path': full_name})
                                self.create(cr, uid, data, context=context)
        if all_bck:
            self.unlink(cr, uid, all_bck.values(), context=context)
        return True

    def open_wiz(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        self.populate(cr, 1, context=context)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'backup.download',
            'view_type': 'form',
            'view_mode': 'tree,form',
        }

    def get_content(self, cr, uid, ids, context=None):
        name = self.read(cr, uid, ids[0], ['name'], context=context)['name']
        name = name.replace('.dump', '')
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'backup.download',
            'datas': {'ids': [ids[0]], 'target_filename': name}
        }

backup_download()
