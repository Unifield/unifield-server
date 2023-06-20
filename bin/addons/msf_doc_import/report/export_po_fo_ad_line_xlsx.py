# -*- coding: utf-8 -*-
from spreadsheet_xml.xlsx_write import XlsxReport
from spreadsheet_xml.xlsx_write import XlsxReportParser
from tools.translate import _


class po_fo_ad_line(XlsxReportParser):

    def _get_ad(self, obj):
        if not obj.analytic_distribution_id or not obj.analytic_distribution_id.cost_center_lines:
            return ['100%', '', '']
        percentages, an_codes, dest_codes = [], [], []
        for cc_line in obj.analytic_distribution_id.cost_center_lines:
            percentages.append(str(cc_line.percentage) + '%')
            an_codes.append(cc_line.analytic_id.code)
            dest_codes.append(cc_line.destination_id.code)
        return [';'.join(percentages), ';'.join(an_codes), ';'.join(dest_codes)]

    def generate(self, context=None):
        wiz = self.pool.get('wizard.import.ad.line').browse(self.cr, self.uid, self.ids[0], context=context)
        if wiz.purchase_id:
            obj = wiz.purchase_id
        else:
            obj = wiz.sale_id

        sheet = self.workbook.active

        self.create_style_from_template('header_style', 'A1')

        self.create_style_from_template('text_line_style', 'B2')
        self.create_style_from_template('integer_line_style', 'C2')
        self.create_style_from_template('price_style', 'E2')
        self.duplicate_column_dimensions(default_width=10.75)
        sheet.freeze_panes = 'A4'
        sheet.protection.sheet = True
        # Styles
        sheet.title = obj.name.replace('/', '_')

        sheet.append([self.cell_ro(_('Reference'), 'header_style'), self.cell_ro(obj.name, 'header_style')])
        if wiz.purchase_id:
            partner_label = _('Supplier')
        else:
            partner_label = _('Customer')
        sheet.append([self.cell_ro(partner_label, 'header_style'), self.cell_ro(obj.partner_id.name, 'header_style')])

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

        currency = obj.pricelist_id.currency_id.name
        ad_header = self._get_ad(obj)

        for line in obj.order_line:
            if line.state not in ('cancel', 'cancel_r'):
                if not line.analytic_distribution_id:
                    ad = ad_header
                else:
                    ad = self._get_ad(line)

                if wiz.purchase_id:
                    qty = line.product_qty
                else:
                    qty = line.product_uom_qty
                sheet.append([
                    self.cell_ro(line.line_number, 'text_line_style'),
                    self.cell_ro(line.product_id and line.product_id.default_code or line.comment or '', 'text_line_style'),
                    self.cell_ro(line.product_id and line.product_id.name or line.nomenclature_description or '', 'text_line_style'),
                    self.cell_ro(qty, 'integer_line_style'),
                    self.cell_ro(line.product_uom.name, 'text_line_style'),
                    self.cell_ro(line.price_unit, 'price_style'),
                    self.cell_ro(currency, 'text_line_style'),
                    self.cell_ro(ad[0], 'text_line_style', unlock=True),
                    self.cell_ro(ad[1], 'text_line_style', unlock=True),
                    self.cell_ro(ad[2], 'text_line_style', unlock=True),
                ])

XlsxReport('report.export_po_fo_ad_line_xlsx', parser=po_fo_ad_line, template='addons/msf_doc_import/report/export_po_fo_ad_line.xlsx')

