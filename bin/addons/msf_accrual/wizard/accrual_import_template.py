# -*- coding: utf-8 -*-
from spreadsheet_xml.xlsx_write import XlsxReport
from spreadsheet_xml.xlsx_write import XlsxReportParser
from tools.translate import _
from openpyxl.cell import WriteOnlyCell
from openpyxl import Workbook


class accrual_import_parser(XlsxReportParser):

    def add_cell(self, value=None, style='default_style'):
        # None value set an xls empty cell
        # False value set the xls False()
        new_cell = WriteOnlyCell(self.workbook.active, value=value)
        new_cell.style = style
        self.rows.append(new_cell)

    def generate(self, context=None):
        sheet = self.workbook.active
        sheet.sheet_view.showGridLines = True

        sheet.column_dimensions['A'].width = 40.0
        sheet.column_dimensions['B'].width = 15.0
        sheet.column_dimensions['C'].width = 15.0
        sheet.column_dimensions['D'].width = 15.0
        sheet.column_dimensions['E'].width = 15.0
        sheet.column_dimensions['F'].width = 15.0
        sheet.column_dimensions['G'].width = 15.0

        sheet.title = _('Accrual Lines')
        self.create_style_from_template('header_style', 'A1')

        header = [
            (_('Description')),
            (_('Account')),
            (_('Quantity')),
            (_('Unit Price')),
            (_('Destination')),
            (_('Cost Center')),
            (_('Funding Pool')),
        ]
        sheet.append([self.cell_ro(h, 'header_style') for h in header])


XlsxReport('report.accrual_import_template_xlsx', parser=accrual_import_parser, template='addons/msf_accrual/wizard/Accrual_Lines_Import_Template_File.xlsx')
