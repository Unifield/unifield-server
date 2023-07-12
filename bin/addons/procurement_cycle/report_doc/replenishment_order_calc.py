# -*- coding: utf-8 -*-
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from tools.translate import _


def get_lines(self, objects):
    if not self.localcontext['is_multi']:
        return objects[0].order_calc_line_ids
    else:
        return sorted([x for y in objects for x in y.order_calc_line_ids], key=lambda line: line.product_id.default_code)


def get_export_title(self):
    title = _('Order Calc Excel Export')
    if self.localcontext['only_warning']():
        title = _('Order Calc With Warning')
    elif self.localcontext['is_multi']():
        if self.localcontext['with_state']():
            title = _('All Consolidated OC Lines')
        else:
            title = _('Draft Consolidated OC Lines')

    return title


class order_calc_parser(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(order_calc_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'only_warning': lambda *a : False,
            'is_multi': lambda *a : False,
            'with_state': lambda *a : False,
            'get_lines': lambda *a: get_lines(self, *a),
            'get_export_title': lambda *a: get_export_title(self),
        })


SpreadsheetReport('report.report_replenishment_order_calc_xls', 'replenishment.order_calc', 'addons/procurement_cycle/report_doc/replenishment_order_calc.mako', parser=order_calc_parser)


class order_calc_warning_parser(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(order_calc_warning_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'only_warning': lambda *a : True,
            'is_multi': lambda *a : False,
            'with_state': lambda *a : False,
            'get_lines': lambda *a: get_lines(self, *a),
            'get_export_title': lambda *a: get_export_title(self),
        })


SpreadsheetReport('report.report_replenishment_order_calc_warning_xls', 'replenishment.order_calc', 'addons/procurement_cycle/report_doc/replenishment_order_calc.mako', parser=order_calc_warning_parser)


class order_calc_draft_consolidated_parser(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(order_calc_draft_consolidated_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'only_warning': lambda *a : False,
            'is_multi': lambda *a : True,
            'with_state': lambda *a : False,
            'get_lines': lambda *a: get_lines(self, *a),
            'get_export_title': lambda *a: get_export_title(self),
        })


SpreadsheetReport('report.report_replenishment_order_calc_draft_consolidated_xls', 'replenishment.order_calc', 'addons/procurement_cycle/report_doc/replenishment_order_calc.mako', parser=order_calc_draft_consolidated_parser)


class order_calc_all_consolidated_parser(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(order_calc_all_consolidated_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'only_warning': lambda *a : False,
            'is_multi': lambda *a : True,
            'with_state': lambda *a : True,
            'get_lines': lambda *a: get_lines(self, *a),
            'get_export_title': lambda *a: get_export_title(self),
        })


SpreadsheetReport('report.report_replenishment_order_calc_consolidated_xls', 'replenishment.order_calc', 'addons/procurement_cycle/report_doc/replenishment_order_calc.mako', parser=order_calc_all_consolidated_parser)
