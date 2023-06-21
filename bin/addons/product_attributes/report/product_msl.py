# -*- coding: utf-8 -*-
from spreadsheet_xml.xlsx_write import XlsxReport
from spreadsheet_xml.xlsx_write import XlsxReportParser
from datetime import datetime
from tools.translate import _


class product_msl(XlsxReportParser):

    def generate(self, context=None):
        if context is None:
            context = {}

        instance_code = self.pool.get('res.company')._get_instance_record(self.cr, self.uid).code

        sheet = self.workbook.active

        self.create_style_from_template('title_style', 'A1')
        self.create_style_from_template('filter_txt', 'A2')
        self.create_style_from_template('filter_date', 'B3')


        self.create_style_from_template('header_row', 'A5')
        self.create_style_from_template('row', 'A6')

        sheet.column_dimensions['A'].width = 16
        sheet.column_dimensions['B'].width = 45
        sheet.column_dimensions['C'].width = 32
        sheet.column_dimensions['D'].width = 25
        sheet.column_dimensions['E'].width = 17
        sheet.column_dimensions['F'].width = 17
        sheet.column_dimensions['G'].width = 30
        sheet.column_dimensions['H'].width = 30
        sheet.column_dimensions['I'].width = 16
        sheet.column_dimensions['J'].width = 16
        sheet.column_dimensions['K'].width = 16
        sheet.freeze_panes = 'A6'

        sheet.title = _('MSL Products')

        sheet.merged_cells.ranges.append("A1:F1")
        sheet.append([self.cell_ro(_('MSL Products'), 'title_style')])

        sheet.append([
            self.cell_ro(_('Instance'), 'filter_txt'),
            self.cell_ro(instance_code, 'filter_txt'),
        ])
        sheet.append([
            self.cell_ro(_('Date'), 'filter_txt'),
            self.cell_ro(datetime.now(), 'filter_date'),
        ])
        sheet.append([])

        sheet.append([
            self.cell_ro(_('Code'), 'header_row'),
            self.cell_ro(_('Description'), 'header_row'),
            self.cell_ro(_('Family'), 'header_row'),
            self.cell_ro(_('Standardization Level'), 'header_row'),
            self.cell_ro(_('OC Subscription'), 'header_row'),
            self.cell_ro(_('UniData Status'), 'header_row'),
            self.cell_ro(_('UniField Status'), 'header_row'),
            self.cell_ro(_('MSL DB'), 'header_row'),
            self.cell_ro(_('Justification?'), 'header_row'),
            self.cell_ro(_('Controlled Substance?'), 'header_row'),
            self.cell_ro(_('MML code valid in this DB ?'), 'header_row'),
        ])

        prod_obj = self.pool.get('product.product')

        fields = prod_obj.fields_get(self.cr, self.uid, ['standard_ok', 'state_ud', 'is_msl_valid', 'is_mml_valid'], context=context)
        label_standard_ok = dict(fields['standard_ok']['selection'])
        label_state_ud = dict(fields['state_ud']['selection'])
        label_is_mml_valid = dict(fields['is_mml_valid']['selection'])

        total = prod_obj.search(self.cr, self.uid, [('oc_validation', '=', True)], count=True, context=context)

        page_size = 500
        offset = 0
        bk_id = self.context.get('background_id')

        while True:
            if self.model == 'unifield.instance':
                prod_ids = prod_obj.search(self.cr, self.uid, [('msl_project_ids', 'in', self.ids)], limit=page_size, offset=offset, context=context)
            else:
                prod_ids = prod_obj.search(self.cr, self.uid, [('in_msl_instance', '=', True)], limit=page_size, offset=offset, context=context)
            if not prod_ids:
                break
            offset += page_size

            if bk_id:
                self.pool.get('memory.background.report').write(self.cr, self.uid, bk_id, {'percent': min(0.9, max(0.1,offset/float(total)))})


            for prod in prod_obj.browse(self.cr, self.uid, prod_ids, fields_to_fetch=['code', 'name', 'nomen_manda_2', 'standard_ok', 'oc_subscription', 'state_ud', 'state', 'in_msl_instance', 'justification_code_id', 'controlled_substance', 'is_mml_valid'], context=context):
                sheet.append([
                    self.cell_ro(prod.code, 'row'),
                    self.cell_ro(prod.name, 'row'),
                    self.cell_ro(prod.nomen_manda_2.name, 'row'),
                    self.cell_ro(label_standard_ok.get(prod.standard_ok), 'row'),
                    self.cell_ro(prod.oc_subscription and _('Yes') or _('No'), 'row'),
                    self.cell_ro(label_state_ud.get(prod.state_ud), 'row'),
                    self.cell_ro(prod.state.name, 'row'),
                    self.cell_ro(', '.join([x.instance_id.instance for x in prod.in_msl_instance if x.instance_id]), 'row'),
                    self.cell_ro(prod.justification_code_id and prod.justification_code_id.code or '', 'row'),
                    self.cell_ro(prod.controlled_substance or '', 'row'),
                    self.cell_ro(label_is_mml_valid.get(prod.is_mml_valid), 'row'),
                ])
            if len(prod_ids) < page_size:
                break

        sheet.auto_filter.ref = "A5:K5"

XlsxReport('report.report.project_product_msl', parser=product_msl, template='addons/product_attributes/report/product_mml.xlsx')
XlsxReport('report.report.product_msl', parser=product_msl, template='addons/product_attributes/report/product_mml.xlsx')

