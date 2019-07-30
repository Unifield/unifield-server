# -*- coding: utf-8 -*-
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport


class CountingSheetParser(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(CountingSheetParser, self).__init__(cr, uid, name, context=context)
        self.counter = 0
        self.localcontext.update({
            'get_headers': self.get_headers,
            'next_counter': self.get_next_counter,
            'reset_counter': self.reset_counter,
            'display_product_attributes': self.display_product_attributes,
            'yesno': self.yesno,
            'to_excel': self.to_excel,
        })

    @staticmethod
    def to_excel(value):
        if isinstance(value, report_sxw._dttime_format):
            return value.format().replace(' ', 'T')
        return value

    @staticmethod
    def display_product_attributes(item):
        attributes = {'is_kc': 'KC', 'is_dg': 'DG', 'is_cs': 'CS'}
        return ','.join([name for attribute, name in attributes.items() if getattr(item, attribute, False)])

    @staticmethod
    def yesno(value):
        return 'Y' if value else 'N'

    def get_next_counter(self):
        self.counter += 1
        return self.counter

    def reset_counter(self):
        self.counter = 0

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

SpreadsheetReport('report.physical_inventory_counting_sheet_xls', 'physical.inventory', 'addons/stock/report/physical_inventory_counting_sheet_xls.mako', parser=CountingSheetParser)

report_sxw.report_sxw(
    'report.physical_inventory_counting_sheet_pdf',
    'physical.inventory',
    'addons/stock/report/physical_inventory_counting_sheet.rml',
    parser=CountingSheetParser,
    header='internal'
)
