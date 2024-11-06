# -*- coding: utf-8 -*-
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport


class DiscrepanciesReportParser(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(DiscrepanciesReportParser, self).__init__(cr, uid, name, context=context)
        self.counter = 0
        self.localcontext.update({
            'get_headers': self.get_headers,
            'next_counter': self.get_next_counter,
            'reset_counter': self.reset_counter,
            'to_excel': self.to_excel,
            'get_adjustement': self.get_adjustement,
        })

    @staticmethod
    def to_excel(value):
        if isinstance(value, report_sxw._dttime_format):
            return value.format().replace(' ', 'T')
        return value

    def get_next_counter(self):
        self.counter += 1
        return self.counter

    def reset_counter(self):
        self.counter = 0

    def get_adjustement(self):
        reason_obj = self.pool.get('stock.reason.type')

        pi_rt_ids = reason_obj.search(self.cr, self.uid, [('pi_discrepancy_type', '=', True)])
        all_reason = []
        for x in reason_obj.read(self.cr, self.uid, pi_rt_ids, ['complete_name'], context={'lang': self.localcontext.get('lang')}):
            all_reason.append(x['complete_name'])

        return ','.join(all_reason)

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


SpreadsheetReport('report.physical_inventory_discrepancies_report_xls', 'physical.inventory', 'addons/stock/report/physical_inventory_discrepancies_report_xls.mako', parser=DiscrepanciesReportParser)

report_sxw.report_sxw(
    'report.physical_inventory_discrepancies_report_pdf',
    'physical.inventory',
    'addons/stock/report/physical_inventory_discrepancies_report.rml',
    parser=DiscrepanciesReportParser,
    header=False
)
