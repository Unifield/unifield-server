# -*- coding: utf-8 -*-
from spreadsheet_xml.xlsx_write import XlsxReport
from spreadsheet_xml.xlsx_write import XlsxReportParser
from datetime import datetime
from dateutil.relativedelta import relativedelta
from tools import misc
from tools.translate import _
from openpyxl.utils.cell import column_index_from_string, get_column_letter
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Border, Side


class asset_parser(XlsxReportParser):

    def generate(self, context=None):
        asset_obj = self.pool.get('product.asset')
        reg_data = self.pool.get('asset.register.commons').get_asset_register_data(self.cr, self.uid, self.uid, context=context)

        asset_count = 0
        init_value = 0
        accumulated_depreciation = 0
        remain_net_value_book = 0
        remain_net_value_func = 0

        sheet = self.workbook.active
        sheet.freeze_panes = 'S5'

        report_infos_title_style = self.create_style_from_template('report_infos_title_style', 'A1')
        report_infos_value_style = self.create_style_from_template('report_infos_value_style', 'B1')
        header_style = self.create_style_from_template('header_style', 'C4')
        header_style.outline = False
        thin = Side(border_style="thin", color="000000", style='thin')
        medium = Side(border_style="medium", color="000000", style='medium')
        header_style.border = Border(top=medium, left=thin, right=thin, bottom=medium)
        big_title_style = self.create_style_from_template('big_title_style', 'E1')
        row_cell_style = self.create_style_from_template('row_cell_style', 'F6')
        total_style = self.create_style_from_template('total_style', 'B8')


        self.duplicate_row_dimensions(range(1, 6))
        self.duplicate_column_dimensions(default_width=15)

        sheet.title = _('Fixed Assets Register')

        row1 = []

        inst_cell = WriteOnlyCell(sheet, value=_('Prop. Instance:'))
        report_infos_title_style.border = Border(top=thin, left=thin, right=thin, bottom=thin)
        inst_cell.style = report_infos_title_style
        inst_val_cell = WriteOnlyCell(sheet, value=reg_data.get('prop_instance',''))
        report_infos_value_style.border = Border(top=thin, left=thin, right=medium, bottom=thin)
        inst_val_cell.style = report_infos_value_style
        sheet.merged_cells.ranges.append("E1:N2")
        cell_title = WriteOnlyCell(sheet, value=_('Fixed Assets Register'))
        big_title_style.border = Border(top=thin, left=medium, right=medium, bottom=medium)
        cell_title.style = big_title_style
        empty_title_cell = WriteOnlyCell(sheet, value='')
        empty_title_cell.style = big_title_style
        date_cell = WriteOnlyCell(sheet, value=_('Report Date:'))
        report_infos_title_style.border = Border(top=thin, left=medium, right=thin, bottom=thin)
        date_cell.style = report_infos_title_style
        date_val_cell = WriteOnlyCell(sheet, value=reg_data.get('report_date',''))
        report_infos_value_style.border = Border(top=thin, left=thin, right=thin, bottom=thin)
        date_val_cell.style = report_infos_value_style
        row1.extend([inst_cell, inst_val_cell, '', '', cell_title] + ([empty_title_cell] * 9) + ([''] * 2) + [date_cell, date_val_cell])
        sheet.append(row1)

        row2 = []

        curr_cell = WriteOnlyCell(sheet, value=_('Func. Currency:'))
        report_infos_title_style.border = Border(top=thin, left=thin, right=thin, bottom=medium)
        curr_cell.style = report_infos_title_style
        curr_val_cell = WriteOnlyCell(sheet, value=reg_data.get('func_currency', ''))
        report_infos_value_style.border = Border(top=thin, left=thin, right=medium, bottom=medium)
        curr_val_cell.style = report_infos_value_style
        period_cell = WriteOnlyCell(sheet, value=_('Period:'))
        report_infos_title_style.border = Border(top=thin, left=medium, right=thin, bottom=medium)
        period_cell.style = report_infos_title_style
        period_val_cell = WriteOnlyCell(sheet, value=reg_data.get('current_period',''))
        report_infos_value_style.border = Border(top=thin, left=thin, right=thin, bottom=medium)
        period_val_cell.style = report_infos_value_style
        row2.extend([curr_cell, curr_val_cell, '', '', cell_title] + ([''] * 11) + [period_cell, period_val_cell])
        sheet.append(row2)

        sheet.append([])

        row_headers = [
            (_('Asset code')),
            (_('Capitalization Entry sequence')),
            (_('Capitalization Period')),
            (_('Product code')),
            (_('Product Description')),
            (_('Serial Number')),
            (_('Instance creator')),
            (_('Instance of use')),
            (_('Analytic distribution')),
            (_('Asset type')),
            (_('Useful life')),
            (_('Booking Currency')),
            (_('Initial Value Booking Curr.')),
            (_('Accumulated Depr. Booking Curr.')),
            (_('Remaining net value Booking Currency')),
            (_('Remaining net value Func. Currency')),
            (_('Fixed Asset Status')),
            (_('External Asset ID')),
        ]

        header_row = []
        for header in row_headers:
            cell_t = WriteOnlyCell(sheet, value=header)
            if header == _('External Asset ID'):
                header_style.border = Border(top=medium, left=thin, right=medium, bottom=medium)
            cell_t.style = header_style
            header_row.append(cell_t)
        sheet.append(header_row)

        asset_fields = ['name', 'move_line_id', 'prod_int_code', 'prod_int_name', 'serial_nb', 'instance_id',
                        'used_instance_id', 'analytic_distribution_id', 'asset_type_id', 'useful_life_id',
                        'invo_currency', 'invo_value', 'depreciation_amount', 'disposal_amount', 'state',
                        'external_asset_id']

        sorted_assets = [*(reg_data.get('draft_asset_ids', [])),
                         *(reg_data.get('open_asset_ids', [])),
                         *(reg_data.get('active_asset_ids', [])),
                         *(reg_data.get('running_asset_ids', [])),
                         *(reg_data.get('depreciated_asset_ids', [])),
                         *(reg_data.get('disposed_asset_ids', []))]

        for asset_id in sorted_assets:
            asset_count += 1
            asset_row = []
            asset = asset_obj.browse(self.cr, self.uid, asset_id, fields_to_fetch= asset_fields, context=context)
            sheet.row_dimensions[asset_count + 5].height = 45
            for field in row_headers:
                if field == _('Asset code'):
                    cell_value = asset.name or ''
                if field == _('Capitalization Entry sequence'):
                    cell_value = asset.move_line_id and asset.move_line_id.move_id and asset.move_line_id.move_id.name or ''
                if field == _('Capitalization Period'):
                    cell_value = asset.move_line_id and asset.move_line_id.period_id and asset.move_line_id.period_id.name or ''
                if field == _('Product code'):
                    cell_value = asset.prod_int_code or ''
                if field == _('Product Description'):
                    cell_value = asset.prod_int_name or ''
                if field == _('Serial Number'):
                    cell_value = asset.serial_nb or ''
                if field == _('Instance creator'):
                    cell_value = asset.instance_id and asset.instance_id.instance or ''
                if field == _('Instance of use'):
                    cell_value = asset.used_instance_id and asset.used_instance_id.instance or ''
                if field == _('Analytic distribution'):
                    asset_ad = ''
                    ads = []
                    if asset.analytic_distribution_id and asset.analytic_distribution_id.funding_pool_lines:
                        for fp_line in asset.analytic_distribution_id.funding_pool_lines:
                            cc_code = fp_line.cost_center_id.code
                            dest_code = fp_line.destination_id.code
                            fp_code = fp_line.analytic_id.code
                            percentage = str(fp_line.percentage)
                            line_ad = ';'.join([cc_code, dest_code , fp_code, percentage])
                            ads.append(line_ad)
                        asset_ad = ' | '.join(ads)
                    cell_value = asset_ad
                if field == _('Asset type'):
                    cell_value = asset.asset_type_id and asset.asset_type_id.name or ''
                if field == _('Useful life'):
                    cell_value = asset.useful_life_id and asset.useful_life_id.year or ''
                if field == _('Booking Currency'):
                    cell_value = asset.invo_currency and asset.invo_currency.name or ''
                if field == _('Initial Value Booking Curr.'):
                    cell_value = asset.invo_value
                    init_value += asset.invo_value or 0
                if field == _('Accumulated Depr. Booking Curr.'):
                    cell_value = asset.depreciation_amount
                    accumulated_depreciation += asset.depreciation_amount or 0
                if field == _('Remaining net value Booking Currency'):
                    cell_value = asset.disposal_amount
                    remain_net_value_book += asset.disposal_amount
                if field == _('Remaining net value Func. Currency'):
                    rate = self.pool.get('res.currency').browse(self.cr, self.uid, reg_data.get('func_currency_id'), fields_to_fetch=['rate'], context=context).rate
                    func_amount = asset.disposal_amount * rate
                    cell_value = func_amount
                    remain_net_value_func += func_amount
                if field == _('Fixed Asset Status'):
                    cell_value = asset.state or ''
                if field == _('External Asset ID'):
                    cell_value = asset.external_asset_id or ''

                cell = WriteOnlyCell(sheet, value=cell_value)
                cell.style = row_cell_style
                asset_row.append(cell)

            sheet.append(asset_row)

        total_title = _('Summary: ') + 'Total'
        total_cell = WriteOnlyCell(sheet, value=total_title)
        total_style.border = Border(top=medium, left=thin, right=thin, bottom=medium)
        total_cell.style = total_style
        total_val_cell = WriteOnlyCell(sheet, value=asset_count)
        total_val_cell.style = total_style
        empty_total_cell = WriteOnlyCell(sheet, value='')
        empty_total_cell.style = total_style
        total_init_value_cell = WriteOnlyCell(sheet, value=init_value)
        total_init_value_cell.style = total_style
        total_accumul_depr_cell = WriteOnlyCell(sheet, value=init_value)
        total_accumul_depr_cell.style = total_style
        remain_net_value_book_cell = WriteOnlyCell(sheet, value=remain_net_value_book)
        remain_net_value_book_cell.style = total_style
        remain_net_value_func_cell = WriteOnlyCell(sheet, value=remain_net_value_func)
        remain_net_value_func_cell.style = total_style
        last_empty_cell = WriteOnlyCell(sheet, value='')
        total_style.border = Border(top=medium, left=thin, right=medium, bottom=medium)
        last_empty_cell.style = total_style

        total_row = [total_cell, total_val_cell] +\
                    ([empty_total_cell] * 10) +\
                    [total_init_value_cell, total_accumul_depr_cell, remain_net_value_book_cell, remain_net_value_func_cell] +\
                    [empty_total_cell, last_empty_cell]

        sheet.row_dimensions[asset_count + 5].height = 20
        sheet.append(total_row)

        return True

XlsxReport('report.asset.register.report.xlsx', parser=asset_parser, template='addons/product_asset/report/Fixed_assets_register_mockup.xlsx')