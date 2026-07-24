# -*- coding: utf-8 -*-
from spreadsheet_xml.xlsx_write import XlsxReport
from spreadsheet_xml.xlsx_write import XlsxReportParser
from tools.translate import _
from datetime import datetime
from openpyxl.cell import WriteOnlyCell


class signature_email_logs_parser(XlsxReportParser):

    def add_cell(self, value=None, style='default_style', number_format=None):
        # None value set a xls empty cell
        # False value set the xls False()
        new_cell = WriteOnlyCell(self.workbook.active, value=value)
        new_cell.style = style
        if number_format:
            new_cell.number_format = number_format
        self.rows.append(new_cell)

    def generate(self, context=None):
        if context is None:
            context = {}

        email_log_obj = self.pool.get('email.log')

        sheet = self.workbook.active
        sheet.title = _('Signature Email Logs')
        self.duplicate_column_dimensions(default_width=10.75)

        # Styles
        default_style = self.create_style_from_template('default_style', 'A2')

        header_style = self.create_style_from_template('header_style', 'A1')
        line_date_style = self.create_style_from_template('line_date_style', 'C2')

        # Lines data
        row_headers = [
            (_('Recipients'), header_style),
            (_('Recipients Names'), header_style),
            (_('Date Sent'), header_style),
        ]

        row_header = []
        for header, current_style in row_headers:
            cell_t = WriteOnlyCell(sheet, value=header)
            cell_t.style = current_style
            row_header.append(cell_t)
        sheet.append(row_header)

        email_sign_notif_model_id = self.pool.get('ir.model').search(self.cr, 1, [('model', '=', 'email.signature.notification')])[0]
        email_log_ids = email_log_obj.search(self.cr, self.uid, [('sender_model_id', '=', email_sign_notif_model_id)], context=context)
        for email_log in email_log_obj.read(self.cr, self.uid, email_log_ids, context=context):
            self.rows = []

            self.add_cell(email_log['recipients'], default_style)
            self.add_cell(email_log['recipient_names'] or '', default_style)
            self.add_cell(email_log['date_sent'] and datetime.strptime(email_log['date_sent'], '%Y-%m-%d %H:%M:%S.%f') \
                          or '', line_date_style, number_format='DD/MM/YYYY HH:MM')

            sheet.append(self.rows)


XlsxReport('report.report_signature_email_logs', parser=signature_email_logs_parser, template='addons/msf_tools/report/signature_email_logs_report.xlsx')
