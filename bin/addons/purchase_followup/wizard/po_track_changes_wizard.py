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


class po_track_changes_wizard(osv.osv_memory):
    _name = 'po.track.changes.wizard'
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
        'po_line_ids': fields.text(
            string='Purchase Orders Lines',
            readonly=True
        ),
        'po_id': fields.many2one(
            'purchase.order',
            string='Purchase Order Ref.',
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
        po_line_obj = self.pool.get('purchase.order.line')

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        for wizard in self.browse(cr, uid, ids, context=context):
            po_domain = []

            if wizard.start_date:
                po_domain.append(('create_date', '>=', wizard.start_date))

            if wizard.end_date:
                po_domain.append(('create_date', '<=', wizard.end_date))

            if wizard.po_id:
                po_domain.append(('order_id', '=', wizard.po_id.id))

            po_line_ids = po_line_obj.search(cr, uid, po_domain, context=context)

            if not po_line_ids:
                raise osv.except_osv(
                    _('Error'),
                    _('No data found with these parameters'),
                )

            self.write(cr, uid, [wizard.id], {'po_line_ids': po_line_ids}, context=context)

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
            'file_name': 'PURCHASE ORDER Track Changes report',
            'report_name': 'po.track.changes.report_xls',
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 3

        data = {'ids': ids, 'context': context}
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'po.track.changes.report_xls',
            'datas': data,
            'context': context,
        }


po_track_changes_wizard()
