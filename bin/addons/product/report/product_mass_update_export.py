# -*- coding: utf-8 -*-

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport


class product_mass_update_export_parser(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(product_mass_update_export_parser, self).__init__(cr, uid, name, context=context)
        self.counter = 0
        self.localcontext.update({
            'getErrors': self.get_errors,
        })

    def get_errors(self):
        upd_errors = []

        if not self.ids:
            return upd_errors

        for upd_error in self.pool.get('product.mass.update').browse(self.cr, self.uid, self.ids[0], fields_to_fetch=['not_deactivated_product_ids'], context=self.localcontext).not_deactivated_product_ids:
            upd_errors.append({
                'default_code': upd_error.product_id.default_code,
                'name': upd_error.product_id.name,
                'stock_exist': upd_error.stock_exist,
                'qty_available': upd_error.product_id.qty_available,
                'virtual_available': upd_error.product_id.virtual_available,
                'open_documents': upd_error.open_documents,
            })

        return upd_errors


SpreadsheetReport('report.product_mass_update_export_xls', 'product.mass.update', 'addons/product/report/product_mass_update_export_xls.mako', parser=product_mass_update_export_parser)
