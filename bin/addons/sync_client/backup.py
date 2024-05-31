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
import pooler
import threading
from functools import reduce

class BackupConfig(osv.osv):
    """ Backup configurations """
    _name = "backup.config"
    _description = "Backup configuration"
    _pg_psw_env_var_is_set = False
    _error = ''
    _logger = logging.getLogger('sync.client')
    _trace = True

    def _get_bck_info(self, cr, uid, ids, field_name, args, context=None):
        ret = {}
        for _id in ids:
            ret[_id] = {'cloud_date': False, 'cloud_backup': False, 'cloud_url': False, 'cloud_error': False, 'backup_date': False, 'backup_path': False, 'backup_size': False}

        local_instance = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id
        if local_instance:
            cl = self.pool.get('msf.instance.cloud').read(cr, uid, local_instance.id, ['cloud_url'], context=context)
            for _id in ids:
                ret[_id]['cloud_url'] = cl['cloud_url']

            verion_obj = self.pool.get('sync.version.instance.monitor')
            v_id = verion_obj.search(cr, uid, [('instance_id', '=', local_instance.id)], context=context)
            if v_id:
                v_info = verion_obj.read(cr, uid, v_id[0], ['backup_path', 'backup_date', 'cloud_date', 'cloud_backup', 'cloud_error', 'backup_size', 'cloud_size'], context=context)
                for _id in ids:
                    del(v_info['id'])
                    ret[_id].update(v_info)
        return ret

    _columns = {
        'name' : fields.char('Path to backup to', size=254),
        'beforemanualsync':fields.boolean('Backup before manual sync'),
        'beforeautomaticsync':fields.boolean('Backup before automatic sync'),
        'aftermanualsync':fields.boolean('Backup after manual sync'),
        'afterautomaticsync':fields.boolean('Backup after automatic sync'),
        'scheduledbackup':fields.boolean('Scheduled backup'),
        'beforepatching': fields.boolean('Before patching', readonly=1),
        'cloud_date': fields.function(_get_bck_info, type='datetime', string='Last Cloud Date', method=True, multi='cloud'),
        'cloud_backup': fields.function(_get_bck_info, type='char', string='Last Cloud', method=True, multi='cloud'),
        'cloud_url': fields.function(_get_bck_info, type='char', string='Cloud URL', method=True, multi='cloud'),
        'cloud_size': fields.function(_get_bck_info, type='float', string='Cloud Size Zipped', method=True, multi='cloud'),
        'cloud_error': fields.function(_get_bck_info, type='text', string='Cloud Error', method=True, multi='cloud'),
        'backup_date': fields.function(_get_bck_info, type='datetime', string='Last Backup Date', method=True, multi='cloud'),
        'backup_path': fields.function(_get_bck_info, type='char', string='Last Backup', method=True, multi='cloud'),
        'backup_size': fields.function(_get_bck_info, type='float', string='Backup Size', method=True, multi='cloud'),

        'wal_directory': fields.char('Local Path to WAL Archive Dir', help='Must be set in postgresql.conf', size=256),
        'remote_user': fields.char('Remote User', help='Keep empty to use default value', size=256),
        'remote_host': fields.char('Remote Host', help='Keep empty to use default value', size=256),
        'ssh_config_dir': fields.char('Local Path to ssh config dir', size=512),

        'basebackup_date': fields.datetime('Date of base backup', readonly=1),
        'basebackup_error': fields.text('Base backup error', readonly=1),
        'rsync_date': fields.datetime('Date of last rsync', readonly=1),
        'rsync_error': fields.text('Rsync error', readonly=1),
        'help_wal': fields.function(tools.misc.get_fake, type='boolean', string='Display steps to set Continuous Backup', method=True),
        'backup_type': fields.selection([('cont_back', 'Continuous Backup'), ('sharepoint', 'Direct push to Sharepoint')], 'Backup Type', required=True),
    }

    _defaults = {
        'backup_type': 'sharepoint',
        'name' : 'c:\\backup\\',
        'beforemanualsync' : True,
        'beforeautomaticsync' : True,
        'aftermanualsync' : True,
        'afterautomaticsync' : True,
        'beforepatching': True,
        'ssh_config_dir': 'C:\\Program Files (x86)\\msf\\SSH_CONFIG',
    }

    def _activate_push_cron(self, cr, uid, ids, context=None):
        ir_cron = self.pool.get('ir.cron')

        for bck in self.read(cr, uid, ids, ['backup_type'], context=context):
            od_active =  bck['backup_type'] == 'sharepoint'

        od_task = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_instance', 'ir_cron_remote_backup')
        if not ir_cron.search(cr, uid, [('id', '=', od_task[1]), ('active', '=', od_active)]):
            ir_cron.write(cr, uid, od_task[1], {'active': od_active})

        wal_task = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'sync_client', 'ir_cron_wal')
        if not ir_cron.search(cr, uid, [('id', '=', wal_task[1]), ('active', '=', not od_active)]):
            ir_cron.write(cr, uid, wal_task[1], {'active': not od_active})

        return True

    _constraints = [
        (_activate_push_cron, '', [])
    ]

    def button_basebackup(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'basebackup_error': _('In progress')}, context=context)
        new_thread = threading.Thread(
            target=self.generate_basebackup_bg,
            args=(cr, uid, ids, context)
        )
        new_thread.start()
        return True

    def generate_basebackup_bg(self, old_cr, uid, ids, context=None, new_cr=True):
        try:
            if context is None:
                context = {}
            ctx_no_write = context.copy()
            ctx_no_write['no_write_access'] = True

            is_pg14 = tools.sql.is_pg14(old_cr)
            if new_cr:
                cr = pooler.get_db(old_cr.dbname).cursor()
            else:
                cr = old_cr
            bk = self.browse(cr, uid, ids[0], context)
            if bk.backup_type != 'cont_back':
                raise Exception(_('Continuous Backup is disabled'))
            if not bk.wal_directory:
                raise Exception(_('"Path to WAL Dir" is empty'))
            if not os.path.isdir(bk.wal_directory):
                raise Exception(_('%s not found') % (bk.wal_directory,))


            tools.misc.pg_basebackup(cr.dbname, bk.wal_directory, is_pg14)
            self.write(cr, uid, [bk.id], {'basebackup_date': time.strftime('%Y-%m-%d %H:%M:%S'), 'basebackup_error': False}, context=ctx_no_write)
            return True
        except Exception as e:
            cr.rollback()
            import traceback, sys
            tb_s = reduce(lambda x, y: x+y, traceback.format_exception(*sys.exc_info()))
            self.write(cr, uid, [ids[0]], {'basebackup_error': '%s\n\n%s' % (e, tools.ustr(tb_s))}, context=ctx_no_write)
            cr.commit()
            raise e

        finally:
            if new_cr:
                cr.commit()
                cr.close(True)

    def sent_continuous_backup_bg(self, cr, uid, context=None):
        new_thread = threading.Thread(
            target=self.sent_continuous_backup,
            args=(cr, uid, context)
        )
        new_thread.start()
        return True

    def sent_continuous_backup(self, old_cr, uid, context=None):
        try:
            if context is None:
                context = {}
            cr = pooler.get_db(old_cr.dbname).cursor()
            ids = self.search(cr, uid, [], context=context)
            bk = self.read(cr, uid, ids[0], ['backup_type', 'basebackup_date'], context=context)
            if bk['backup_type'] != 'cont_back':
                self._logger.info(_('Continuous backup disabled'))
                return True
            if not bk['basebackup_date']:
                if context.get('sync_type'):
                    self._logger.info('Base Backup disabled after sync')
                    return True
                self.generate_basebackup_bg(cr, uid, ids, context=context, new_cr=False)
            self.sent_to_remote_bg(cr, uid, ids, context=context, new_cr=False)
            return True

        except Exception:
            cr.rollback()
            raise
        finally:
            cr.commit()
            cr.close(True)

    def button_rsync(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'rsync_error': _('In progress')}, context=context)
        new_thread = threading.Thread(
            target=self.sent_to_remote_bg,
            args=(cr, uid, ids, context)
        )
        new_thread.start()
        return True

    def sent_to_remote_bg(self, old_cr, uid, ids, context=None, new_cr=True):
        try:
            if context is None:
                context = {}
            ctx_no_write = context.copy()
            ctx_no_write['no_write_access'] = True
            if new_cr:
                cr = pooler.get_db(old_cr.dbname).cursor()
            else:
                cr = old_cr

            if not tools.config.get('send_to_onedrive') and not tools.misc.use_prod_sync(cr, uid, self.pool):
                raise Exception(_('Only production instances are allowed !'))

            dbname = cr.dbname
            bk = self.browse(cr, uid, ids[0], context)
            if bk.backup_type != 'cont_back':
                raise Exception('Continuous Backup is disabled')
            if not bk.wal_directory:
                raise Exception('"Path to WAL Dir" is empty')
            tools.misc.force_wal_generation(cr, bk.wal_directory)
            tools.misc.sent_to_remote(bk.wal_directory, config_dir=bk.ssh_config_dir, remote_user=bk.remote_user, remote_host=bk.remote_host, remote_dir=dbname)
            self.write(cr, uid, [bk.id], {'rsync_date': time.strftime('%Y-%m-%d %H:%M:%S'), 'rsync_error': False}, context=ctx_no_write)
            return True
        except Exception as e:
            cr.rollback()
            import traceback, sys
            tb_s = reduce(lambda x, y: x+y, traceback.format_exception(*sys.exc_info()))
            self.write(cr, uid, [ids[0]], {'rsync_error': '%s\n\n%s' % (e, tools.ustr(tb_s))}, context=ctx_no_write)
            cr.commit()
            raise e
        finally:
            if new_cr:
                cr.commit()
                cr.close(True)


    def _send_to_cloud_bg(self, cr, uid, wiz_id, context=None):
        new_cr = pooler.get_db(cr.dbname).cursor()
        try:
            self.pool.get('msf.instance.cloud').send_backup(new_cr, uid, progress=wiz_id, context=context)
        except Exception as e:
            self._error = e
        finally:
            new_cr.commit()
            new_cr.close(True)
        return True

    def send_to_cloud(self, cr, uid, ids, context=None):
        self._error = ''
        wiz_id = self.pool.get('msf.instance.cloud.progress').create(cr, uid, {}, context=context)
        new_thread = threading.Thread(
            target=self._send_to_cloud_bg,
            args=(cr, uid, wiz_id, context)
        )
        new_thread.start()
        new_thread.join(3.0)
        if new_thread.is_alive():
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'sync_client', 'upload_backup_form')[1]
            return {
                'name':_("Upload in progress"),
                'view_mode': 'form',
                'view_id': [view_id],
                'view_type': 'form',
                'res_model': 'msf.instance.cloud.progress',
                'res_id': wiz_id,
                'type': 'ir.actions.act_window',
                'target': 'new',
                'context': context,
            }

            #raise osv.except_osv(_('OK'), _('Process to send backup is in progress ... please check Version Instances Monitor'))
        if self._error:
            raise self._error
        return True


    def test_cloud(self, cr, uid, ids, context=None):
        local_instance = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id
        return self.pool.get('msf.instance.cloud').test_connection(cr, uid, [local_instance.id], context)

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

        if state.startswith('after'):
            self.sent_continuous_backup_bg(cr, uid, context)
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
        version_instance_module = self.pool.get('sync.version.instance.monitor')
        bkp = self.browse(cr, uid, ids, context)
        if bkp and bkp[0] and bkp[0].name: #US-786 If no path define -> return
            bck = bkp[0]
            try:
                # US-386: Check if file/path exists and raise exception, no need to prepare the backup, thus no pg_dump is executed
                version = self.get_server_version(cr, uid, context=context)
                outfile = os.path.join(bck.name, "%s-%s%s-%s.dump" %
                                       (cr.dbname, datetime.now().strftime("%Y%m%d-%H%M%S"),
                                        suffix, version))
                bkpfile = open(outfile,"wb")
                bkpfile.close()
            except Exception as e:
                # If there is exception with the opening of the file
                if isinstance(e, IOError):
                    error = "Backup Error: %s %s. Please provide the correct path or deactivate the backup feature." %(tools.ustr(e.strerror), tools.ustr(e.filename))
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
                error = "Couldn't dump database : pg_dump returns an error for path %s." % outfile
            elif not os.path.isfile(outfile):
                error = 'The backup file could not be found on the disk with path %s' % outfile
            elif not os.stat(outfile).st_size > 0:
                error = 'The backup file should be bigger that 0 (actually size=%s bytes)' % os.stat(outfile).st_size
            if error:
                self._logger.exception('Cannot perform the backup %s.' % error)
                # commit to not lock the sql transaction
                cr.commit()
                raise osv.except_osv(_('Error! Cannot perform the backup.'), error)
            else:
                version_instance_module.create(cr, uid, {'backup_path': outfile, 'backup_size': os.path.getsize(outfile), 'backup_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, context=context)
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
        if isinstance(ids, int):
            ids = [ids]
        toret = super(ir_cron, self).write(cr, uid, ids, vals, context=context)
        crons = self.browse(cr, uid, ids, context=context)
        if crons and crons[0] and crons[0].model=='backup.config' and crons[0].function == 'scheduled_backups':
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
        'failed': fields.boolean('Failed'),
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
                if f.endswith('.dump') or f.endswith('.KO'):
                    full_name = os.path.join(path, f)
                    if os.path.isfile(full_name):
                        failed = f.endswith('.KO')
                        stat = os.stat(full_name)
                        #US-653: Only list the files with size > 0 to avoid web side error
                        if stat.st_size or failed:
                            data = {'mtime': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)), 'failed': failed}
                            if full_name in all_bck:
                                self.write(cr, uid, [all_bck[full_name]], data, context=context)
                                del all_bck[full_name]
                            else:
                                data.update({'name': f, 'path': full_name})
                                self.create(cr, uid, data, context=context)
        if all_bck:
            self.unlink(cr, uid, list(all_bck.values()), context=context)
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
        f_data = self.read(cr, uid, ids[0], ['name', 'failed'], context=context)
        if f_data['failed']:
            raise osv.except_osv(_('Warning'), _('This is a failed backup'))

        name = f_data['name'].replace('.dump', '')
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'backup.download',
            'datas': {'ids': [ids[0]], 'target_filename': name}
        }

    _default = {
        'failed': False,
    }
backup_download()

class msf_instance_cloud_progress(osv.osv_memory):
    _name = 'msf.instance.cloud.progress'
    _description = 'Upload backup'

    _columns = {
        'name': fields.float('Progress', readonly='1'),
        'state': fields.char('State', size=64, readonly='1'),
        'start': fields.datetime('Start Time', readonly='1'),
        'message': fields.text('Message', readonly='1'),
    }

    _defaults = {
        'state': 'In Progress',
        'name': 0,
        'start': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'message': '',
    }
msf_instance_cloud_progress()

