# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import osv
from osv import fields

import tools
from tools.translate import _

import pooler
import time
import threading
import logging
import os
import csv
import codecs
import cStringIO
from xlwt import Workbook, easyxf, Borders

# the ';' delimiter is recognize by default on the Microsoft Excel version I tried
STOCK_MISSION_REPORT_NAME_PATTERN = 'Stock_Mission_Rerport_%s_%s'
CSV_DELIMITER = ';'

HEADER_DICT = {
        'ns_nv_vals': (
            ('Reference', 'default_code'),
            ('Name', 'pt_name'),
            ('UoM', 'pu_name'),
            ('Instance stock', 'l_internal_qty'),
            ('Warehouse stock', 'l_wh_qty'),
            ('Cross-Docking Qty.', 'l_cross_qty'),
            ('Secondary Stock Qty.', 'l_secondary_qty'),
            ('Internal Cons. Unit Qty.', 'l_cu_qty'),
            ('AMC', 'product_amc'),
            ('FMC', 'product_consumption'),
            ('In Pipe Qty', 'l_in_pipe_qty'),),
        'ns_v_vals': (
            ('Reference', 'default_code'),
            ('Name', 'pt_name'),
            ('UoM', 'pu_name'),
            ('Cost Price', 'pt_standard_price'),
            ('Func. Cur.', 'rc_name'),
            ('Instance stock', 'l_internal_qty'),
            ('Instance stock val.', 'l_internal_qty_pt_price'),
            ('Warehouse stock', 'l_wh_qty'),
            ('Cross-Docking Qty.', 'l_cross_qty'),
            ('Secondary Stock Qty.', 'l_secondary_qty'),
            ('Internal Cons. Unit Qty.', 'l_cu_qty'),
            ('AMC', 'product_amc'),
            ('FMC', 'product_consumption'),
            ('In Pipe Qty', 'l_in_pipe_qty'),),
        's_nv_vals': (
            ('Reference', 'default_code'),
            ('Name', 'pt_name'),
            ('UoM', 'pu_name'),
            ('Instance stock', 'l_internal_qty'),
            ('Stock Qty.', 'l_stock_qty'),
            ('Unallocated Stock Qty.', 'l_central_qty'),
            ('Cross-Docking Qty.', 'l_cross_qty'),
            ('Secondary Stock Qty.', 'l_secondary_qty'),
            ('Internal Cons. Unit Qty.', 'l_cu_qty'),
            ('AMC', 'product_amc'),
            ('FMC', 'product_consumption'),
            ('In Pipe Qty', 'l_in_pipe_qty'),),
        's_v_vals': (
            ('Reference', 'default_code'),
            ('Name', 'pt_name'),
            ('UoM', 'pu_name'),
            ('Cost Price', 'pt_standard_price'),
            ('Func. Cur.', 'rc_name'),
            ('Instance stock', 'l_internal_qty'),
            ('Instance stock val.', 'l_internal_qty_pt_price'),
            ('Stock Qty.', 'l_stock_qty'),
            ('Unallocated Stock Qty.', 'l_central_qty'),
            ('Cross-Docking Qty.', 'l_cross_qty'),
            ('Secondary Stock Qty.', 'l_secondary_qty'),
            ('Internal Cons. Unit Qty.', 'l_cu_qty'),
            ('AMC', 'product_amc'),
            ('FMC', 'product_consumption'),
            ('In Pipe Qty', 'l_in_pipe_qty'),),
        }


GET_EXPORT_REQUEST = '''SELECT
        l.product_id AS product_id,
        replace(l.default_code, '%%', '%%%%') as default_code,
        replace(pt.name, '%%', '%%%%') as pt_name,
        replace(pu.name, '%%', '%%%%') as pu_name,
        trim(to_char(l.internal_qty, '999999999999.999')) as l_internal_qty,
        trim(to_char(l.wh_qty, '999999999999.999')) as l_wh_qty,
        trim(to_char(l.cross_qty, '999999999999.999')) as l_cross_qty,
        trim(to_char(l.secondary_qty, '999999999999.999')) as l_secondary_qty,
        trim(to_char(l.cu_qty, '999999999999.999')) as l_cu_qty,
        trim(to_char(l.in_pipe_qty, '999999999999.999')) as l_in_pipe_qty,
        trim(to_char(l.stock_qty, '999999999999.999')) as l_stock_qty,
        trim(to_char(l.central_qty, '999999999999.999')) as l_central_qty,
        trim(to_char(l.cross_qty, '999999999999.999')) as l_cross_qty,
        trim(to_char(l.cu_qty, '999999999999.999')) as l_cu_qty,
        trim(to_char(pt.standard_price, '999999999999.999')) as pt_standard_price,
        replace(rc.name, '%%', '%%%%') as rc_name,
        trim(to_char((l.internal_qty * pt.standard_price), '999999999999.999')) as l_internal_qty_pt_price
    FROM stock_mission_report_line l
         LEFT JOIN product_product pp ON l.product_id = pp.id
         LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
         LEFT JOIN product_uom pu ON pt.uom_id = pu.id
         LEFT JOIN res_currency rc ON pp.currency_id = rc.id
    WHERE l.mission_report_id = %s
    ORDER BY l.default_code'''

class excel_semicolon(csv.excel):
    delimiter = CSV_DELIMITER

class msr_in_progress(osv.osv_memory):
    '''
        US-1218: This memory class is used to store temporary values regarding the report process, when a report is in progress, at it into the table
        so that it will not be reprocessed again in the same transaction.
        If a thread is already started, another one will be ignored if the current one is not done!
    '''
    _name = "msr_in_progress"

    _columns = {
        'report_id': fields.many2one('stock.mission.report', "Report"),
        'done_ok': fields.boolean(string='Processing done'),
        'start_date': fields.datetime(string='Start date'),
    }

    _defaults = {
        'done_ok': lambda *a: False,
        'start_date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
    }

    def create(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        for id in ids:
            super(msr_in_progress, self).create(cr, 1, {'report_id': id}, context=None)
        return

    def _already_processed(self, cr, uid, id, context=None):
        report_ids = self.search(cr, 1, [('report_id', '=', id), ('done_ok', '=', True)], context=context)
        if report_ids:
            return True
        return False

    def _is_in_progress(self, cr, uid, context=None):
        report_ids = self.search(cr, 1, [], context=context)
        if report_ids:
            return True
        return False

    def _delete_all(self, cr, uid, context=None):
        report_ids = self.search(cr, 1, [], context=context)
        self.unlink(cr, 1, report_ids, context)
        return

msr_in_progress()

class stock_mission_report(osv.osv):
    _name = 'stock.mission.report'
    _description = 'Mission stock report'

    def _get_local_report(self, cr, uid, ids, field_name, args, context=None):
        '''
        Check if the mission stock report is a local report or not
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}

        local_instance_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.id

        for report in self.read(cr, uid, ids, ['instance_id'], context=context):
            res[report['id']] = False
            if report['instance_id'] \
                and report['instance_id'][0] == local_instance_id:
                res[report['id']] = True

        return res

    def _src_local_report(self, cr, uid, obj, name, args, context=None):
        '''
        Returns the local or not report mission according to args
        '''
        res = []

        local_instance_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.id

        for arg in args:
            if len(arg) > 2 and arg[0] == 'local_report':
                if (arg[1] == '=' and arg[2] in ('True', 'true', 't', 1)) or \
                    (arg[1] in ('!=', '<>') and arg[2] in ('False', 'false', 'f', 0)):
                    res.append(('instance_id', '=', local_instance_id))
                elif (arg[1] == '=' and arg[2] in ('False', 'false', 'f', 0)) or \
                    (arg[1] in ('!=', '<>') and arg[2] in ('True', 'true', 't', 1)):
                    res.append(('instance_id', '!=', local_instance_id))
                else:
                    raise osv.except_osv(_('Error'), _('Bad operator'))

        return res

    _columns = {
        'name': fields.char(size=128, string='Name', required=True),
        'instance_id': fields.many2one('msf.instance', string='Instance', required=True),
        'full_view': fields.boolean(string='Is a full view report ?'),
        'local_report': fields.function(_get_local_report, fnct_search=_src_local_report,
                                        type='boolean', method=True, store=False,
                                        string='Is a local report ?', help='If the report is a local report, it will be updated periodically'),
        'report_line': fields.one2many('stock.mission.report.line', 'mission_report_id', string='Lines'),
        'last_update': fields.datetime(string='Last update'),
        'move_ids': fields.many2many('stock.move', 'mission_move_rel', 'mission_id', 'move_id', string='Noves'),
        'export_ok': fields.boolean(string='Export file possible ?'),
    }

    _defaults = {
        'full_view': lambda *a: False,
        #'export_ok': False,
    }

    def create(self, cr, uid, vals, context=None):
        '''
        Create lines at report creation
        '''
        res = super(stock_mission_report, self).create(cr, uid, vals, context=context)

        local_instance_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.id

        # Not update lines for full view or non local reports
        if vals.get('instance_id', False) and vals['instance_id'] == local_instance_id and not vals.get('full_view', False):
            if not context.get('no_update', False):
                self.update(cr, uid, res, context=context)

        return res

    def xls_write_header(self, sheet, cell_list, style):
        column_count = 0
        for column in cell_list:
            sheet.write(0, column_count, _(column), style)
            column_count += 1

    def xls_write_row(self, sheet, cell_list, row_count, style):
        column_count = 0
        for column in cell_list:
            sheet.write(row_count, column_count, _(column), style)
            column_count += 1

    def generate_csv_files(self, request_result, field_to_file, product_values):

        # write headers of the csv file
        writer = field_to_file['csv_writer']
        header_row = field_to_file['header']
        header_row = [_(column_name) for column_name, colum_property in header_row]
        writer.writerow(header_row)

        for row in request_result:
            try:
                product_amc = 0.00
                reviewed_consumption = 0.00
                if row['product_id'] in product_values and product_values[row['product_id']]:
                    if product_values[row['product_id']].get('product_amc', False):
                        product_amc = product_values[row['product_id']]['product_amc']
                    if product_values[row['product_id']].get('product_consumption', False):
                        reviewed_consumption = product_values[row['product_id']]['reviewed_consumption']

                data_list = []
                data_list_append = data_list.append
                for columns_name, property_name in field_to_file['header']:
                    if property_name == 'product_amc':
                        data_list_append(product_amc)
                    elif property_name == 'product_consumption':
                        data_list_append(reviewed_consumption)
                    elif 'qty' in property_name:
                        data_list_append(eval(row.get(property_name, False)))
                    else:
                        data_list_append(row.get(property_name, False))

                writer = field_to_file['csv_writer']
                writer.writerow(data_list)
            except Exception, e:
                logging.getLogger('Mission stock report').warning("""An error is occured when generate the mission stock report file : %s\n""" % e, exc_info=True)

        # close file
        csvfile = field_to_file['csv_file']
        csvfile.close()

    def generate_xls_files(self, request_result, field_to_file, product_values):

        # write the headers
        borders = Borders()
        borders.left = Borders.THIN
        borders.right = Borders.THIN
        borders.top = Borders.THIN
        borders.bottom = Borders.THIN

        header_style = easyxf("""
                font: height 220;
                font: name Calibri;
                pattern: pattern solid, fore_colour tan;
                align: wrap on, vert center, horiz center;
            """)
        header_style.borders = borders

        sheet = field_to_file['sheet']
        header_row = field_to_file['header']
        header_row = [_(column_name) for column_name, colum_property in header_row]
        self.xls_write_header(sheet, header_row, header_style)

        sheet.row(0).height_mismatch = True
        sheet.row(0).height = 45*20

        # this style is done to be the same than previous mako configuration
        row_style = easyxf("""
                font: height 220;
                font: name Calibri;
                align: wrap on, vert center, horiz center;
            """)
        row_style.borders = borders

        # write the lines
        row_count = 1
        for row in request_result:
            try:
                product_amc = 0.00
                reviewed_consumption = 0.00
                if row['product_id'] in product_values and product_values[row['product_id']]:
                    if product_values[row['product_id']].get('product_amc', False):
                        product_amc = product_values[row['product_id']]['product_amc']
                    if product_values[row['product_id']].get('product_consumption', False):
                        reviewed_consumption = product_values[row['product_id']]['reviewed_consumption']

                data_list = []
                data_list_append = data_list.append
                for columns_name, property_name in field_to_file['header']:
                    if property_name == 'product_amc':
                        data_list_append(product_amc)
                    elif property_name == 'product_consumption':
                        data_list_append(reviewed_consumption)
                    elif 'qty' in property_name:
                        data_list_append(eval(row.get(property_name, False)))
                    else:
                        data_list_append(row.get(property_name, False))

                sheet = field_to_file['sheet']
                self.xls_write_row(sheet, data_list, row_count, row_style)
                sheet.row(row_count).height_mismatch = True
                sheet.row(row_count).height = 60*20 # to fit the previous hardcoded mako configuration
                row_count += 1
            except Exception, e:
                logging.getLogger('MSR').warning("""An error is occured when generate the mission stock report xls file : %s\n""" % e, exc_info=True)
        book = field_to_file['book']
        book.save(field_to_file['xls_file'])

        # close file
        xlsfile = field_to_file['xls_file']
        xlsfile.close()

    def background_update(self, cr, uid, ids, context=None):
        """
        Run the update of local stock report in background
        """
        if not ids:
            ids = []

        threaded_calculation = threading.Thread(target=self.update_newthread, args=(cr, uid, ids, context))
        threaded_calculation.start()
        return {'type': 'ir.actions.act_window_close'}

    def update_newthread(self, cr, uid, ids=[], context=None):
        # Open a new cursor : Don't forget to close it at the end of method
        cr = pooler.get_db(cr.dbname).cursor()
        msr_in_progress = self.pool.get('msr_in_progress')
        try:
            if msr_in_progress._is_in_progress(cr, uid, context):
                logging.getLogger('MSR').info("""____________________ Another process is progress, this request is ignore: %s""" % time.strftime('%Y-%m-%d %H:%M:%S'))
                return

            logging.getLogger('MSR').info("""____________________ Start the update process of MSR, at %s""" % time.strftime('%Y-%m-%d %H:%M:%S'))
            self.update(cr, uid, ids=[], context=None)
            msr_in_progress._delete_all(cr, uid, context)
            cr.commit()
            logging.getLogger('MSR').info("""____________________ Finished the update process of MSR, at %s""" % time.strftime('%Y-%m-%d %H:%M:%S'))
        except Exception as e:
            cr.rollback()
            logging.getLogger('MSR').error("""____________________ Error while running the update process of MSR, at %s - Error: %s""" % (time.strftime('%Y-%m-%d %H:%M:%S'), str(e)), exc_info=True)
            msr_in_progress._delete_all(cr, uid, context)
        finally:
            cr.close(True)

    def update(self, cr, uid, ids=[], context=None):
        '''
        Create lines if new products exist or update the existing lines
        '''
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        line_obj = self.pool.get('stock.mission.report.line')
        msr_in_progress = self.pool.get('msr_in_progress')

        report_ids = self.search(cr, uid, [('local_report', '=', True), ('full_view', '=', False)], context=context)
        full_report_ids = self.search(cr, uid, [('full_view', '=', True)], context=context)

        instance_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id

        # Create a local report if no exist
        if not report_ids and context.get('update_mode', False) not in ('update', 'init') and instance_id:
            c = context.copy()
            c.update({'no_update': True})
            report_ids = [self.create(cr, uid, {'name': instance_id.name,
                                               'instance_id': instance_id.id,
                                               'full_view': False}, context=c)]

        # Create a full view report if no exist
        if not full_report_ids and context.get('update_mode', False) not in ('update', 'init') and instance_id:
            c = context.copy()
            c.update({'no_update': True})
            full_report_ids = [self.create(cr, uid, {'name': 'Full view',
                                               'instance_id': instance_id.id,
                                               'full_view': True}, context=c)]

        cr.commit()

        if context.get('update_full_report'):
            report_ids = full_report_ids
        else:
            all_report_ids = report_ids + full_report_ids
            for report_id in all_report_ids:
                # register immediately this report id into the table temp
                msr_in_progress.create(cr, uid, report_id, context)

        product_obj = self.pool.get('product.product')
        product_ids = product_obj.search(cr, uid, [],
                context=context, order='NO_ORDER')
        logging.getLogger('MSR').info("""___ start to read %s products at %s...""" % (len(product_ids), time.strftime('%Y-%m-%d %H:%M:%S')))

        # read only the products that can have product_amc or reviewed_consumption
        # 2 cases:
        # A - the product that have only product_amc
        # B - the product that have only reviewed_consumption

        # A
        cr.execute("""SELECT id FROM product_product
                WHERE id IN (SELECT product_id FROM stock_move)""")
        product_amc_ids = [x[0] for x in cr.fetchall()]
        product_amc_ids = list(set(product_amc_ids).intersection(product_ids))
        product_amc_result = product_obj.read(cr, uid, product_amc_ids, ['product_amc'], context=context)

        # B
        cr.execute("""SELECT id FROM product_product
                WHERE id IN (SELECT name FROM monthly_review_consumption_line)""")

        product_reviewed_ids = [x[0] for x in cr.fetchall()]
        product_reviewed_ids = list(set(product_reviewed_ids).intersection(product_ids))
        product_reviewed_result = product_obj.read(cr, uid, product_reviewed_ids, ['reviewed_consumption'], context=context)
        logging.getLogger('MSR').info("""___ finish read at %s ...""" % time.strftime('%Y-%m-%d %H:%M:%S'))

        logging.getLogger('MSR').info("""___ Number of MSR lines to be updated: %s, at %s""" % (len(product_reviewed_ids) + len(product_amc_ids), time.strftime('%Y-%m-%d %H:%M:%S')))

        product_values = dict.fromkeys(product_ids, None)

        # Update the final dict with this results
        for product_dict in product_amc_result:
            if product_values[product_dict['id']] is None:
                product_values[product_dict['id']] = {}
            product_values[product_dict['id']]['product_amc'] = product_dict['product_amc']
        for product_dict in product_reviewed_result:
            if product_values[product_dict['id']] is None:
                product_values[product_dict['id']] = {}
            product_values[product_dict['id']]['reviewed_consumption'] = product_dict['reviewed_consumption']

        # Check in each report if new products are in the database and not in the report
        for report in self.read(cr, uid, report_ids, ['local_report', 'full_view'], context=context):
            # Create one line by product
            cr.execute('''SELECT p.id from product_product p
                          WHERE NOT EXISTS (
                            SELECT product_id
                            FROM
                            stock_mission_report_line smrl WHERE mission_report_id = %s
                            AND p.id = smrl.product_id)
                        ''' % report['id'])
            for product in cr.fetchall():
                line_obj.create(cr, uid, {'product_id': product, 'mission_report_id': report['id']}, context=context)

            # Don't update lines for full view or non local reports
            if not report['local_report']:
                continue

            #US-1218: If this report is previously processed, then do not redo it again for this transaction!
            if msr_in_progress._already_processed(cr, uid, report['id'], context):
                continue

            logging.getLogger('MSR').info("""___ updating the report lines of the report: %s, at %s (this may take very long time!)""" % (report['id'], time.strftime('%Y-%m-%d %H:%M:%S')))
            if context.get('update_full_report'):
                full_view = self.search(cr, uid, [('full_view', '=', True)])
                if full_view:
                    line_obj.update_full_view_line(cr, uid, context=context)
            elif not report['full_view']:
                # Update all lines
                self.update_lines(cr, uid, [report['id']])

            msr_ids = msr_in_progress.search(cr, uid, [('report_id', '=', report['id'])], context=context)
            msr_in_progress.write(cr, uid, msr_ids, {'done_ok': True}, context=context)

            logging.getLogger('MSR').info("""___ exporting the report lines of the report %s to csv, at %s""" % (report['id'], time.strftime('%Y-%m-%d %H:%M:%S')))
            self._get_export(cr, uid, report['id'], product_values,
                    export_format='xls', context=context)
            # Update the update date on report
            self.write(cr, uid, [report['id']], {'last_update': time.strftime('%Y-%m-%d %H:%M:%S')}, context=context)
            logging.getLogger('MSR').info("""___ finished processing completely for the report: %s, at %s \n""" % (report['id'], time.strftime('%Y-%m-%d %H:%M:%S')))

        # After update of all normal reports, update the full view report
        if not context.get('update_full_report'):
            c = context.copy()
            c.update({'update_full_report': True})
            self.update(cr, uid, [], context=c)

        return True

    def update_lines(self, cr, uid, report_ids, context=None):
        location_obj = self.pool.get('stock.location')
        data_obj = self.pool.get('ir.model.data')
        line_obj = self.pool.get('stock.mission.report.line')
        product_obj = self.pool.get('product.product')
        # Search considered SLocation
        stock_location_id = data_obj.get_object_reference(cr, uid, 'stock', 'stock_location_stock')
        if stock_location_id:
            stock_location_id = stock_location_id[1]
        internal_loc = location_obj.search(cr, uid, [('usage', '=', 'internal')], context=context)
        central_loc = location_obj.search(cr, uid, [('central_location_ok', '=', True)], context=context)
        cross_loc = location_obj.search(cr, uid, [('cross_docking_location_ok', '=', True)], context=context)
        stock_loc = location_obj.search(cr, uid, [('location_id', 'child_of', stock_location_id),
                                                  ('id', 'not in', cross_loc),
                                                  ('central_location_ok', '=', False)], context=context)
        cu_loc = location_obj.search(cr, uid, [('usage', '=', 'internal'), ('location_category', '=', 'consumption_unit')], context=context)
        secondary_location_id = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_intermediate_client_view')
        if secondary_location_id:
            secondary_location_id = secondary_location_id[1]
        secondary_location_ids = location_obj.search(cr, uid, [('location_id', 'child_of', secondary_location_id)], context=context)

        cu_loc = location_obj.search(cr, uid, [('location_id', 'child_of', cu_loc)], context=context)
        central_loc = location_obj.search(cr, uid, [('location_id', 'child_of', central_loc)], context=context)

        # Check if the instance is a coordination or a project
        coordo_id = False
        company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
        coordo = self.pool.get('msf.instance').search(cr, uid, [('level', '=', 'coordo')], context=context)
        if company.instance_id.level == 'project' and coordo:
            coordo_id = self.pool.get('msf.instance').browse(cr, uid, coordo[0], context=context).instance

        for report_id in report_ids:
            # In-Pipe moves
            cr.execute('''SELECT m.product_id, sum(m.product_qty), m.product_uom, p.name
                          FROM stock_move m
                              LEFT JOIN stock_picking s ON m.picking_id = s.id
                              LEFT JOIN res_partner p ON s.partner_id2 = p.id
                          WHERE s.type = 'in' AND m.state in ('confirmed', 'waiting', 'assigned')
                          GROUP BY m.product_id, m.product_uom, p.name
                          ORDER BY m.product_id''')

            in_pipe_moves = cr.fetchall()
            current_product = None
            line = None
            vals = {}
            in_pipe_products = set()
            for product_id, qty, uom, partner in in_pipe_moves:
                if current_product != product_id:
                    if line and vals and (vals.get('in_pipe_qty', False) or vals.get('in_pipe_coor_qty', False)):
                        in_pipe_products.add(current_product)
                        line_obj.write(cr, uid, [line.id], vals)
                    line_id = line_obj.search(cr, uid, [('product_id', '=', product_id),
                                                        ('mission_report_id', '=', report_id)])

                    vals = {'in_pipe_qty': 0.00,
                            'in_pipe_coor_qty': 0.00,
                            'updated': True}
                    current_product = product_id
                    if not line_id:
                        continue

                line = line_obj.browse(cr, uid, line_id[0],
                        fields_to_fetch=['id', 'product_id'])
                if uom != line.product_id.uom_id.id:
                    qty = self.pool.get('product.uom')._compute_qty(cr, uid, uom, qty, line.product_id.uom_id.id)

                vals['in_pipe_qty'] += qty

                if partner == coordo_id:
                    vals['in_pipe_coor_qty'] += qty

            if line and vals and (vals.get('in_pipe_qty', False) or vals.get('in_pipe_coor_qty', False)):
                in_pipe_products.add(current_product)
                line_obj.write(cr, uid, [line.id], vals)

            # Update in-pipe quantities for all other lines
            no_pipe_line_ids = line_obj.search(cr, uid, [
                ('product_id', 'not in', list(in_pipe_products)),
                ('mission_report_id', '=', report_id),
                '|', ('in_pipe_qty', '!=', 0.00), ('in_pipe_coor_qty', '!=', 0.00),
            ], order='NO_ORDER', context=context)
            line_obj.write(cr, uid, no_pipe_line_ids, {
                'in_pipe_qty': 0.00,
                'in_pipe_coor_qty': 0.00,
            }, context=context)

            # All other moves
            cr.execute('''
                        SELECT id, product_id, product_uom, product_qty, location_id, location_dest_id
                        FROM stock_move
                        WHERE state = 'done'
                        AND id not in (SELECT move_id FROM mission_move_rel WHERE mission_id = %s)
            ''' % (report_id))
            res = cr.fetchall()
            for move in res:
                cr.execute('INSERT INTO mission_move_rel VALUES (%s, %s)' %
                        (report_id, move[0]))
                product = product_obj.browse(cr, uid, move[1],
                        fields_to_fetch=['uom_id', 'standard_price'])
                line_id = line_obj.search(cr, uid, [('product_id', '=', move[1]),
                                                    ('mission_report_id', '=', report_id)])
                if line_id:
                    line = line_obj.browse(cr, uid, line_id[0])
                    qty = self.pool.get('product.uom')._compute_qty(cr, uid, move[2], move[3], product.uom_id.id)
                    vals = {'internal_qty': line.internal_qty or 0.00,
                            'stock_qty': line.stock_qty or 0.00,
                            'central_qty': line.central_qty or 0.00,
                            'cross_qty': line.cross_qty or 0.00,
                            'secondary_qty': line.secondary_qty or 0.00,
                            'cu_qty': line.cu_qty or 0.00,
                            'updated': True}

                    if move[4] in internal_loc:
                        vals['internal_qty'] -= qty
                    if move[4] in stock_loc:
                        vals['stock_qty'] -= qty
                    if move[4] in central_loc:
                        vals['central_qty'] -= qty
                    if move[4] in cross_loc:
                        vals['cross_qty'] -= qty
                    if move[4] in secondary_location_ids:
                        vals['secondary_qty'] -= qty
                    if move[4] in cu_loc:
                        vals['cu_qty'] -= qty

                    if move[5] in internal_loc:
                        vals['internal_qty'] += qty
                    if move[5] in stock_loc:
                        vals['stock_qty'] += qty
                    if move[5] in central_loc:
                        vals['central_qty'] += qty
                    if move[5] in cross_loc:
                        vals['cross_qty'] += qty
                    if move[5] in secondary_location_ids:
                        vals['secondary_qty'] += qty
                    if move[5] in cu_loc:
                        vals['cu_qty'] += qty

                    vals.update({'internal_val': vals['internal_qty'] * product.standard_price})
                    line_obj.write(cr, uid, line.id, vals)
        return True

    def _get_export(self, cr, uid, ids, product_values, export_format='csv', context=None):
        '''
        Get the CSV files of the stock mission report.
        This method generates 4 files (according to option set) :
            * 1 file with no split of WH and no valuation
            * 1 file with no split of WH and valuation
            * 1 file with split of WH and no valuation
            * 1 file with split of WH and valuation
        '''
        context = context or {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # check attachments_path
        obj_model, obj_id = self.pool.get('ir.model.data').get_object_reference(cr, uid,
                'base_setup', 'attachment_config_default')
        attachments_path = self.pool.get(obj_model,).read(cr, uid, obj_id,
                ['name'])['name']
        if not attachments_path or not os.path.exists(attachments_path):
            raise osv.except_osv(_('Error'), _("attachments_path %s doesn't exists.") % attachments_path)

        logger = logging.getLogger('MSR')
        for report_id in ids:

            logger.info('___ Start export SQL request...')
            cr.execute(GET_EXPORT_REQUEST, (report_id, ))
            request_result = cr.dictfetchall()

            logger.info('___ Start CSV and XLS generation...')
            for report_type in ('ns_nv_vals', 'ns_v_vals', 's_nv_vals', 's_v_vals'):
                field_to_file = {}
                book = Workbook()
                sheet = book.add_sheet('Sheet 1')
                csv_file = open(os.path.join(attachments_path,
                    STOCK_MISSION_REPORT_NAME_PATTERN % (report_id,
                        report_type + '.csv')), 'w')
                field_to_file = {
                        'csv_file': csv_file,
                        'csv_writer': UnicodeWriter(csv_file, dialect=excel_semicolon),
                        'xls_file': open(os.path.join(attachments_path,
                            STOCK_MISSION_REPORT_NAME_PATTERN % (report_id,
                                report_type + '.xls')), 'w'),
                        'header': HEADER_DICT[report_type],
                        'book': book,
                        'sheet': sheet,}

                # generate CSV file
                self.generate_csv_files(request_result, field_to_file, product_values)

                # generate XLS files
                self.generate_xls_files(request_result, field_to_file, product_values)

                self.write(cr, uid, [report_id], {'export_ok': True}, context=context)
            logger.info('___ CSV & XLS generation finished !')
            del request_result
        return True

stock_mission_report()

class UnicodeWriter:
    """
    A CSV writer which will write rows to CSV file "f",
    which is encoded in the given encoding.
    from https://docs.python.org
    """

    # utf-8-sig is important here. It is the only encoding working with Windows
    # Microsoft Excel and also Linux
    # https://docs.python.org/2/library/codecs.html#encodings-and-unicode
    def __init__(self, f, dialect=csv.excel, encoding="utf-8-sig", **kwds):
        # Redirect output to a queue
        self.queue = cStringIO.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        self.writer.writerow([not isinstance(s, (int, long, float)) and s.encode("utf-8") or s for s in row])
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        # ... and reencode it into the target encoding
        data = self.encoder.encode(data)
        # write to the target stream
        self.stream.write(data)
        # empty queue
        self.queue.truncate(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)

class stock_mission_report_line(osv.osv):
    _name = 'stock.mission.report.line'
    _description = 'Mission stock report line'
    _order = 'default_code'

    def _get_product_type_selection(self, cr, uid, context=None):
        return self.pool.get('product.template').PRODUCT_TYPE

    def _get_product_subtype_selection(self, cr, uid, context=None):
        return self.pool.get('product.template').PRODUCT_SUBTYPE

    def onChangeSearchNomenclature(self, cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, context=None):
        return self.pool.get('product.product').onChangeSearchNomenclature(cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=num, context=context)

    def _get_nomen_s(self, cr, uid, ids, fields, *a, **b):
        value = {}
        for f in fields:
            value[f] = False

        ret = {}
        for id in ids:
            ret[id] = value
        return ret

    def _search_nomen_s(self, cr, uid, obj, name, args, context=None):
        # Some verifications
        if context is None:
            context = {}

        if not args:
            return []
        narg = []
        for arg in args:
            el = arg[0].split('_')
            el.pop()
            narg = [('_'.join(el), arg[1], arg[2])]

        return narg

    def _get_template(self, cr, uid, ids, context=None):
        return self.pool.get('stock.mission.report.line').search(cr, uid, [('product_id.product_tmpl_id', 'in', ids)], context=context)

    def _get_wh_qty(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for line in self.browse(cr, uid, ids, context=context,
                fields_to_fetch=['id', 'stock_qty', 'central_qty']):
            res[line.id] = line.stock_qty + line.central_qty

        return res

    def _get_internal_val(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for line in self.read(cr, uid, ids, ['internal_qty', 'cost_price'],
                context=context):
            res[line['id']] = line['internal_qty'] * line['cost_price']
        return res

    def xmlid_code_migration(self, cr, ids):
        cr.execute('UPDATE stock_mission_report_line l set xmlid_code = (select xmlid_code from product_product p where p.id=l.product_id)')
        print 'UPDATE stock_mission_report_line l set xmlid_code = (select xmlid_code from product_product p where p.id=l.product_id)'
        print cr.statusmessage
        return True

    def is_migration(self, cr, ids):
        cr.execute('UPDATE stock_mission_report_line l set international_status = (select international_status from product_product p where p.id=l.product_id)')
        print 'UPDATE stock_mission_report_line l set international_status = (select international_status from product_product p where p.id=l.product_id)'
        print cr.statusmessage

        return True

    _columns = {
        'product_id': fields.many2one('product.product', string='Name', required=True, ondelete="cascade", select=1),
        'default_code': fields.related('product_id', 'default_code', string='Reference', type='char', size=64, store=True, write_relate=False),
        'xmlid_code': fields.related('product_id', 'xmlid_code', string='MSFID', type='char', size=18, store=True, write_relate=False, _fnct_migrate=xmlid_code_migration),
        'old_code': fields.related('product_id', 'old_code', string='Old Code', type='char'),
        'name': fields.related('product_id', 'name', string='Name', type='char'),
        'categ_id': fields.related('product_id', 'categ_id', string='Category', type='many2one', relation='product.category',
                                   store={'product.template': (_get_template, ['type'], 10),
                                          'stock.mission.report.line': (lambda self, cr, uid, ids, c={}: ids, ['product_id'], 10)},
                                   write_relate=False),
        'type': fields.related('product_id', 'type', string='Type', type='selection', selection=_get_product_type_selection,
                               store={'product.template': (_get_template, ['type'], 10),
                                      'stock.mission.report.line': (lambda self, cr, uid, ids, c={}: ids, ['product_id'], 10)},
                               write_relate=False),
        'subtype': fields.related('product_id', 'subtype', string='Subtype', type='selection', selection=_get_product_subtype_selection,
                                  store={'product.template': (_get_template, ['subtype'], 10),
                                         'stock.mission.report.line': (lambda self, cr, uid, ids, c={}: ids, ['product_id'], 10)},
                                  write_relate=False),
        'international_status': fields.related(
            'product_id',
            'international_status',
            type='many2one',
            relation='product.international.status',
            string='International status',
            store=True,
            write_relate=False,
            _fnct_migrate=is_migration,
        ),
        # mandatory nomenclature levels
        'nomen_manda_0': fields.related('product_id', 'nomen_manda_0', type='many2one', relation='product.nomenclature', string='Main Type'),
        'nomen_manda_1': fields.related('product_id', 'nomen_manda_1', type='many2one', relation='product.nomenclature', string='Group'),
        'nomen_manda_2': fields.related('product_id', 'nomen_manda_2', type='many2one', relation='product.nomenclature', string='Family'),
        'nomen_manda_3': fields.related('product_id', 'nomen_manda_3', type='many2one', relation='product.nomenclature', string='Root'),
        # optional nomenclature levels
        'nomen_sub_0': fields.related('product_id', 'nomen_sub_0', type='many2one', relation='product.nomenclature', string='Sub Class 1'),
        'nomen_sub_1': fields.related('product_id', 'nomen_sub_1', type='many2one', relation='product.nomenclature', string='Sub Class 2'),
        'nomen_sub_2': fields.related('product_id', 'nomen_sub_2', type='many2one', relation='product.nomenclature', string='Sub Class 3'),
        'nomen_sub_3': fields.related('product_id', 'nomen_sub_3', type='many2one', relation='product.nomenclature', string='Sub Class 4'),
        'nomen_sub_4': fields.related('product_id', 'nomen_sub_4', type='many2one', relation='product.nomenclature', string='Sub Class 5'),
        'nomen_sub_5': fields.related('product_id', 'nomen_sub_5', type='many2one', relation='product.nomenclature', string='Sub Class 6'),
        'nomen_manda_0_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Main Type', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_manda_1_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Group', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_manda_2_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Family', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_manda_3_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Root', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_sub_0_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 1', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_sub_1_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 2', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_sub_2_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 3', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_sub_3_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 4', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_sub_4_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 5', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_sub_5_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 6', fnct_search=_search_nomen_s, multi="nom_s"),
        'product_amc': fields.related('product_id', 'product_amc', type='float', string='AMC'),
        'reviewed_consumption': fields.related('product_id', 'reviewed_consumption', type='float', string='FMC'),
        'currency_id': fields.related('product_id', 'currency_id', type='many2one', relation='res.currency', string='Func. cur.'),
        'cost_price': fields.related('product_id', 'standard_price', type='float', string='Cost price'),
        'uom_id': fields.related('product_id', 'uom_id', type='many2one', relation='product.uom', string='UoM',
                                store={
                                    'product.template': (_get_template, ['type'], 10),
                                    'stock.mission.report.line': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 10),
                                },
                                write_relate=False),
        'mission_report_id': fields.many2one('stock.mission.report', string='Mission Report', required=True),
        'internal_qty': fields.float(digits=(16,2), string='Instance Stock'),
        'internal_val': fields.function(_get_internal_val, method=True, type='float', string='Instance Stock Val.'),
        #'internal_val': fields.float(digits=(16,2), string='Instance Stock Val.'),
        'stock_qty': fields.float(digits=(16,2), string='Stock Qty.'),
        'stock_val': fields.float(digits=(16,2), string='Stock Val.'),
        'central_qty': fields.float(digits=(16,2), string='Unallocated Stock Qty.'),
        'central_val': fields.float(digits=(16,2), string='Unallocated Stock Val.'),
        'wh_qty': fields.function(_get_wh_qty, method=True, type='float', string='Warehouse stock',
                                  store={'stock.mission.report.line': (lambda self, cr, uid, ids, c=None: ids, ['stock_qty', 'central_qty'], 10),}),
        'cross_qty': fields.float(digits=(16,3), string='Cross-docking Qty.'),
        'cross_val': fields.float(digits=(16,3), string='Cross-docking Val.'),
        'secondary_qty': fields.float(digits=(16,2), string='Secondary Stock Qty.'),
        'secondary_val': fields.float(digits=(16,2), string='Secondary Stock Val.'),
        'cu_qty': fields.float(digits=(16,2), string='Internal Cons. Unit Qty.'),
        'cu_val': fields.float(digits=(16,2), string='Internal Cons. Unit Val.'),
        'in_pipe_qty': fields.float(digits=(16,2), string='In Pipe Qty.'),
        'in_pipe_val': fields.float(digits=(16,2), string='In Pipe Val.'),
        'in_pipe_coor_qty': fields.float(digits=(16,2), string='In Pipe from Coord.'),
        'in_pipe_coor_val': fields.float(digits=(16,2), string='In Pipe from Coord.'),
        'updated': fields.boolean(string='Updated'),
        'full_view': fields.related('mission_report_id', 'full_view', string='Full view', type='boolean', store=True),
        'move_ids': fields.many2many('stock.move', 'mission_line_move_rel', 'line_id', 'move_id', string='Noves'),
        'instance_id': fields.many2one(
            'msf.instance',
            string='HQ Instance',
            required=True,
        ),
    }

    @tools.cache(skiparg=2)
    def _get_default_destination_instance_id(self, cr, uid, context=None):
        instance = self.pool.get('res.users').get_browse_user_instance(cr, uid, context)
        if instance:
            if instance.parent_id:
                if instance.parent_id.parent_id:
                    return instance.parent_id.parent_id.id
                return instance.parent_id.id
            return instance.id

        return False

    _defaults = {
        'internal_qty': 0.00,
        'internal_val': 0.00,
        'stock_qty': 0.00,
        'stock_val': 0.00,
        'wh_qty': 0.00,
        'central_qty': 0.00,
        'central_val': 0.00,
        'cross_qty': 0.00,
        'cross_val': 0.00,
        'secondary_qty': 0.00,
        'secondary_val': 0.00,
        'cu_qty': 0.00,
        'cu_val': 0.00,
        'in_pipe_qty': 0.00,
        'in_pipe_val': 0.00,
        'in_pipe_coor_qty': 0.00,
        'in_pipe_coor_val': 0.00,
        'instance_id': _get_default_destination_instance_id,
    }

    def update_full_view_line(self, cr, uid, context=None):
        request = '''SELECT l.product_id AS product_id,
                            sum(l.internal_qty) AS internal_qty,
                            sum(l.stock_qty) AS stock_qty,
                            sum(l.central_qty) AS central_qty,
                            sum(l.cross_qty) AS cross_qty,
                            sum(l.secondary_qty) AS secondary_qty,
                            sum(l.cu_qty) AS cu_qty,
                            sum(l.in_pipe_qty) AS in_pipe_qty,
                            sum(l.in_pipe_coor_qty) AS in_pipe_coor_qty,
                            sum(l.internal_qty)*t.standard_price AS internal_val
                     FROM stock_mission_report_line l
                       LEFT JOIN
                          stock_mission_report m
                       ON l.mission_report_id = m.id
                       LEFT JOIN
                          product_product p
                       ON l.product_id = p.id
                       LEFT JOIN
                          product_template t
                       ON p.product_tmpl_id = t.id
                     WHERE m.full_view = False
                       AND (l.internal_qty != 0.00
                       OR l.stock_qty != 0.00
                       OR l.central_qty != 0.00
                       OR l.cross_qty != 0.00
                       OR l.secondary_qty != 0.00
                       OR l.cu_qty != 0.00
                       OR l.in_pipe_qty != 0.00
                       OR l.in_pipe_coor_qty != 0.00)
                     GROUP BY l.product_id, t.standard_price'''

        cr.execute(request)

        vals = cr.fetchall()
        mission_report_id = False
        for line in vals:
            line_ids = self.search(cr, uid, [('full_view', '=', True), ('product_id', '=', line[0])],
                    limit=1, order='NO_ORDER', context=context)
            if not line_ids:
                if not mission_report_id:
                    mission_report_id = self.pool.get('stock.mission.report').search(cr, uid,
                            [('full_view', '=', True)], limit=1,
                            order='NO_ORDER', context=context)
                    if not mission_report_id:
                        continue
                line_id = self.create(cr, uid, {'mission_report_id': mission_report_id[0],
                                                'product_id': line[0]}, context=context)
            else:
                line_id = line_ids[0]

            cr.execute("""UPDATE stock_mission_report_line SET
                    internal_qty=%s, stock_qty=%s,
                    central_qty=%s, cross_qty=%s, secondary_qty=%s,
                    cu_qty=%s, in_pipe_qty=%s, in_pipe_coor_qty=%s,
                    wh_qty=%s
                    WHERE id=%s""" % (line[1] or 0.00, line[2] or 0.00,
                        line[3] or 0.00,line[4] or 0.00, line[5] or 0.00,line[6] or 0.00,line[7] or 0.00,line[8] or 0.00, (line[2] or 0.00) + (line[3] or 0.00), line_id))
        return True

stock_mission_report_line()
