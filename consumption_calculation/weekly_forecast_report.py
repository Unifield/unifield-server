# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 TeMPO Consulting, MSF
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#
#    GNU Affero General Public License for more details.
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from mx.DateTime.DateTime import DateFrom, RelativeDateTime, Age, now
import threading
import time

from osv import fields
from osv import osv
from osv.orm import browse_record
from tools.translate import _
import pooler


LIKELY_EXPIRE_STATUS = [
    ('draft', 'Draft'),
    ('in_progress', 'In Progress'),
    ('ready', 'Ready'),
    ('error', 'Error'),
]
CONSUMPTION_TYPE = [
    ('fmc', 'FMC -- Forecasted Monthly Consumption'), 
    ('amc', 'AMC -- Average Monthly Consumption'), 
    ('rac', 'RAC -- Real Average Consumption'),
]


class weekly_forecast_report(osv.osv):
    '''
    Weekly forecast report
    '''
    _name  = 'weekly.forecast.report'
    _description = 'Stock forecast by week'
    _rec_name = 'id'
    _order = 'requestor_date desc, id'
    
    _columns = {
        'location_id': fields.many2one(
            'stock.location',
            string='Location',
            required=True,
        ),
        'interval': fields.integer(
            string='Interval',
            required=True,
        ),
        'interval_type': fields.selection(
            [('week', 'Weeks'), ('month', 'Months')],
            string='Interval type',
            required=True,
        ),
        'consumption_type': fields.selection(
            CONSUMPTION_TYPE,
            string='Consumption',
            required=True,
        ),
        'consumption_from': fields.date(
            string='From',
        ),
        'consumption_to': fields.date(
            string='To',
        ),
        'requestor_id': fields.many2one(
            'res.users',
            string='Requestor',
        ),
        'requestor_date': fields.datetime(
            string='Date of te demand',
        ),
        'status': fields.selection(
            LIKELY_EXPIRE_STATUS,
            string='Status',
            readonly=True,
        ),
        'xml_data': fields.text(
            string='XML data',
            readonly=True,
        ),
        'progress': fields.float(
            digits=(16,2),
            string='Progression',
            readonly=True,
        ),
        'progress_comment': fields.text(
            string='Status of the progression',
            readonly=True,
        ),
    }
    
    _defaults = {
        'requestor_id': lambda self, cr, uid, c={}: uid,
        'requestor_date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'consumption_to': lambda *a: time.strftime('%Y-%m-%d'),
        'consumption_type': 'fmc',
        'status': 'draft',
    }

    def copy(self, cr, uid, report_id, defaults=None, context=None):
        """
        Reset value on copy.

        :param cr: Cursor to the database
        :param uid: ID of the user that launches the method
        :param report_id: ID of the weekly.forecast.report object to duplicate
        :param defaults: Default values for the new object
        :param context: Context of the call

        :return The ID of the new object
        """
        if context is None:
            context = {}

        if defaults is None:
            defaults = {}

        defaults.update({
            'status': 'draft',
            'progress': 0.00,
            'progress_comment': '',
            'xml_data': '',
            'requestor_date': time.strftime('%Y-%d-%m %H:%M:%S'),
        })

        return super(weekly_forecast_report, self).copy(cr, uid, report_id, defaults, context=context)
    
    def period_change(self, cr, uid, ids, consumption_from, consumption_to, consumption_type, context=None):
        """
        Get the first or last day of month
        """
        res = {}
        
        if consumption_type == 'amc':
            if consumption_from:
                res.update({
                    'consumption_from': (DateFrom(consumption_from) + RelativeDateTime(day=1)).strftime('%Y-%m-%d'),
                })
            if consumption_to:
                res.update({
                    'consumption_to': (DateFrom(consumption_to) + RelativeDateTime(months=1, day=1, days=-1)).strftime('%Y-%m-%d'),
                })
                
        return {'value': res}
    
    def _get_average_consumption(self, cr, uid, product_id, consumption_type, date_from, date_to, context=None):
        """
        Return the average consumption for all locations
        """
        if context is None:
            context = {}
            
        product_obj = self.pool.get('product.product')
        res = 0.00
        
        if context.get('manual_consumption'):
            return context.get('manual_consumption')
        
        new_context = context.copy()
        new_context.update({
            'from_date': date_from,
            'to_date': date_to,
            'average': True,
        })
        
        if consumption_type == 'fmc':
            res = product_obj.read(cr, uid, product_id, ['reviewed_consumption'], context=new_context)['reviewed_consumption']
        elif consumption_type == 'amc':
            res = product_obj.compute_amc(cr, uid, product_id, context=new_context)
        else:
            res = product_obj.read(cr, uid, product_id, ['monthly_consumption'], context=new_context)['monthly_consumption']
            
        return res
    
    def process_lines(self, cr, uid, ids, context=None):
        '''
        Create one line by product for the period
        '''
        if context is None:
            context = {}
        if ids:
            if isinstance(ids, (int, long)):
                ids = [ids]
            report = self.browse(cr, uid, ids[0], context=context)
            if report:
                if report.interval > 20 or report.interval < 1:
                    raise osv.except_osv(
                        _('Error'),
                        _('The number of intervals must be between 1 and 20'),
                    )

                if report.status == 'in_progress':
                    # currently in progress
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'weekly.forecast.report',
                        'res_id': ids[0],
                        'view_type': 'form',
                        'view_mode': 'form,tree',
                        'context': context,
                        'target': 'crush',
                    }
                elif report.status == 'ready':
                    # report already build, show it
                    return self.open_report(cr, uid, ids, context=context)

        self.write(cr, uid, ids, {'status': 'in_progress'},
                   context=context)

        cr.commit()
        new_thread = threading.Thread(target=self._process_lines,
                        args=(cr, uid, ids, context))
        new_thread.start()
        new_thread.join(10.0)
        if new_thread.isAlive():
            # more than 10 secs to compute data
            # displaying 'waiting form'
            view_id = self.pool.get('ir.model.data').get_object_reference(
                cr, uid, 'consumption_calculation',
                'weekly_forecast_report_waiting_view')[1]
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'weekly.forecast.report',
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': ids[0],
                'view_id': [view_id],
                'context': context,
                'target': 'same',
            }

        return self.open_report(cr, uid, ids, context=context)

    def open_report(self, cr, uid, ids, context=None):
        """
        Open the Excel file

        :param cr: Cursor to the database
        :param uid: ID of the use that runs the method
        :param ids: List of ID of the weekly.forecast.report
        :param context: Context of the call

        :return Return a dictionary with the action to open the report
        :rtype dict
        """
        datas = {'ids': ids}
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'weekly.forecast.report_xls',
            'datas': datas,
            'nodestroy': True,
            'context': context,
        }

    def in_progress(self, cr, uid, ids, context=None):
        """
        Refresh the tree view

        :param cr: Cursor to the database
        :param uid: ID of the use that runs the method
        :param ids: List of ID of the weekly.forecast.report
        :param context: Context of the call

        :return Return a dictionary with the action to open the report
        :rtype dict
        """
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'weekly.forecast.report',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'context': context,
        }
    
    def _check_report_values(self, report_brw, context=None):
        """
        Check if the consistency of the values of the report.
        
        :param report_brw: browse_record of a weekly.forecast.report to check
        :param context: Context of the call (will be updated by this method)
        
        :return True if all is ok, raise an error otherwise
        :rtype boolean
        """
        if not isinstance(report_brw, browse_record):
            raise osv.except_osv(
                _('Error'),
                _('The parameter \'report_brw\' of the method _check_report_values() must be a browse_record instance'),
            )
        
        if context is None:
            context = {}
        
        if report_brw.interval <= 0 or not report_brw.interval_type:
            raise osv.except_osv(_('Error'), _('You must enter an interval value !'))

        if report_brw.consumption_type in ('amc', 'rac') and report_brw.consumption_from > report_brw.consumption_to:
            raise osv.except_osv(_('Error'), _('You cannot have \'To date\' older than \'From date\''))

        if report_brw.consumption_type in ('amc', 'rac'):
            context.update({'from': report_brw.consumption_from, 'to': report_brw.consumption_to})
            
        return True

    def _process_lines(self, cr, uid, ids, context=None):
        """
        For each product of the DB, display the forecasted stock
        quantity value according to consumption, expired and in-pipe values.
        
        :param cr: Cursor to the database
        :param uid: ID of the user that called this method
        :param ids: ID or list of ID of weekly.forecast.report to generate
        :param context: Context of the call
        
        :return True if all is ok
        :rtype boolean
        """
        # Objects
        product_obj = self.pool.get('product.product')
        loc_obj = self.pool.get('stock.location')
        uom_obj = self.pool.get('product.uom')
        
        if context is None:
            context = {}
            
        if isinstance(ids, (int, long)):
            ids = [ids]

        # background cursor
        new_cr = pooler.get_db(cr.dbname).cursor()
 
        try:
            for report in self.browse(new_cr, uid, ids, context=context):
                nb_products = product_obj.search(new_cr, uid, [('type', '=', 'product'),], count=True, context=context)
                # Process the products by group of 500
                offset = 50.00
                nb_offset = (nb_products / offset) + 1
                
                # Report values
                self._check_report_values(report)
                
                # Get all locations
                location_ids = loc_obj.search(new_cr, uid, [
                    ('location_id', 'child_of', report.location_id.id),
                    ('quarantine_location', '=', False),
                ], order='location_id', context=context)
                
                context.update({
                    'location_id': location_ids,
                    'location': location_ids,
                })

                # Compute intervals
                intervals = []
                dict_int_from = {}
                i = 0
                while i != report.interval:
                    i += 1
                    if report.interval_type == 'week':
                        interval_name = 'Week %s' % i
                        interval_from = now() + RelativeDateTime(weeks=i-1, hour=0, minute=0, second=0)
                        interval_to = now() + RelativeDateTime(weeks=i, days=-1, hour=23, minute=59, second=59)
                    else:
                        interval_name = 'Month %s' % i
                        interval_from = now() + RelativeDateTime(months=i-1, hour=0, minute=0, second=0)
                        interval_to = now() + RelativeDateTime(months=i, days=-1, hour=23, minute=59, second=59)
                    
                    intervals.append((interval_name, interval_from, interval_to, i+8))
                    dict_int_from.setdefault(interval_from.strftime('%Y-%m-%d'), interval_name)
                
                percent_completed = 0.00
                progress_comment = ""
                product_ids = []
                product_cons = {}
                in_pipe_vals = {}
                exp_vals = {}
                for i in range(int(nb_offset)):
                    tmp_product_ids = product_obj.search(new_cr, uid, [('type', '=', 'product')], limit=offset, offset=i, context=context)
                    product_ids.extend(tmp_product_ids)
                    # Get consumption, in-pipe and expired quantities for each product
                    product_cons.update(self._get_product_consumption(new_cr, uid, tmp_product_ids, location_ids, report, context=context))
                    in_pipe_vals.update(self._get_in_pipe_vals(new_cr, uid, tmp_product_ids, location_ids, report, context=context))
                    exp_vals.update(self._get_expiry_batch(new_cr, uid, product_cons, location_ids, report, context=context))

                    percent_completed = (((i*offset)/nb_products) * 0.50) * 100
                    progress_comment = """
                        Calculation of consumption values by product: %(treated_products)s/%(nb_products)s

                        Calculation of in-pipe quantities by product and interval: %(treated_products)s/%(nb_products)s

                        Calculation of expiry quantities by product and interval: %(treated_products)s/%(nb_products)s

                        ------------------------------------------------------------------------------------------------

                        Calculate the forecasted quantity by product and period: 0/%(nb_products)s

                    """ % {
                            'treated_products': int(i*offset),
                            'nb_products': nb_products,
                    }
                    self.write(new_cr, uid, [report.id], {
                        'status': 'in_progress',
                        'progress': percent_completed,
                        'progress_comment': progress_comment,
                    }, context=context)
                    new_cr.commit()

                line_values = """<Row></Row><Row>
                      <Cell ss:StyleID=\"header\"><Data ss:Type=\"String\">Product Code</Data></Cell>
                      <Cell ss:StyleID=\"header\"><Data ss:Type=\"String\">Description</Data></Cell>
                      <Cell ss:StyleID=\"header\"><Data ss:Type=\"String\">Unit Price</Data></Cell>
                      <Cell ss:StyleID=\"header\"><Data ss:Type=\"String\">Stock value</Data></Cell>
                      <Cell ss:StyleID=\"header\"><Data ss:Type=\"String\">AMC/FMC</Data></Cell>
                      <Cell ss:StyleID=\"header\"><Data ss:Type=\"String\">Current Stock Qty</Data></Cell>
                      <Cell ss:StyleID=\"header\"><Data ss:Type=\"String\">Pipeline Qty</Data></Cell>
                      <Cell ss:StyleID=\"header\"><Data ss:Type=\"String\">Expiry Qty</Data></Cell>"""
                
                for interval in intervals:
                    line_values += """<Cell ss:StyleID=\"header\"><Data ss:Type=\"String\">%(interval_name)s</Data></Cell>""" % {
                        'interval_name': interval[0],
                    }

                line_values += """</Row>"""
                
                context.update({
                    'from_date': False,
                    'to_date': False,
                })
                stock_products = product_obj.read(new_cr, uid, product_ids, [
                    'qty_available',
                    'default_code',
                    'name',
                    'standard_price',
                    'uom_id',
                ], context=context)

                j = 0
                for product in stock_products:
                    product_id = product['id']
                    j += 1
                    cons = product_cons[product_id][1]
                    if not cons:
                        continue
                    weekly_cons = cons
                    if report.interval_type == 'week':
                        weekly_cons = round(cons / 30 * 7, 2)
                        weekly_cons = uom_obj._change_round_up_qty(new_cr, uid, product['uom_id'][0], weekly_cons, 'weekly_cons', result={})['value']['weekly_cons']

                    line_values += """<Row>
                          <Cell ss:StyleID=\"line\"><Data ss:Type=\"String\">%(product_code)s</Data></Cell>
                          <Cell ss:StyleID=\"line\"><Data ss:Type=\"String\">%(product_name)s</Data></Cell>
                          <Cell ss:StyleID=\"line\"><Data ss:Type=\"Number\">%(unit_price)s</Data></Cell>
                          <Cell ss:StyleID=\"line\" ss:Formula=\"=RC[-1]*RC[2]\"><Data ss:Type=\"Number\"></Data></Cell>
                          <Cell ss:StyleID=\"line\"><Data ss:Type=\"Number\">%(consumption)s</Data></Cell>
                          <Cell ss:StyleID=\"line\"><Data ss:Type=\"Number\">%(stock_qty)s</Data></Cell>
                          <Cell ss:StyleID=\"line\"><Data ss:Type=\"Number\">%(pipe_qty)s</Data></Cell>
                          <Cell ss:StyleID=\"line\"><Data ss:Type=\"Number\">%(exp_qty)s</Data></Cell>""" % {
                        'product_code': product['default_code'],
                        'product_name': product['name'],
                        'unit_price': product['standard_price'],
                        'consumption': cons,
                        'stock_qty': product['qty_available'],
                        'pipe_qty': in_pipe_vals[product_id]['total'],
                        'exp_qty': exp_vals[product_id]['total'],
                    }

                    inter = {}
                    for in_name, in_from, in_to, in_cn in intervals:
                        inter.setdefault(in_name, {
                            'date_from': in_from,
                            'date_to': in_to,
                            'exp_qty': 0.00,
                            'pipe_qty': 0.00,
                            'cn': in_cn,
                        })

                    # Return the last from date of interval closest to date
                    def get_interval_by_date(date):
                        date = DateFrom(date)
                        if report.interval_type == 'week':
                            st_day = now().day_of_week
                            last_date = date + RelativeDateTime(weekday=(st_day, 0))
                            if date.iso_week[2] == last_date.iso_week[2]:
                                return date
                            elif date.iso_week[2] > last_date.iso_week[2]:
                                return last_date
                            else:
                                return date + RelativeDateTime(weeks=-1) + RelativeDateTime(weekday=(st_day, 0))
                        else:
                            st_day = now().day
                            if date.day >= st_day:
                                return date + RelativeDateTime(day=st_day)
                            else:
                                return date + RelativeDateTime(months=-1, day=st_day)
                    
                    # Put expired quantity into the good interval
                    for exp_key, exp_val in exp_vals[product_id].iteritems():
                        if exp_key != 'total':
                            date_key = get_interval_by_date(exp_key).strftime('%Y-%m-%d')
                            int_name = dict_int_from.get(date_key, False)
                            if int_name:
                                inter[int_name]['exp_qty'] += exp_val

                    # Put In-pipe quantity into the good interval
                    for inp_key, inp_val in in_pipe_vals[product_id].iteritems():
                        if inp_key != 'total':
                            date_key = get_interval_by_date(inp_key).strftime('%Y-%m-%d')
                            int_name = dict_int_from.get(date_key, False)
                            if int_name:
                                inter[int_name]['pipe_qty'] += inp_val

                    # Sort the key of the dict, to have the values in good order
                    # TODO: Use OrderedDict instead of this sort of dict keys but only available on Python 2.7
                    interval_keys = inter.keys()
                    interval_keys.sort(key=lambda x: int(x[5:]))
                    last_value = product['qty_available']
                    for interval_name in interval_keys:
                        interval_values = inter.get(interval_name)
                        last_value = last_value - weekly_cons - interval_values['exp_qty'] + interval_values['pipe_qty']
                        line_values += """<Cell ss:StyleID=\"line\"><Data ss:Type=\"Number\">%(value)s</Data></Cell>""" % {
                            'value': last_value,
                        }

                    # Ponderation of 30 percent on this part of the process 
                    percent_completed = (0.5 + ((float(j)/nb_products) * 0.50)) * 100.00
                    progress_comment = """
                            Calculation of consumption values by product: %(nb_products)s/%(nb_products)s

                            Calculation of in-pipe quantities by product and interval: %(nb_products)s/%(nb_products)s

                            Calculation of expiry quantities by product and interval: %(nb_products)s/%(nb_products)s

                            ------------------------------------------------------------------------------------------------

                            Calculate the forecasted quantity by product and period: %(treated_products)s/%(nb_products)s

                    """ % {
                        'treated_products': j,
                        'nb_products': nb_products,
                    }
                    self.write(new_cr, uid, [report.id], {
                        'status': 'in_progress',
                        'progress': percent_completed,
                        'progress_comment': progress_comment,
                    }, context=context)
                    new_cr.commit()

                    line_values += """
                        </Row>
                    """
                self.write(new_cr, uid, [report.id], {'xml_data': line_values, 'status': 'ready', 'progress': 100.00}, context=context)

            new_cr.commit()
        except Exception as e:
            new_cr.rollback()
            progress_comment = """
            An error occured during the processing of the report.\n
            Details of the error:\n
            %s
            """ % str(e)
            self.write(new_cr, uid, [report.id], {'status': 'error', 'progress_comment': progress_comment}, context=context)
            new_cr.commit()

        new_cr.close()

        return True

    def _get_product_consumption(self, cr, uid, product_ids, location_ids, report, context=None):
        """
        Computes and return a list of tuples like (product_id, product_consumption).

        :param cr: Cursor to the database
        :param uid: ID of the user that called this methed
        :param product_ids: List of ID of product.product
        :param location_ids: List of ID of stock.location
        :param report: browse_record of a weekly.forecast.report
        :param context: Context of the call

        :return A dictionary with ID of product as key and the expired quantity
                for this product in the given stock locations by date.
        :rtype dict
        """
        # Objects
        product_obj = self.pool.get('product.product')

        if context is None:
            context = {}

        context.update({
            'from_date': report.consumption_from,
            'to_date': report.consumption_to,
            'location_id': location_ids,
            'location': location_ids,
        })

        res = {}

        cons_field = 'product_amc'
        if report.consumption_type == 'fmc':
            cons_field = 'reviewed_consumption'
        elif report.consumption_type == 'rac':
            cons_field = 'monthly_consumption'

        products = product_obj.read(cr, uid, product_ids, ['perishable', 'batch_management', cons_field], context=context)
        for product in products:
            p_cons = product[cons_field]
            res[product['id']] = (product, p_cons)

        return res

    def _get_expiry_batch(self, cr, uid, product_cons, location_ids, report, context=None):
        """
        Returns a dictionary with for each product in products, the expiry quantities per date.

        :param cr: Cursor to the database
        :param uid: ID of the user that called this method
        :param product_cons: List of tuples like (product_id, product_cons_value)
        :param location_ids: List of ID of stock.location
        :param report: browse_record of a weekly.forecast.report
        :param context: Context of the call

        :return A dictionary with ID of product as key and the expired quantity
                for this product in the given stock locations by date.
        :rtype dict
        """
        # Objects
        lot_obj = self.pool.get('stock.production.lot')

        if context is None:
            context = {}

        context.update({
            'location_id': location_ids,
            'location': location_ids,
        })

        res = {}

        if report.interval_type == 'week':
            report_end_date = now() + RelativeDateTime(weeks=report.interval)
        else:
            report_end_date = now() + RelativeDateTime(months=report.interval)

        for product, av_cons in product_cons.itervalues():
            res.setdefault(product['id'], {'total': 0.00})
            if not product['perishable'] and not product['batch_management']:
                continue

            prodlot_ids = lot_obj.search(cr, uid, [
                ('product_id', '=', product['id']),
                ('stock_available', '>', 0.00),
                ('life_date', '>=', time.strftime('%Y-%m-%d')),
                ('life_date', '<=', report_end_date.strftime('%Y-%m-%d')),
            ], order='life_date', context=context)

            last_expiry_date = now() - RelativeDateTime(days=1)
            total_expired = 0.00
            rest = 0.00
            already_cons = 0.00
            for lot in lot_obj.browse(cr, uid, prodlot_ids, context=context):
                l_expired_qty = 0.00
                lot_days = Age(DateFrom(lot.life_date), last_expiry_date)
                lot_coeff = (lot_days.years*365.0 + lot_days.months*30.0 + lot_days.days)/30.0
                if lot_coeff >= 0.00: last_expiry_date = DateFrom(lot.life_date)
                if lot_coeff < 0.00: lot_coeff = 0.00
                lot_cons = self.pool.get('product.uom')._compute_qty(cr, uid, lot.product_id.uom_id.id, round(lot_coeff*av_cons,2), lot.product_id.uom_id.id) + rest
                if lot_cons > 0.00:
                    if lot_cons >= lot.stock_available:
                        already_cons += lot.stock_available
                        rest = lot_cons - lot.stock_available
                        l_expired_qty = 0.00
                    else:
                        l_expired_qty = lot.stock_available - lot_cons
                        already_cons += lot_cons
                        rest = 0.00
                else:
                    l_expired_qty = lot.stock_available

                if l_expired_qty:
                    total_expired += l_expired_qty
                    res[product['id']].setdefault(lot.life_date, 0.00)
                    res[product['id']].setdefault('total', 0.00)
                    res[product['id']][lot.life_date] += l_expired_qty
                    res[product['id']]['total'] += l_expired_qty

        return res

    def _get_in_pipe_vals(self, cr, uid, product_ids, location_ids, report, context=None):
        """
        Returns a dictionary with for each product in product_ids, the quantity in-pipe.

        :param cr: Cursor to the database
        :param uid: ID of the user that called this method
        :param product_ids: List of ID of product.product
        :param location_ids: List of ID of stock.location
        :param report: browse_record of a weekly.forecast.report
        :param context: Context of the call

        :return A dictionary with ID of product as key and in-pipe quantity for
                this product in the givent stock locations by date
        :rtype dict
        """
        if context is None:
            context = {}

        res = {}

        cr.execute("""
            SELECT product_id, sum(qty) AS qty, date
            FROM
            ((SELECT 
               p.id AS product_id, 
               sum(s.product_qty/u1.factor/u2.factor) AS qty, 
               s.date AS date 
            FROM 
               stock_move s
               LEFT JOIN product_product p ON p.id = s.product_id
               LEFT JOIN product_template pt ON p.product_tmpl_id = pt.id
               LEFT JOIN product_uom u1 ON s.product_uom = u1.id
               LEFT JOIN product_uom u2 ON pt.uom_id = u2.id
            WHERE
               s.location_id IN %(location_ids)s
               AND
               s.product_id IN %(product_ids)s
               AND 
               s.state IN ('assigned', 'confirmed')
            GROUP BY p.id, s.date)
        UNION
            (SELECT 
               p.id AS product_id, 
               sum(s.product_qty/u1.factor/u2.factor) AS qty, 
               s.date AS date 
            FROM 
               stock_move s
               LEFT JOIN product_product p ON p.id = s.product_id
               LEFT JOIN product_template pt ON p.product_tmpl_id = pt.id
               LEFT JOIN product_uom u1 ON s.product_uom = u1.id
               LEFT JOIN product_uom u2 ON pt.uom_id = u2.id
            WHERE
              s.location_dest_id IN %(location_ids)s
              AND
              s.product_id IN %(product_ids)s
              AND
              s.state IN ('assigned', 'confirmed')
            GROUP BY p.id, s.date))
            AS subrequest
            GROUP BY product_id, date;
        """, {
            'location_ids': tuple(location_ids), 
            'product_ids': tuple(product_ids)
        })

        for r in cr.dictfetchall():
            res.setdefault(r['product_id'], {'total': 0.00})
            res[r['product_id']].setdefault(r['date'], 0.00)
            res[r['product_id']][r['date']] = r['qty']
            res[r['product_id']].setdefault('total', 0.00)
            res[r['product_id']]['total'] = r['qty']

        return res
        
weekly_forecast_report()


class weekly_forecast_product_report(osv.osv):
    _name = 'weekly.forecast.product.report'
    _rec_name = 'product_id'

    _columns = {
        'product_id': fields.many2one(
            'product.product',
            string='Product',
            required=True,
            select=1,
        ),
        'report_id': fields.many2one(
            'weekly.forecast.report',
            string='Report',
            required=True,
            select=1,
        ),
        'consumption': fields.float(
            digits=(16,2),
            string='AMC/FMC',
        ),
        'av_qty': fields.float(
            digits=(16,2),
            string='Current Stock Qty',
        ),
        'in_pipe_qty': fields.float(
            digits=(16,2),
            string='Pipeline Qty',
        ),
        'exp_qty': fields.float(
            digits=(16,2),
            string='Expiry Qty',
        ),
        'qty_values': fields.text(
            string='Qty. Values',
        ),
    }

weekly_forecast_product_report()


class weekly_forecast_product_interval_report(osv.osv):
    _name = 'weekly.forecast.product.interval.report'

    _columns = {
        'name': fields.char(
            size=64,
            string='Name',
            required=True,
        ),
        'line_id': fields.many2one(
            'weekly.forecast.product.report',
            string='Product report line',
            required=True,
            select=1,
        ),
        'date_from': fields.date(
            string='From',
        ),
        'date_to': fields.date(
            string='To',
        ),
        'exp_qty': fields.float(
            digits=(16,2),
            string='Exp. Qty',
        ),
        'inp_qty': fields.float(
            digits=(16,2),
            string='In-Pipe Qty',
        ),
    }

weekly_forecast_product_interval_report()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
