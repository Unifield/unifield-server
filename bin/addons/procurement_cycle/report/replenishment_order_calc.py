# -*- coding: utf-8 -*-
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport


class order_calc_parser(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(order_calc_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'only_warning': lambda *a : False,
        })

SpreadsheetReport('report.report_replenishment_order_calc_xls', 'replenishment.order_calc', 'addons/procurement_cycle/report/replenishment_order_calc.mako', parser=order_calc_parser)

class order_calc_warning_parser(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(order_calc_warning_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'only_warning': lambda *a : True,
        })

SpreadsheetReport('report.report_replenishment_order_calc_warning_xls', 'replenishment.order_calc', 'addons/procurement_cycle/report/replenishment_order_calc.mako', parser=order_calc_warning_parser)
