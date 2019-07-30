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
from order_types import ORDER_CATEGORY

import time

ORDER_TYPES_SELECTION = [
    ('regular', _('Regular')),
    ('donation_exp', _('Donation before expiry')),
    ('donation_st', _('Standard donation')),
    ('loan', _('Loan')),
    ('in_kind', _('In Kind Donation')),
    ('purchase_list', _('Purchase List')),
    ('direct', _('Direct Purchase Order')),
]


class stock_reception_wizard(osv.osv_memory):
    _name = 'stock.reception.wizard'
    _rec_name = 'report_date'

    _columns = {
        'report_date': fields.datetime(string='Date of the demand', readonly=True),
        'company_id': fields.many2one('res.company', string='Company', readonly=True),
        'moves_ids': fields.text(string='Moves', readonly=True),
        'start_date': fields.date(string='Date from'),
        'end_date': fields.date(string='Date to'),
        'reason_type_id': fields.many2one('stock.reason.type', string='Reason type'),
        'partner_id': fields.many2one('res.partner', string='Partner', help="The partner you want have the IN data"),
        'order_category': fields.selection(ORDER_CATEGORY, string='Order Category'),
        'order_type': fields.selection(ORDER_TYPES_SELECTION, string='Order Type'),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Product Main Type'),
        'location_dest_id': fields.many2one('stock.location', 'Dest. Location', select=True,
                                            help="Location where the system will stock the finished products."),
    }

    _defaults = {
        'report_date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'company_id': lambda self, cr, uid, ids, c={}: self.pool.get('res.users').browse(cr, uid, uid).company_id.id,
    }

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
                ('type', '=', 'in'),
                ('purchase_line_id', '!=', False),
                ('picking_id.state', '=', 'done'),
            ]
            if wizard.start_date:
                move_domain.append(('picking_id.date', '>=', wizard.start_date))

            if wizard.end_date:
                move_domain.append(('picking_id.date', '<=', wizard.end_date))

            if wizard.reason_type_id:
                move_domain.append(('reason_type_id', '=', wizard.reason_type_id.id))

            if wizard.partner_id:
                move_domain.append(('picking_id.partner_id', '=', wizard.partner_id.id))

            if wizard.order_category:
                move_domain.append(('picking_id.order_category', '=', wizard.order_category))

            if wizard.order_type:
                move_domain.append(('purchase_line_id.order_id.order_type', '=', wizard.order_type))

            if wizard.nomen_manda_0:
                move_domain.append(('purchase_line_id.product_id.nomen_manda_0', '=', wizard.nomen_manda_0.id))

            if wizard.location_dest_id:
                move_domain.append(('location_dest_id', '=', wizard.location_dest_id.id))

            move_ids = move_obj.search(cr, uid, move_domain, order='picking_id, line_number', context=context)

            if not move_ids:
                raise osv.except_osv(
                    _('Error'),
                    _('No data found with these parameters'),
                )

            self.write(cr, uid, [wizard.id], {'moves_ids': move_ids}, context=context)

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
            'file_name': _('Receptions Report'),
            'report_name': 'stock.reception.report_xls',
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 3

        data = {'ids': ids, 'context': context}
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'stock.reception.report_xls',
            'datas': data,
            'context': context,
        }


stock_reception_wizard()
