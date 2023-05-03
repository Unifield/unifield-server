# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF
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
from osv import osv
from tools.translate import _
import time
from datetime import datetime
from spreadsheet_xml.xlsx_write import XlsxReport
from spreadsheet_xml.xlsx_write import XlsxReportParser
from openpyxl.cell import WriteOnlyCell

DOC_TYPES = {
    'purchase.order': 'PO',
    'sale.order': 'IR',
    'account.bank.statement.cash': 'Cash Register',
    'account.bank.statement.bank': 'Bank Register',
    'account.bank.statement.cheque': 'Cheque Register',
    'account.invoice.si': 'Supplier Invoice',
    'account.invoice.donation': 'Donation',
    'stock.picking': 'IN',
}


def _get_filters_info(self, fields, search_domain, source, context=None):
    if context is None:
        context = {}
    if not (self or fields or search_domain or source):
        raise osv.except_osv(_('Error!'), _('Please fill all attributes to use this method'))
    if source not in ['signature.follow_up.search.pdf', 'signature.follow_up.search.xlsx']:
        raise osv.except_osv(_('Error!'), _('This method is only usable for the Signature Follow Up Search Exports'))

    data = []
    for filter in search_domain:
        if not fields.get(filter[0], False):
            continue
        name = fields.get(filter[0]) and fields[filter[0]]['string'] or filter[0]
        value = filter[2]
        if filter[0] == 'user_id':
            if value == self.uid and {'name': _('My Signature'), 'value': _('Yes')} not in data:
                name = _('My Signatures')
                value = _('Yes')
            elif value != self.uid:
                value = self.pool.get('res.users').browse(self.cr, self.uid, value, context=context).name
            else:
                continue
        elif filter[0] == 'signed':
            if filter[1] == '>':
                name = _('Signed')
                value = _('Yes')
            else:
                name = _('To be signed')
                value = _('Yes')
        elif filter[0] == 'status':
            if value == 'open':
                name = _('Open')
                value = _('Yes')
            elif value == 'partial':
                name = _('Partially Signed')
                value = _('Yes')
            elif value == 'signed':
                name = _('Fully Signed')
                value = _('Yes')
        elif filter[0] == 'doc_type':
            if filter[1] == 'in':
                if 'purchase.order' in filter[2]:
                    name = _('Supply')
                    value = _('Yes')
                elif 'account.bank.statement.cash' in filter[2]:
                    name = _('Finance')
                    value = _('Yes')
            else:
                value = DOC_TYPES.get(value, value)
        elif filter[0] == 'signature_is_closed':
            value = filter[2] and _('Yes') or _('No')
        elif filter[0] != 'doc_name':
            continue

        data.append({'name': name, 'value': value})
    return data


class signature_follow_up_search_report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(signature_follow_up_search_report, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'getTitleInfo': self.get_title_info,
            'getFiltersInfo': self.get_filters_info,
            'getLines': self.get_lines,
        })

    def get_title_info(self):
        company_name = self.pool.get('res.users').browse(self.cr, self.uid, self.uid, context=self.localcontext).company_id.name

        return company_name + ' - ' + self.formatLang(time.strftime('%Y-%m-%d'), date=True)

    def get_filters_info(self):
        fields = self.pool.get('signature.follow_up').fields_get(self.cr, self.uid, context=self.localcontext)

        return _get_filters_info(self, fields, self.localcontext.get('search_domain', {}),
                                 'signature.follow_up.search.pdf', context=self.localcontext)

    def get_lines(self):
        sign_foup_obj = self.pool.get('signature.follow_up')
        line_ids = sign_foup_obj.search(self.cr, self.uid, self.localcontext.get('search_domain', []), context=self.localcontext)
        return sign_foup_obj.browse(self.cr, self.uid, line_ids, context=self.localcontext)


report_sxw.report_sxw('report.signature.follow_up.search.pdf', 'signature.follow_up',
                      'useability_dashboard_and_menu/report/signature_follow_up_search_report.rml', header=False,
                      parser=signature_follow_up_search_report)


class signature_follow_up_search_report_xlsx(XlsxReportParser):

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

        sheet = self.workbook.active
        sheet.sheet_view.showGridLines = False

        sheet.column_dimensions['A'].width = 25.0
        sheet.column_dimensions['B'].width = 30.0
        sheet.column_dimensions['C'].width = 20.0
        sheet.column_dimensions['D'].width = 20.0
        sheet.column_dimensions['E'].width = 20.0
        sheet.column_dimensions['F'].width = 20.0
        sheet.column_dimensions['G'].width = 10.0
        sheet.column_dimensions['H'].width = 30.0
        sheet.column_dimensions['I'].width = 20.0

        # Styles
        default_style = self.create_style_from_template('default_style', 'A2')

        big_title_style = self.create_style_from_template('big_title_style', 'A1')
        big_bold_style = self.create_style_from_template('big_bold_style', 'A4')
        big_style = self.create_style_from_template('big_style', 'A5')

        line_header_style = self.create_style_from_template('line_header_style', 'A9')
        line_style = self.create_style_from_template('line_style', 'A10')
        date_style = self.create_style_from_template('date_style', 'H10')

        sheet.title = _('Signature Follow Up')
        # Header data
        sheet.row_dimensions[1].height = 40
        instance_name = self.pool.get('res.users').browse(self.cr, self.uid, self.uid).company_id.instance_id.instance
        today = time.strftime(self.pool.get('date.tools').get_date_format(self.cr, self.uid, context=context))
        cell_title = WriteOnlyCell(sheet, value=_('Signature Follow Up - %s - %s') % (instance_name, today))
        cell_title.style = big_title_style
        self.apply_template_style('A1', cell_title)
        sheet.append([cell_title])
        sheet.merged_cells.ranges.append("A1:I1")

        sheet.append([])
        sheet.append([])

        cell_fu = WriteOnlyCell(sheet, value=_('Filters used :'))
        cell_fu.style = big_bold_style
        sheet.merged_cells.ranges.append("A4:B4")
        sheet.append([cell_fu])

        idx = 4
        fields = self.pool.get('signature.follow_up').fields_get(self.cr, self.uid, context=context)
        for filter in _get_filters_info(self, fields, context.get('search_domain', {}),
                                        'signature.follow_up.search.xlsx', context=context):
            cell_fin = WriteOnlyCell(sheet, value=filter.get('name', ''))
            cell_fin.style = big_style
            cell_fid = WriteOnlyCell(sheet, value=filter.get('value', ''))
            cell_fid.style = big_style
            sheet.append([cell_fin, cell_fid])
            idx += 1

        sheet.append([])

        row_headers = [
            (_('User')),
            (_('Document Name')),
            (_('Document State')),
            (_('Document Type')),
            (_('Type of Signature')),
            (_('Signature State')),
            (_('Signed')),
            (_('Signature Date')),
            (_('Signature Closed')),
        ]

        # Lines data
        row_header = []
        sheet.row_dimensions[idx + 2].height = 30
        for header in row_headers:
            cell_t = WriteOnlyCell(sheet, value=header)
            cell_t.style = line_header_style
            row_header.append(cell_t)
        sheet.append(row_header)

        # Get data with domain in context
        sign_foup_obj = self.pool.get('signature.follow_up')
        sign_foup_ids = sign_foup_obj.search(self.cr, self.uid, context.get('search_domain', []), context=context)
        for sign in sign_foup_obj.browse(self.cr, self.uid, sign_foup_ids, context=context):
            self.rows = []

            self.add_cell(sign.user_id and sign.user_id.name or '', line_style)
            self.add_cell(sign.doc_name or '', line_style)
            self.add_cell(self.getSel(sign, 'doc_state') or '', line_style)
            self.add_cell(self.getSel(sign, 'doc_type') or '', line_style)
            self.add_cell(self.getSel(sign, 'subtype') or '', line_style)
            self.add_cell(self.getSel(sign, 'status') or '', line_style)
            self.add_cell(sign.signed > 0 and _('Yes') or _('No'), line_style)
            self.add_cell(datetime.strptime(sign.signature_date, '%Y-%m-%d %H:%M:%S') or '', date_style, number_format='DD/MM/YYYY HH:MM')
            self.add_cell(sign.signature_is_closed and _('Yes') or _('No'), line_style)

            sheet.append(self.rows)


XlsxReport('report.signature.follow_up.search.xlsx', parser=signature_follow_up_search_report_xlsx,
           template='addons/useability_dashboard_and_menu/report/signature_follow_up_search_report.xlsx')
