#!/usr/bin/env python
# -*- coding: utf-8 -*-


from report import report_sxw
from osv import osv
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport

class product_simple_template(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(product_simple_template, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'get_headers': self.get_headers,
            'get_title': lambda *a: "Products Export",
        })

    def compute_stock_value(self, record, index, objects):
        return record.qty_available*record.standard_price

    def get_headers(self):
        #   return list of cols:
            # Header Name
            # col type (string, date, datetime, bool, number, float, int)
            # method to compute the value, Parameters: record, index, objects
        return [
            ['Line Number', 'int', lambda r, index, *a: index+1],
            ['Name', 'string', lambda r, *a: r.name or ''],
            ['Stock Valuation', 'float', self.compute_stock_value],
        ]
SpreadsheetReport('report.spreadsheet.simple_template_xls', 'product.product', parser=product_simple_template)


class product_custom(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(product_custom, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'get_uom_stock': self.get_uom_stock,
            'get_categ_avg': self.get_categ_avg,
        })
        self.categ = {}

    def get_uom_stock(self, o):
        uom = {}
        for prod in o:
            uom.setdefault(prod.uom_id.name, 0)
            uom[prod.uom_id.name] += prod.qty_available

            self.categ.setdefault(prod.categ_id.name, 0)
            self.categ[prod.categ_id.name] += prod.qty_available*prod.standard_price
        return uom.iteritems()

    def get_categ_avg(self, o):
        return self.categ.iteritems()

SpreadsheetReport('report.spreadsheet.custom_xls', 'product.product', 'spreadsheet_xml_examples/report/custom.mako', parser=product_custom)
