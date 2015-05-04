# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF 
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
from datetime import datetime
from tools.translate import _
from mx.DateTime import RelativeDate
from mx.DateTime import RelativeDateTime
from mx.DateTime import now
from mx.DateTime import Parser

import time
import pooler
import netsvc



class procurement_order(osv.osv):
    _name = 'procurement.order'
    _inherit = 'procurement.order'
    
    def run_automatic_cycle(self, cr, uid, use_new_cursor=False, batch_id=False, context=None):
        '''
        Create procurement on fixed date
        '''
        if use_new_cursor:
            cr = pooler.get_db(use_new_cursor).cursor()
            
        request_obj = self.pool.get('res.request')
        cycle_obj = self.pool.get('stock.warehouse.order.cycle')
        proc_obj = self.pool.get('procurement.order')
        freq_obj = self.pool.get('stock.frequence')

        start_date = time.strftime('%Y-%m-%d %H:%M:%S')
        
        cycle_ids = cycle_obj.search(cr, uid, [('next_date', '<=', datetime.now())])
        
        created_proc = []
        report = []
        report_except = 0
        ran_proc = []

        self.check_exception_proc(cr, uid, [], context=context)
        
        # We start with only category Automatic Supply
        for cycle in cycle_obj.browse(cr, uid, cycle_ids):
            # We define the replenish location
            location_id = False
            if not cycle.location_id or not cycle.location_id.id:
                location_id = cycle.warehouse_id.lot_input_id.id
            else:
                location_id = cycle.location_id.id
                
            d_values = {'leadtime': cycle.leadtime,
                        'coverage': cycle.order_coverage,
                        'safety_time': cycle.safety_stock_time,
                        'consumption_period_from': cycle.consumption_period_from,
                        'consumption_period_to': cycle.consumption_period_to,
                        'past_consumption': cycle.past_consumption,
                        'reviewed_consumption': cycle.reviewed_consumption,
                        'manual_consumption': cycle.manual_consumption,}

            if cycle.product_ids:
                ran_proc.append(cycle.id)
                for line in cycle.product_ids:
                    # Update the safety stock according to the safety stock defined in the line
                    d_values.update({'safety_stock': line.safety_stock})
                    proc_id = self.create_proc_cycle(cr, uid, cycle, line.product_id.id, location_id, d_values, line)

                    if proc_id:
                        created_proc.append(proc_id)
            
            if cycle.frequence_id:
                freq_obj.write(cr, uid, cycle.frequence_id.id, {'last_run': datetime.now()})

        created_doc = '''################################
Created documents : \n'''
                    
        for proc in proc_obj.browse(cr, uid, created_proc):
            if proc.state == 'exception':
                report.append('PROC %d: from stock - %3.2f %-5s - %s' % \
                               (proc.id, proc.product_qty, proc.product_uom.name,
                                proc.product_id.name,))
                report_except += 1
            elif proc.purchase_id:
                created_doc += "    * %s => %s \n" % (proc.name, proc.purchase_id.name)
                
        end_date = time.strftime('%Y-%m-%d %H:%M:%S')
                
        summary = '''Here is the procurement scheduling report for Order Cycle

        Start Time: %s
        End Time: %s
        Total Rules processed: %d
        Procurements with exceptions: %d
        \n %s \n Exceptions: \n'''% (start_date, end_date, len(ran_proc), report_except, len(created_proc) > 0 and created_doc or '')
        summary += '\n'.join(report)
        if batch_id:
            self.pool.get('procurement.batch.cron').write(cr, uid, batch_id, {'last_run_on': time.strftime('%Y-%m-%d %H:%M:%S')})
            old_request = request_obj.search(cr, uid, [('batch_id', '=', batch_id), ('name', '=', 'Procurement Processing Report (Order cycle).')])
            request_obj.write(cr, uid, old_request, {'batch_id': False})
        
        request_obj.create(cr, uid,
                {'name': "Procurement Processing Report (Order cycle).",
                 'act_from': uid,
                 'act_to': uid,
                 'batch_id': batch_id,
                 'body': summary,
                })
        # UF-952 : Requests should be in consistent state
#        if req_id:
#            request_obj.request_send(cr, uid, [req_id])
        
        if use_new_cursor:
            cr.commit()
            cr.close()
            
        return {}
    
    def create_proc_cycle(self, cr, uid, cycle, product_id, location_id, d_values=None, line=None, context=None):
        '''
        Creates a procurement order for a product and a location
        '''
        proc_obj = self.pool.get('procurement.order')
        cycle_obj = self.pool.get('stock.warehouse.order.cycle')
        product_obj = self.pool.get('product.product')
        wf_service = netsvc.LocalService("workflow")
        proc_id = False
       
        if context is None:
            context = {}
        if d_values is None:
            d_values = {}

        if isinstance(product_id, (int, long)):
            product_id = [product_id]
            
        if d_values.get('past_consumption', False):
            # If the AMC should be used, compute the period of calculation
            if not d_values.get('consumption_period_from', False):
                order_coverage = d_values.get('coverage', 3)
                d_values.update({'consumption_period_from': (now() + RelativeDate(day=1, months=-round(order_coverage, 1)+1)).strftime('%Y-%m-%d')})
            if not d_values.get('consumption_period_to', False):
                d_values.update({'consumption_period_to': (now() + RelativeDate(days=-1, day=1, months=1)).strftime('%Y-%m-%d')})
            context.update({'from_date': d_values.get('consumption_period_from'), 'to_date': d_values.get('consumption_period_to')})
        
        product = product_obj.browse(cr, uid, product_id[0], context=context)

        newdate = datetime.today().strftime('%Y-%m-%d %H:%M:%S')
        if line and line.required_date:
            newdate = line.required_date

        quantity_to_order = self._compute_quantity(cr, uid, cycle, product, location_id, d_values, context=context)
            
        # Create a procurement only if the quantity to order is more than 0.00
        if quantity_to_order <= 0.00:
            return False
        else:
            proc_id = proc_obj.create(cr, uid, {
                                    'name': _('Procurement cycle: %s') % (cycle.name,),
                                    'origin': cycle.name,
                                    'unique_rule_type': 'stock.warehouse.order.cycle',
                                    'date_planned': newdate,
                                    'product_id': product.id,
                                    'product_qty': quantity_to_order,
                                    'product_uom': product.uom_id.id,
                                    'location_id': location_id,
                                    'procure_method': 'make_to_order',
            })
            # Confirm the procurement order
            wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_confirm', cr)
            wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_check', cr)
            context.update({'button': 'scheduler'})
            cycle_obj.write(cr, uid, [cycle.id], {'procurement_id': proc_id}, context=context)
        
        return proc_id
    
    def _compute_quantity(self, cr, uid, cycle_id, product, location_id, d_values=None, context=None):
        '''
        Compute the quantity of product to order like thid :
            [Delivery lead time (from supplier tab of the product or by default or manually overwritten) x Monthly Consumption]
            + Order coverage (number of months : 3 by default, manually overwritten) x Monthly consumption
            - Projected available quantity
        '''
        if d_values is None:
            d_values = {}

        # Get the delivery lead time of the product if the leadtime is not defined in rule and no supplier found in product form
        delivery_leadtime = product.procure_delay and round(int(product.procure_delay)/30.0, 2) or 1
        # Get the leadtime of the rule if defined
        if 'leadtime' in d_values and d_values.get('leadtime', 0.00) != 0.00:
            delivery_leadtime = d_values.get('leadtime')
        elif product.seller_ids:
            # Get the supplier lead time if supplier is defined
            # The seller delay is defined in days, so divide it by 30.0 to have a LT in months
            delivery_leadtime = product.seller_delay and round(int(product.seller_delay)/30.0, 2) or 1
                
        # Get the monthly consumption
        monthly_consumption = 0.00
        
        if 'reviewed_consumption' in d_values and d_values.get('reviewed_consumption'):
            monthly_consumption = product.reviewed_consumption
        elif 'past_consumption' in d_values and d_values.get('past_consumption'):
            monthly_consumption = product.product_amc
        else:
            monthly_consumption = d_values.get('manual_consumption', 0.00)
            
        # Get the order coverage
        order_coverage = d_values.get('coverage', 0.00)
        
        # Get the projected available quantity
        available_qty = self.get_available(cr, uid, product.id, location_id, monthly_consumption, d_values)
        
        qty_to_order = (delivery_leadtime * monthly_consumption) + (order_coverage * monthly_consumption) - available_qty

        if not context.get('get_data', False):
            res = round(self.pool.get('product.uom')._compute_qty(cr, uid, product.uom_id.id, qty_to_order, product.uom_id.id), 2)
        else:
            delta = 0
            if monthly_consumption:
                delta = available_qty / monthly_consumption * 30

            if delta <= 0.00:
                req_date = now().strftime('%Y-%m-%d')
            else:
                req_date = (now() + RelativeDateTime(days=delta)).strftime('%Y-%m-%d')
            res = round(self.pool.get('product.uom')._compute_qty(cr, uid, product.uom_id.id, qty_to_order, product.uom_id.id), 2), req_date

        return res
        
    def get_available(self, cr, uid, product_id, location_id, monthly_consumption, d_values=None, context=None):
        '''
        Compute the projected available quantity like this :
            Available stock (real stock - picked reservation)
            + Quantity on order ("in pipe")
            - Safety stock [blank by default but can be overwritten for a product category or at product level]
            - Safety time [= X (= 0 by default) month x Monthly consumption (validated consumption by default or
                        manually overwritten for a product or at product level)]
            - Expiry quantities.
        '''
        if context is None:
            context = {}
        if d_values is None:
            d_values = {}
            
        product_obj = self.pool.get('product.product')
        
        context.update({'location': location_id,
                        'compute_child': True, })
        
        product = product_obj.browse(cr, uid, product_id, context=context)

        ''' Set this part of algorithm as comment because this algorithm seems to be equal to virtual stock
        
            To do validate by Magali
            
            Picked reservation will be developed on future sprint
        ''' 
        
        # Get the available stock
        # Get the real stock
        picked_resa = product_obj.get_product_available(cr, uid, [product_id], context={'states': ['assigned'],
                                                                                       'what': ('in, out'), 
                                                                                       'location': location_id,
                                                                                       'compute_child': True,})
            
        available_stock = product.qty_available + picked_resa.get(product.id)
            
        quantity_on_order = product_obj.get_product_available(cr, uid, [product_id], context={'states': ['confirmed', 'hidden'],
                                                                                              'what': ('in, out'), 
                                                                                              'location': location_id,
                                                                                              'compute_child': True,})
           
        # Get the safety stock
        safety_stock = d_values.get('safety_stock', 0)
        
        # Get the safety time
        safety_time = d_values.get('safety_time', 0)
        
        # Get the expiry quantity
        expiry_quantity = product_obj.get_expiry_qty(cr, uid, product_id, location_id, monthly_consumption, d_values, context=context)
        expiry_quantity = expiry_quantity and expiry_quantity or 0.00

        
        # Set this part of algorithm as comments because this algorithm seems to be equal to virtual stock
#        return product.virtual_available - safety_stock - (safety_time * monthly_consumption) - expiry_quantity
        return available_stock + quantity_on_order.get(product.id) - safety_stock - (safety_time * monthly_consumption) - expiry_quantity
    
    def get_diff_date(self, date):
        '''
        Returns the number of month between the date in parameter and today
        '''
        date = Parser.DateFromString(date)
        today = datetime.today()
        
        # The batch is expired
        if date.year < today.year or (date.year == today.year and date.month < today.month):
            return 0 
        
        # The batch expires this month
        if date.year == today.year and date.month == today.month:
            return 0
        
        # The batch expires in one month
        if date.year == today.year and date.month == today.month+1 and date.day >= today.day:
            return 0
        
        # Compute the number of months
        nb_month = 0
        nb_month += (date.year - today.year) * 12
        nb_month += date.month - today.month
        if date.day < today.day:
            nb_month -= 1
            
        return nb_month
        
procurement_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
