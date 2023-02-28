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

import time

from osv import fields, osv
from tools.translate import _


class supplier_performance_wizard(osv.osv_memory):
    _name = 'supplier.performance.wizard'

    _columns = {
        'report_date': fields.datetime(string='Generated on', readonly=True),
        'state': fields.selection(selection=[('draft', 'Draft'), ('in_progress', 'In Progress'), ('ready', 'Ready')], string='State'),
        'company_id': fields.many2one('res.company', string='Company', readonly=True),
        'company_currency_id': fields.many2one('res.currency', string='Company Currency', readonly=True),
        'date_from': fields.date(string='From'),
        'date_to': fields.date(string='To'),
        'partner_id': fields.many2one('res.partner', string='Specific Supplier'),
        'pt_text': fields.text(string='Partner Types Text', readonly=True),
        'partner_type_internal': fields.boolean(string='Internal'),
        'partner_type_section': fields.boolean(string='Inter-section'),
        'partner_type_external': fields.boolean(string='External'),
        'partner_type_esc': fields.boolean(string='ESC'),
        'partner_type_intermission': fields.boolean(string='Intermission'),
        'ot_text': fields.text(string='Order Types Text', readonly=True),
        'po_type_regular': fields.boolean(string='Regular'),
        'po_type_donation_exp': fields.boolean(string='Donation before expiry'),
        'po_type_donation_st': fields.boolean(string='Standard donation'),
        'po_type_loan': fields.boolean(string='Loan'),
        'po_type_loan_return': fields.boolean(string='Loan Return'),
        'po_type_in_kind': fields.boolean(string='In Kind Donation'),
        'po_type_purchase_list': fields.boolean(string='Purchase List'),
        'po_type_direct': fields.boolean(string='Direct Purchase Order'),
        'pol_ids': fields.text(string='Order Lines', readonly=True),
        'order_id': fields.many2one('purchase.order.line', string='Order Line'),
    }

    _defaults = {
        'report_date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'state': 'draft',
        'company_id': lambda self, cr, uid, ids, c={}: self.pool.get('res.users').browse(cr, uid, uid).company_id.id,
        'company_currency_id': lambda self, cr, uid, ids, c={}: self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id,
    }

    def _get_partner_types(self, cr, uid, wizard, context=None):
        '''
        Return a list of Partner Types
        '''
        if context is None:
            context = {}

        PARTNER_TYPES_SELECTION = {
            'internal': _('Internal'),
            'section': _('Inter-section'),
            'external': _('External'),
            'esc': _('ESC'),
            'intermission': _('Intermission'),
        }
        partner_types = []

        if wizard.partner_type_internal:
            partner_types.append('internal')
        if wizard.partner_type_section:
            partner_types.append('section')
        if wizard.partner_type_external:
            partner_types.append('external')
        if wizard.partner_type_esc:
            partner_types.append('esc')
        if wizard.partner_type_intermission:
            partner_types.append('intermission')

        return partner_types, ', '.join(PARTNER_TYPES_SELECTION[pt] for pt in partner_types)

    def _get_order_types(self, cr, uid, wizard, context=None):
        '''
        Return a list of PO Order Types
        '''
        if context is None:
            context = {}

        ORDER_TYPES_SELECTION = {
            'regular': _('Regular'),
            'donation_exp': _('Donation before expiry'),
            'donation_st': _('Standard donation'),
            'loan': _('Loan'),
            'loan_return': _('Loan Return'),
            'in_kind': _('In Kind Donation'),
            'purchase_list': _('Purchase List'),
            'direct': _('Direct Purchase Order'),
        }
        order_types = []

        if wizard.po_type_regular:
            order_types.append('regular')
        if wizard.po_type_donation_exp:
            order_types.append('donation_exp')
        if wizard.po_type_donation_st:
            order_types.append('donation_st')
        if wizard.po_type_loan:
            order_types.append('loan')
        if wizard.po_type_loan_return:
            order_types.append('loan_return')
        if wizard.po_type_in_kind:
            order_types.append('in_kind')
        if wizard.po_type_purchase_list:
            order_types.append('purchase_list')
        if wizard.po_type_direct:
            order_types.append('direct')

        return order_types, ', '.join(ORDER_TYPES_SELECTION[ot] for ot in order_types)

    def get_values(self, cr, uid, ids, context=None):
        '''
        Retrieve the data according to values in wizard and print the report in Excel format.
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        pol_obj = self.pool.get('purchase.order.line')

        for wizard in self.browse(cr, uid, ids, context=context):
            vals = {}
            pol_domain = [
                ('state', 'in', ['done', 'cancel', 'cancel_r']),
                ('partner_id.supplier', '=', True),
            ]

            if wizard.date_from:
                pol_domain.append(('create_date', '>=', wizard.date_from))

            if wizard.date_to:
                pol_domain.append(('create_date', '<=', wizard.date_to))

            if wizard.partner_id:
                pol_domain.append(('partner_id', '=', wizard.partner_id.id))

            partner_types, pt_text = self._get_partner_types(cr, uid, wizard, context=context)
            if partner_types:
                pol_domain.append(('partner_id.partner_type', 'in', partner_types))
                vals.update({'pt_text': pt_text})

            order_types, ot_text = self._get_order_types(cr, uid, wizard, context=context)
            if order_types:
                pol_domain.append(('order_id.order_type', 'in', order_types))
                vals.update({'ot_text': ot_text})

            vals.update({
                'pol_ids': pol_obj.search(cr, uid, pol_domain, order='order_id desc, line_number asc', context=context)
            })

            if not vals.get('pol_ids'):
                raise osv.except_osv(
                    _('Error'),
                    _('No data found with these parameters'),
                )

            self.write(cr, uid, [wizard.id], vals, context=context)

        return True

    def print_excel(self, cr, uid, ids, context=None):
        '''
        Retrieve the data according to values in wizard and print the report in Excel format.
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        self.get_values(cr, uid, ids, context=context)

        background_id = self.pool.get('memory.background.report').create(cr, uid, {
            'file_name': 'Supplier Performance Report',
            'report_name': 'supplier.performance.report_xls',
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 3

        data = {'ids': ids, 'context': context}
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'supplier.performance.report_xls',
            'datas': data,
            'context': context,
        }


supplier_performance_wizard()
