##############################################################################
# -*- coding: utf-8 -*-
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting
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
import time
import tools
from datetime import datetime
from dateutil.relativedelta import relativedelta

from tools.translate import _
from tools.sql import drop_view_if_exists


class delete_old_supplier_catalogue(osv.osv):
    _name = 'delete.old.supplier.catalogue'
    _description = 'Delete old ESC catalogues'

    _columns = {
        'name': fields.char('Name', size=128),
        'start_time': fields.datetime(string='Force Date and time of next execution'),
        'interval': fields.integer(string='Interval number', required=True),
        'interval_unit': fields.selection(selection=[('weeks', 'Weeks'), ('months', 'Months')], string='Interval Unit', required=True),
        'active': fields.boolean(string='Active', readonly=True),
        'cron_id': fields.many2one('ir.cron', string='Associated cron job', readonly=True),
        'next_scheduled_task': fields.related('cron_id', 'nextcall', type='datetime', readonly=1, string="Next Execution Date"),
        'partner_id': fields.many2one('res.partner', 'Specific Partner', domain=[('supplier', '=', True), ('partner_type', '=', 'esc')]),
        'message': fields.text(string='Last Execution Message', readonly=True),
    }

    _defaults = {
        'active': False,
    }

    def create(self, cr, uid, vals, context=None):
        '''
        Create the delete_old_supplier_catalogue and the ir_cron associated with it
        '''
        if context is None:
            context = {}

        cron_obj = self.pool.get('ir.cron')

        new_id = super(delete_old_supplier_catalogue, self).create(cr, uid, vals, context=context)

        # Generate new ir.cron
        cron_vals = {
            'name': vals.get('name') or _('Delete ESC catalogues older than 6 months'),
            'user_id': 1,
            'active': False,
            'interval_number': vals.get('interval') or 6,
            'interval_type': vals.get('interval_unit') or 'months',
            'numbercall': 0,
            'nextcall': vals.get('start_time') or time.strftime('%Y-%m-%d %H:%M:%S'),
            'model': self._name,
            'function': 'run_catalogue_mass_deletion',
            'args': '(%s,)' % new_id,
        }
        cron_id = cron_obj.create(cr, uid, cron_vals, context=context)
        to_write = {'cron_id': cron_id}
        self.write(cr, uid, [new_id], to_write, context=context)

        return new_id

    def write(self, cr, uid, ids, vals, context=None):
        """
        Write on the delete_old_supplier_catalogue and the ir_cron associated with it
        """
        if not ids:
            return True

        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        cron_obj = self.pool.get('ir.cron')
        if 'interval' in vals and vals['interval'] <= 0:
            raise osv.except_osv(_('Error'), _('Interval number can not be negative or zero !'))

        res = super(delete_old_supplier_catalogue, self).write(cr, uid, ids, vals, context=context)

        for cat_del in self.browse(cr, uid, ids, context=context):
            cron_vals = {
                'active': cat_del.active,
                'numbercall': cat_del.interval and -1 or 0,
                'interval_number': cat_del.interval,
                'interval_type': cat_del.interval_unit,
                'nextcall': cat_del.start_time or time.strftime('%Y-%m-%d %H:%M:%S'),
            }
            if cat_del.cron_id:
                if not cat_del.start_time and 'nextcall' in cron_vals:
                    del(cron_vals['nextcall'])
                cron_obj.write(cr, uid, [cat_del.cron_id.id], cron_vals, context=context)
            elif not vals.get('cron_id', False):
                cron_vals.update({
                    'name': cat_del.name or _('Delete ESC catalogues older than 6 months'),
                    'user_id': 1,
                    'model': self._name,
                    'function': 'run_catalogue_mass_deletion',
                    'args': '(%s,)' % cat_del.id
                })
                cron_id = cron_obj.create(cr, uid, cron_vals, context=context)
                self.write(cr, uid, [cat_del.id], {'cron_id': cron_id}, context=context)

        if cat_del.active and cat_del.start_time:
            super(delete_old_supplier_catalogue, self).write(cr, uid, ids, {'start_time': False}, context=context)

        return res

    def unlink(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        raise osv.except_osv(_('Error'), _('This task can not be deleted'))

    def manual_run_catalogue_mass_deletion(self, cr, uid, ids, context=None, params=None):
        if context is None:
            context = {}
        if params is None:
            params = {}
        if isinstance(ids, int):
            ids = [ids]

        return self.run_catalogue_mass_deletion(cr, uid, ids, context=context)

    def run_catalogue_mass_deletion(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        cat_obj = self.pool.get('supplier.catalogue')
        for task in self.read(cr, uid, ids, ['partner_id'], context=context):
            msg = ''
            try:
                cat_domain = [('active', 'in', ['t', 'f']), ('partner_id.partner_type', '=', 'esc'), ('from_sync', '=', False),
                              ('period_to', '!=', False), ('period_to', '<=', datetime.now() - relativedelta(months=6))]
                if task['partner_id']:
                    cat_domain.append(('partner_id', '=', task['partner_id'][0]))
                old_catalogue_ids = cat_obj.search(cr, uid, cat_domain, context=context)
                if old_catalogue_ids:
                    cat_data = cat_obj.read(cr, uid, old_catalogue_ids, ['name'], context=context)
                    cat_names = ', '.join([cat['name'] for cat in cat_data])
                    cat_obj.unlink(cr, uid, old_catalogue_ids, context=context)
                    if len(old_catalogue_ids) == 1:
                        msg = _('%s: 1 catalogue was deleted: %s') % (datetime.now().strftime('%d/%m/%Y %H:%M:%S'), cat_names)
                    else:
                        msg = _('%s: %s catalogues were deleted: %s') % (datetime.now().strftime('%d/%m/%Y %H:%M:%S'), len(old_catalogue_ids), cat_names)
                else:
                    msg = _('%s: No catalogues were deleted') % (datetime.now().strftime('%d/%m/%Y %H:%M:%S'),)
            except Exception as e:
                cr.rollback()
                msg = tools.misc.get_traceback(e)
            finally:
                self.write(cr, uid, task['id'], {'message': msg}, context=context)

        return True

    def active_auto_catalogue_deletion(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        return self.write(cr, uid, ids, {'active': True}, context=context)

    def deactive_auto_catalogue_deletion(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        return self.write(cr, uid, ids, {'active': False}, context=context)


delete_old_supplier_catalogue()


class res_log_catalogue_deletion(osv.osv):
    _name ='res.log.catalogue.deletion'
    _order = 'create_date desc'
    _auto = False
    _columns = {
        'name': fields.char('Message', size=250, help='The logging message.', readonly=True, select=1),
        'user_id': fields.many2one('res.users', 'User', readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True, select=1),
    }

    def init(self, cr):
        drop_view_if_exists(cr, 'res_log_catalogue_deletion')
        cr.execute("""
            CREATE OR REPLACE VIEW res_log_catalogue_deletion AS (
                SELECT
                    l.id as id,
                    l.name as name, 
                    l.user_id as user_id, 
                    l.create_date as create_date
                FROM
                    res_log l
                WHERE
                    l.name LIKE '%Catalogue Deletion:%'
            )
        """)


res_log_catalogue_deletion()
