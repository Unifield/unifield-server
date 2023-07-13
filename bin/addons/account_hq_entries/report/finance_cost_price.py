# -*- coding: utf-8 -*-
from spreadsheet_xml.xlsx_write import XlsxReport
from spreadsheet_xml.xlsx_write import XlsxReportParser
from datetime import datetime
from tools.translate import _


class finance_cost_price(XlsxReportParser):

    def generate(self, context=None):
        if context is None:
            context = {}

        sheet = self.workbook.active

        self.create_style_from_template('head_title', 'A1')
        self.create_style_from_template('head_content', 'C1')
        self.create_style_from_template('date_content', 'C5')

        self.create_style_from_template('row_title', 'A7')

        date_st = [
            self.create_style_from_template('date_odd', 'A8'),
            self.create_style_from_template('date_even', 'A9')
        ]

        txt_st = [
            self.create_style_from_template('txt_odd', 'B8'),
            self.create_style_from_template('txt_even', 'B9')
        ]

        float_st = [
            self.create_style_from_template('float_odd', 'G8'),
            self.create_style_from_template('float_even', 'G9')
        ]


        self.duplicate_column_dimensions(default_width=20.43)
        sheet.freeze_panes = 'A8'


        prod = self.pool.get('product.product').browse(self.cr, self.uid, self.ids[0], fields_to_fetch=['default_code', 'name', 'company_id'], context=context)
        sheet.title = prod.default_code

        sheet.merged_cells.ranges.append("A1:B1")
        sheet.merged_cells.ranges.append("C1:F1")
        sheet.append([self.cell_ro(_('Instance'), 'head_title'), self.cell_ro('', 'head_title'),  self.cell_ro(prod.company_id.instance_id.instance, 'head_content')] + [self.cell_ro('', 'head_content')]*3)

        sheet.merged_cells.ranges.append("A2:B2")
        sheet.merged_cells.ranges.append("C2:F2")
        sheet.append([self.cell_ro(_('Product code'), 'head_title'), self.cell_ro('', 'head_title'),  self.cell_ro(prod.default_code, 'head_content')] + [self.cell_ro('', 'head_content')]*3)

        sheet.merged_cells.ranges.append("A3:B3")
        sheet.merged_cells.ranges.append("C3:F3")
        sheet.append([self.cell_ro(_('Product Description'), 'head_title'), self.cell_ro('', 'head_title'),  self.cell_ro(prod.name, 'head_content')] + [self.cell_ro('', 'head_content')]*3)

        sheet.merged_cells.ranges.append("A4:B4")
        sheet.merged_cells.ranges.append("C4:F4")
        sheet.append([self.cell_ro(_('Currency'), 'head_title'), self.cell_ro('', 'head_title'), self.cell_ro(prod.company_id.currency_id.name, 'head_content')] + [self.cell_ro('', 'head_content')]*3)

        sheet.merged_cells.ranges.append("A5:B5")
        sheet.merged_cells.ranges.append("C5:F5")
        sheet.append([self.cell_ro(_('Generation Date'), 'head_title'), self.cell_ro('', 'head_title'), self.cell_ro(datetime.now(), 'date_content')] + [self.cell_ro('', 'head_content')]*3)

        sheet.append([])

        sheet.append([
            self.cell_ro(_('Date'), 'row_title'),
            self.cell_ro(_('User'), 'row_title'),
            self.cell_ro(_('Old Finance Price'), 'row_title'),
            self.cell_ro(_('New Finance Price'), 'row_title'),
            self.cell_ro(_('Transaction'), 'row_title'),
            self.cell_ro(_('Stock Level Before'), 'row_title'),
            self.cell_ro(_('Qty Processed'), 'row_title'),
            self.cell_ro(_('Unit Price'), 'row_title'),
            self.cell_ro(_('Matching Type'), 'row_title'),
        ])

        matching_obj = self.pool.get('finance_price.track_changes')
        matching_ids = matching_obj.search(self.cr, self.uid, [('product_id', '=', prod.id)], order='id desc', context=context)

        color = 1
        previous_in = 0
        for tc in matching_obj.browse(self.cr, self.uid, matching_ids, context=context):
            if abs(tc.new_price - tc.old_price) < 0.0001:
                continue

            if previous_in != tc.stock_move_id.id:
                previous_in = tc.stock_move_id.id
                color = 1 - color
            sheet.append([
                self.cell_ro(tc.date and datetime.strptime(tc.date, '%Y-%m-%d %H:%M:%S') or '', date_st[color]),
                self.cell_ro(tc.user_id.name, txt_st[color]),
                self.cell_ro(round(tc.old_price, 5), float_st[color]),
                self.cell_ro(round(tc.new_price, 5), float_st[color]),
                self.cell_ro(tc.stock_picking_id and tc.stock_picking_id.name or tc.invoice_id and tc.invoice_id.name or tc.comment or '', txt_st[color]),
                self.cell_ro(tc.stock_before, float_st[color]),
                self.cell_ro(tc.qty_processed, float_st[color]),
                self.cell_ro(round(tc.price_unit, 5), float_st[color]),
                self.cell_ro(self.getSel(tc, 'matching_type'), txt_st[color]),
            ])

XlsxReport('report.report_finance_cost_price', parser=finance_cost_price, template='addons/account_hq_entries/report/finance_cost_price.xlsx')

