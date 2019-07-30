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


class ir_track_changes_wizard(osv.osv_memory):
    _name = 'ir.track.changes.wizard'
    _rec_name = 'report_date'
    _order = 'report_date desc'

    _columns = {
        'report_date': fields.datetime(
            string='Date of the demand',
            readonly=True,
        ),
        'company_id': fields.many2one(
            'res.company',
            string='Company',
            readonly=True,
        ),
        'start_date': fields.date(
            string='Start date',
        ),
        'end_date': fields.date(
            string='End date',
        ),
        'order_line_ids': fields.text(
            string='Orders Lines',
            readonly=True
        ),
        'order_id': fields.many2one(
            'sale.order',
            string='Order Ref.',
        ),
    }

    _defaults = {
        'report_date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'company_id': lambda self, cr, uid, ids, c={}: self.pool.get('res.users').browse(cr, uid, uid).company_id.id,
    }

    def get_values(self, cr, uid, ids, context=None):
        '''
        Retrieve the data according to values in wizard
        '''
        ir_line_obj = self.pool.get('sale.order.line')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for wizard in self.browse(cr, uid, ids, context=context):
            ir_domain = [('procurement_request', '=', 't')]

            if wizard.start_date:
                ir_domain.append(('create_date', '>=', wizard.start_date))

            if wizard.end_date:
                ir_domain.append(('create_date', '<=', wizard.end_date))

            if wizard.order_id:
                ir_domain.append(('order_id', '=', wizard.order_id.id))

            ir_line_ids = ir_line_obj.search(cr, uid, ir_domain, context=context)

            if not ir_line_ids:
                raise osv.except_osv(
                    _('Error'),
                    _('No data found with these parameters'),
                )

            self.write(cr, uid, [wizard.id], {'order_line_ids': ir_line_ids}, context=context)

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
            'file_name': 'INTERNAL REQUEST Track Changes report',
            'report_name': 'ir.track.changes.report_xls',
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 3

        data = {'ids': ids, 'context': context}
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'ir.track.changes.report_xls',
            'datas': data,
            'context': context,
        }


ir_track_changes_wizard()
