# -*- coding: utf-8 -*-
from spreadsheet_xml.xlsx_write import XlsxReport
from spreadsheet_xml.xlsx_write import XlsxReportParser
from tools.translate import _
from datetime import datetime
from openpyxl.cell import WriteOnlyCell
from openpyxl.drawing import image
from PIL import Image as PILImage
from tools import file_open


class return_from_unit_parser(XlsxReportParser):

    def add_cell(self, value=None, style='default_style'):
        # None value set an xls empty cell
        # False value set the xls False()
        new_cell = WriteOnlyCell(self.workbook.active, value=value)
        new_cell.style = style
        self.rows.append(new_cell)

    def generate(self, context=None):
        wizard = self.pool.get('wizard.return.from.unit.import').browse(self.cr, self.uid, self.ids[0], context=context)
        pick = wizard.picking_id

        sheet = self.workbook.active
        sheet.sheet_view.showGridLines = False

        # MSF logo
        img = image.Image(PILImage.open(file_open('addons/msf_doc_import/report/images/msf-logo.png', 'rb')))
        img.anchor = 'A1'
        sheet.add_image(img)

        sheet.column_dimensions['A'].width = 7.0
        sheet.column_dimensions['B'].width = 20.0
        sheet.column_dimensions['C'].width = 65.0
        sheet.column_dimensions['D'].width = 15.0
        sheet.column_dimensions['E'].width = 10.0
        sheet.column_dimensions['F'].width = 20.0
        sheet.column_dimensions['G'].width = 20.0
        sheet.column_dimensions['H'].width = 65.0

        sheet.append([])
        sheet.append([])
        sheet.append([])
        sheet.append([])
        sheet.append([])

        # Styles
        default_style = self.create_style_from_template('default_style', 'A1')

        big_title_style = self.create_style_from_template('big_title_style', 'C6')
        medium_title_style = self.create_style_from_template('medium_title_style', 'F6')
        boldl_open_bottom_style = self.create_style_from_template('boldl_open_bottom_style', 'C8')
        boldr_open_bottom_style = self.create_style_from_template('boldr_open_bottom_style', 'D8')
        openl_top_style = self.create_style_from_template('openl_top_style', 'C9')
        openr_top_style = self.create_style_from_template('openr_top_style', 'D9')
        date_style = self.create_style_from_template('date_style', 'J2')
        bold_frame = self.create_style_from_template('bold_frame', 'B24')
        frame = self.create_style_from_template('frame', 'B27')

        line_header_style = self.create_style_from_template('line_header_style', 'A12')
        line_right_style = self.create_style_from_template('line_right_style', 'A13')
        line_style = self.create_style_from_template('line_style', 'B13')
        line_date_style = self.create_style_from_template('line_date_style', 'J3')
        float_style = self.create_style_from_template('float_style', 'J4')

        sheet.title = _('Return from Unit')
        # Empty cells
        cell_empty = WriteOnlyCell(sheet)
        cell_empty.style = default_style
        cell_empty_date = WriteOnlyCell(sheet)
        cell_empty_date.style = date_style

        # Header data
        cell_empty_title = WriteOnlyCell(sheet)
        cell_empty_title.style = big_title_style
        cell_title = WriteOnlyCell(sheet, value=_('Return of Products'))
        cell_title.style = big_title_style
        self.apply_template_style('C6', cell_title)
        cell_r = WriteOnlyCell(sheet, value=_('Ref:'))
        cell_r.style = medium_title_style
        cell_iname = WriteOnlyCell(sheet, value=pick.name)
        cell_iname.style = default_style
        sheet.append([cell_empty, cell_empty, cell_title, cell_empty_title, cell_empty, cell_r, cell_iname])
        sheet.merged_cells.ranges.append("C6:D6")

        sheet.append([])

        cell_ft = WriteOnlyCell(sheet, value=_('From:'))
        cell_ft.style = boldl_open_bottom_style
        cell_tt = WriteOnlyCell(sheet, value=_('To:'))
        cell_tt.style = boldl_open_bottom_style
        cell_empty_r_open_bottom = WriteOnlyCell(sheet)
        cell_empty_r_open_bottom.style = boldr_open_bottom_style
        sheet.append([cell_empty, cell_empty, cell_ft, cell_empty_r_open_bottom, cell_empty, cell_tt, cell_empty_r_open_bottom])
        sheet.merged_cells.ranges.append("C8:D8")
        sheet.merged_cells.ranges.append("F8:G8")

        sheet.row_dimensions[9].height = 70
        cell_ext_cu = WriteOnlyCell(sheet, value=pick.ext_cu.name)
        cell_ext_cu.style = openl_top_style
        cell_empty_l_open_top = WriteOnlyCell(sheet)
        cell_empty_l_open_top.style = openl_top_style
        cell_empty_r_open_top = WriteOnlyCell(sheet)
        cell_empty_r_open_top.style = openr_top_style
        sheet.append([cell_empty, cell_empty, cell_ext_cu, cell_empty_r_open_top, cell_empty, cell_empty_l_open_top, cell_empty_r_open_top])
        sheet.merged_cells.ranges.append("C9:D9")
        sheet.merged_cells.ranges.append("F9:G9")

        sheet.append([])

        cell_sd = WriteOnlyCell(sheet, value=_('Creation Date: %s') % (datetime.strptime(pick.date, '%Y-%m-%d %H:%M:%S').strftime("%d/%m/%Y %H:%M"),))
        cell_sd.style = default_style
        cell_dd = WriteOnlyCell(sheet, value=_('Expected Receipt Date: %s') % (datetime.strptime(pick.min_date, '%Y-%m-%d %H:%M:%S').strftime("%d/%m/%Y %H:%M"),))
        cell_dd.style = default_style
        sheet.append([cell_empty, cell_empty, cell_sd, cell_empty_date, cell_empty, cell_empty, cell_dd, cell_empty_date])
        sheet.merged_cells.ranges.append("G11:H11")

        row_headers = [
            (_('Line')),
            (_('Product Code')),
            (_('Product Description')),
            (_('Quantity')),
            (_('UoM')),
            (_('Batch Number')),
            (_('Expiry Date')),
            (_('Comment')),
        ]

        # Lines data
        row_header = []
        for header in row_headers:
            cell_t = WriteOnlyCell(sheet, value=header)
            cell_t.style = line_header_style
            row_header.append(cell_t)
        sheet.append(row_header)

        new_row = 13
        while new_row < 23:
            self.rows = []

            self.add_cell(str(new_row - 12), line_right_style)
            self.add_cell('', line_style)
            self.add_cell('', line_style)
            self.add_cell('', float_style)
            self.add_cell('', line_style)
            self.add_cell('', line_style)
            self.add_cell('', line_date_style)
            self.add_cell('', line_style)

            sheet.append(self.rows)
            new_row += 1

        # Bottom data
        sheet.append([])

        sheet.row_dimensions[24].height = 25
        cell_sng = WriteOnlyCell(sheet, value=_('Sent by:'))
        cell_sng.style = bold_frame
        cell_sng2 = WriteOnlyCell(sheet, value=_('Received by:'))
        cell_sng2.style = bold_frame
        cell_empty_b_frame = WriteOnlyCell(sheet)
        cell_empty_b_frame.style = bold_frame
        sheet.append([cell_empty, cell_sng, cell_empty_b_frame, cell_empty, cell_empty, cell_empty, cell_sng2, cell_empty_b_frame])
        sheet.merged_cells.ranges.append("B24:C24")
        sheet.merged_cells.ranges.append("G24:H24")

        sheet.append([])
        sheet.append([])

        sheet.row_dimensions[27].height = 25
        cell_dp = WriteOnlyCell(sheet, value=_('Date and place:'))
        cell_dp.style = frame
        cell_empty_frame = WriteOnlyCell(sheet)
        cell_empty_frame.style = frame
        sheet.append([cell_empty, cell_dp, cell_empty_frame, cell_empty, cell_empty, cell_empty, cell_dp, cell_empty_frame])
        sheet.merged_cells.ranges.append("B27:C27")
        sheet.merged_cells.ranges.append("G27:H27")


XlsxReport('report.report_return_from_unit_xls', parser=return_from_unit_parser, template='addons/msf_doc_import/report/return_from_unit_export.xlsx')

