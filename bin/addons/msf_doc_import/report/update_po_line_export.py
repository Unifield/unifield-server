# -*- coding: utf-8 -*-
from spreadsheet_xml.xlsx_write import XlsxReport
from spreadsheet_xml.xlsx_write import XlsxReportParser
from tools.translate import _
from openpyxl.cell import WriteOnlyCell
from openpyxl.drawing import image
from PIL import Image as PILImage
from tools import file_open


class update_po_line_export_parser(XlsxReportParser):

    def add_cell(self, value=None, style='default_style'):
        # None value set an xls empty cell
        # False value set the xls False()
        new_cell = WriteOnlyCell(self.workbook.active, value=value)
        new_cell.style = style
        self.rows.append(new_cell)

    def generate(self, context=None):
        if context is None:
            context = {}

        pol_obj = self.pool.get('purchase.order.line')
        wizard = self.pool.get('wizard.update.po.line.import').browse(self.cr, self.uid, self.ids[0], context=context)
        po = wizard.po_id

        sheet = self.workbook.active

        sheet.column_dimensions['A'].width = 7.0
        sheet.column_dimensions['B'].width = 20.0
        sheet.column_dimensions['C'].width = 65.0
        sheet.column_dimensions['D'].width = 65.0
        sheet.column_dimensions['E'].width = 13.0
        sheet.column_dimensions['F'].width = 13.0
        sheet.column_dimensions['G'].width = 17.0
        sheet.column_dimensions['H'].width = 10.0

        sheet.protection.sheet = True

        # Styles
        line_header_style = self.create_style_from_template('line_header_style', 'A1')
        line_style = self.create_style_from_template('line_style', 'B2')
        int_style = self.create_style_from_template('int_style', 'A2')
        float_style = self.create_style_from_template('float_style', 'F2')

        sheet.title = _('Update PO lines')
        row_headers = [
            (_('Line')),
            (_('Product Code')),
            (_('Product Description')),
            (_('Comment')),
            (_('Quantity')),
            (_('Product UoM')),
            (_('Unit Price')),
            (_('Currency')),
        ]

        # Lines data
        row_header = []
        for header in row_headers:
            cell_t = WriteOnlyCell(sheet, value=header)
            cell_t.style = line_header_style
            row_header.append(cell_t)
        sheet.append(row_header)

        pol_domain = [('order_id', '=', po.id), ('state', 'not in', ['cancel', 'cancel_r'])]
        po_line_ids = pol_obj.search(self.cr, self.uid, pol_domain, context=context)
        if po_line_ids:
            ftf = ['line_number', 'product_id', 'comment', 'product_qty', 'product_uom', 'price_unit']
            for line in pol_obj.browse(self.cr, self.uid, po_line_ids, fields_to_fetch=ftf, context=context):
                sheet.append([
                    self.cell_ro(line.line_number, int_style),
                    self.cell_ro(line.product_id and line.product_id.default_code or '', line_style),
                    self.cell_ro(line.product_id and line.product_id.name or '', line_style, wrap_text=True),
                    self.cell_ro(line.comment or '', line_style, unlock=True, wrap_text=True),
                    self.cell_ro(line.product_qty, float_style, unlock=True),
                    self.cell_ro(line.product_uom.name, line_style),
                    self.cell_ro(line.price_unit, float_style, unlock=True),
                    self.cell_ro(po.pricelist_id.currency_id.name, line_style)
                ])


XlsxReport('report.report_update_po_line_export', parser=update_po_line_export_parser, template='addons/msf_doc_import/report/update_po_line_export.xlsx')
