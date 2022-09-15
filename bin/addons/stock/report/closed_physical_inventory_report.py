# -*- coding: utf-8 -*-
from osv import osv
from datetime import datetime
from spreadsheet_xml.xlsx_write import XlsxReport
from spreadsheet_xml.xlsx_write import XlsxReportParser
from tools.translate import _
from openpyxl.cell import WriteOnlyCell
import tools


class closed_physical_inventory_parser(XlsxReportParser):

    def add_cell(self, value=None, style='default_style'):
        # None value set an xls empty cell
        # False value set the xls False()
        new_cell = WriteOnlyCell(self.workbook.active, value=value)
        new_cell.style = style
        self.rows.append(new_cell)

    def generate(self, context=None):
        pi = self.pool.get('physical.inventory').browse(self.cr, self.uid, self.ids[0], context=context)
        if pi.state != 'closed':
            raise osv.except_osv(_('Error'), _('This export is only available for closed Physical Inventories'))

        SUB_RT_SEL = {
            'encoding_err': _('Encoding Error'),
            'process_err': _('Process Error'),
            'pick_err': _('Picking Error'),
            'recep_err': _('Reception Error'),
            'bn_err': _('Batch Number related Error'),
            'unexpl_err': _('Unjustified/Unexplained Error')
        }

        sheet = self.workbook.active
        sheet.sheet_view.showGridLines = False

        sheet.column_dimensions['A'].width = 7.0
        sheet.column_dimensions['B'].width = 20.0
        sheet.column_dimensions['C'].width = 65.0
        sheet.column_dimensions['D'].width = 7.0
        sheet.column_dimensions['E'].width = 15.0
        sheet.column_dimensions['F'].width = 15.0
        sheet.column_dimensions['G'].width = 20.0
        sheet.column_dimensions['H'].width = 15.0
        sheet.column_dimensions['I'].width = 15.0
        sheet.column_dimensions['J'].width = 15.0
        sheet.column_dimensions['K'].width = 15.0
        sheet.column_dimensions['L'].width = 15.0
        sheet.column_dimensions['M'].width = 20.0
        sheet.column_dimensions['N'].width = 25.0
        sheet.column_dimensions['O'].width = 65.0

        # Styles
        default_style = self.create_style_from_template('default_style', 'A1')

        big_title_style = self.create_style_from_template('big_title_style', 'B1')
        bold_right_style = self.create_style_from_template('bold_right_style', 'A3')
        bold_frame = self.create_style_from_template('bold_frame', 'C3')
        middle_bold_frame = self.create_style_from_template('middle_bold_frame', 'G5')
        bold_date_frame = self.create_style_from_template('bold_date_frame', 'G3')

        line_header_style = self.create_style_from_template('line_header_style', 'A9')
        top_line_style = self.create_style_from_template('top_line_style', 'A10')
        top_left_line_style = self.create_style_from_template('top_left_line_style', 'B10')
        top_float_style = self.create_style_from_template('top_float_style', 'E10')
        top_date_style = self.create_style_from_template('top_date_style', 'H10')
        line_style = self.create_style_from_template('line_style', 'A11')
        left_line_style = self.create_style_from_template('left_line_style', 'B11')
        float_style = self.create_style_from_template('float_style', 'E11')
        date_style = self.create_style_from_template('date_style', 'H11')

        sheet.title = _('Closed Inventory')
        # Empty cells
        cell_empty = WriteOnlyCell(sheet)
        cell_empty.style = default_style

        # Header data
        sheet.row_dimensions[0].height = 70
        cell_title = WriteOnlyCell(sheet, value=_('Closed Inventory'))
        cell_title.style = big_title_style
        self.apply_template_style('B1', cell_title)
        sheet.append([cell_empty, cell_title])
        sheet.merged_cells.ranges.append("B1:J1")

        sheet.append([])

        cell_ic = WriteOnlyCell(sheet, value=_('Inventory Counter Name'))
        cell_ic.style = bold_right_style
        cell_icd = WriteOnlyCell(sheet, value=pi.responsible or '')
        cell_icd.style = bold_frame
        cell_id = WriteOnlyCell(sheet, value=_('Inventory Date'))
        cell_id.style = bold_right_style
        cell_idd = WriteOnlyCell(sheet, value=datetime.strptime(pi.date_done[0:10], '%Y-%m-%d'))
        cell_idd.style = bold_date_frame
        cell_ide = WriteOnlyCell(sheet)
        cell_ide.style = bold_date_frame
        sheet.append([cell_ic, cell_empty, cell_icd, cell_empty, cell_id, cell_empty, cell_idd, cell_ide])
        sheet.merged_cells.ranges.append("A3:B3")
        sheet.merged_cells.ranges.append("E3:F3")
        sheet.merged_cells.ranges.append("G3:H3")

        sheet.append([])

        cell_ir = WriteOnlyCell(sheet, value=_('Inventory Reference'))
        cell_ir.style = bold_right_style
        cell_ird = WriteOnlyCell(sheet, value=pi.ref)
        cell_ird.style = bold_frame
        cell_il = WriteOnlyCell(sheet, value=_('Location'))
        cell_il.style = bold_right_style
        cell_ild = WriteOnlyCell(sheet, value=pi.location_id and pi.location_id.name or '')
        cell_ild.style = middle_bold_frame
        cell_ile = WriteOnlyCell(sheet)
        cell_ile.style = middle_bold_frame
        sheet.append([cell_ir, cell_empty, cell_ird, cell_empty, cell_il, cell_empty, cell_ild, cell_ile])
        sheet.merged_cells.ranges.append("A5:B5")
        sheet.merged_cells.ranges.append("E5:F5")
        sheet.merged_cells.ranges.append("G5:H5")

        sheet.append([])

        cell_in = WriteOnlyCell(sheet, value=_('Inventory Name'))
        cell_in.style = bold_right_style
        cell_ind = WriteOnlyCell(sheet, value=pi.name)
        cell_ind.style = bold_frame
        sheet.append([cell_in, cell_empty, cell_ind])
        sheet.merged_cells.ranges.append("A7:B7")

        sheet.append([])

        row_headers = [
            (_('Line #')),
            (_('Item Code')),
            (_('Description')),
            (_('UoM')),
            (_('Quantity counted')),
            (_('Qty ignored in stock (only if > 0)')),
            (_('Batch Number')),
            (_('Expiry Date')),
            (_('Total Qty counted + ignored in stock')),
            (_('Specification')),
            (_('BN Management')),
            (_('ED Management')),
            (_('Reason Type')),
            (_('Sub Reason Type')),
            (_('Comment')),
        ]

        # Lines data
        row_header = []
        sheet.row_dimensions[8].height = 100
        for header in row_headers:
            cell_t = WriteOnlyCell(sheet, value=header)
            cell_t.style = line_header_style
            row_header.append(cell_t)
        sheet.append(row_header)

        # Get lines through discrepancy lines
        rep_lines = {}
        specifications = {'is_kc': _('CC'), 'is_dg': _('DG'), 'is_cs': _('CS')}
        for disc_line in pi.discrepancy_line_ids:
            counted_qty = ''
            if not disc_line.counted_qty_is_empty or (disc_line.counted_qty_is_empty and not disc_line.ignored):
                counted_qty = disc_line.counted_qty
            ignored_qty = ''
            if disc_line.ignored:
                ignored_qty = abs(disc_line.discrepancy_qty)

            if disc_line.product_id.id not in rep_lines:
                rep_lines.update({disc_line.product_id.id: {
                    'product_code': disc_line.product_id.default_code,
                    'description': disc_line.product_id.name,
                    'uom': disc_line.product_uom_id.name,
                    'total_qty': (counted_qty or 0) + (ignored_qty or 0),
                    'specification': ','.join([name for attribute, name in specifications.items() if getattr(disc_line.product_id, attribute, False)]),
                    'need_bn': disc_line.product_id.batch_management and _('Y') or _('N'),
                    'need_ed': disc_line.product_id.perishable and _('Y') or _('N'),
                    'lines': [],
                }})
            else:
                rep_lines[disc_line.product_id.id].update({
                    'total_qty': rep_lines[disc_line.product_id.id]['total_qty'] + (counted_qty or 0) + (ignored_qty or 0),
                })
            rep_lines[disc_line.product_id.id]['lines'].append({
                'line_number': disc_line.line_no,
                'qty_counted': counted_qty,
                'qty_ignored': ignored_qty,
                'prodlot': disc_line.batch_number and tools.ustr(disc_line.batch_number) or '',
                'expiry_date': disc_line.expiry_date and datetime.strptime(disc_line.expiry_date[0:10], '%Y-%m-%d') or '',
                'reason_type': disc_line.reason_type_id.complete_name,
                'sub_reason_type': SUB_RT_SEL.get(disc_line.sub_reason_type, ''),
                'comment': disc_line.comment or '',
            })

        # Get remaining lines through counting lines
        ctx = context.copy()
        ctx.update({'location': pi.location_id.id, 'location_id': pi.location_id.id})
        line_order = []
        for count_line in pi.counting_line_ids:
            if count_line.product_id.id not in line_order:  # Get the order of lines to display
                line_order.append(count_line.product_id.id)
            if not count_line.discrepancy:
                bn_domain = [('product_id', '=', count_line.product_id.id), ('name', '=ilike', count_line.batch_number), ('life_date', '=', count_line.expiry_date)]
                bn_ids = self.pool.get('stock.production.lot').search(self.cr, self.uid, bn_domain, context=context)
                ctx.update({'prodlot_id': (count_line.is_bn or count_line.is_ed) and bn_ids and bn_ids[0] or False})
                prod_stock = self.pool.get('product.product').browse(self.cr, self.uid, count_line.product_id.id, fields_to_fetch=['qty_available'], context=ctx)['qty_available']

                count_line_qty = float(count_line.quantity)
                if count_line.product_id.id not in rep_lines:
                    rep_lines.update({count_line.product_id.id: {
                        'product_code': count_line.product_id.default_code,
                        'description': count_line.product_id.name,
                        'uom': count_line.product_uom_id.name,
                        'total_qty': count_line_qty,
                        'specification': ','.join([name for attribute, name in specifications.items() if getattr(count_line.product_id, attribute, False)]),
                        'need_bn': count_line.is_bn and _('Y') or _('N'),
                        'need_ed': count_line.is_ed and _('Y') or _('N'),
                        'lines': [],
                    }})
                else:
                    rep_lines[count_line.product_id.id].update({
                        'total_qty': rep_lines[count_line.product_id.id]['total_qty'] + count_line_qty,
                    })
                if not count_line_qty and count_line_qty != 0:
                    qty_ignored = prod_stock or count_line.product_id.qty_available
                elif count_line_qty == 0:
                    qty_ignored = 0
                else:
                    qty_ignored = ''
                rep_lines[count_line.product_id.id]['lines'].append({
                    'line_number': count_line.line_no,
                    'qty_counted': ((count_line_qty or count_line_qty == 0) and count_line_qty) or '',
                    'qty_ignored': qty_ignored,
                    'prodlot': count_line.batch_number and tools.ustr(count_line.batch_number) or '',
                    'expiry_date': count_line.expiry_date and datetime.strptime(count_line.expiry_date[0:10], '%Y-%m-%d') or '',
                    'reason_type': '',
                    'sub_reason_type': '',
                    'comment': '',
                })

        for product_id in line_order:
            if rep_lines.get(product_id, False):
                self.rows = []

                p_code = rep_lines[product_id]['product_code']
                p_desc = rep_lines[product_id]['description']
                uom = rep_lines[product_id]['uom']
                spec = rep_lines[product_id]['specification']
                need_bn = rep_lines[product_id]['need_bn']
                need_ed = rep_lines[product_id]['need_ed']

                self.add_cell('', top_line_style)
                self.add_cell(p_code, top_left_line_style)
                self.add_cell(p_desc, top_left_line_style)
                self.add_cell(uom, top_line_style)
                self.add_cell('', top_float_style)
                self.add_cell('', top_float_style)
                self.add_cell('', top_line_style)
                self.add_cell('', top_date_style)
                self.add_cell(rep_lines[product_id]['total_qty'] or 0, top_float_style)
                self.add_cell('', top_line_style)
                self.add_cell('', top_line_style)
                self.add_cell('', top_line_style)
                self.add_cell('', top_line_style)
                self.add_cell('', top_line_style)
                self.add_cell('', top_line_style)

                sheet.append(self.rows)
                for line in sorted(rep_lines[product_id].get('lines', []), key=lambda x: x['line_number']):
                    self.rows = []

                    self.add_cell(line['line_number'], line_style)
                    self.add_cell(p_code, left_line_style)
                    self.add_cell(p_desc, left_line_style)
                    self.add_cell(uom, line_style)
                    self.add_cell(line['qty_counted'], float_style)
                    self.add_cell(line['qty_ignored'], float_style)
                    self.add_cell(line['prodlot'], line_style)
                    self.add_cell(line['expiry_date'], date_style)
                    self.add_cell('', float_style)
                    self.add_cell(spec, line_style)
                    self.add_cell(need_bn, line_style)
                    self.add_cell(need_ed, line_style)
                    self.add_cell(line['reason_type'], line_style)
                    self.add_cell(line['sub_reason_type'], line_style)
                    self.add_cell(line['comment'], line_style)

                    sheet.append(self.rows)


XlsxReport('report.report_closed_physical_inventory', parser=closed_physical_inventory_parser, template='addons/stock/report/closed_physical_inventory_report.xlsx')
