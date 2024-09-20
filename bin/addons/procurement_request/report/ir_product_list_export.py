# -*- coding: utf-8 -*-
from osv import osv
from tools.translate import _
from datetime import datetime
from spreadsheet_xml.xlsx_write import XlsxReport
from spreadsheet_xml.xlsx_write import XlsxReportParser
from openpyxl.cell import WriteOnlyCell


class ir_product_list_export(XlsxReportParser):

    def add_cell(self, value=None, style='default_style', number_format=None):
        # None value set an xls empty cell
        # False value set the xls False()
        new_cell = WriteOnlyCell(self.workbook.active, value=value)
        new_cell.style = style
        if number_format:
            new_cell.number_format = number_format
        self.rows.append(new_cell)

    def generate(self, context=None):
        if context is None:
            context = {}

        wiz = self.pool.get('ir.product.list.export.wizard').browse(self.cr, self.uid, self.ids[0], context=context)
        p_list = wiz and wiz.product_list_id or False

        sheet = self.workbook.active

        sheet.column_dimensions['A'].width = 30.0
        sheet.column_dimensions['B'].width = 70.0
        sheet.column_dimensions['C'].width = 15.0
        sheet.column_dimensions['D'].width = 20.0

        # Styles
        self.create_style_from_template('default_style', 'E1')

        big_title_style = self.create_style_from_template('big_title_style', 'A1')

        line_header_style = self.create_style_from_template('line_header_style', 'A2')
        line_style = self.create_style_from_template('line_style', 'B2')
        number_style = self.create_style_from_template('number_style', 'C10')
        date_style = self.create_style_from_template('date_style', 'D10')

        sheet.title = 'IR_Product_List_Export'
        # Header data
        sheet.row_dimensions[1].height = 20
        cell_title = WriteOnlyCell(sheet, value=_('INTERNAL REQUEST'))
        cell_title.style = big_title_style
        self.apply_template_style('A1', cell_title)
        sheet.append([cell_title])
        sheet.merged_cells.ranges.append("A1:D1")

        cell_empty = WriteOnlyCell(sheet)
        cell_empty.style = line_style

        top_headers = [
            (_('Priority')),
            (_('Requested Date')),
            (_('Requestor')),
            (_('Location Requestor')),
            (_('Origin')),
            (_('Details')),
            (_('Functional Currency')),
        ]
        for top_header in top_headers:
            cell_th = WriteOnlyCell(sheet, value=top_header)
            cell_th.style = line_header_style
            sheet.append([cell_th, cell_empty])

        # Lines data
        row_headers = [
            (_('Product Code')),
            (_('Product Description')),
            (_('Quantity')),
            (_('Date of Stock Take')),
        ]
        row_header = []
        for header in row_headers:
            cell_t = WriteOnlyCell(sheet, value=header)
            cell_t.style = line_header_style
            row_header.append(cell_t)
        sheet.append(row_header)

        # Get data from the product list
        if p_list:
            for list_line in p_list.product_ids:
                self.rows = []

                self.add_cell(list_line.ref, line_style)
                self.add_cell(list_line.desc, line_style)
                self.add_cell(0, number_style)
                self.add_cell('', date_style, number_format='DD/MM/YYYY')

                sheet.append(self.rows)
        else:
            self.rows = []

            self.add_cell('', line_style)
            self.add_cell('', line_style)
            self.add_cell(0, number_style)
            self.add_cell('', date_style, number_format='DD/MM/YYYY')

            sheet.append(self.rows)


XlsxReport('report.report_ir_product_list_export', parser=ir_product_list_export,
           template='addons/procurement_request/report/ir_product_list_export.xlsx')
