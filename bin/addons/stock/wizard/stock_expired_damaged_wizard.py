# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF
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
import time


class stock_expired_damaged_wizard(osv.osv_memory):
    _name = 'stock.expired.damaged.wizard'
    _rec_name = 'report_date'

    _columns = {
        'report_date': fields.datetime(string='Date of the demand', readonly=True),
        'company_id': fields.many2one('res.company', string='Company', readonly=True),
        'moves_ids': fields.text(string='Moves', readonly=True),
        'start_date': fields.date(string='Start Date'),
        'end_date': fields.date(string='End Date'),
        'location_id': fields.many2one('stock.location', 'Specific Source Location', select=True),
        'location_dest_id': fields.many2one('stock.location', 'Specific Destination Location', select=True),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Product Main Type'),
        'reason_types_ids': fields.text(string='Reason Types', readonly=True),
        'loss_ok': fields.boolean(string='12 Loss'),
        'loss_scrap_ok': fields.boolean(string='12.1 Loss / Scrap'),
        'loss_sample_ok': fields.boolean(string='12.2 Loss / Sample'),
        'loss_expiry_ok': fields.boolean(string='12.3 Loss / Expiry'),
        'loss_damage_ok': fields.boolean(string='12.4 Loss / Damage'),
    }

    _defaults = {
        'report_date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'company_id': lambda self, cr, uid, ids, c={}: self.pool.get('res.users').browse(cr, uid, uid).company_id.id,
        'loss_ok': True,
        'loss_scrap_ok': True,
        'loss_sample_ok': True,
        'loss_expiry_ok': True,
        'loss_damage_ok': True,
    }

    def _get_reason_types(self, cr, uid, wizard):
        '''
        Return a list of Reason Type ids
        '''
        obj_data = self.pool.get('ir.model.data')
        reason_type_ids = []

        if wizard.loss_ok:
            reason_type_ids.append(obj_data.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loss')[1])

        if wizard.loss_scrap_ok:
            reason_type_ids.append(obj_data.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_scrap')[1])

        if wizard.loss_sample_ok:
            reason_type_ids.append(obj_data.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_sample')[1])

        if wizard.loss_expiry_ok:
            reason_type_ids.append(obj_data.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_expiry')[1])

        if wizard.loss_damage_ok:
            reason_type_ids.append(obj_data.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_damage')[1])

        return reason_type_ids

    def get_values(self, cr, uid, ids, context=None):
        '''
        Retrieve the data according to values in wizard
        '''
        move_obj = self.pool.get('stock.move')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for wizard in self.browse(cr, uid, ids, context=context):
            move_domain = [
                ('type', '=', 'internal'),
                ('picking_id.state', '=', 'done'),
            ]

            if wizard.start_date:
                move_domain.append(('date', '>=', wizard.start_date))

            if wizard.end_date:
                move_domain.append(('date', '<=', wizard.end_date))

            if wizard.location_id:
                move_domain.append(('location_id', '=', wizard.location_id.id))
            else:
                move_domain.append(('location_id.usage', '=', 'internal'))

            if wizard.location_dest_id:
                move_domain.append(('location_dest_id', '=', wizard.location_dest_id.id))
            else:
                move_domain.extend(['|', ('location_dest_id.quarantine_location', '=', True),
                                    ('location_dest_id.destruction_location', '=', True)])

            if wizard.nomen_manda_0:
                move_domain.append(('product_id.nomen_manda_0', '=', wizard.nomen_manda_0.id))

            reason_types_ids = self._get_reason_types(cr, uid, wizard)
            if reason_types_ids:
                move_domain.append(('reason_type_id', 'in', reason_types_ids))

            move_ids = move_obj.search(cr, uid, move_domain, order='picking_id, line_number', context=context)

            if not move_ids:
                raise osv.except_osv(
                    _('Error'),
                    _('No data found with these parameters'),
                )

            self.write(cr, uid, [wizard.id], {'moves_ids': move_ids, 'reason_types_ids': reason_types_ids}, context=context)

        return True

    def print_excel(self, cr, uid, ids, context=None):
        '''
        Retrieve the data according to values in wizard
        and print the report in Excel format.
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        self.get_values(cr, uid, ids, context=context)

        background_id = self.pool.get('memory.background.report').create(cr, uid, {
            'file_name': _('Expired-Damaged Products Report'),
            'report_name': 'stock.expired.damaged.report_xls',
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 3

        data = {'ids': ids, 'context': context}
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'stock.expired.damaged.report_xls',
            'datas': data,
            'context': context,
        }


stock_expired_damaged_wizard()
