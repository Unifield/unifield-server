# -*- coding: utf-8 -*-
from osv import osv
from tools.translate import _
from datetime import datetime
from spreadsheet_xml.xlsx_write import XlsxReport
from spreadsheet_xml.xlsx_write import XlsxReportParser
from openpyxl.cell import WriteOnlyCell


class catalogue_export_track_changes_report_xlsx(XlsxReportParser):

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

        ftf = ['name', 'partner_id']
        catalogue = self.pool.get('supplier.catalogue').browse(self.cr, self.uid, self.ids[0], fields_to_fetch=ftf, context=context)
        if catalogue.partner_id.partner_type != 'external':
            raise osv.except_osv(_('Error'), _('This export is only available for Catalogues of External Partners'))
        sheet = self.workbook.active

        sheet.column_dimensions['A'].width = 10.0
        sheet.column_dimensions['B'].width = 20.0
        sheet.column_dimensions['C'].width = 15.0
        sheet.column_dimensions['D'].width = 15.0
        sheet.column_dimensions['E'].width = 15.0
        sheet.column_dimensions['F'].width = 30.0
        sheet.column_dimensions['G'].width = 50.0
        sheet.column_dimensions['H'].width = 50.0
        sheet.column_dimensions['I'].width = 25.0

        # Styles
        self.create_style_from_template('default_style', 'J1')

        big_title_style = self.create_style_from_template('big_title_style', 'A1')

        line_header_style = self.create_style_from_template('line_header_style', 'A2')
        line_style = self.create_style_from_template('line_style', 'A3')
        date_style = self.create_style_from_template('date_style', 'B3')

        sheet.title = 'Catalogue Track changes'
        # Header data
        sheet.row_dimensions[1].height = 25
        cell_title = WriteOnlyCell(sheet, value=_('Catalogue %s - Track changes') % (catalogue.name,))
        cell_title.style = big_title_style
        self.apply_template_style('A1', cell_title)
        sheet.append([cell_title])
        sheet.merged_cells.ranges.append("A1:I1")

        row_headers = [
            (_('Log ID')),
            (_('Date')),
            (_('Sequence')),
            (_('Description')),
            (_('Method')),
            (_('Field Description')),
            (_('Old Value')),
            (_('New Value')),
            (_('User')),
        ]

        # Lines data
        row_header = []
        for header in row_headers:
            cell_t = WriteOnlyCell(sheet, value=header)
            cell_t.style = line_header_style
            row_header.append(cell_t)
        sheet.append(row_header)

        # Get data of the track changes for the catalogue
        model_ids = self.pool.get('ir.model').search(self.cr, self.uid, [('model', '=', 'supplier.catalogue')], context=context)
        audll_obj = self.pool.get('audittrail.log.line')
        cat_domain = [('res_id', '=', catalogue.id), ('object_id', '=', model_ids[0])]
        audll_ids = audll_obj.search(self.cr, self.uid, cat_domain, order='log desc', context=context)
        for audll in audll_obj.browse(self.cr, self.uid, audll_ids, context=context):
            self.rows = []

            self.add_cell(audll.log or '', line_style)
            self.add_cell(audll.timestamp and datetime.strptime(audll.timestamp, '%Y-%m-%d %H:%M:%S') or '',
                          date_style, number_format='DD/MM/YYYY HH:MM:SS')
            self.add_cell(audll.other_column or '', line_style)
            self.add_cell(self.getSel(audll, 'sub_obj_name') or '', line_style)
            self.add_cell(self.getSel(audll, 'method') or '', line_style)
            self.add_cell(audll.field_description or '', line_style)
            self.add_cell(audll.old_value_text or '', line_style)
            self.add_cell(audll.new_value_text or '', line_style)
            self.add_cell(audll.user_id.name or '', line_style)

            sheet.append(self.rows)


XlsxReport('report.catalogue.export.track.changes', parser=catalogue_export_track_changes_report_xlsx,
           template='addons/supplier_catalogue/report/catalogue_export_track_changes_report.xlsx')
