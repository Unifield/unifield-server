# -*- coding: utf-8 -*-

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport


class product_ed_bn_mass_update_export_parser(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(product_ed_bn_mass_update_export_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'getData': self.get_data,
        })

    def get_data(self, update_id):
        upd_hist_obj = self.pool.get('product.ed_bn.mass.update.history')

        hist_data = []
        if not update_id:
            return hist_data

        upd_hist_line_ids = upd_hist_obj.search(self.cr, self.uid, [('p_mass_upd_id', '=', update_id)], context=self.localcontext)
        for hist_line in upd_hist_obj.browse(self.cr, self.uid, upd_hist_line_ids, context=self.localcontext):
            hist_data.append({
                'default_code': hist_line.product_id.default_code,
                'description': hist_line.product_id.name,
                'old_bn': hist_line.old_bn,
                'old_ed': hist_line.old_ed,
            })

        return hist_data


SpreadsheetReport('report.product_ed_bn_mass_update_export_xls', 'product.mass.update', 'addons/product/report/product_ed_bn_mass_update_export_xls.mako', parser=product_ed_bn_mass_update_export_parser)
