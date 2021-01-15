# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2020 TeMPO Consulting, MSF
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


class fo_follow_up_finance_wizard(osv.osv_memory):
    _name = 'fo.follow.up.finance.wizard'
    _rec_name = 'report_date'
    _order = 'report_date desc'

    _columns = {
        'start_date': fields.date(string='Start date'),
        'end_date': fields.date(string='End date'),
        'partner_ids': fields.many2many('res.partner', 'fo_follow_up_wizard_partner_rel', 'wizard_id', 'partner_id', 'Partners'),
        'order_id': fields.many2one('sale.order', string='Order Ref.'),
        'order_ids': fields.text(string='Orders', readonly=True),  # don't use many2many to avoid memory usage issue
        'report_date': fields.datetime(string='Date of the export', readonly=True),
        'company_id': fields.many2one('res.company', string='Company', readonly=True),
    }

    _defaults = {
        'report_date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'company_id': lambda self, cr, uid, ids, c={}: self.pool.get('res.users').browse(cr, uid, uid).company_id.id,
    }

    def get_values(self, cr, uid, ids, context=None):
        """
        Retrieves the data according to the values in the wizard
        """
        inv_obj = self.pool.get('account.invoice')
        fo_obj = self.pool.get('sale.order')
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for wizard in self.browse(cr, uid, ids, context=context):
            fo_ids = []
            if context.get('selected_inv_ids'):
                set_fo_ids = set()
                for inv in inv_obj.browse(cr, uid, context['selected_inv_ids'], fields_to_fetch=['order_ids'], context=context):
                    for fo in inv.order_ids:
                        set_fo_ids.add(fo.id)
                fo_ids = list(set_fo_ids)
            else:
                fo_domain = []
                if wizard.start_date:
                    fo_domain.append(('date_order', '>=', wizard.start_date))
                if wizard.end_date:
                    fo_domain.append(('date_order', '<=', wizard.end_date))
                if wizard.partner_ids:
                    fo_domain.append(('partner_id', 'in', [p.id for p in wizard.partner_ids]))
                if wizard.order_id:
                    fo_domain.append(('id', '=', wizard.order_id.id))
                fo_ids = fo_obj.search(cr, uid, fo_domain, context=context)
            if not fo_ids:
                raise osv.except_osv(
                    _('Error'),
                    _('No field orders found.'),
                )
            self.pool.get('sale.followup.multi.wizard')._check_max_line_number(cr, fo_ids)
            self.write(cr, uid, [wizard.id], {'order_ids': fo_ids}, context=context)
        return True

    def print_excel(self, cr, uid, ids, context=None):
        """
        Prints the report in Excel format.
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.get_values(cr, uid, ids, context=context)
        background_id = self.pool.get('memory.background.report').create(cr, uid, {
            'file_name': 'FO Follow-up Finance',
            'report_name': 'fo.follow.up.finance',
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 3

        data = {'ids': ids, 'context': context}
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'fo.follow.up.finance',
            'datas': data,
            'context': context,
        }


fo_follow_up_finance_wizard()
