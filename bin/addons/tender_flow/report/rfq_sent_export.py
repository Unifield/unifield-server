# -*- coding: utf-8 -*-
from spreadsheet_xml.xlsx_write import XlsxReport
from spreadsheet_xml.xlsx_write import XlsxReportParser
from tools.translate import _
from openpyxl.cell import WriteOnlyCell
from datetime import datetime


class rfq_sent_export_parser(XlsxReportParser):

    def add_cell(self, value=None, style='default_style', wrap_text=None):
        # None value set an xls empty cell
        # False value set the xls False()
        new_cell = WriteOnlyCell(self.workbook.active, value=value)
        new_cell.style = style
        if wrap_text:
            new_cell.alignment = new_cell.alignment.copy(wrapText=True)
        self.rows.append(new_cell)

    def generate(self, context=None):
        if context is None:
            context = {}

        addr_obj = self.pool.get('res.partner.address')
        pol_obj = self.pool.get('purchase.order.line')
        rfq = self.pool.get('purchase.order').browse(self.cr, self.uid, self.ids[0], context=context)

        sheet = self.workbook.active

        sheet.column_dimensions['A'].width = 20.0
        sheet.column_dimensions['B'].width = 30.0
        sheet.column_dimensions['C'].width = 65.0
        sheet.column_dimensions['D'].width = 13.0
        sheet.column_dimensions['E'].width = 7.0
        sheet.column_dimensions['F'].width = 20.0
        sheet.column_dimensions['G'].width = 15.0
        sheet.column_dimensions['H'].width = 15.0
        sheet.column_dimensions['I'].width = 10.0
        sheet.column_dimensions['J'].width = 65.0
        sheet.column_dimensions['K'].width = 13.0

        # Styles
        header_style = self.create_style_from_template('line_header_style', 'A1')
        line_style = self.create_style_from_template('line_style', 'B1')
        int_style = self.create_style_from_template('int_style', 'A13')
        float_style = self.create_style_from_template('float_style', 'D13')
        date_style = self.create_style_from_template('date_style', 'B4')

        sheet.title = _('Update Sent RfQ')

        header_lines = [
            (_('Order Reference'), 'standard', rfq.name),
            (_('Order Type'), 'standard', rfq.order_type),
            (_('Order Category'), 'standard', rfq.categ),
            (_('Valid Till'), 'date', rfq.valid_till and datetime.strptime(rfq.valid_till, '%Y-%m-%d') or ''),
            (_('Details'), 'standard', rfq.details or ''),
            (_('Tender'), 'standard', rfq.tender_id and rfq.tender_id.name or ''),
            (_('Supplier'), 'standard', rfq.partner_id and rfq.partner_id.name or ''),
            (_('Delivery address'), 'standard',
             rfq.rfq_delivery_address and addr_obj.name_get(self.cr, self.uid, [rfq.rfq_delivery_address.id], context=context)[0][1] or ''),
            (_('Notes'), 'standard', rfq.notes or ''),
            (_('Source Document'), 'standard', rfq.origin or ''),
            (_('Customer Ref.'), 'standard', rfq.customer_ref or ''),
        ]

        # headers
        for header, val_style, val in header_lines:
            cell_h = WriteOnlyCell(sheet, value=header)
            cell_h.style = header_style
            cell_hv = WriteOnlyCell(sheet, value=val)
            style = line_style
            if val_style == 'date':
                style = date_style
            cell_hv.style = style
            cell_hv.alignment = cell_hv.alignment.copy(wrapText=True)
            sheet.append([cell_h, cell_hv])

        row_headers = [
            (_('Line Number')),
            (_('Product Code')),
            (_('Product Description')),
            (_('Quantity')),
            (_('UoM')),
            (_('Price')),
            (_('Requested Delivery Date')),
            (_('Confirmed Delivery Date')),
            (_('Currency')),
            (_('Comment')),
            (_('State')),
        ]

        # Lines data
        row_header = []
        for header in row_headers:
            cell_t = WriteOnlyCell(sheet, value=header)
            cell_t.style = header_style
            row_header.append(cell_t)
        sheet.append(row_header)
        sheet.row_dimensions[11].height = 30

        rfql_domain = [('order_id', '=', rfq.id), ('state', 'not in', ['cancel', 'cancel_r'])]
        rfql_ids = pol_obj.search(self.cr, self.uid, rfql_domain, context=context)
        if rfql_ids:
            ftf = ['line_number', 'product_id', 'product_qty', 'product_uom', 'price_unit', 'date_planned',
                   'confirmed_delivery_date', 'comment', 'rfq_line_state']
            for line in pol_obj.browse(self.cr, self.uid, rfql_ids, fields_to_fetch=ftf, context=context):
                self.rows = []

                self.add_cell(line.line_number, int_style),
                self.add_cell(line.product_id and line.product_id.default_code or '', line_style),
                self.add_cell(line.product_id and line.product_id.name or '', line_style, wrap_text=True),
                self.add_cell(line.product_qty, float_style),
                self.add_cell(line.product_uom.name, line_style),
                self.add_cell(line.price_unit, float_style),
                self.add_cell(line.date_planned and datetime.strptime(line.date_planned, '%Y-%m-%d') or '', date_style),
                self.add_cell(line.confirmed_delivery_date and datetime.strptime(line.confirmed_delivery_date, '%Y-%m-%d') or '', date_style),
                self.add_cell(rfq.pricelist_id.currency_id.name, line_style),
                self.add_cell(line.comment or '', line_style),
                self.add_cell(line.rfq_line_state, line_style)

                sheet.append(self.rows)


XlsxReport('report.report_rfq_sent_export', parser=rfq_sent_export_parser, template='addons/tender_flow/report/rfq_sent_export.xlsx')
