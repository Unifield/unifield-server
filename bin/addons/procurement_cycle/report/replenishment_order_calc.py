# -*- coding: utf-8 -*-
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from osv import osv

def get_lines(self, objects):
    if not self.localcontext['is_multi']:
        return objects[0].order_calc_line_ids
    else:
        return sorted([x for y in objects for x in y.order_calc_line_ids], key=lambda line: line.product_id.default_code)

class order_calc_parser(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(order_calc_parser, self).__init__(cr, uid, name, context=context)
        raise osv.except_osv('oo', 'ooo')
        self.localcontext.update({
            'only_warning': lambda *a : False,
            'is_multi': lambda *a : False,
            'with_state': lambda *a : False,
            'get_lines': lambda *a: get_lines(self, *a),
        })

SpreadsheetReport('report.report_replenishment_order_calc_xls', 'replenishment.order_calc', 'addons/procurement_cycle/report/replenishment_order_calc.mako', parser=order_calc_parser)

class order_calc_warning_parser(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(order_calc_warning_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'only_warning': lambda *a : True,
            'is_multi': lambda *a : False,
            'with_state': lambda *a : False,
            'get_lines': lambda *a: get_lines(self, *a),
        })

SpreadsheetReport('report.report_replenishment_order_calc_warning_xls', 'replenishment.order_calc', 'addons/procurement_cycle/report/replenishment_order_calc.mako', parser=order_calc_warning_parser)

class order_calc_draft_consolidated_parser(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(order_calc_draft_consolidated_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'only_warning': lambda *a : False,
            'is_multi': lambda *a : True,
            'with_state': lambda *a : False,
            'get_lines': lambda *a: get_lines(self, *a),
        })

SpreadsheetReport('report.report_replenishment_order_calc_draft_consolidated_xls', 'replenishment.order_calc', 'addons/procurement_cycle/report/replenishment_order_calc.mako', parser=order_calc_draft_consolidated_parser)

class order_calc_all_consolidated_parser(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(order_calc_all_consolidated_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'only_warning': lambda *a : False,
            'is_multi': lambda *a : True,
            'with_state': lambda *a : True,
            'get_lines': lambda *a: get_lines(self, *a),
        })

SpreadsheetReport('report.report_replenishment_order_calc_consolidated_xls', 'replenishment.order_calc', 'addons/procurement_cycle/report/replenishment_order_calc.mako', parser=order_calc_all_consolidated_parser)
