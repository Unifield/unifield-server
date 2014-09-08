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
            if os.name == "nt":
                outfile = "%s\\%s-%s.dump" % (bck.name.rstrip('\\'), cr.dbname, datetime.now().strftime("%Y%m%d-%H%M%S"))
            else:
                outfile = "%s/%s-%s.dump" % (bck.name.rstrip('/'), cr.dbname, datetime.now().strftime("%Y%m%d-%H%M%S"))
            bkpfile = open(outfile,"wb")
            bkpfile.write(data)
            bkpfile.close()
            return "Backup done"
        raise Exception, "No backup defined"

    def scheduled_backups(self, cr, uid, context=None):
        bkp_ids = self.search(cr, uid, [('scheduledbackup', '=', True)], context=context)
        if bkp_ids:
            self.exp_dump(cr, uid, bkp_ids, context=context)

BackupConfig()
