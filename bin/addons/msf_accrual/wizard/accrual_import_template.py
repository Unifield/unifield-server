# -*- coding: utf-8 -*-
from spreadsheet_xml.xlsx_write import XlsxReport
from spreadsheet_xml.xlsx_write import XlsxReportParser
from tools.translate import _
from openpyxl.cell import WriteOnlyCell


class accrual_import_parser(XlsxReportParser):
    def generate(self, context=None):
        sheet = self.workbook.active
        sheet.sheet_view.showGridLines = True

        sheet.column_dimensions['A'].width = 40.0
        sheet.column_dimensions['B'].width = 15.0
        sheet.column_dimensions['C'].width = 25.0
        sheet.column_dimensions['D'].width = 30.0
        sheet.column_dimensions['E'].width = 15.0
        sheet.column_dimensions['F'].width = 15.0
        sheet.column_dimensions['G'].width = 15.0
        sheet.column_dimensions['H'].width = 15.0

        sheet.title = _('Accrual Lines')
        self.create_style_from_template('header_style', 'A1')

        header = [
            (_('Description')),
            (_('Reference')),
            (_('Expense Account')),
            (_('Accrual Amount Booking')),
            (_('Percentage')),
            (_('Cost Center')),
            (_('Destination')),
            (_('Funding Pool')),
        ]
        sheet.append([self.cell_ro(h, 'header_style') for h in header])


XlsxReport('report.accrual_import_template_xlsx', parser=accrual_import_parser, template='addons/msf_accrual/wizard/Accrual_Lines_Import_Template_File.xlsx')
