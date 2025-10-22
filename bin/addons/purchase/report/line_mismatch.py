# -*- coding: utf-8 -*-
from spreadsheet_xml.xlsx_write import XlsxReport
from spreadsheet_xml.xlsx_write import XlsxReportParser
from datetime import datetime
from tools.translate import _


class line_mismatch(XlsxReportParser):

    def generate(self, context=None):
        if context is None:
            context = {}

        date_obj = self.pool.get('date.tools')
        ftf = ['name', 'catalogue_id', 'order_line_mismatch', 'partner_id', 'catalogue_ratio_plain_text', 'catalogue_deviation_plain_text']
        po = self.pool.get('purchase.order').browse(self.cr, self.uid, self.ids[0], fields_to_fetch=ftf, context=context)
        sheet = self.workbook.active

        self.create_style_from_template('title_style', 'A1')
        self.create_style_from_template('title_right_style', 'E1')
        self.create_style_from_template('header_style', 'A2')
        self.create_style_from_template('header_right_style', 'E2')
        self.create_style_from_template('header_bottom_style', 'A11')
        self.create_style_from_template('header_bottom_right_style', 'E11')
        self.create_style_from_template('col_title', 'A13')

        self.create_style_from_template('row_int', 'A14')
        self.create_style_from_template('row_text', 'B14')
        self.create_style_from_template('row_float', 'F14')
        self.create_style_from_template('row_date', 'L14')


        self.duplicate_column_dimensions(default_width=10.75)
        for col in ['P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W']:
            sheet.column_dimensions[col].hidden = True
        sheet.freeze_panes = 'A14'
        sheet.auto_filter.ref = "A13:X13"

        sheet.title = _('PO Catalogue Mismatch')

        sheet.merged_cells.ranges.append("A1:E1")
        sheet.append([
            self.cell_ro(_('PO Catalogue lines mismatch'), 'title_style'),
            self.cell_ro('', 'title_style'), self.cell_ro('', 'title_style'), self.cell_ro('', 'title_style'),
            self.cell_ro('', 'title_right_style')
        ])

        row_idx = 2
        for key, value in [
                (_('PO Reference'), po.name),
                (_('Supplier'), po.partner_id.name),
                (_('Catalogue name:'), po.catalogue_id and po.catalogue_id.name or ''),
                (_('Catalogue currency:'), po.catalogue_id and po.catalogue_id.currency_id and po.catalogue_id.currency_id.name or ''),

        ]:
            sheet.merged_cells.ranges.append("A%(row_idx)d:B%(row_idx)d" % {'row_idx': row_idx})
            sheet.merged_cells.ranges.append("C%(row_idx)d:E%(row_idx)d" % {'row_idx': row_idx})
            sheet.append([
                self.cell_ro(key, 'header_style'), self.cell_ro('', 'header_style'),
                self.cell_ro(value, 'header_style'), self.cell_ro('', 'header_style'), self.cell_ro('', 'header_right_style')
            ])
            row_idx += 1
        sheet.merged_cells.ranges.append("A%(row_idx)d:B%(row_idx)d" % {'row_idx': row_idx})
        sheet.merged_cells.ranges.append("C%(row_idx)d:E%(row_idx)d" % {'row_idx': row_idx})
        sheet.append([
            self.cell_ro(_('Catalogue From date: %s') % (po.catalogue_id.period_from and date_obj.get_date_formatted(self.cr, self.uid, datetime=po.catalogue_id.period_from) or '/'), 'header_style'),
            self.cell_ro('', 'header_style'),
            self.cell_ro(_('Catalogue To date: %s') % (po.catalogue_id.period_to and date_obj.get_date_formatted(self.cr, self.uid, datetime=po.catalogue_id.period_to) or '/'), 'header_style'),
            self.cell_ro('', 'header_style'), self.cell_ro('', 'header_right_style')
        ])
        row_idx += 1
        sheet.merged_cells.ranges.append("A%(row_idx)d:B%(row_idx)d" % {'row_idx': row_idx})
        sheet.merged_cells.ranges.append("C%(row_idx)d:E%(row_idx)d" % {'row_idx': row_idx})
        sheet.append([
            self.cell_ro(_('Report generated:'), 'header_style'), self.cell_ro('', 'header_style'),
            self.cell_ro(date_obj.get_date_formatted(self.cr, self.uid, datetime=datetime.now().strftime('%Y-%m-%d')), 'header_style'), self.cell_ro('', 'header_style'), self.cell_ro('', 'header_right_style')
        ])
        row_idx += 1

        sheet.merged_cells.ranges.append("A%(row_idx)d:E%(row_idx)d" % {'row_idx': row_idx})
        sheet.append([self.cell_ro('', 'header_style'), self.cell_ro('', 'header_style'), self.cell_ro('', 'header_style'), self.cell_ro('', 'header_style'), self.cell_ro('', 'header_right_style')])
        row_idx += 1

        sheet.merged_cells.ranges.append("A%(row_idx)d:E%(row_idx)d" % {'row_idx': row_idx})
        sheet.append([
            self.cell_ro(_('Catalogue adherence summary'), 'title_style'), self.cell_ro('', 'title_style'),
            self.cell_ro('', 'title_style'), self.cell_ro('', 'title_style'), self.cell_ro('', 'title_right_style')
        ])
        row_idx += 1
        sheet.merged_cells.ranges.append("A%(row_idx)d:E%(row_idx)d" % {'row_idx': row_idx})
        sheet.append([
            self.cell_ro(po.catalogue_ratio_plain_text, 'header_style'), self.cell_ro('', 'header_style'),
            self.cell_ro('', 'header_style'), self.cell_ro('', 'header_style'), self.cell_ro('', 'header_right_style')
        ])
        row_idx += 1
        sheet.merged_cells.ranges.append("A%(row_idx)d:E%(row_idx)d" % {'row_idx': row_idx})
        sheet.append([
            self.cell_ro(po.catalogue_deviation_plain_text, 'header_bottom_right_style'),
            self.cell_ro('', 'header_bottom_style'), self.cell_ro('', 'header_bottom_style'),
            self.cell_ro('', 'header_bottom_style'), self.cell_ro('', 'header_bottom_right_style')
        ])
        row_idx += 1

        sheet.append([])
        row_idx += 1

        col_title = [_('PO line'), _('Product Code'), _('Product Description'), _('PO Quantity'),
                     _('UoM'), _('PO Unit Price'), _('Catalogue Unit Price'), _('PO Subtotal'),
                     _('Catalogue Subtotal'), _('Currency'), _('% PO Unit Price Deviation'),
                     _('Delivery Request Date'), _('Mismatch'), _('Catalogue SoQ'), _('Comment'),
                     _('External Ref'), _('Justification Code'), _('Justification Coordination'),
                     _('HQ Remarks'), _('Justification Y/N'), _('Cold chain type'),
                     _('Dangerous Good Type'), _('Controlled Substance Type'), _('State')]
        sheet.append([self.cell_ro(x, 'col_title') for x in col_title])


        fields = self.pool.get('purchase.order.line').fields_get(self.cr, self.uid, ['catalog_mismatch', 'state_to_display'], context=context)
        label_catalog_mismatch = dict(fields['catalog_mismatch']['selection'])
        label_state_to_display = dict(fields['state_to_display']['selection'])

        fields = self.pool.get('product.product').fields_get(self.cr, self.uid, ['dangerous_goods'], context=context)
        label_dangerous_goods = dict(fields['dangerous_goods']['selection'])

        for line in po.order_line_mismatch:
            catalog_price_unit, catalog_subtotal, catalog_price_deviation = '', '', ''
            if not isinstance(line.catalog_price_unit, bool) and line.catalog_price_unit is not None:
                catalog_price_unit = line.catalog_price_unit
            if not isinstance(line.catalog_subtotal, bool) and line.catalog_subtotal is not None:
                catalog_subtotal = line.catalog_subtotal
            if not isinstance(line.catalog_price_deviation, bool) and line.catalog_price_deviation is not None \
                    and line.catalog_price_deviation != 0:
                catalog_price_deviation = line.catalog_price_deviation

            sheet.append([
                self.cell_ro(line.line_number, 'row_int'),
                self.cell_ro(line.product_id.default_code, 'row_text'),
                self.cell_ro(line.product_id.name, 'row_text'),
                self.cell_ro(line.product_qty, 'row_float'),
                self.cell_ro(line.product_uom.name, 'row_text'),
                self.cell_ro(line.price_unit, 'row_float'),
                self.cell_ro(catalog_price_unit, 'row_float'),
                self.cell_ro(line.price_subtotal, 'row_float'),
                self.cell_ro(catalog_subtotal, 'row_float'),
                self.cell_ro(line.currency_id.name, 'row_text'),
                self.cell_ro(catalog_price_deviation, 'row_float'),
                self.cell_ro(line.date_planned and datetime.strptime(line.date_planned, '%Y-%m-%d') or '', 'row_date'),
                self.cell_ro(label_catalog_mismatch.get(line.catalog_mismatch) or '', 'row_text'),
                self.cell_ro(line.catalog_soq or '', 'row_float'),
                self.cell_ro(line.comment or '', 'row_text'),
                self.cell_ro(line.external_ref or '', 'row_text'),
                self.cell_ro(line.product_id and line.product_id.justification_code_id and line.product_id.justification_code_id.code or '', 'row_text'),
                self.cell_ro('', 'row_text'),
                self.cell_ro('', 'row_text'),
                self.cell_ro('', 'row_text'),
                self.cell_ro(line.product_id and line.product_id.heat_sensitive_item and line.product_id.heat_sensitive_item.code == 'yes' and line.product_id.cold_chain and line.product_id.cold_chain.code or '', 'row_text'),
                self.cell_ro(line.product_id and line.product_id.dangerous_goods != 'False' and label_dangerous_goods.get(line.product_id.dangerous_goods) or '', 'row_text'),
                self.cell_ro(line.product_id and (line.product_id.controlled_substance == 'True' and 'CS / NP' or line.product_id.controlled_substance) or '', 'row_text'),
                self.cell_ro(label_state_to_display.get(line.state_to_display) or '', 'row_text'),
            ])


XlsxReport('report.report_line_mismatch', parser=line_mismatch, template='addons/purchase/report/line_mismatch.xlsx')

