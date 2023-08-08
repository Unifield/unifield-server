# -*- coding: utf-8 -*-
from osv import fields, osv
from tools.translate import _
assert _ # pyflakes
from tools import misc
import time
from time import strptime
import netsvc
import os
import threading
from datetime import datetime
from spreadsheet_xml.xlsx_write import XlsxReport
from spreadsheet_xml.xlsx_write import XlsxReportParser
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment
import tools


class field_balance_spec_report(osv.osv_memory):
    _name = "field.balance.spec.report"

    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Top proprietary instance', required=True),
        'fiscalyear_id': fields.many2one('account.fiscalyear', 'Fiscal year', required=True),
        'period_id': fields.many2one('account.period', 'Period', required=True),
        'selection': fields.selection([('entries_total', 'Total of entries reconciled in later period'),
                                       ('entries_details', 'Details of entries reconciled in later period')],
                                      string="Select", required=True),
        'eoy': fields.boolean('End of Year'),
    }

    _defaults = {
        'fiscalyear_id': lambda self, cr, uid, c: self.pool.get('account.fiscalyear').find(cr, uid, time.strftime('%Y-%m-%d'), context=c),
        'selection': lambda *a: 'entries_total',
    }

    def button_create_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        report = self.browse(cr, uid, ids[0], context=context)
        data = {}
        data['form'] = {}
        mission_instance = ''
        year = ''
        period_name = ''
        if report.instance_id:
            mission_instance = "%s" % report.instance_id.instance
        if report.period_id:
            period_name = report.period_id.name or ''
            data['form'].update({'period_id': report.period_id.id})
        data['form'].update({'selection': report.selection})
        data['target_filename'] = '%s - %s - Field Balance specification report' % (mission_instance, period_name)
        data['context'] = context
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'field_balance_spec_report',
            'datas': data,
            'context': context,
        }

field_balance_spec_report()


class field_balance_spec_parser(XlsxReportParser):
    _name = "field.balance.spec.parser"

    def add_cell(self, value=None, style='default_style'):
        # None value set an xls empty cell
        # False value set the xls False()
        new_cell = WriteOnlyCell(self.workbook.active, value=value)
        new_cell.style = style
        self.rows.append(new_cell)

    def generate(self, context=None):

        SUB_RT_SEL = {
            'encoding_err': _('Encoding Error'),
            'process_err': _('Process Error'),
            'pick_err': _('Picking Error'),
            'recep_err': _('Reception Error'),
            'bn_err': _('Batch Number related Error'),
            'unexpl_err': _('Unjustified/Unexplained Error')
        }

        sheet = self.workbook.active
        sheet.sheet_view.showGridLines = True

        sheet.column_dimensions['A'].width = 12.0
        sheet.column_dimensions['B'].width = 25.0
        sheet.column_dimensions['C'].width = 22.0
        sheet.column_dimensions['D'].width = 12.0
        sheet.column_dimensions['E'].width = 5.0
        sheet.column_dimensions['F'].width = 12.0
        sheet.column_dimensions['G'].width = 12.0
        sheet.column_dimensions['H'].width = 15.0
        sheet.column_dimensions['I'].width = 7.0
        sheet.column_dimensions['J'].width = 20.0
        sheet.column_dimensions['K'].width = 25.0
        sheet.column_dimensions['L'].width = 25.0

        # Styles
        default_style = self.create_style_from_template('default_style', 'F10')

        big_title_style = self.create_style_from_template('big_title_style', 'A1')
        bold_blue_style = self.create_style_from_template('bold_blue_style', 'A3')
        empty_blue_frame = self.create_style_from_template('empty_blue_frame', 'B5')
        grey_bold_frame = self.create_style_from_template('grey_bold_frame', 'A9')
        empty_grey_frame = self.create_style_from_template('empty_grey_frame', 'B9')
        blue_date_frame = self.create_style_from_template('blue_date_frame', 'C5')

        line_header_style = self.create_style_from_template('line_header_style', 'A9')
        top_line_style = self.create_style_from_template('top_line_style', 'A10')
        top_left_line_style = self.create_style_from_template('top_left_line_style', 'B10')
        top_float_style = self.create_style_from_template('top_float_style', 'E10')
        top_date_style = self.create_style_from_template('top_date_style', 'H10')
        line_style = self.create_style_from_template('line_style', 'A11')
        left_line_style = self.create_style_from_template('left_line_style', 'B11')
        float_style = self.create_style_from_template('float_style', 'E11')
        date_style = self.create_style_from_template('date_style', 'D3')

        sheet.title = _('Field Balance Specification Report')
        # Empty cells
        cell_empty = WriteOnlyCell(sheet)
        cell_empty.style = default_style

        # Header data
        sheet.row_dimensions[1].height = 20
        cell_title = WriteOnlyCell(sheet, value=_('Field Balance Specification Report'))
        cell_title.style = big_title_style
        cell_g1 = WriteOnlyCell(sheet, value=_('Rates'))
        cell_g1.style = bold_blue_style
        cell_g1.alignment = Alignment(horizontal='center')
        cell_h1 = WriteOnlyCell(sheet, value=_('Current period'))
        cell_h1.style = bold_blue_style
        cell_h1.alignment = Alignment(horizontal='center')
        sheet.append([cell_title, cell_empty, cell_empty, cell_empty, cell_empty, cell_empty, cell_g1, cell_h1])
        sheet.merged_cells.ranges.append("A1:F1")

        cell_g2 = WriteOnlyCell(sheet, value='EUR')
        cell_g2.style = default_style
        cell_g2.alignment = Alignment(horizontal='right')
        cell_h2 = WriteOnlyCell(sheet, value=1)
        cell_h2.number_format = "0.0000"
        cell_h2.alignment = Alignment(horizontal='right')
        sheet.append([cell_empty, cell_empty, cell_empty, cell_empty, cell_empty, cell_empty, cell_g2, cell_h2])

        cell_a3 = WriteOnlyCell(sheet, value=_('Country Program'))
        cell_a3.style = bold_blue_style
        cell_b3 = WriteOnlyCell(sheet, value='North East Syria')
        cell_b3.style = default_style
        cell_c3 = WriteOnlyCell(sheet, value=_('Date of the report'))
        cell_c3.style = bold_blue_style
        cell_d3 = WriteOnlyCell(sheet, value='02/07/1982')
        cell_d3.style = date_style
        cell_d3.number_format = 'dd/mm/yyyy;@'
        cell_g3 = WriteOnlyCell(sheet, value='USD')
        cell_g3.style = default_style
        cell_g3.alignment = Alignment(horizontal='right')
        cell_h3 = WriteOnlyCell(sheet, value=0.9706)
        cell_h3.number_format = "0.0000"
        cell_h3.alignment = Alignment(horizontal='right')
        sheet.append([cell_a3, cell_b3, cell_c3, cell_d3, cell_empty, cell_empty, cell_g3, cell_h3])

        cell_a4 = WriteOnlyCell(sheet, value=_('Month:'))
        cell_a4.style = bold_blue_style
        cell_b4 = WriteOnlyCell(sheet, value='Oct. 2022')
        cell_b4.style = default_style
        cell_c4 = WriteOnlyCell(sheet, value=_('Date of review'))
        cell_c4.style = bold_blue_style
        cell_g4 = WriteOnlyCell(sheet, value='IQD')
        cell_g4.style = default_style
        cell_g4.alignment = Alignment(horizontal='right')
        cell_h4 = WriteOnlyCell(sheet, value=1417.0760)
        cell_h4.number_format = "0.0000"
        cell_h4.alignment = Alignment(horizontal='right')
        sheet.append([cell_a4, cell_b4, cell_c4, cell_empty, cell_empty, cell_empty, cell_g4, cell_h4])

        cell_a5 = WriteOnlyCell(sheet, value=_('Finco:'))
        cell_a5.style = bold_blue_style
        cell_b5 = WriteOnlyCell(sheet, value='')
        cell_b5.style = empty_blue_frame
        cell_c5 = WriteOnlyCell(sheet, value='23/11/2022')
        cell_c5.style = blue_date_frame
        cell_c5.number_format = 'dd/mm/yyyy;@'
        cell_g5 = WriteOnlyCell(sheet, value='SYP')
        cell_g5.style = default_style
        cell_g5.alignment = Alignment(horizontal='right')
        cell_h5 = WriteOnlyCell(sheet, value=3003.54)
        cell_h5.number_format = "0.0000"
        cell_h5.alignment = Alignment(horizontal='right')
        sheet.append([cell_a5, cell_b5, cell_c5, cell_empty, cell_empty, cell_empty, cell_g5, cell_h5])

        cell_a6 = WriteOnlyCell(sheet, value=_('HoM:'))
        cell_a6.style = bold_blue_style
        cell_b6 = WriteOnlyCell(sheet, value='')
        cell_b6.style = empty_blue_frame
        cell_c6 = WriteOnlyCell(sheet, value='24/11/2022')
        cell_c6.style = blue_date_frame
        cell_g6 = WriteOnlyCell(sheet, value='TRY')
        cell_g6.style = default_style
        cell_g6.alignment = Alignment(horizontal='right')
        cell_h6 = WriteOnlyCell(sheet, value=18)
        cell_h6.number_format = "0.0000"
        cell_h6.alignment = Alignment(horizontal='right')
        sheet.append([cell_a6, cell_b6, cell_c6, cell_empty, cell_empty, cell_empty, cell_g6, cell_h6])

        cell_a7 = WriteOnlyCell(sheet, value=_('HQ reviewer:'))
        cell_a7.style = bold_blue_style
        cell_b7 = WriteOnlyCell(sheet, value='')
        cell_b7.style = empty_blue_frame
        cell_c7 = WriteOnlyCell(sheet, value='25/11/2022')
        cell_c7.style = blue_date_frame
        sheet.append([cell_a7, cell_b7, cell_c7, cell_empty, cell_empty, cell_empty, cell_empty, cell_empty])

        sheet.append([])

        cell_a9 = WriteOnlyCell(sheet, value=_('Balance account'))
        cell_a9.style = grey_bold_frame
        cell_b9 = WriteOnlyCell(sheet)
        cell_b9.style = empty_grey_frame
        cell_c9 = WriteOnlyCell(sheet)
        cell_c9.style = empty_grey_frame
        cell_d9 = WriteOnlyCell(sheet)
        cell_d9.style = empty_grey_frame
        cell_e9 = WriteOnlyCell(sheet)
        cell_e9.style = empty_grey_frame
        cell_f9 = WriteOnlyCell(sheet)
        cell_f9.style = empty_grey_frame
        cell_g9 = WriteOnlyCell(sheet)
        cell_g9.style = empty_grey_frame
        cell_h9 = WriteOnlyCell(sheet, value=_('UniField Balance in Euro'))
        cell_h9.style = grey_bold_frame
        cell_i9 = WriteOnlyCell(sheet)
        cell_i9.style = empty_grey_frame
        cell_j9 = WriteOnlyCell(sheet)
        cell_j9.style = empty_grey_frame
        cell_k9 = WriteOnlyCell(sheet, value=_("Field's comments"))
        cell_k9.style = grey_bold_frame
        cell_l9 = WriteOnlyCell(sheet, value=_('HQ comments'))
        cell_l9.style = grey_bold_frame
        sheet.append([cell_a9, cell_b9, cell_c9, cell_d9, cell_e9, cell_f9, cell_g9, cell_h9, cell_i9, cell_j9, cell_k9, cell_l9])

        sheet.append([])


        row_headers = [
            (_('Balance account')),
            (''),
            (''),
            (''),
            (''),
            (''),
            (''),
            (_('UniField Balance in Euro')),
            (''),
            (''),
            (_("Field's comments")),
            (_('HQ comments')),
        ]

        # Lines data
        row_header = []
        sheet.row_dimensions[8].height = 100
        for header in row_headers:
            cell_t = WriteOnlyCell(sheet, value=header)
            if header != '':
                cell_t.style = line_header_style
            else:
                cell_t.style = empty_grey_frame
            row_header.append(cell_t)
        sheet.append(row_header)
        self.pool.get('')


XlsxReport('report.field_balance_spec_report', parser=field_balance_spec_parser, template='addons/vertical_integration/report/Proposal Balspec2.xlsx')
