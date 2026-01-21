# -*- coding: utf-8 -*-
from osv import osv
from spreadsheet_xml.xlsx_write import XlsxReport
from spreadsheet_xml.xlsx_write import XlsxReportParser
from tools.translate import _
from datetime import datetime
from openpyxl.cell import WriteOnlyCell


class tkc_kcl_comparison_parser(XlsxReportParser):

    def add_cell(self, value=None, style='default_style', number_format=None):
        # None value set an xls empty cell
        # False value set the xls False()
        new_cell = WriteOnlyCell(self.workbook.active, value=value)
        new_cell.style = style
        if number_format:
            new_cell.number_format = number_format
        self.rows.append(new_cell)

    def generate(self, context=None):
        kcl = self.pool.get('wizard.return.from.unit.import').browse(self.cr, self.uid, self.ids[0], context=context)

        if not kcl.composition_version_id:
            raise osv.except_osv(_('Error'), _('You can only generate this report on a KCL using a Version'))

        sheet = self.workbook.active
        self.duplicate_column_dimensions(default_width=10.75)

        # Styles
        default_style = self.create_style_from_template('default_style', 'A3')

        title_style = self.create_style_from_template('title_style', 'A22')
        header_style = self.create_style_from_template('header_style', 'A1')
        header_dark_style = self.create_style_from_template('header_dark_style', 'N29')
        header_bold_style = self.create_style_from_template('header_bold_style', 'A4')
        header_blue_style = self.create_style_from_template('header_blue_style', 'E29')
        line_style = self.create_style_from_template('line_style', 'B1')
        line_grey_style = self.create_style_from_template('line_grey_style', 'A10')
        line_dark_grey_style = self.create_style_from_template('line_dark_grey_style', 'A30')
        line_date_style = self.create_style_from_template('line_date_style', 'B2')
        line_float_style = self.create_style_from_template('line_float_style', 'F31')
        line_float_dark_grey_style = self.create_style_from_template('line_float_dark_grey_style', 'F30')

        # Header data: 4 frames
        cell_1_db_title = WriteOnlyCell(sheet, value=_('DB/Instance name'))
        cell_1_db_title.style = header_style
        instance_name = self.pool.get('res.users').browse(self.cr, self.uid, [self.uid], context=context)[0].company_id.instance_id.name
        cell_1_db_name = WriteOnlyCell(sheet, value=instance_name or '')
        cell_1_db_name.style = line_style
        sheet.append([cell_1_db_title, cell_1_db_name])
        sheet.merged_cells.ranges.append("B1:C1")

        cell_1_generated_title = WriteOnlyCell(sheet, value=_('Generated on'))
        cell_1_db_title.style = header_style
        cell_1_generated_name = WriteOnlyCell(sheet, value=datetime.now().strftime('%Y-%m-%d'))
        cell_1_generated_name.style = line_date_style
        sheet.append([cell_1_generated_title, cell_1_generated_name])
        sheet.merged_cells.ranges.append("B2:C2")

        sheet.append([])

        cell_2_title = WriteOnlyCell(sheet, value=_('Theoretical Kit Composition details'))
        cell_2_title.style = header_bold_style
        sheet.append([cell_2_title])
        sheet.merged_cells.ranges.append("A4:C4")

        cell_2_prod_title = WriteOnlyCell(sheet, value=_('TKC/Product'))
        cell_2_prod_title.style = header_style
        cell_2_prod_name = WriteOnlyCell(sheet, value=kcl.composition_version_id.composition_product_id.name)
        cell_2_prod_name.style = line_style
        sheet.append([cell_2_prod_title, cell_2_prod_name])
        sheet.merged_cells.ranges.append("B5:C5")

        cell_2_ver_title = WriteOnlyCell(sheet, value=_('TKC/Version'))
        cell_2_ver_title.style = header_style
        cell_2_ver_name = WriteOnlyCell(sheet, value=kcl.composition_version_id.composition_version_txt)
        cell_2_ver_name.style = line_style
        sheet.append([cell_2_ver_title, cell_2_ver_name])
        sheet.merged_cells.ranges.append("B6:C6")

        cell_2_date_title = WriteOnlyCell(sheet, value=_('TKC/Creation Date'))
        cell_2_date_title.style = header_style
        cell_2_date_name = WriteOnlyCell(sheet, value=kcl.composition_version_id.composition_creation_date)
        cell_2_date_name.style = line_date_style
        sheet.append([cell_2_date_title, cell_2_date_name])
        sheet.merged_cells.ranges.append("B7:C7")

        cell_2_active_title = WriteOnlyCell(sheet, value=_('TKC/Active'))
        cell_2_active_title.style = header_style
        cell_2_active_name = WriteOnlyCell(sheet, value=kcl.composition_version_id.active and _('Yes') or _('No'))
        cell_2_active_name.style = line_style
        sheet.append([cell_2_active_title, cell_2_active_name])
        sheet.merged_cells.ranges.append("B8:C8")

        cell_notes = WriteOnlyCell(sheet, value=_('Notes'))
        cell_notes.style = header_style
        sheet.append([cell_notes])
        sheet.merged_cells.ranges.append("A9:C9")

        sheet.row_dimensions[9].height = 30
        cell_notes2 = WriteOnlyCell(sheet, value='')
        cell_notes2.style = line_grey_style
        sheet.append([cell_notes2])
        sheet.merged_cells.ranges.append("A10:C10")

        sheet.append([])

        cell_3_title = WriteOnlyCell(sheet, value=_('Kit Composition List details'))
        cell_3_title.style = header_bold_style
        sheet.append([cell_3_title])
        sheet.merged_cells.ranges.append("A12:C12")

        cell_3_prod_title = WriteOnlyCell(sheet, value=_('KCL/Product'))
        cell_3_prod_title.style = header_style
        cell_3_prod_name = WriteOnlyCell(sheet, value=kcl.composition_product_id.name)
        cell_3_prod_name.style = line_style
        sheet.append([cell_3_prod_title, cell_3_prod_name])
        sheet.merged_cells.ranges.append("B13:C13")

        cell_3_ver_title = WriteOnlyCell(sheet, value=_('KCL/Version'))
        cell_3_ver_title.style = header_style
        sheet.append([cell_3_ver_title, cell_2_ver_name])
        sheet.merged_cells.ranges.append("B14:C14")

        cell_3_bn_title = WriteOnlyCell(sheet, value=_('KCL/Batch Nb'))
        cell_3_bn_title.style = header_style
        cell_3_bn_name = WriteOnlyCell(sheet, value=kcl.composition_lot_id and kcl.composition_lot_id.name or '')
        cell_3_bn_name.style = line_style
        sheet.append([cell_3_bn_title, cell_3_bn_name])
        sheet.merged_cells.ranges.append("B15:C15")

        cell_3_exp_title = WriteOnlyCell(sheet, value=_('KCL/Expiry Date'))
        cell_3_exp_title.style = header_style
        cell_3_exp_name = WriteOnlyCell(sheet, value=kcl.composition_exp)
        cell_3_exp_name.style = line_date_style
        sheet.append([cell_3_exp_title, cell_3_exp_name])
        sheet.merged_cells.ranges.append("B16:C16")

        cell_3_date_title = WriteOnlyCell(sheet, value=_('KCL/Creation Date'))
        cell_3_date_title.style = header_style
        cell_3_date_name = WriteOnlyCell(sheet, value=kcl.composition_creation_date)
        cell_3_date_name.style = line_date_style
        sheet.append([cell_3_date_title, cell_3_date_name])
        sheet.merged_cells.ranges.append("B17:C17")

        sheet.append([cell_notes])
        sheet.merged_cells.ranges.append("A18:C18")

        sheet.row_dimensions[19].height = 30
        sheet.append([cell_notes2])
        sheet.merged_cells.ranges.append("A19:C19")

        sheet.append([])


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


XlsxReport('report.report_tkc_kcl_comparison', parser=tkc_kcl_comparison_parser, template='addons/kit/report/tkc_kcl_comparison_report.xlsx')

