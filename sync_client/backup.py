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
import release
import re

def get_server_version():
    version = release.version or ""
    ver_match = re.match('(.*)-\d{8}-\d{6}$', version)
    if ver_match:
        version = ver_match.group(1)
    return version

class BackupConfig(osv.osv):
    """ Backup configurations """
    _name = "backup.config"
    _description = "Backup configuration"
    _pg_psw_env_var_is_set = False

    _columns = {
        'name' : fields.char('Path to backup to', size=254),
        'beforemanualsync':fields.boolean('Backup before manual sync'),
        'beforeautomaticsync':fields.boolean('Backup before automatic sync'),
        'aftermanualsync':fields.boolean('Backup after manual sync'),
        'afterautomaticsync':fields.boolean('Backup after automatic sync'),
        'scheduledbackup':fields.boolean('Scheduled backup'),
    }

    _defaults = {
        'name' : 'c:\\backup\\',
        'beforemanualsync' : True,
        'beforeautomaticsync' : True,
        'aftermanualsync' : True,
        'afterautomaticsync' : True,
    }

    def _set_pg_psw_env_var(self):
        if os.name == 'nt' and not os.environ.get('PGPASSWORD', ''):
            os.environ['PGPASSWORD'] = tools.config['db_password']
            self._pg_psw_env_var_is_set = True

    def _unset_pg_psw_env_var(self):
        if os.name == 'nt' and self._pg_psw_env_var_is_set:
            os.environ['PGPASSWORD'] = ''

    def exp_dump_for_state(self, cr, uid, state, context=None):
        context = context or {}
        logger = context.get('logger')
        bkp_ids = self.search(cr, uid, [(state, '=', True)], context=context)
        if bkp_ids:
            if logger:
                logger.append("Database %s backup started.." % state)
                logger.write()
            self.exp_dump(cr, uid, bkp_ids, context)
            if logger:
                logger.append("Database %s backup successful" % state)
                logger.write()

    def exp_dump(self, cr, uid, ids, context=None):
        bkp = self.browse(cr, uid, ids, context)
        if bkp and bkp[0]:
            bck = bkp[0]
            self._set_pg_psw_env_var()

            cmd = ['pg_dump', '--format=c', '--no-owner']
            if tools.config['db_user']:
                cmd.append('--username=' + tools.config['db_user'])
            if tools.config['db_host']:
                cmd.append('--host=' + tools.config['db_host'])
            if tools.config['db_port']:
                cmd.append('--port=' + str(tools.config['db_port']))
            cmd.append(cr.dbname)

            stdin, stdout = tools.exec_pg_command_pipe(*tuple(cmd))
            stdin.close()
            data = stdout.read()
            res = stdout.close()
            if res:
                raise Exception, "Couldn't dump database"
            self._unset_pg_psw_env_var()
            outfile = os.path.join(bck.name, "%s-%s-%s.dump" % (cr.dbname, datetime.now().strftime("%Y%m%d-%H%M%S"), get_server_version()))
            bkpfile = open(outfile,"wb")
            bkpfile.write(data)
            bkpfile.close()
            return "Backup done"
        raise Exception, "No backup defined"

    def scheduled_backups(self, cr, uid, context=None):
        bkp_ids = self.search(cr, uid, [('scheduledbackup', '=', True)], context=context)
        if bkp_ids:
            self.exp_dump(cr, uid, bkp_ids, context=context)

    def write(self, cr, uid, ids, vals, context=None):
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
