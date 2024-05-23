#!/usr/bin/env python
# -*- coding: utf-8 -*-

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport

class tender_rfq_comparison_line_report(dict):

    def __init__(self):
        super(tender_rfq_comparison_line_report, self).__init__()

    def __getattr__(self, attr):
        return self.get(attr, None)

class tender_rfq_comparison(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(tender_rfq_comparison, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'get_compare_lines': self.get_compare_lines,
        })

    def get_compare_lines(self, tender_obj):
        """
        Return for each tender line, the values of RfQ lines
        """
        pol_obj = self.pool.get('purchase.order.line')
        cur_obj = self.pool.get('res.currency')
        lines = []

        s_ids = tender_obj.supplier_ids
        l_index = 1
        for line in tender_obj.tender_line_ids:
            if line.line_state != 'draft':
                continue

            cs_id = False       # Choosen supplier ID
            rfql_id = False     # Choosen RfQ line ID
            if line.purchase_order_line_id:
                cs_id = line.purchase_order_line_id.order_id.partner_id.name
                rfql_id = line.purchase_order_line_id.id

            line_vals = tender_rfq_comparison_line_report()
            line_vals.update({
                'line_number': l_index,
                'tender_line_id': line.id,
                'product_code': line.product_id.default_code,
                'product_name': line.product_id.name,
                'quantity': line.qty,
                'uom_id': line.product_uom.name,
                'choosen_supplier_id': cs_id,
                'rfq_line_id': rfql_id,
            })
            l_index += 1
            for sup in s_ids:
                sid = sup.id
                rfql_ids = pol_obj.search(self.cr, self.uid, [
                    ('order_id.partner_id', '=', sid),
                    ('tender_line_id', '=', line.id),
                ])
                rfql = None
                qty, pu = 0.00, 0.00
                if rfql_ids:
                    rfql = pol_obj.browse(self.cr, self.uid, rfql_ids[0])
                    qty = rfql.product_qty
                    pu = rfql.price_unit
                    to_cur = rfql.order_id.tender_id.currency_id and rfql.order_id.tender_id.currency_id.id or \
                        self.localcontext['company'].currency_id.id
                    if rfql.order_id.pricelist_id.currency_id.id != to_cur:
                        pu = cur_obj.compute(self.cr, self.uid, rfql.order_id.pricelist_id.currency_id.id, to_cur, pu, round=True)

                line_vals.update({
                    'name_%s' % sid: sup.name,
                    'qty_%s' % sid: rfql and qty or 0.00,
                    'unit_price_%s' % sid: rfql and pu or 0.00,
                    'comment_%s' % sid: rfql and rfql.comment or '',
                    'confirmed_delivery_date_%s' % sid: rfql and rfql.confirmed_delivery_date or False,
                })

            lines.append(line_vals)

        return lines


SpreadsheetReport('report.tender_rfq_comparison_xls', 'tender', 'tender_flow/report/tender_rfq_comparison_xls.mako', parser=tender_rfq_comparison)
