# -*- coding: utf-8 -*-
from osv import osv
from spreadsheet_xml.xlsx_write import XlsxReport
from spreadsheet_xml.xlsx_write import XlsxReportParser
from tools.translate import _
from datetime import datetime
from openpyxl.cell import WriteOnlyCell


class tkc_kcl_comparison_parser(XlsxReportParser):

    def add_cell(self, value=None, style='default_style', number_format=None):
        # None value set a xls empty cell
        # False value set the xls False()
        new_cell = WriteOnlyCell(self.workbook.active, value=value)
        new_cell.style = style
        if number_format:
            new_cell.number_format = number_format
        self.rows.append(new_cell)

    def generate(self, context=None):
        kcl = self.pool.get('composition.kit').browse(self.cr, self.uid, self.ids[0], context=context)
        tkc = kcl.composition_version_id
        mml_msl_sel = {'T': _('Yes'), 'F': _('No'), 'na': ''}

        # Fetch first to have the deviations
        deviation_data, comparison_data = self.get_tkc_kcl_comparison_data(self.cr, self.uid, kcl.id, context=context)

        sheet = self.workbook.active
        sheet.title = _('TKC KCL Comparison')
        self.duplicate_column_dimensions(default_width=10.75)

        # Styles
        default_style = self.create_style_from_template('default_style', 'E3')

        title_style = self.create_style_from_template('title_style', 'A21')
        header_style = self.create_style_from_template('header_style', 'A1')
        header_dark_style = self.create_style_from_template('header_dark_style', 'N25')
        header_bold_style = self.create_style_from_template('header_bold_style', 'A4')
        header_blue_style = self.create_style_from_template('header_blue_style', 'D25')
        header_green_style = self.create_style_from_template('header_green_style', 'G25')
        art_deviation_style = self.create_style_from_template('art_deviation_style', 'B22')
        line_style = self.create_style_from_template('line_style', 'A27')
        line_grey_style = self.create_style_from_template('line_grey_style', 'A10')
        line_dark_grey_style = self.create_style_from_template('line_dark_grey_style', 'A26')
        line_date_style = self.create_style_from_template('line_date_style', 'K27')
        line_float_style = self.create_style_from_template('line_float_style', 'E27')
        line_float_dark_grey_style = self.create_style_from_template('line_float_dark_grey_style', 'E26')
        line_red_float_dark_grey_style = self.create_style_from_template('line_red_float_dark_grey_style', 'N31')

        # Header data: 4 frames
        cell_default = WriteOnlyCell(sheet, value='')
        cell_default.style = default_style
        cell_header_empty = WriteOnlyCell(sheet, value='')
        cell_header_empty.style = header_style
        cell_empty = WriteOnlyCell(sheet, value='')
        cell_empty.style = line_style

        cell_1_db_title = WriteOnlyCell(sheet, value=_('DB/Instance name'))
        cell_1_db_title.style = header_style
        instance_name = self.pool.get('res.users').browse(self.cr, self.uid, [self.uid], context=context)[0].company_id.instance_id.instance
        cell_1_db_name = WriteOnlyCell(sheet, value=instance_name or '')
        cell_1_db_name.style = line_style
        sheet.append([cell_1_db_title, cell_1_db_name, cell_empty])
        sheet.merged_cells.ranges.append("B1:C1")

        cell_1_generated_title = WriteOnlyCell(sheet, value=_('Generated on'))
        cell_1_generated_title.style = header_style
        cell_1_generated_name = WriteOnlyCell(sheet, value=datetime.now())
        cell_1_generated_name.style = line_date_style
        sheet.append([cell_1_generated_title, cell_1_generated_name, cell_empty])
        sheet.merged_cells.ranges.append("B2:C2")

        sheet.append([])

        cell_2_title = WriteOnlyCell(sheet, value=_('Theoretical Kit Composition details'))
        cell_2_title.style = header_bold_style
        sheet.append([cell_2_title, cell_header_empty, cell_header_empty])
        sheet.merged_cells.ranges.append("A4:C4")

        cell_2_prod_title = WriteOnlyCell(sheet, value=_('TKC/Product'))
        cell_2_prod_title.style = header_style
        cell_2_prod_name = WriteOnlyCell(sheet, value='[%s] %s' % (tkc.composition_product_id.default_code, tkc.composition_product_id.name))
        cell_2_prod_name.style = line_style
        sheet.append([cell_2_prod_title, cell_2_prod_name, cell_empty])
        sheet.merged_cells.ranges.append("B5:C5")

        cell_2_ver_title = WriteOnlyCell(sheet, value=_('TKC/Version'))
        cell_2_ver_title.style = header_style
        cell_2_ver_name = WriteOnlyCell(sheet, value=tkc.composition_version_txt)
        cell_2_ver_name.style = line_style
        sheet.append([cell_2_ver_title, cell_2_ver_name, cell_empty])
        sheet.merged_cells.ranges.append("B6:C6")

        cell_2_date_title = WriteOnlyCell(sheet, value=_('TKC/Creation Date'))
        cell_2_date_title.style = header_style
        cell_2_date_name = WriteOnlyCell(sheet, value=datetime.strptime(tkc.composition_creation_date, '%Y-%m-%d'))
        cell_2_date_name.style = line_date_style
        sheet.append([cell_2_date_title, cell_2_date_name, cell_empty])
        sheet.merged_cells.ranges.append("B7:C7")

        cell_2_active_title = WriteOnlyCell(sheet, value=_('TKC/Active'))
        cell_2_active_title.style = header_style
        cell_2_active_name = WriteOnlyCell(sheet, value=tkc.active and _('Yes') or _('No'))
        cell_2_active_name.style = line_style
        sheet.append([cell_2_active_title, cell_2_active_name, cell_empty])
        sheet.merged_cells.ranges.append("B8:C8")

        cell_notes = WriteOnlyCell(sheet, value=_('Notes'))
        cell_notes.style = header_style
        sheet.append([cell_notes, cell_header_empty, cell_header_empty])
        sheet.merged_cells.ranges.append("A9:C9")

        sheet.row_dimensions[10].height = 30
        cell_notes2_tkc = WriteOnlyCell(sheet, value=tkc.composition_description or '')
        cell_notes2_tkc.style = line_grey_style
        sheet.append([cell_notes2_tkc, cell_empty, cell_empty])
        sheet.merged_cells.ranges.append("A10:C10")

        sheet.append([])

        cell_3_title = WriteOnlyCell(sheet, value=_('Kit Composition List details'))
        cell_3_title.style = header_bold_style
        sheet.append([cell_3_title, cell_header_empty, cell_header_empty])
        sheet.merged_cells.ranges.append("A12:C12")

        cell_3_prod_title = WriteOnlyCell(sheet, value=_('KCL/Product'))
        cell_3_prod_title.style = header_style
        cell_3_prod_name = WriteOnlyCell(sheet, value='[%s] %s' % (kcl.composition_product_id.default_code, kcl.composition_product_id.name))
        cell_3_prod_name.style = line_style
        sheet.append([cell_3_prod_title, cell_3_prod_name, cell_empty])
        sheet.merged_cells.ranges.append("B13:C13")

        cell_3_ver_title = WriteOnlyCell(sheet, value=_('KCL/Version'))
        cell_3_ver_title.style = header_style
        sheet.append([cell_3_ver_title, cell_2_ver_name, cell_empty])
        sheet.merged_cells.ranges.append("B14:C14")

        cell_3_bn_title = WriteOnlyCell(sheet, value=_('KCL/Batch Nb'))
        cell_3_bn_title.style = header_style
        cell_3_bn_name = WriteOnlyCell(sheet, value=kcl.composition_lot_id and kcl.composition_lot_id.name or '')
        cell_3_bn_name.style = line_style
        sheet.append([cell_3_bn_title, cell_3_bn_name, cell_empty])
        sheet.merged_cells.ranges.append("B15:C15")

        cell_3_exp_title = WriteOnlyCell(sheet, value=_('KCL/Expiry Date'))
        cell_3_exp_title.style = header_style
        cell_3_exp_name = WriteOnlyCell(sheet, value=kcl.composition_exp and datetime.strptime(kcl.composition_exp, '%Y-%m-%d') or '')
        cell_3_exp_name.style = line_date_style
        sheet.append([cell_3_exp_title, cell_3_exp_name, cell_empty])
        sheet.merged_cells.ranges.append("B16:C16")

        cell_3_date_title = WriteOnlyCell(sheet, value=_('KCL/Creation Date'))
        cell_3_date_title.style = header_style
        cell_3_date_name = WriteOnlyCell(sheet, value=datetime.strptime(kcl.composition_creation_date, '%Y-%m-%d'))
        cell_3_date_name.style = line_date_style
        sheet.append([cell_3_date_title, cell_3_date_name, cell_empty])
        sheet.merged_cells.ranges.append("B17:C17")

        sheet.append([cell_notes, cell_header_empty, cell_header_empty])
        sheet.merged_cells.ranges.append("A18:C18")

        sheet.row_dimensions[19].height = 30
        cell_notes2_kcl = WriteOnlyCell(sheet, value=kcl.composition_description or '')
        cell_notes2_kcl.style = line_grey_style
        sheet.append([cell_notes2_kcl, cell_empty, cell_empty])
        sheet.merged_cells.ranges.append("A19:C19")

        sheet.append([])

        cell_4_title = WriteOnlyCell(sheet, value=_('Comparison Summary'))
        cell_4_title.style = title_style
        sheet.append([cell_4_title, cell_default, cell_default])
        sheet.merged_cells.ranges.append("A21:C21")

        cell_4_art = WriteOnlyCell(sheet, value=_('KCL-TKC Article Deviation (%)'))
        cell_4_art.style = header_style
        cell_4_art_percent = WriteOnlyCell(sheet, value=deviation_data['prod_deviation'])
        cell_4_art_percent.style = art_deviation_style
        sheet.append([cell_4_art, cell_4_art_percent, cell_empty])
        sheet.merged_cells.ranges.append("B22:C22")

        sheet.row_dimensions[23].height = 45
        cell_4_qty = WriteOnlyCell(sheet, value=_('KCL-TKC Quantity Deviation (%)'))
        cell_4_qty.style = header_style
        cell_4_qty_percent = WriteOnlyCell(sheet, value=deviation_data['qty_deviation'])
        cell_4_qty_percent.style = line_style
        sheet.append([cell_4_qty, cell_4_qty_percent, cell_empty])
        sheet.merged_cells.ranges.append("B23:C23")

        sheet.append([])

        # Lines data
        row_headers = [
            (_('Product Code'), header_style),
            (_('Product Description'), header_style),
            (_('UoM'), header_style),
            (_('TKC Module'), header_blue_style),
            (_('TKC Total Quantity'), header_blue_style),
            (_('TKC Comment'), header_blue_style),
            (_('KCL Module'), header_green_style),
            (_('KCL Total Quantity'), header_green_style),
            (_('KCL Quantity'), header_green_style),
            (_('KCL Batch Number'), header_green_style),
            (_('KCL Expiry Date'), header_green_style),
            (_('KCL Comment'), header_green_style),
            (_('KCL Asset'), header_green_style),
            (_('Difference between TKC and KCL'), header_dark_style),
            (_('B. Num mandatory'), line_dark_grey_style),
            (_('Exp. Date mandatory'), line_dark_grey_style),
            (_('CC'), line_dark_grey_style),
            (_('DG'), line_dark_grey_style),
            (_('CS'), line_dark_grey_style),
            (_('MML'), line_dark_grey_style),
            (_('MSL'), line_dark_grey_style),
        ]

        row_header = []
        for header, current_style in row_headers:
            cell_t = WriteOnlyCell(sheet, value=header)
            cell_t.style = current_style
            row_header.append(cell_t)
        sheet.append(row_header)

        for prod_id in comparison_data:
            sum_data = comparison_data[prod_id]
            self.rows = []

            self.add_cell(sum_data['prod_name'], line_dark_grey_style)
            self.add_cell(sum_data['prod_desc'], line_dark_grey_style)
            self.add_cell(sum_data['tkc_uom'], line_dark_grey_style)
            self.add_cell(sum_data['tkc_module'], line_dark_grey_style)
            self.add_cell(sum_data['sum_tkc_qty'], line_float_dark_grey_style)
            self.add_cell(sum_data['tkc_comment'] or '', line_dark_grey_style)
            self.add_cell('', line_dark_grey_style)
            self.add_cell(sum_data['sum_kcl_qty'], line_float_dark_grey_style)
            self.add_cell('', line_dark_grey_style)
            self.add_cell('', line_dark_grey_style)
            self.add_cell('', line_dark_grey_style)
            self.add_cell('', line_dark_grey_style)
            self.add_cell('', line_dark_grey_style)
            self.add_cell(sum_data['sum_diff'], line_red_float_dark_grey_style)
            self.add_cell(sum_data['bn_mandatory'] and _('Y') or _('N'), line_dark_grey_style)
            self.add_cell(sum_data['exp_mandatory'] and _('Y') or _('N'), line_dark_grey_style)
            self.add_cell(sum_data['kc'] and _('Y') or '', line_dark_grey_style)
            self.add_cell(sum_data['dg'] and _('Y') or '', line_dark_grey_style)
            self.add_cell(sum_data['cs'] and _('Y') or '', line_dark_grey_style)
            self.add_cell(mml_msl_sel.get(sum_data['mml_status'], ''), line_dark_grey_style)
            self.add_cell(mml_msl_sel.get(sum_data['msl_status'], ''), line_dark_grey_style)

            sheet.append(self.rows)

            for kcl_line in sum_data['kcl_lines']:
                self.rows = []

                self.add_cell(sum_data['prod_name'], line_style)
                self.add_cell(sum_data['prod_desc'], line_style)
                self.add_cell(sum_data['tkc_uom'], line_style)
                self.add_cell('', line_style)
                self.add_cell('', line_style)
                self.add_cell('', line_style)
                self.add_cell(kcl_line['kcl_module'], line_style)
                self.add_cell('', line_style)
                self.add_cell(kcl_line['kcl_qty'], line_float_style)
                self.add_cell(kcl_line['kcl_bn'], line_style)
                self.add_cell(kcl_line['kcl_exp'] and datetime.strptime(kcl_line['kcl_exp'], '%Y-%m-%d') or '', line_date_style, number_format='DD/MM/YYYY')
                self.add_cell(kcl_line['kcl_comment'], line_style)
                self.add_cell(kcl_line['kcl_asset'], line_style)
                self.add_cell('', line_style)
                self.add_cell(sum_data['bn_mandatory'] and _('Y') or _('N'), line_style)
                self.add_cell(sum_data['exp_mandatory'] and _('Y') or _('N'), line_style)
                self.add_cell(sum_data['kc'] and _('Y') or '', line_style)
                self.add_cell(sum_data['dg'] and _('Y') or '', line_style)
                self.add_cell(sum_data['cs'] and _('Y') or '', line_style)
                self.add_cell(mml_msl_sel.get(sum_data['mml_status'], ''), line_style)
                self.add_cell(mml_msl_sel.get(sum_data['msl_status'], ''), line_style)

                sheet.append(self.rows)


    def get_tkc_kcl_comparison_data(self, cr, uid, kcl_id, context=None):
        '''
        Fetch the comparison data and matching percentage for each product of the KCL
        '''
        if context is None:
            context = {}
        if not kcl_id:
            raise osv.except_osv(_('Error'), _('KCL info should be filled to use this method'))

        ftf = ['composition_version_id', 'composition_item_ids']
        kcl = self.pool.get('composition.kit').browse(cr, uid, kcl_id, fields_to_fetch=ftf, context=context)

        cr.execute("""
            SELECT k.item_product_id, p.default_code, t.name, p.batch_management, p.perishable, p.is_kc, p.is_dg, p.is_cs,
                u.name, string_agg(DISTINCT(k.item_module), ';'), string_agg(DISTINCT(k.comment), ';'), SUM(k.item_qty)
            FROM composition_item k
                LEFT JOIN product_product p ON k.item_product_id=p.id
                LEFT JOIN product_template t ON p.product_tmpl_id=t.id
                LEFT JOIN product_uom u ON k.item_uom_id=u.id
            WHERE item_kit_id = %s
            GROUP BY k.item_product_id, p.default_code, t.name, u.name, p.batch_management, p.perishable, p.is_kc, 
                p.is_dg, p.is_cs, u.name
            ORDER BY string_agg(DISTINCT(k.item_module), ';')
        """, (kcl.composition_version_id.id,))
        tkc_prod, kcl_prod = [], []
        deviation_data, comparison_data = {}, {}
        for x in cr.fetchall():
            if x[0] not in tkc_prod:
                tkc_prod.append(x[0])
            prod_mml_msl = self.pool.get('product.product').read(cr, uid, x[0], ['mml_status', 'msl_status'], context=context)
            comparison_data[x[0]] = {
                'prod_name': x[1],
                'prod_desc': x[2],
                'bn_mandatory': x[3],
                'exp_mandatory': x[4],
                'kc': x[5],
                'dg': x[6],
                'cs': x[7],
                'mml_status': prod_mml_msl['mml_status'],
                'msl_status': prod_mml_msl['msl_status'],
                'tkc_uom': x[8],
                'tkc_module': x[9],
                'tkc_comment': x[10],
                'sum_tkc_qty': x[11],
                'sum_kcl_qty': 0,
                'sum_diff': x[11],
                'kcl_lines': [],
            }

        for kit_item in kcl.composition_item_ids:
            prod = kit_item.item_product_id
            if prod.id not in kcl_prod:
                kcl_prod.append(prod.id)
            if not comparison_data.get(prod.id):
                comparison_data[prod.id] = {
                    'prod_name': prod.default_code,
                    'prod_desc': prod.name,
                    'bn_mandatory': prod.batch_management,
                    'exp_mandatory': prod.perishable,
                    'kc': prod.is_kc,
                    'dg': prod.is_dg,
                    'cs': prod.is_cs,
                    'mml_status': prod.mml_status,
                    'msl_status': prod.msl_status,
                    'tkc_uom': kit_item.item_uom_id.name,
                    'tkc_module': '',
                    'tkc_comment': '',
                    'sum_tkc_qty': 0,
                    'sum_kcl_qty': 0,
                    'sum_diff': 0,
                    'kcl_lines': [],
                }
            comparison_data[prod.id]['kcl_lines'].append({
                'kcl_module': kit_item.item_module or '',
                'kcl_qty': kit_item.item_qty,
                'kcl_bn': kit_item.item_lot or '',
                'kcl_exp': kit_item.item_exp or '',
                'kcl_comment': kit_item.comment or '',
                'kcl_asset': kit_item.item_asset_id and kit_item.item_asset_id.name or '',
            })
            comparison_data[prod.id]['sum_kcl_qty'] += kit_item.item_qty
            comparison_data[prod.id]['sum_diff'] = comparison_data[prod.id]['sum_kcl_qty'] - comparison_data[prod.id]['sum_tkc_qty']

        prod_deviation = round((len(kcl_prod) - len(tkc_prod)) / len(tkc_prod), 2)  # Kept like this for the Excel cell format
        qty_deviation = []
        for prod_id in list(set(tkc_prod + kcl_prod)):
            if comparison_data.get(prod_id):
                comp_data = comparison_data[prod_id]
                if comp_data['sum_tkc_qty'] != 0:
                    qty_deviation_percent = round((comp_data['sum_diff'] / comp_data['sum_tkc_qty']) * 100)
                else:
                    qty_deviation_percent = 100
                if qty_deviation_percent != 0:
                    qty_deviation.append('%s: %s%s%%' % (comp_data['prod_name'], qty_deviation_percent > 0 and '+' or '', qty_deviation_percent))
        deviation_data.update({
            'prod_deviation': prod_deviation,
            'qty_deviation': '; '.join(qty_deviation),
        })

        return deviation_data, comparison_data


XlsxReport('report.report_tkc_kcl_comparison', parser=tkc_kcl_comparison_parser, template='addons/kit/report/tkc_kcl_comparison_report.xlsx')
