# -*- coding: utf-8 -*-
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport


class product_stock_out_parser(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(product_stock_out_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
        })

SpreadsheetReport('report.report_product_stock_out_xls', 'product.stock_out', 'addons/procurement_cycle/report/product_stock_out.mako', parser=product_stock_out_parser)

