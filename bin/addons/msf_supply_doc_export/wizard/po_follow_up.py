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
        'po_date_from': fields.date("PO date from", required="False"),
        'po_date_thru': fields.date("PO date to", required="False"),
        'partner_id': fields.many2one('res.partner', 'Supplier', required=False),
        'project_ref': fields.char('Supplier reference', size=64, required=False),
        'background_time': fields.integer('Number of second before background processing'),
        'draft_ok': fields.boolean('Draft'),
        'validated_ok': fields.boolean('Validated'),
        'sourced_ok': fields.boolean('Sourced'),
        'confirmed_ok': fields.boolean('Confirmed'),
        'closed_ok': fields.boolean('Closed'),
        'cancel_ok': fields.boolean('Cancel'),
        'pending_only_ok': fields.boolean('Pending order line only'),
    }

    _defaults = {
        'export_format': lambda *a: 'xls',
        'background_time': lambda *a: 20,
    }

    def excel_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        return self.button_validate(cr, uid, ids, report_name='po.follow.up_xls', context=None)


    def pdf_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        return self.button_validate(cr, uid, ids, report_name='po.follow.up_rml', context=None)


    def get_state_list(self, cr, uid, wiz, context=None):
        if context is None:
            context = {}
        res = []
        if wiz.draft_ok:
            res.append('draft')
            res.append('draft_p')
        if wiz.validated_ok:
            res.append('validated')
            res.append('validated_p')
        if wiz.sourced_ok:
            res.append('sourced')
            res.append('sourced_p')
        if wiz.confirmed_ok:
            res.append('confirmed')
            res.append('confirmed_p')
        if wiz.closed_ok:
            res.append('done')
        if wiz.cancel_ok:
            res.append('cancel')

        if not res:
            res = [key for key, value in PURCHASE_ORDER_STATE_SELECTION]

        return res


    def get_states_str(selft, cr, uid, states, context=None):
        if context is None:
            context = {}
        res = [value for key, value in PURCHASE_ORDER_STATE_SELECTION if key in states]

        return ', '.join(res).strip(', ')


    def button_validate(self, cr, uid, ids, report_name, context=None):
        if context is None:
            context = {}

        wiz = self.browse(cr, uid, ids)[0]

        domain = [('rfq_ok', '=', False)]
        report_parms = {
            'title': 'PO Follow Up per Supplier',
            'run_date': time.strftime("%d.%m.%Y"),
            'date_from': '',
            'date_thru': '',
            'state': '',
            'supplier': '',
            'pending_only_ok': wiz.pending_only_ok,
        }

        # PO number
        if wiz.po_id:
            domain.append(('id', '=', wiz.po_id.id))

        # Status
        state_list = self.get_state_list(cr, uid, wiz, context=context)
        domain.append(('state', 'in', state_list))
        report_parms['state'] = self.get_states_str(cr, uid, state_list, context=context)

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


# already defined in account_mcdb/wizard/output_currency_for_export.py
# class background_report(osv.osv_memory):
#        _name = 'memory.background.report'
#        _description = 'Report result'
#
#        _columns = {
#            'file_name': fields.char('Filename', size=256),
#            'report_name': fields.char('Report Name', size=256),
#            'report_id': fields.integer('Report id'),
#            'percent': fields.float('Percent'),
#            'finished': fields.boolean('Finished'),
#        }
#        def update_percent(self, cr, uid, ids, percent, context=None):
#            self.write(cr, uid, ids, {'percent': percent})
# background_report()
