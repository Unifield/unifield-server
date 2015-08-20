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
            'gen_line_link': self.gen_line_link,
            'get_same_and_default_currency': self.get_same_and_default_currency,
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
                pu = 0.00
                if rfql_ids:
                    rfql = pol_obj.browse(self.cr, self.uid, rfql_ids[0])
                    pu = rfql.price_unit
                    same_cur = rfql.order_id.pricelist_id.currency_id.id == self.localcontext['company'].currency_id.id
                    if not same_cur:
                        pu = cur_obj.compute(
                            self.cr,
                            self.uid,
                            rfql.order_id.pricelist_id.currency_id.id,
                            self.localcontext['company'].currency_id.id,
                            pu,
                            round=True)

                line_vals.update({
                    'name_%s' % sid: sup.name,
                    'unit_price_%s' % sid: pu,
                    'comment_%s' % sid: rfql and rfql.comment or '',
                })

            lines.append(line_vals)

        return lines

    def get_same_and_default_currency(self, tender_obj):

        if tender_obj == 'draft' or not tender_obj.rfq_ids:
            return (True, self.localcontext['company'].currency_id)

        current_cur = False

        for rfq in tender_obj.rfq_ids:
            next_cur = rfq.currency_id
            if current_cur and current_cur.id != next_cur.id:
                return (False, self.localcontext['company'].currency_id)
            current_cur = rfq.currency_id
        return (True, current_cur)

    def gen_line_link(self, tender_obj):
        link_line_supp = {}

        same_cur, currency = self.get_same_and_default_currency(tender_obj)
        cur_obj = self.pool.get('res.currency')

        if tender_obj.rfq_ids:
            # fine we have rfqs
            for rfq in tender_obj.rfq_ids:
                for line in rfq.order_line:
                    data = {'notes': line.notes, 'price_unit': line.price_unit}
                    if not same_cur:
                        data['price_unit'] = cur_obj.compute(self.cr, self.uid, line.currency_id.id, currency.id, line.price_unit, round=True)

                    link_line_supp.setdefault(line.product_id.id, {}).setdefault(rfq.partner_id.id, data)
        elif tender_obj.supplier_ids:
            for line in tender_obj.tender_line_ids:
                link_line_supp[line.product_id.id] = {}
                for supp in tender_obj.supplier_ids:
                    link_line_supp[line.product_id.id][supp.id] = {}

        return link_line_supp


SpreadsheetReport('report.tender_rfq_comparison_xls', 'tender', 'tender_flow/report/tender_rfq_comparison_xls.mako', parser=tender_rfq_comparison)
