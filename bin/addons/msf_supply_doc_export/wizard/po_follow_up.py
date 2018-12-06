#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
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
from purchase import PURCHASE_ORDER_STATE_SELECTION

import time
from datetime import datetime

class po_follow_up(osv.osv_memory):
    _name = 'po.follow.up'
    _description = 'PO Follow up report wizard'

    _columns = {
        'po_id': fields.many2one('purchase.order', string="Order Reference", help="Unique number of the Purchase Order. Optional", required=False),
        'state': fields.selection(PURCHASE_ORDER_STATE_SELECTION, 'State', help="The state of the purchase order. Optional", select=True, required=False),
        'po_date_from': fields.date("PO date from", required="False"),
        'po_date_thru': fields.date("PO date to", required="False"),
        'partner_id': fields.many2one('res.partner', 'Supplier', required=False),
        'project_ref': fields.char('Supplier reference', size=64, required=False),
        'export_format': fields.selection([('xls', 'Excel'), ('pdf', 'PDF')], string="Export format", required=True),
        'background_time': fields.integer('Number of second before background processing'),
    }

    _defaults = {
        'export_format': lambda *a: 'xls',
        'background_time': lambda *a: 20,
    }

    def button_validate(self, cr, uid, ids, context=None):
        wiz = self.browse(cr, uid, ids)[0]

        domain = [('rfq_ok', '=', False)]
        states = {}
        for state_val, state_string in PURCHASE_ORDER_STATE_SELECTION:
            states[state_val] = state_string
        report_parms = {
            'title': _('PO Follow Up per Supplier'),
            'run_date': time.strftime("%d.%m.%Y"),
            'date_from': '',
            'date_thru': '',
            'state': '',
            'supplier': ''
        }

        # PO number
        if wiz.po_id:
            domain.append(('id', '=', wiz.po_id.id))

        # Status
        if wiz.state:
            domain.append(('state', '=', wiz.state))
            report_parms['state'] = states[wiz.state]

        # Dates
        if wiz.po_date_from:
            domain.append(('date_order', '>=', wiz.po_date_from))
            tmp = datetime.strptime(wiz.po_date_from, "%Y-%m-%d")
            report_parms['date_from'] = tmp.strftime("%d.%m.%Y")

        if wiz.po_date_thru:
            domain.append(('date_order', '<=', wiz.po_date_thru))
            tmp = datetime.strptime(wiz.po_date_thru, "%Y-%m-%d")
            report_parms['date_thru'] = tmp.strftime("%d.%m.%Y")

        # Supplier
        if wiz.partner_id:
            domain.append(('partner_id', '=', wiz.partner_id.id))
            report_parms['supplier'] = wiz.partner_id.name

        # Supplier Reference
        if wiz.project_ref:
            domain.append(('project_ref', 'like', wiz.project_ref))

        # get the PO ids based on the selected criteria
        po_obj = self.pool.get('purchase.order')
        po_ids = po_obj.search(cr, uid, domain)

        if not po_ids:
            raise osv.except_osv(_('Error'), _('No Purchase Orders match the specified criteria.'))
            return True

        report_header = []
        report_header.append(report_parms['title'])

        report_header_line2 = ''
        if wiz.partner_id:
            report_header_line2 += wiz.partner_id.name
        report_header_line2 += '  Report run date: ' + time.strftime("%d.%m.%Y")  # TODO to be removed
        if wiz.po_date_from:
            report_header_line2 += wiz.po_date_from
        # UF-2496: Minor fix to append the "date from" correctly into header
        if wiz.po_date_thru:
            if wiz.po_date_from:
                report_header_line2 += ' - '
            report_header_line2 += wiz.po_date_thru
        report_header.append(report_header_line2)

        datas = {'ids': po_ids, 'report_header': report_header, 'report_parms': report_parms}
        if wiz.export_format == 'xls':
            report_name = 'po.follow.up_xls'
        else:
            report_name = 'po.follow.up_rml'

        if wiz.po_date_from:
            domain.append(('date_order', '>=', wiz.po_date_from))

        background_id = self.pool.get('memory.background.report').create(cr, uid, {'file_name': report_name, 'report_name': report_name}, context=context)
        context['background_id'] = background_id
        context['background_time'] = wiz.background_time
        return {
            'type': 'ir.actions.report.xml',
            'report_name': report_name,
            'datas': datas,
            'nodestroy': True,
            'context': context,
        }

po_follow_up()

