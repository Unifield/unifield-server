# -*- coding: utf-8 -*-
from spreadsheet_xml.xlsx_write import XlsxReport
from spreadsheet_xml.xlsx_write import XlsxReportParser
from datetime import datetime
from dateutil.relativedelta import relativedelta
from tools import misc
from tools.translate import _
from openpyxl.utils.cell import column_index_from_string, get_column_letter
from openpyxl.cell import WriteOnlyCell


class inventory_parser(XlsxReportParser):

    def add_cell(self, value=None, style='default_style'):
        # None value set an xls empty cell
        # False value set the xls False()
        new_cell = WriteOnlyCell(self.workbook.active, value=value)
        new_cell.style = style
        self.rows.append(new_cell)

    def generate(self, context=None):
        inventory = self.pool.get('replenishment.inventory.review').browse(self.cr, self.uid, self.ids[0], context=context)
        inventory_line_obj = self.pool.get('replenishment.inventory.review.line')

        sheet = self.workbook.active
        sheet.freeze_panes = 'D16'

        sub_title_style = self.create_style_from_template('sub_title_style', 'A3')
        sub_value_style = self.create_style_from_template('sub_value_style', 'C3')
        green_header_style = self.create_style_from_template('green_header_style', 'A15')
        red_header_style = self.create_style_from_template('red_header_style', 'F15')
        orange_header_style = self.create_style_from_template('orange_header_style', 'G15')
        blue_header_style = self.create_style_from_template('blue_header_style', 'Z15')
        yellow_header_style = self.create_style_from_template('yellow_header_style', 'AM15')
        pink1_header_style = self.create_style_from_template('pink1_header_style', 'AR15')
        pink2_header_style = self.create_style_from_template('pink2_header_style', 'AS15')

        default_style = self.create_style_from_template('default_style', 'A16')
        red_default_style = self.create_style_from_template('red_default_style', 'A17')
        grey_style = self.create_style_from_template('grey_style', 'H3')
        red_grey_style = self.create_style_from_template('red_grey_style', 'I3')
        percent_style = self.create_style_from_template('percent_style', 'H4')
        red_percent_style = self.create_style_from_template('red_percent_style', 'I4')
        float_style = self.create_style_from_template('float_style', 'H5')
        red_cell_style = self.create_style_from_template('red_cell_style', 'I5')
        date_style = self.create_style_from_template('date_style', 'H6')
        red_date_style = self.create_style_from_template('red_date_style', 'I6')

        self.duplicate_row_dimensions(range(1, 16))
        self.duplicate_column_dimensions(default_width=15)

        sheet.column_dimensions.group('AO', get_column_letter(column_index_from_string('AO')+2*inventory.projected_view - 1), hidden=False)
        sheet.column_dimensions.group('D', 'F', hidden=False)
        sheet.column_dimensions.group('S', 'V', hidden=False)
        sheet.row_dimensions.group(2, 14, hidden=False)


        sheet.title = _('Inv. Review')
        cell_title = WriteOnlyCell(sheet, value=_('Inventory Review'))
        self.apply_template_style('A1', cell_title)
        sheet.append([cell_title, ''])
        sheet.merged_cells.ranges.append("A1:B1")


        sheet.append([])


        time_unit_str = self.getSel(inventory, 'time_unit')
        doc_headers = [
            (_('Stock location configuration description'), inventory.location_config_id.description, ''),
            (_('Scheduled reviews periodicity'), inventory.frequence_name or '', ''),
            (_('Generated'), datetime.now(), 'dt'),
            (_('RR-AMC periodicity (1st month)'), self.to_datetime(inventory.amc_first_date), 'd'),
            (_('RR-AMC periodicity (last month)'), self.to_datetime(inventory.amc_last_date), 'd'),
            (_('Projected view (months from generation date)'), inventory.projected_view, ''),
            (_('Final day of projection'), self.to_datetime(inventory.final_date_projection), 'd'),
            (_('Sleeping stock alert parameter (months)'), inventory.sleeping, ''),
            (_('Display durations in'), time_unit_str, ''),
        ]

        row_index = 3
        for title, value, v_type in doc_headers:
            cell_t = WriteOnlyCell(sheet, value=title)
            cell_t.style = sub_title_style
            cell_e =  WriteOnlyCell(sheet)
            cell_e.style = sub_title_style
            cell_v = WriteOnlyCell(sheet, value=value)
            cell_v.style = sub_value_style
            if v_type == 'd':
                cell_v.number_format = 'DD/MM/YYYY'
            elif v_type == 'dt':
                cell_v.number_format = 'DD/MM/YYYY HH:MM'
            sheet.append([cell_t, cell_e, cell_v])
            sheet.merged_cells.ranges.append("A%(row_index)d:B%(row_index)d" % {'row_index':row_index})
            row_index += 1

        sheet.append([])
        sheet.append([])
        sheet.append([])

        row_headers = [
            (_('Product Code'), green_header_style),
            (_('Product Description'), green_header_style),
            (_('RR Lifecycle'), green_header_style),
            (_('Replaced/Replacing'), green_header_style),
            (_('MML'), green_header_style),
            (_('MSL'), green_header_style),
            (_('Warnings Recap'), red_header_style),
            (_('Segment Ref/name'), orange_header_style),
            (_('RR Type'), orange_header_style),
            ('%s %s' % (_('Internal LT'), time_unit_str), orange_header_style),
            ('%s %s' % (_('External LT'), time_unit_str), orange_header_style),
            (_('Total lead time'), orange_header_style),
            ('%s %s' % (_('Order coverage'), time_unit_str), orange_header_style),
            (_('SS (Qty)'), orange_header_style),
            (_('Buffer (Qty)'), orange_header_style),
            (_('Valid'), orange_header_style),
            (_('RR-FMC (average for period)'), orange_header_style),
            (_('RR-AMC (average for AMC period)'), orange_header_style),
            (_('Standard Deviation HMC'), orange_header_style),
            (_('Coefficient of Variation of HMC'), orange_header_style),
            (_('Standard Deviation of HMC vs FMC'), orange_header_style),
            (_('Coefficient of Variant of HMC and FMC'), orange_header_style),
            (_('Real Stock in location(s)'), blue_header_style),
            (_('Pipeline Qty'), blue_header_style),
            (_('Reserved Stock Qty'), blue_header_style),
            (_('(RR-FMC) Projected stock Qty'), blue_header_style),
            (_('(RR-AMC) Projected stock'), blue_header_style),
            (_('Qty of Projected Expiries before consumption'), blue_header_style),
            (_('Qty expiring within period'), blue_header_style),
            (_('Open Loan on product (Yes/No)'), blue_header_style),
            (_('Donations pending (Yes/No)'), blue_header_style),
            (_('Sleeping stock Qty'), blue_header_style),
            ('%s %s' % (time_unit_str,_('of supply (RR-AMC)')), blue_header_style),
            ('%s %s' % (time_unit_str, _('of supply (RR-FMC)')), blue_header_style),
            (_('Qty lacking before next RDD'), blue_header_style),
            (_('Qty lacking needed by'), yellow_header_style),
            (_('ETA date of next pipeline'), yellow_header_style),
            (_('Date to start preparing the next order'),  yellow_header_style),
            (_('Next order to be generated/issued by date'), yellow_header_style),
            (_('RDD for next order'), yellow_header_style),
        ]


        for nb_month in range(0, inventory.projected_view):
            row_headers.append(('%s M%s\n %s' % (_('RR value'), nb_month, self.get_month(inventory.generation_date, nb_month)), pink1_header_style))

        for nb_month in range(0, inventory.projected_view):
            row_headers.append(('%s\nM%s %s' % (_('Projected'), nb_month, self.get_month(inventory.generation_date, nb_month)), pink2_header_style))

        row_header = []
        for header, style in row_headers:
            cell_t = WriteOnlyCell(sheet, value=header)
            cell_t.style = style
            row_header.append(cell_t)
        sheet.append(row_header)

        new_row = 16
        inventory_line_ids = inventory_line_obj.search(self.cr, self.uid, [('review_id', '=', inventory.id)], context=context)
        browse_size = 1
        browse_index = 0
        while browse_index < len(inventory_line_ids):
            for line in inventory_line_obj.browse(self.cr, self.uid, inventory_line_ids[browse_index:browse_index+browse_size], context=context):
                browse_index += browse_size
                self.rows = []
                sheet.row_dimensions[new_row].height = 40

                # For MML alert 2
                if line.mml_status == 'F' or line.msl_status == 'F':
                    def_style = red_default_style
                    def_grey_style = red_grey_style
                    def_float_style = red_cell_style
                    def_percent_style = red_percent_style
                    def_date_style = red_date_style
                else:
                    def_style = default_style
                    def_grey_style = grey_style
                    def_float_style = float_style
                    def_percent_style = percent_style
                    def_date_style = date_style

                self.add_cell(line.product_id.default_code, def_style)
                self.add_cell(line.product_id.name, def_style)
                self.add_cell(line.segment_ref_name and self.getSel(line, 'status') or _('N/A'), def_style)
                self.add_cell(line.paired_product_id and line.paired_product_id.default_code or None, def_style)
                self.add_cell(self.getSel(line, 'mml_status'), def_style)
                self.add_cell(self.getSel(line, 'msl_status'), def_style)
                self.add_cell(line.warning or None, def_style)
                self.add_cell(line.segment_ref_name or None, def_style)
                self.add_cell(line.segment_ref_name and self.getSel(line, 'rule') or None, def_style)

                if inventory.time_unit == 'd':
                    lt_style = def_style
                else:
                    lt_style = def_float_style

                if line.segment_ref_name:
                    self.add_cell(line.internal_lt or None, lt_style)
                    self.add_cell(line.external_lt or None, lt_style)
                    self.add_cell(line.total_lt or None, lt_style)
                    self.add_cell(line.order_coverage or None, lt_style)
                    self.add_cell(line.safety_stock_qty or None, def_style)
                else:
                    self.add_cell('', def_style)
                    self.add_cell('', def_style)
                    self.add_cell('', def_style)
                    self.add_cell('', def_style)
                    self.add_cell('', def_style)

                if line.rule == 'cycle':
                    self.add_cell(line.buffer_qty or None, def_style)
                else:
                    self.add_cell('', def_grey_style)

                self.add_cell(line.valid_rr_fmc and _('Yes') or _('No'), def_style)
                self.add_cell(line.rr_fmc_avg or None, def_float_style)
                self.add_cell(line.rr_amc or None, def_float_style)
                self.add_cell(line.std_dev_hmc or None, def_float_style)
                self.add_cell(line.coef_var_hmc/100. or None, def_percent_style)

                if line.rule == 'cycle':
                    self.add_cell(line.std_dev_hmc_fmc or None, def_float_style)
                    self.add_cell(line.coef_var_hmc_fmc/100. or None, def_percent_style)
                else:
                    self.add_cell('', def_grey_style)
                    self.add_cell('', def_grey_style)

                self.add_cell(line.real_stock or None, def_style)
                self.add_cell(line.pipeline_qty or None, def_style)
                self.add_cell(line.reserved_stock_qty or None, def_style)

                if line.projected_stock_qty and line.rule == 'cycle':
                    self.add_cell(line.projected_stock_qty, def_style)
                else:
                    self.add_cell('', def_style)

                if line.projected_stock_qty_amc and (line.rule == 'cycle' or not line.segment_ref_name):
                    self.add_cell(line.projected_stock_qty_amc, def_style)
                else:
                    self.add_cell('', def_style)

                if line.expired_qty_before_cons:
                    self.add_cell(line.expired_qty_before_cons, def_style)
                else:
                    self.add_cell('', def_style)

                if line.total_expired_qty:
                    self.add_cell(line.total_expired_qty, def_style)
                else:
                    self.add_cell('', def_style)

                self.add_cell(line.open_loan and _('Yes') or _('No'), def_style)
                self.add_cell(line.open_donation and _('Yes') or _('No'), def_style)

                self.add_cell(line.sleeping_qty or None, def_style)
                self.add_cell(line.unit_of_supply_amc or None, def_float_style)

                self.add_cell(line.unit_of_supply_fmc or None, def_float_style)
                self.add_cell(line.qty_lacking or None, def_style)
                self.add_cell(self.to_datetime(line.qty_lacking_needed_by), def_date_style)
                self.add_cell(self.to_datetime(line.eta_for_next_pipeline), def_date_style)
                self.add_cell(self.to_datetime(line.date_preparing), def_date_style)
                self.add_cell(self.to_datetime(line.date_next_order_validated), def_date_style)
                self.add_cell(self.to_datetime(line.date_next_order_rdd), def_date_style)

                nb_pas = 0
                for detail_pas in line.pas_ids:
                    nb_pas += 1
                    if detail_pas.rr_fmc is not None and detail_pas.rr_fmc is not False:
                        if line.rule != 'minmax':
                            self.add_cell(detail_pas.rr_fmc, def_style)
                        elif detail_pas.rr_max is not False:
                            self.add_cell('%g / %g'% (detail_pas.rr_fmc, detail_pas.rr_max), def_style)
                        else:
                            self.add_cell(_('Invalid'), def_style)
                    else:
                        self.add_cell(_('Invalid'), def_style)

                for detail_pas in line.pas_ids:
                    if detail_pas.projected is not None and detail_pas.projected is not False:
                        if detail_pas.projected:
                            self.add_cell(detail_pas.projected, def_float_style)
                        else:
                            self.add_cell(detail_pas.projected, red_cell_style)
                    else:
                        self.add_cell()

                for nb_month in range(nb_pas, inventory.projected_view):
                    self.add_cell('', def_style)
                    self.add_cell('', def_style)

                sheet.append(self.rows)
                new_row += 1

    def get_month(self, start, nb_month):
        return _(misc.month_abbr[(datetime.strptime(start, '%Y-%m-%d %H:%M:%S') + relativedelta(hour=0, minute=0, second=0, months=nb_month)).month])

XlsxReport('report.report_replenishment_inventory_review_xls2', parser=inventory_parser, template='addons/procurement_cycle/report_doc/replenishment_inventory_review.xlsx')

