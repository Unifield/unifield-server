# -*- coding: utf-8 -*-
from spreadsheet_xml.xlsx_write import XlsxReport
from spreadsheet_xml.xlsx_write import XlsxReportParser
from tools.translate import _


class po_ad_line(XlsxReportParser):

    def _get_ad(self, obj):
        if not obj.analytic_distribution_id or not obj.analytic_distribution_id.cost_center_lines:
            return ['100', '', '']
        if len(obj.analytic_distribution_id.cost_center_lines) > 1:
            return ['MIX', '', '']
        return ['100', obj.analytic_distribution_id.cost_center_lines[0].analytic_id.code, obj.analytic_distribution_id.cost_center_lines[0].destination_id.code]

    def generate(self, context=None):
        po = self.pool.get('purchase.order').browse(self.cr, self.uid, self.ids[0], context=context)

        sheet = self.workbook.active

        self.create_style_from_template('header_style', 'A1')

        self.create_style_from_template('text_line_style', 'B2')
        self.create_style_from_template('integer_line_style', 'C2')
        self.create_style_from_template('price_style', 'E2')
        self.duplicate_column_dimensions(default_width=10.75)
        sheet.freeze_panes = 'A4'

        # Styles
        sheet.title = po.name.replace('/', '_')

        sheet.append([self.cell_ro(_('Reference'), 'header_style'), self.cell_ro(po.name, 'header_style')])
        sheet.append([self.cell_ro(_('Supplier'), 'header_style'), self.cell_ro(po.partner_id.name, 'header_style')])

        header = [
            _('Line'),
            _('Product Code'),
            _('Product Description'),
            _('Quantity'),
            _('UoM'),
            _('Price'),
            _('Currency'),
            _('Percentage'),
            _('Cost Center'),
            _('Destination'),
        ]
        sheet.append([self.cell_ro(h, 'header_style') for h in header])

        currency = po.pricelist_id.currency_id.name
        ad_header = self._get_ad(po)

        for line in po.order_line:
            if line.state not in ('cancel', 'cancel_r'):
                if not line.analytic_distribution_id:
                    ad = ad_header
                else:
                    ad = self._get_ad(line)
                sheet.append([
                    self.cell_ro(line.line_number, 'text_line_style'),
                    self.cell_ro(line.product_id and line.product_id.default_code or line.comment or '', 'text_line_style'),
                    self.cell_ro(line.product_id and line.product_id.name or line.nomenclature_description or '', 'text_line_style'),
                    self.cell_ro(line.product_qty, 'integer_line_style'),
                    self.cell_ro(line.product_uom.name, 'text_line_style'),
                    self.cell_ro(line.price_unit, 'price_style'),
                    self.cell_ro(currency, 'text_line_style'),
                    self.cell_ro(ad[0], 'text_line_style'),
                    self.cell_ro(ad[1], 'text_line_style'),
                    self.cell_ro(ad[2], 'text_line_style'),
                ])

XlsxReport('report.export_po_ad_line_xlsx', parser=po_ad_line, template='addons/msf_doc_import/report/export_po_ad_line.xlsx')

