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


class fo_follow_up_finance(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context=None):
        super(fo_follow_up_finance, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'getLang': self._get_lang,
            'getReportLines': self._get_report_lines,
        })

    def _get_lang(self):
        return self.localcontext.get('lang', 'en_MF')

    def _get_report_lines(self, report):
        """
        Returns all report lines as a list of dict
        """
        lines = []
        if report.order_ids:
            # first: retrieve raw data
            sql_req = """
                select
                    so.name AS fo_number, cust.name as customer_name, so.client_order_ref as customer_reference,
                    coalesce(po.name, '') as po_number, coalesce(sup.name, '') as supplier_name, 
                    in_iv.number as in_number,
                    out_iv.number as out_number, out_iv.id as out_iv_id,
                    in_picking.name as IN,
                    coalesce(out_picking.name, out_iv.name) as OUT,
                    out_aml.corrected or out_aml.last_cor_was_only_analytic as out_aji_corr,
                    in_aml.corrected or in_aml.last_cor_was_only_analytic as in_aji_corr
                    from sale_order_line sol
                    inner join sale_order so on so.id = sol.order_id
                    left join purchase_order_line pol on pol.linked_sol_id = sol.id
                    left join purchase_order po on po.id = pol.order_id
                    left join account_invoice_line in_ivl on in_ivl.order_line_id = pol.id
                    left join account_invoice in_iv on in_iv.id = in_ivl.invoice_id
                    left join account_move in_am on in_am.id = in_iv.move_id
                    left join account_move_line in_aml on in_aml.invoice_line_id = in_ivl.id and in_aml.move_id=in_am.id
                    left join stock_picking in_picking on in_picking.id = in_iv.picking_id 
                    left join account_invoice_line out_ivl on out_ivl.sale_order_line_id = sol.id
                    left join account_invoice out_iv on out_iv.id = out_ivl.invoice_id
                    left join stock_picking out_picking on out_picking.id = out_iv.picking_id
                    left join account_move out_am on out_am.id = out_iv.move_id
                    left join account_move_line out_aml on out_aml.invoice_line_id = out_ivl.id and out_aml.move_id = out_am.id
                    left join res_partner cust on cust.id = so.partner_id
                    left join res_partner sup on sup.id = po.partner_id
                where
                    in_iv.refunded_invoice_id is NULL and
                    out_iv.refunded_invoice_id is NULL and
                    coalesce(out_iv.from_supply, 't')='t' and
                    coalesce(in_iv.from_supply, 't')='t' and
                    so.id in %s;
            """
            self.cr.execute(sql_req, (tuple(report.order_ids),))
            lines = self.cr.dictfetchall()
            # second: process data if needed
            for l in lines:
                l['customer_reference'] = l['customer_reference'] and l['customer_reference'].split('.')[-1] or ''
        return lines


SpreadsheetReport('report.fo.follow.up.finance', 'fo.follow.up.finance.wizard',
                  'addons/finance/report/fo_follow_up_finance_xls.mako', parser=fo_follow_up_finance)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
