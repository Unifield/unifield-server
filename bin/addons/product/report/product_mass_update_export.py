# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from tools.translate import _


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
