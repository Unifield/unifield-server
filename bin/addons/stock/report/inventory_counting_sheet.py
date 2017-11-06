# -*- coding: utf-8 -*-
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport


class inventory_counting_sheet_template(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(inventory_counting_sheet_template, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'get_headers': self.get_headers,
        })

    def get_headers(self, objects):
        #   return list of cols:
            # Header Name
            # col type (string, date, datetime, bool, number, float, int)
            # method to compute the value, Parameters: record, index, objects
        return [
            # ['Line Number', 'int', lambda r, index, *a: index+1],
            # ['Name', 'string', lambda r, *a: r.name or ''],
            # ['Stock Valuation', 'float', self.compute_stock_value],
        ]

SpreadsheetReport('report.stock.inventory_counting_sheet_xls', 'stock.inventory', 'addons/stock/report/inventory_counting_sheet.xml', parser=inventory_counting_sheet_template)
