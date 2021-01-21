# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2020 TeMPO Consulting, MSF. All Rights Reserved
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

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from base import currency_date
from datetime import datetime


class fo_follow_up_finance(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context=None):
        super(fo_follow_up_finance, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'getLang': self._get_lang,
            'getReportLines': self._get_report_lines,
        })

    def _get_lang(self):
        return self.localcontext.get('lang', 'en_MF')

    def _get_line_fctal_amount(self, line_subtotal, booking_curr_id, doc_date, posting_date):
        """
        Returns the line subtotal in functional currency based on the data in parameter
        """
        line_subtotal_fctal = 0.0
        user_obj = self.pool.get('res.users')
        curr_obj = self.pool.get('res.currency')
        fctal_curr_id = user_obj.browse(self.cr, self.uid, self.uid).company_id.currency_id.id
        today = datetime.today().strftime('%Y-%m-%d')
        if booking_curr_id and line_subtotal:
            if booking_curr_id == fctal_curr_id:
                line_subtotal_fctal = line_subtotal
            else:
                curr_date = currency_date.get_date(self, self.cr, doc_date or today, posting_date or today)
                line_subtotal_fctal = curr_obj.compute(self.cr, self.uid, booking_curr_id, fctal_curr_id, line_subtotal,
                                                       round=True, context={'currency_date': curr_date})
        return line_subtotal_fctal

    def _process_report_lines(self, lines):
        """
        Formats the raw data retrieved by the SQL request in _get_report_lines
        """
        picking_obj = self.pool.get('stock.picking')
        shipment_obj = self.pool.get('shipment')
        processed = {}  # store the transport files processed (perf)
        for l in lines:
            # e.g. extract 21/se_HQ1/HT101/PO00011 from se_HQ1C1.21/se_HQ1/HT101/PO00011
            l['customer_reference'] = l['customer_reference'] and l['customer_reference'].split('.')[-1] or ''
            l['si_line_subtotal_fctal'] = self._get_line_fctal_amount(l['si_line_subtotal'], l['si_currency_id'],
                                                                      l['si_doc_date'], l['si_posting_date'])
            l['si_state'] = l['si_state'] and self.getSelValue('account.invoice', 'state', l['si_state']) or ''
            l['fo_status'] = l['fo_status'] and self.getSelValue('sale.order', 'state', l['fo_status']) or ''
            l['fo_line_status'] = l['fo_line_status'] and self.getSelValue('sale.order.line', 'state', l['fo_line_status']) or ''
            l['is_delivered'] = False
            if l['transport_file']:
                if ':' in l['transport_file']:
                    # e.g. extract "SHIP/00004-01" from "se_HQ1C1.21/se_HQ1/HT101/PO00011 : SHIP/00004-01"
                    l['transport_file'] = l['transport_file'].split(':')[-1].strip()
                if l['transport_file'] in processed:
                    l['is_delivered'] = processed[l['transport_file']]
                else:
                    if l['pick_id'] and picking_obj.browse(self.cr, self.uid, l['pick_id'], fields_to_fetch=['state']).state == 'delivered':
                        l['is_delivered'] = True
                    elif l.get('transport_file', '').startswith('SHIP') and \
                            shipment_obj.search_exist(self.cr, self.uid, [('name', '=', l['transport_file']), ('state', '=', 'delivered')]):
                        l['is_delivered'] = True
                    processed[l['transport_file']] = l['is_delivered']
            l['out_inv_line_subtotal_fctal'] = self._get_line_fctal_amount(l['out_inv_line_subtotal'], l['out_inv_currency_id'],
                                                                           l['out_inv_doc_date'], l['out_inv_posting_date'])
            l['out_inv_state'] = l['out_inv_state'] and self.getSelValue('account.invoice', 'state', l['out_inv_state']) or ''
        return lines

    def _get_report_lines(self, report):
        """
        Returns all report lines as a list of dict
        """
        lines = []
        if report.order_ids:
            bg_obj = self.pool.get('memory.background.report')
            bg_id = self.localcontext.get('background_id')
            # first: retrieve raw data
            sql_req = """
                select
                    so.name AS fo_number, cust.name as customer_name, so.client_order_ref as customer_reference,
                    coalesce(po.name, '') as po_number, coalesce(sup.name, '') as supplier_name, in_iv.id as si,
                    coalesce(in_iv.number, '') as si_number, coalesce(cast(in_ivl.line_number as varchar), '') as si_line_number, 
                    coalesce(in_ivl.name, '') as si_line_description, coalesce(in_ivl.price_unit, 0) as si_line_unit_price,
                    coalesce(in_ivl.quantity, 0) as si_line_quantity, coalesce(in_ivl_acc.code, '') as si_line_account_code,
                    coalesce(in_ivl.price_subtotal, 0) as si_line_subtotal, coalesce(in_iv_curr.name, '') as si_currency,
                    in_iv_curr.id as si_currency_id, in_iv.document_date as si_doc_date, in_iv.date_invoice as si_posting_date,
                    coalesce(in_iv.state, '') as si_state,
                    CASE WHEN (in_aml.corrected or in_aml.last_cor_was_only_analytic) = TRUE THEN 'X' ELSE '' END AS reverse_aji_si,
                    so.state as fo_status, sol.state as fo_line_status, sol.line_number as fo_line_number,
                    coalesce(prod.default_code, '') as product_code, coalesce(prod_t.name, '') as product_description,
                    coalesce(sol.product_uom_qty, 0) as qty_ordered, prod_u.name as uom_ordered,
                    coalesce((select sum(product_qty) from
                        stock_move m1, stock_picking p1
                        where
                        p1.id = m1.picking_id and
                        m1.state = 'done' and
                        p1.type = 'out' and 
                        (p1.subtype='standard' or p1.subtype='packing' and m1.pick_shipment_id is not null and m1.not_shipped='f') and
                        m1.sale_line_id = sol.id
                        group by m1.sale_line_id), 0) as qty_delivered,  
                    CASE WHEN coalesce(out_picking.name, out_iv.name) IS NOT NULL 
                        THEN coalesce(out_picking.name, out_iv.name) ELSE '' END AS transport_file,
                    coalesce(out_picking.id, 0) as pick_id,
                    out_iv.id as out_inv, coalesce(out_iv.number, '') as out_inv_number,
                    coalesce(cast(out_ivl.line_number as varchar), '') as out_inv_line_number,
                    coalesce(out_ivl.name, '') as out_inv_description, coalesce(out_ivl.price_unit, 0) as out_inv_unit_price,
                    coalesce(out_ivl.quantity, 0) as out_inv_quantity, coalesce(out_ivl_acc.code, '') as out_inv_account_code,
                    coalesce(out_ivl.price_subtotal, 0) as out_inv_line_subtotal, coalesce(out_iv_curr.name, '') as out_inv_currency,
                    out_iv_curr.id as out_inv_currency_id, out_iv.document_date as out_inv_doc_date,
                    out_iv.date_invoice as out_inv_posting_date,
                    coalesce(out_iv.state, '') as out_inv_state,
                    CASE WHEN (out_aml.corrected or out_aml.last_cor_was_only_analytic) = TRUE THEN 'X' ELSE '' END AS reverse_aji_out_inv
                    from sale_order_line sol
                    inner join sale_order so on so.id = sol.order_id
                    left join purchase_order_line pol on pol.linked_sol_id = sol.id
                    left join purchase_order po on po.id = pol.order_id
                    -- avoid duplicates due to merge lines and/or refunds
                    left join (
                        select in_ivl_tmp.*, coalesce(in_ivl_tmp.order_line_id, invl_pol_rel.po_line_id) as pol_id
                            from account_invoice_line in_ivl_tmp
                            inner join account_invoice in_iv_tmp on in_iv_tmp.id = in_ivl_tmp.invoice_id
                            left join inv_line_po_line_rel invl_pol_rel on invl_pol_rel.inv_line_id = in_ivl_tmp.id
                        where
                            (invl_pol_rel.inv_line_id is NULL or invl_pol_rel.inv_line_id = in_ivl_tmp.id and in_ivl_tmp.order_line_id is null)
                            and in_iv_tmp.refunded_invoice_id is NULL
                            -- main_purchase_id is used to retrieve invoices generated via DPO before they had the tag from_supply
                            and (coalesce(in_iv_tmp.from_supply, 't')='t' or in_iv_tmp.main_purchase_id is not null)
                    ) as in_ivl ON in_ivl.pol_id = pol.id
                    left join account_invoice in_iv on in_iv.id = in_ivl.invoice_id
                    left join account_move in_am on in_am.id = in_iv.move_id
                    left join account_move_line in_aml on in_aml.invoice_line_id = in_ivl.id and in_aml.move_id=in_am.id
                    left join account_invoice_line out_ivl on out_ivl.sale_order_line_id = sol.id
                    left join account_invoice out_iv on out_iv.id = out_ivl.invoice_id
                    left join stock_picking out_picking on out_picking.id = out_iv.picking_id
                    left join account_move out_am on out_am.id = out_iv.move_id
                    left join account_move_line out_aml on out_aml.invoice_line_id = out_ivl.id and out_aml.move_id = out_am.id
                    left join res_partner cust on cust.id = so.partner_id
                    left join res_partner sup on sup.id = po.partner_id
                    left join account_account in_ivl_acc on in_ivl_acc.id = in_ivl.account_id
                    left join account_account out_ivl_acc on out_ivl_acc.id = out_ivl.account_id
                    left join res_currency in_iv_curr on in_iv_curr.id = in_iv.currency_id
                    left join res_currency out_iv_curr on out_iv_curr.id = out_iv.currency_id
                    left join product_product prod on prod.id = sol.product_id
                    left join product_template prod_t on prod_t.id = prod.product_tmpl_id
                    left join product_uom prod_u on prod_u.id = sol.product_uom  
                where
                    out_iv.refunded_invoice_id is NULL and
                    -- from_supply is used to exclude IVO/STV generated via refund before refunded_invoice_id was used
                    coalesce(out_iv.from_supply, 't')='t' and
                    sol.state not in ('cancel', 'cancel_r') and
                    so.id in %s
                order by fo_number DESC, fo_line_number, si_number, si_line_number, out_inv_number, out_inv_line_number;
            """
            self.cr.execute(sql_req, (tuple(report.order_ids),))
            lines = self.cr.dictfetchall()
            if bg_id:
                bg_obj.update_percent(self.cr, self.uid, bg_id, 0.50)
            # second: process data if needed
            lines = self._process_report_lines(lines)
        return lines


SpreadsheetReport('report.fo.follow.up.finance', 'fo.follow.up.finance.wizard',
                  'addons/finance/report/fo_follow_up_finance_xls.mako', parser=fo_follow_up_finance)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
