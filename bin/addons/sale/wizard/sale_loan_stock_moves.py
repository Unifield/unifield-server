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
from msf_partner import PARTNER_TYPE

import time


class sale_loan_stock_moves(osv.osv_memory):
    _name = 'sale.loan.stock.moves'

    _columns = {
        'start_date': fields.date(
            string='Start date',
        ),
        'end_date': fields.date(
            string='End date',
        ),
        'company_id': fields.many2one(
            'res.company',
            string='Company',
            readonly=True,
        ),
        'partner_id': fields.many2one(
            'res.partner',
            string='Partner',
            help="The partner you want have the loans from",
        ),
        'partner_type': fields.selection(
            PARTNER_TYPE,
            string='Partner Type',
        ),
        'product_id': fields.many2one(
            'product.product',
            string='Product Ref.',
        ),
        'origin': fields.char(
            'Origin',
            size=256
        ),
        'nomen_manda_0': fields.many2one(
            'product.nomenclature',
            'Product Main Type',
        ),
        'remove_completed': fields.boolean(
            'Only unfinished loans',
            help='Only show the lines with a quantity balance different than 0'
        ),
        'sm_ids': fields.text(
            string='Stock Moves',
            readonly=True
        ),
        'display_bn_ed': fields.boolean(
            string='Display BN/ED details',
        ),
    }

    _defaults = {
        'display_bn_ed': False,
    }

    def get_values(self, cr, uid, ids, context=None):
        '''
        Retrieve the data according to values in wizard
        '''
        sm_obj = self.pool.get('stock.move')
        prod_obj = self.pool.get('product.product')
        data_obj = self.pool.get('ir.model.data')

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        rt_loan_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loan')[1]
        rt_loan_ret_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loan_return')[1]

        for wizard in self.browse(cr, uid, ids, context=context):
            sm_domain = []

            sm_domain.append(('reason_type_id', 'in', [rt_loan_id, rt_loan_ret_id]))
            sm_domain += ['|', ('type', '=', 'in'), '&', ('location_id.usage', '=', 'internal'),
                          ('location_dest_id.usage', 'in', ['customer', 'supplier'])]

            if wizard.start_date:
                sm_domain.append(('date', '>=', wizard.start_date))

            if wizard.end_date:
                sm_domain.append(('date', '<=', wizard.end_date))

            if wizard.partner_id:
                sm_domain.append(('partner_id', '=', wizard.partner_id.id))

            if wizard.partner_type:
                sm_domain.append(('partner_id.partner_type', '=', wizard.partner_type))

            if wizard.product_id:
                if wizard.nomen_manda_0:
                    if prod_obj.search(cr, uid, [('id', '=', wizard.product_id.id), ('nomen_manda_0', '=', wizard.nomen_manda_0.id)], limit=1, context=context):
                        sm_domain.append(('product_id', '=', wizard.product_id.id))
                    else:
                        raise osv.except_osv(_('Error'), _('The Product (%s) does not have this Nomenclature')
                                             % (wizard.product_id.default_code,))
                else:
                    sm_domain.append(('product_id', '=', wizard.product_id.id))
            elif wizard.nomen_manda_0:
                prod_ids = prod_obj.search(cr, uid, [('nomen_manda_0', '=', wizard.nomen_manda_0.id)], context=context)
                if prod_ids:
                    sm_domain.append(('product_id', 'in', prod_ids))

            if wizard.origin:
                sm_domain.append(('origin', 'like', wizard.origin))

            if not wizard.display_bn_ed:
                sm_domain.append(('state', 'in', ['done', 'cancel']))

            remove_completed = False
            if wizard.remove_completed:
                remove_completed = True

            sm_ids = sm_obj.search(cr, uid, sm_domain, context=context)

            if not sm_ids:
                raise osv.except_osv(
                    _('Error'),
                    _('No data found with these parameters'),
                )

            self.write(cr, uid, [wizard.id], {'sm_ids': sm_ids, 'remove_completed': remove_completed}, context=context)

        return True

    def print_excel(self, cr, uid, ids, context=None):
        '''
        Retrieve the data according to values in wizard
        and print the report in Excel format.
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        self.get_values(cr, uid, ids, context=context)

        background_id = self.pool.get('memory.background.report').create(cr, uid, {
            'file_name': 'Loan Report',
            'report_name': 'sale.loan.stock.moves.report_xls',
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 3

        data = {'ids': ids, 'context': context, 'target_filename': _('Loan Report_%s') % (time.strftime('%Y%m%d_%H_%M'),)}
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'sale.loan.stock.moves.report_xls',
            'datas': data,
            'context': context,
        }


sale_loan_stock_moves()
