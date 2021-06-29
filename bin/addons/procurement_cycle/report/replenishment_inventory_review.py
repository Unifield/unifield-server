# -*- coding: utf-8 -*-
from spreadsheet_xml.xlsx_write import XlsxReport
from spreadsheet_xml.xlsx_write import XlsxReportParser
from datetime import datetime
from dateutil.relativedelta import relativedelta
from tools import misc
from tools.translate import _
import openpyxl
from openpyxl.utils.cell import column_index_from_string, get_column_letter
from openpyxl.styles import NamedStyle, Alignment, Font, Border, Side


class inventory_parser(XlsxReportParser):

    def generate(self, context=None):
        workbook = self.workbook
        sheet = workbook.active
        sheet.title = _('Inv. Review')
        sheet['A1'] = _('Inventory Review')


        row_index = 3

        inventory = self.pool.get('replenishment.inventory.review').browse(self.cr, self.uid, self.ids[0], context=context)

        time_unit_str = self.getSel(inventory, 'time_unit')
        doc_headers = [
            (_('Stock location configuration description'), inventory.location_config_id.description),
            (_('Scheduled reviews periodicity'), inventory.frequence_name or ''),
            (_('Generated'), self.to_datetime('')),
            (_('RR-AMC periodicity (1st month)'), self.to_datetime(inventory.amc_first_date)),
            (_('RR-AMC periodicity (last month)'), self.to_datetime(inventory.amc_last_date)),
            (_('Projected view (months from generation date)'), inventory.projected_view),
            (_('Final day of projection'), self.to_datetime(inventory.final_date_projection)),
            (_('Sleeping stock alert parameter (months)'), inventory.sleeping),
            (_('Display durations in'), time_unit_str),
        ]

        for title, value in doc_headers:
            sheet.cell(row=row_index, column=1, value=title)
            sheet.cell(row=row_index, column=3, value=value)
            row_index += 1


        row_headers = [
            _('Product Code'),
            _('Product Description'),
            _('RR Lifecycle'),
            _('Replaced/Replacing'),
            _('Primary Product list'),
            _('Warnings Recap'),
            _('Segment Ref/name'),
            _('RR (threshold) applied'),
            _('RR (qty) applied'),
            _('Min'),
            _('Max'),
            _('Automatic Supply order  qty'),
            '%s %s' % (_('Internal LT'), time_unit_str),
            '%s %s' % (_('External LT'), time_unit_str),
            _('Total lead time'),
            '%s %s' % (_('Order coverage'), time_unit_str),
            _('SS (Qty)'),
            _('Buffer (Qty)'),
            _('Valid'),
            _('RR-FMC (average for period)'),
            _('RR-AMC (average for AMC period)'),
            _('Standard Deviation HMC'),
            _('Coefficient of Variation of HMC'),
            _('Standard Deviation of HMC vs FMC'),
            _('Coefficient of Variant of HMC and FMC'),
            _('Real Stock in location(s)'),
            _('Pipeline Qty'),
            _('Reserved Stock Qty'),
            _('(RR-FMC)Projected stock Qty'),
            _('(RR-AMC) Projected stock'),
            _('Qty of Projected Expiries before consumption'),
            _('Qty expiring within period'),
            _('Open Loan on product (Yes/No)'),
            _('Donations pending (Yes/No)'),
            _('Sleeping stock Qty'),
            '%s %s' % (time_unit_str,_('of supply (RR-AMC)')),
            '%s %s' % (time_unit_str, _('of supply (RR-FMC)')),
            _('Qty lacking before next RDD'),
            _('Qty lacking needed by'),
            _('ETA date of next pipeline'),
            _('Date to start preparing the next order'),
            _('Next order to be generated/issued by date'),
            _('RDD for next order'),
        ]

        rr_fmc_style = self.create_style_from_cell(sheet['AR15'], 'rr_fmc_style')
        projected_style = self.create_style_from_cell(sheet['AS15'], 'projected_style')

        default_format = {
            'alignment': Alignment(wrapText=True, horizontal='center',  vertical='center'),
            'font': Font(name='Calibri', sz=11.0),
            'border': Border(
                left=Side(border_style='thin', color='FF000000'),
                right=Side(border_style='thin', color='FF000000'),
                top=Side(border_style='thin', color='FF000000'),
                bottom=Side(border_style='thin', color='FF000000'),
            ),
        }
        date_style = NamedStyle(name='date', number_format='DD/MM/YYYY', **default_format)
        default_style = NamedStyle(name='default', number_format='0.00', **default_format)
        precent_style = NamedStyle(name='precent', number_format='0.00%',  **default_format)
        float_style = NamedStyle(name='float', number_format='0.00',  **default_format)
        grey_style = NamedStyle(name='grey', fill=openpyxl.styles.fills.PatternFill(patternType='solid', fgColor=openpyxl.styles.colors.Color(rgb='FFD9D9D9')),  **default_format)

        col_index = column_index_from_string('AR')
        for nb_month in range(0, inventory.projected_view):
            sheet.cell(row=15, column=col_index).style = rr_fmc_style
            row_headers.append('%s M%s\n %s' % (_('RR-FMC'), nb_month, self.get_month(inventory.generation_date, nb_month)))
            col_index += 1

        for nb_month in range(0, inventory.projected_view):
            sheet.cell(row=15, column=col_index).style = projected_style
            row_headers.append('%s\nM%s %s' % (_('Projected'), nb_month, self.get_month(inventory.generation_date, nb_month)))
            col_index += 1

        column = 1
        for header in row_headers:
            sheet.cell(row=15, column=column, value=header)
            column += 1

        row = 16
        for line in inventory.line_ids:
            sheet.row_dimensions[row].height = 40
            sheet.cell(row=row, column=1, value=line.product_id.default_code).style = default_style
            sheet.cell(row=row, column=2, value=line.product_id.name).style = default_style
            sheet.cell(row=row, column=3, value=line.segment_ref_name and self.getSel(line, 'status') or _('N/A')).style = default_style
            sheet.cell(row=row, column=4, value=line.paired_product_id and line.paired_product_id.default_code or '').style = default_style
            sheet.cell(row=row, column=5, value=line.primay_product_list or '').style = default_style
            sheet.cell(row=row, column=6, value=line.warning or '').style = default_style
            sheet.cell(row=row, column=7, value=line.segment_ref_name or '').style = default_style
            sheet.cell(row=row, column=8, value=line.rule == 'cycle' and 'PAS' or '').style = default_style
            sheet.cell(row=row, column=9, value=line.segment_ref_name and self.getSel(line, 'rule') or '').style = default_style
            if line.rule == 'minmax':
                sheet.cell(row=row, column=10, value=line.min_qty).style = default_style
                sheet.cell(row=row, column=11, value=line.max_qty).style = default_style
            else:
                sheet.cell(row=row, column=10).style = grey_style
                sheet.cell(row=row, column=11).style = grey_style

            if line.rule == 'auto':
                sheet.cell(row=row, column=12, value=line.auto_qty).style = default_style
            else:
                sheet.cell(row=row, column=12).style = grey_style

            sheet.cell(row=row, column=13, value=line.internal_lt).style = default_style # float vs int
            sheet.cell(row=row, column=14, value=line.external_lt).style = default_style # float vs int
            sheet.cell(row=row, column=15, value=line.total_lt).style = default_style # float vs int
            sheet.cell(row=row, column=16, value=line.order_coverage).style = default_style # float vs int
            sheet.cell(row=row, column=17, value=line.safety_stock_qty).style = default_style
            if line.rule == 'cycle':
                sheet.cell(row=row, column=18, value=line.buffer_qty).style = default_style
            else:
                sheet.cell(row=row, column=18).style = grey_style

            sheet.cell(row=row, column=19, value=line.valid_rr_fmc and _('Yes') or _('No')).style = default_style
            sheet.cell(row=row, column=20, value=line.rr_fmc_avg).style = float_style
            sheet.cell(row=row, column=21, value=line.rr_amc).style = float_style
            sheet.cell(row=row, column=22, value=line.std_dev_hmc).style = float_style
            sheet.cell(row=row, column=23, value=line.coef_var_hmc/100.).style = precent_style

            if line.rule == 'cycle':
                sheet.cell(row=row, column=24, value=line.std_dev_hmc_fmc).style = float_style
                sheet.cell(row=row, column=25, value=line.coef_var_hmc_fmc).style = float_style
            else:
                sheet.cell(row=row, column=24).style = grey_style
                sheet.cell(row=row, column=25).style = grey_style

            sheet.cell(row=row, column=26, value=line.real_stock).style = default_style
            sheet.cell(row=row, column=27, value=line.pipeline_qty).style = default_style
            sheet.cell(row=row, column=28, value=line.reserved_stock_qty).style = default_style

            sheet.cell(row=row, column=29).style = default_style
            if line.projected_stock_qty and line.rule == 'cycle':
                sheet.cell(row=row, column=29, value=line.projected_stock_qty)

            sheet.cell(row=row, column=30).style = default_style
            if line.projected_stock_qty_amc and (line.rule == 'cycle' or not line.segment_ref_name):
                sheet.cell(row=row, column=30, value=line.projected_stock_qty_amc)

            sheet.cell(row=row, column=31).style = date_style
            if line.expired_qty_before_cons:
                sheet.cell(row=row, column=31, value=line.expired_qty_before_cons)

            sheet.cell(row=row, column=32).style = date_style
            if line.total_expired_qty:
                sheet.cell(row=row, column=32, value=line.total_expired_qty)

            sheet.cell(row=row, column=33, value=line.open_loan and _('Yes') or _('No')).style = default_style
            sheet.cell(row=row, column=34, value=line.open_donation and _('Yes') or _('No')).style = default_style

            sheet.cell(row=row, column=35, value=line.sleeping_qty).style = default_style
            sheet.cell(row=row, column=36, value=line.unit_of_supply_amc).style = default_style

            sheet.cell(row=row, column=37, value=line.unit_of_supply_fmc).style = default_style
            sheet.cell(row=row, column=38, value=line.qty_lacking).style = default_style
            sheet.cell(row=row, column=39, value=self.to_datetime(line.qty_lacking_needed_by)).style = date_style
            sheet.cell(row=row, column=40, value=self.to_datetime(line.eta_for_next_pipeline)).style = date_style
            sheet.cell(row=row, column=41, value=self.to_datetime(line.date_preparing)).style = date_style
            sheet.cell(row=row, column=42, value=self.to_datetime(line.date_next_order_validated)).style = date_style
            sheet.cell(row=row, column=43, value=self.to_datetime(line.date_next_order_rdd)).style = date_style

            column = 44
            for detail_pas in line.pas_ids:
                if detail_pas.rr_fmc is not None and detail_pas.rr_fmc is not False:
                    sheet.cell(row=row, column=column, value=detail_pas.rr_fmc).style = default_style
                else:
                    sheet.cell(row=row, column=column, value=_('Invalid FMC')).style = default_style
                column += 1

            for detail_pas in line.pas_ids:
                if detail_pas.projected is not None and detail_pas.projected is not False:
                    sheet.cell(row=row, column=column, value=detail_pas.projected).style = default_style
                column += 1
            if not line.pas_ids:
                for nb_month in range(0, inventory.projected_view):
                    sheet.cell(row=row, column=column, value='').style = default_style
                    sheet.cell(row=row, column=column+1, value='').style = default_style
                    column += 2
            row += 1
        sheet.column_dimensions.group('AR', get_column_letter(column_index_from_string('AR')+2*inventory.projected_view - 1), hidden=False)

    def get_month(self, start, nb_month):
        return _(misc.month_abbr[(datetime.strptime(start, '%Y-%m-%d %H:%M:%S') + relativedelta(hour=0, minute=0, second=0, months=nb_month)).month])

XlsxReport('report.report_replenishment_inventory_review_xls', parser=inventory_parser, template='addons/procurement_cycle/report/replenishment_inventory_review.xls')

