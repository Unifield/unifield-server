# -*- coding: utf-8 -*-

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport


class product_ed_bn_mass_update_export_parser(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(product_ed_bn_mass_update_export_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'parseDateXls': self._parse_date_xls,
        })

    def _parse_date_xls(self, dt_str, is_datetime=True):
        if not dt_str or dt_str == 'False':
            return ''
        if is_datetime:
            dt_str = dt_str[0:10] if len(dt_str) >= 10 else ''
        if dt_str:
            dt_str += 'T00:00:00.000'
        return dt_str


SpreadsheetReport('report.product_ed_bn_mass_update_export_xls', 'product.mass.update', 'addons/product/report/product_ed_bn_mass_update_export_xls.mako', parser=product_ed_bn_mass_update_export_parser)
