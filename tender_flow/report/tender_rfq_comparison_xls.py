#!/usr/bin/env python
# -*- coding: utf-8 -*-

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport

class tender_rfq_comparison(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(tender_rfq_comparison, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'gen_line_link': self.gen_line_link,
            'get_same_and_default_currency': self.get_same_and_default_currency,
        })

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
