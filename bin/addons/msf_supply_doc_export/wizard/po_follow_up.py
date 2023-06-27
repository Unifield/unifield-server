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
from purchase import PURCHASE_ORDER_STATE_SELECTION, ORDER_TYPES_SELECTION
from order_types import ORDER_CATEGORY

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
        'pending_only_ok': fields.boolean('Pending order lines only'),
        'include_notes_ok': fields.boolean('Include order lines note (PDF)'),
        'export_format': fields.char('Export Format', size=16),
        # Order Types
        'regular_ok': fields.boolean('Regular'),
        'donation_exp_ok': fields.boolean('Donation before expiry'),
        'donation_st_ok': fields.boolean('Standard donation'),
        'loan_ok': fields.boolean('Loan'),
        'loan_return_ok': fields.boolean('Loan Return'),
        'in_kind_ok': fields.boolean('In Kind Donation'),
        'purchase_list_ok': fields.boolean('Purchase List'),
        'direct_ok': fields.boolean('Direct Purchase Order'),
        # Order Categories
        'medical_ok': fields.boolean('Medical'),
        'log_ok': fields.boolean('Logistic'),
        'service_ok': fields.boolean('Service'),
        'transport_ok': fields.boolean('Transport'),
        'other_ok': fields.boolean('Other'),
        # Status
        'draft_ok': fields.boolean('Draft'),
        'validated_ok': fields.boolean('Validated'),
        'sourced_ok': fields.boolean('Sourced'),
        'confirmed_ok': fields.boolean('Confirmed'),
        'closed_ok': fields.boolean('Closed'),
        'cancel_ok': fields.boolean('Cancelled'),
    }

    _defaults = {
        'export_format': lambda *a: 'xls',
        'background_time': lambda *a: 3,
    }

    def excel_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        # Create background report
        report_name = 'po.follow.up_xls'
        background_id = self.pool.get('memory.background.report').\
            create(cr, uid, {'file_name': report_name, 'report_name': report_name}, context=context)
        context['background_id'] = background_id
        context['background_time'] = 3

        self.write(cr, uid, ids, {'export_format': 'xls'}, context=context)
        return self.button_validate(cr, uid, ids, report_name=report_name, context=context)

    def pdf_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        report_name = 'po.follow.up_rml'
        # Create background report
        background_id = self.pool.get('memory.background.report').\
            create(cr, uid, {'file_name': report_name, 'report_name': report_name}, context=context)
        context['background_id'] = background_id
        context['background_time'] = 3

        self.write(cr, uid, ids, {'export_format': 'pdf'}, context=context)
        return self.button_validate(cr, uid, ids, report_name=report_name, context=context)

    def get_types_list(self, cr, uid, wiz, context=None):
        if context is None:
            context = {}
        res = []
        if wiz.regular_ok:
            res.append('regular')
        if wiz.donation_exp_ok:
            res.append('donation_exp')
        if wiz.donation_st_ok:
            res.append('donation_st')
        if wiz.loan_ok:
            res.append('loan')
        if wiz.loan_return_ok:
            res.append('loan_return')
        if wiz.in_kind_ok:
            res.append('in_kind')
        if wiz.purchase_list_ok:
            res.append('purchase_list')
        if wiz.regular_ok:
            res.append('direct')

        if not res:
            res = [key for key, value in ORDER_TYPES_SELECTION]

        return res

    def get_types_str(self, cr, uid, types, context=None):
        if context is None:
            context = {}

        res = [_(value) for key, value in ORDER_TYPES_SELECTION if key in types]
        if len(res) == 0 or len(res) == len(ORDER_TYPES_SELECTION):
            return _('All')

        return ', '.join(res).strip(', ')

    def get_categ_list(self, cr, uid, wiz, context=None):
        if context is None:
            context = {}
        res = []
        if wiz.medical_ok:
            res.append('medical')
        if wiz.log_ok:
            res.append('log')
        if wiz.service_ok:
            res.append('service')
        if wiz.transport_ok:
            res.append('transport')
        if wiz.other_ok:
            res.append('other')

        if not res:
            res = [key for key, value in ORDER_CATEGORY]

        return res

    def get_categs_str(self, cr, uid, categs, context=None):
        if context is None:
            context = {}

        res = [_(value) for key, value in ORDER_CATEGORY if key in categs]
        if len(res) == 0 or len(res) == len(ORDER_CATEGORY):
            return _('All')

        return ', '.join(res).strip(', ')

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

    def get_states_str(self, cr, uid, states, pending_only, context=None):
        if context is None:
            context = {}

        if pending_only:
            res = [_(value) for key, value in PURCHASE_ORDER_STATE_SELECTION if key in states and key not in ['cancel', 'done']]
        else:
            res = [_(value) for key, value in PURCHASE_ORDER_STATE_SELECTION if key in states]

        if len(res) == 0 or len(res) == len(PURCHASE_ORDER_STATE_SELECTION):
            return _('All')

        return ', '.join(res).strip(', ')

    def getAllLineIN(self, cr, uid, po_line_id):
        cr.execute('''
            SELECT
                sm.id, sp.name, sm.product_id, sm.product_qty,
                sm.product_uom, sm.price_unit, sm.state,
                sp.backorder_id, sm.picking_id
            FROM
                stock_move sm, stock_picking sp
            WHERE
                sm.purchase_line_id = %s
              AND
                sm.type = 'in'
              AND
                sm.picking_id = sp.id
            ORDER BY
                sp.name, sp.backorder_id, sm.id asc''', tuple([po_line_id]))
        for res in cr.dictfetchall():
            yield res

        raise StopIteration

    def get_qty_backordered(self, cr, uid, pol_id, qty_ordered, qty_received, first_line):
        pol = self.pool.get('purchase.order.line').browse(cr, uid, pol_id)
        if pol.state.startswith('cancel'):
            return 0.0
        if not qty_ordered:
            return 0.0
        try:
            qty_ordered = float(qty_ordered)
            qty_received = float(qty_received)
        except:
            return 0.0

        # Line partially received:
        in_move_done = self.pool.get('stock.move').search(cr, uid, [
            ('type', '=', 'in'),
            ('purchase_line_id', '=', pol.id),
            ('state', '=', 'done'),
        ])
        if first_line and in_move_done:
            total_done = 0.0
            for move in self.pool.get('stock.move').browse(cr, uid, in_move_done, fields_to_fetch=['product_qty','product_uom']):
                if pol.product_uom.id != move.product_uom.id:
                    total_done += self.pool.get('product.uom')._compute_qty(cr, uid, move.product_uom.id, move.product_qty, pol.product_uom.id)
                else:
                    total_done += move.product_qty
            return qty_ordered - total_done

        return qty_ordered - qty_received

    def has_pending_lines(self, cr, uid, po_id):
        po_line_ids = self.pool.get('purchase.order.line').search(cr, uid, [('order_id','=',po_id)], order='line_number')
        report_lines = []
        for line in self.pool.get('purchase.order.line').browse(cr, uid, po_line_ids):
            same_product_same_uom = []
            same_product = []
            other_product = []

            for inl in self.getAllLineIN(cr, uid, line.id):
                if inl.get('product_id') and inl.get('product_id') == line.product_id.id:
                    if inl.get('product_uom') and inl.get('product_uom') == line.product_uom.id:
                        same_product_same_uom.append(inl)
                    else:
                        same_product.append(inl)
                else:
                    other_product.append(inl)

            first_line = True
            if not same_product_same_uom:
                report_line = {
                    'qty_backordered': self.get_qty_backordered(cr, uid, line.id, line.product_qty, 0.0, first_line),
                }
                if report_line.get('qty_backordered', False) and report_line['qty_backordered'] > 0:
                    report_lines.append(report_line)
                first_line = False

            for spsul in sorted(same_product_same_uom, key=lambda spsu: spsu.get('backorder_id'), reverse=True):
                report_line = {
                    'qty_backordered': self.get_qty_backordered(cr, uid, line.id, first_line and line.product_qty or 0.0, spsul.get('state') == 'done' and spsul.get('product_qty', 0.0) or 0.0, first_line),
                }
                if report_line.get('qty_backordered', False) and report_line['qty_backordered'] > 0:
                    report_lines.append(report_line)

                if first_line:
                    first_line = False

            for spl in sorted(same_product, key=lambda spsu: spsu.get('backorder_id'), reverse=True):
                report_line = {
                    'qty_backordered': self.get_qty_backordered(cr, uid, line.id, first_line and line.product_qty or 0.0, spl.get('state') == 'done' and spl.get('product_qty', 0.0) or 0.0, first_line),
                }
                if report_line.get('qty_backordered', False) and report_line['qty_backordered'] > 0:
                    report_lines.append(report_line)

                if first_line:
                    first_line = False

            for ol in other_product:
                report_line = {
                    'qty_backordered': self.get_qty_backordered(cr, uid, line.id, first_line and line.product_qty or 0.0, ol.get('state') == 'done' and ol.get('product_qty', 0.0) or 0.0, first_line),
                }
                if report_line.get('qty_backordered', False) and report_line['qty_backordered'] > 0:
                    report_lines.append(report_line)

        return report_lines

    def button_validate(self, cr, uid, ids, report_name, context=None):
        if context is None:
            context = {}

        field_sel = self.pool.get('ir.model.fields').get_browse_selection
        wiz = self.browse(cr, uid, ids)[0]

        domain = [('rfq_ok', '=', False)]
        report_parms = {
            'title': _('Export PO Follow-up'),
            'run_date_title': _('Report run date'),
            'date_from_title': _('PO date from'),
            'date_thru_title': _('PO date to'),
            'run_date': wiz.export_format == 'xls' and time.strftime("%Y-%m-%d") or time.strftime("%d.%m.%Y"),
            'date_from': '',
            'date_thru': '',
            'state': '',
            'supplier': '',
            'order_type': '',
            'categ': '',
            'pending_only_ok': wiz.pending_only_ok,
            'include_notes_ok': wiz.include_notes_ok,
            'export_format': wiz.export_format,
        }

        # PO number
        if wiz.po_id:
            domain.append(('id', '=', wiz.po_id.id))

        # Order Types
        types_list = self.get_types_list(cr, uid, wiz, context=context)
        report_parms['order_type'] = self.get_types_str(cr, uid, types_list, context=context)

        # Order Categories
        categ_list = self.get_categ_list(cr, uid, wiz, context=context)
        report_parms['categ'] = self.get_categs_str(cr, uid, categ_list, context=context)

        # Status
        state_list = self.get_state_list(cr, uid, wiz, context=context)
        domain.append(('state', 'in', state_list))
        if wiz.pending_only_ok:
            domain.append(('state', 'not in', ['done', 'cancel']))
        report_parms['state'] = self.get_states_str(cr, uid, state_list, wiz.pending_only_ok, context=context)

        # Dates
        if wiz.po_date_from:
            domain.append(('date_order', '>=', wiz.po_date_from))
            if wiz.export_format == 'xls':
                report_parms['date_from'] = wiz.po_date_from
            else:
                tmp = datetime.strptime(wiz.po_date_from, "%Y-%m-%d")
                report_parms['date_from'] = tmp.strftime("%d.%m.%Y")

        if wiz.po_date_thru:
            domain.append(('date_order', '<=', wiz.po_date_thru))
            if wiz.export_format == 'xls':
                report_parms['date_thru'] = wiz.po_date_thru
            else:
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
            raise osv.except_osv(_('Warning'), _('No Purchase Orders match the specified criteria.'))

        cr.execute("""SELECT COUNT(id) FROM purchase_order_line WHERE order_id IN %s""", (tuple(po_ids),))
        nb_lines = 0
        for x in cr.fetchall():
            nb_lines = x[0]

        # Parameter to define the maximum number of lines. For a custom number:
        # "INSERT INTO ir_config_parameter (key, value) VALUES ('FOLLOWUP_MAX_LINE', 'chosen_number');"
        # Or update the existing one
        config_line = self.pool.get('ir.config_parameter').get_param(cr, 1, 'PO_FOLLOWUP_MAX_LINE')
        if config_line:
            max_line = int(config_line)
        else:
            max_line = 20000

        if nb_lines > max_line:
            raise osv.except_osv(_('Error'), _('The requested report is too heavy to generate: requested %d lines, maximum allowed %d. Please apply further filters so that report can be generated.'), (nb_lines, max_line))

        if wiz.pending_only_ok and report_name == 'po.follow.up_rml':
            filtered_po_ids = []
            for po_id in po_ids:
                if self.has_pending_lines(cr, uid, po_id):
                    filtered_po_ids.append(po_id)
            po_ids = filtered_po_ids

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

        datas = {'ids': po_ids, 'report_header': report_header, 'report_parms': report_parms, 'context': context}

        if wiz.po_date_from:
            domain.append(('date_order', '>=', wiz.po_date_from))

        # For background report
        context['nb_orders'] = len(po_ids)

        return {
            'type': 'ir.actions.report.xml',
            'report_name': report_name,
            'datas': datas,
            'nodestroy': True,
            'context': context,
        }


po_follow_up()
