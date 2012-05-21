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
from mx.DateTime import now

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
        product_obj = self.pool.get('product.product')
        freq_obj = self.pool.get('stock.frequence')

        start_date = time.strftime('%Y-%m-%d %H:%M:%S')
        
        cycle_ids = cycle_obj.search(cr, uid, [('next_date', '<=', datetime.now())])
        
        created_proc = []
        report = []
        report_except = 0
        ran_proc = []
        
        # Cache for product/location
        cache = {}
        
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
                        'safety': cycle.safety_stock,
                        'consumption_period_from': cycle.consumption_period_from,
                        'consumption_period_to': cycle.consumption_period_to,
                        'past_consumption': cycle.past_consumption,
                        'reviewed_consumption': cycle.reviewed_consumption,
                        'manual_consumption': cycle.manual_consumption,}

            if cycle.product_ids:
                product_ids = []
                ran_proc.append(cycle.id)
                for p in cycle.product_ids:
                    product_ids.append(p.id)
                for product in product_obj.browse(cr, uid, product_ids):
                    proc_id = self.create_proc_cycle(cr, uid, cycle, product.id, location_id, d_values, cache=cache)
                    

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
    
    def create_proc_cycle(self, cr, uid, cycle, product_id, location_id, d_values=None, cache=None, context=None):
        '''
        Creates a procurement order for a product and a location
        '''
        proc_obj = self.pool.get('procurement.order')
        cycle_obj = self.pool.get('stock.warehouse.order.cycle')
        product_obj = self.pool.get('product.product')
        wf_service = netsvc.LocalService("workflow")
        report = []
        proc_id = False
       
        if context is None:
            context = {}
        if d_values is None:
            d_values = {}
        if cache is None:
            cache = {}

        if isinstance(product_id, (int, long)):
            product_id = [product_id]
            
        if d_values.get('past_consumption', False):
            if not d_values.get('consumption_period_from', False):
                order_coverage = d_values.get('coverage', 3)
                d_values.update({'consumption_period_from': (now() + RelativeDate(day=1, months=-round(order_coverage, 1)+1)).strftime('%Y-%m-%d')})
            if not d_values.get('consumption_period_to', False):
                d_values.update({'consumption_period_to': (now() + RelativeDate(days=-1, day=1, months=1)).strftime('%Y-%m-%d')})
            context.update({'from_date': d_values.get('consumption_period_from'), 'to_date': d_values.get('consumption_period_to')})
        
        product = product_obj.browse(cr, uid, product_id[0], context=context)
        
        # Enter the stock location in cache to know which products has been already replenish for this location
        if not cache.get(location_id, False):
            cache.update({location_id: []})
        
            
        if product.id not in cache.get(location_id):
            newdate = datetime.today()
            quantity_to_order = self._compute_quantity(cr, uid, cycle, product.id, location_id, d_values, context=context)
                
            if quantity_to_order <= 0:
                return False
            else:
                proc_id = proc_obj.create(cr, uid, {
                                        'name': _('Procurement cycle: %s') % (cycle.name,),
                                        'origin': cycle.name,
                                        'date_planned': newdate.strftime('%Y-%m-%d %H:%M:%S'),
                                        'product_id': product.id,
                                        'product_qty': quantity_to_order,
                                        'product_uom': product.uom_id.id,
                                        'location_id': location_id,
                                        'procure_method': 'make_to_order',
                })
                wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_confirm', cr)
                wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_check', cr)
                context.update({'button': 'scheduler'})
                cycle_obj.write(cr, uid, [cycle.id], {'procurement_id': proc_id}, context=context)
            
            # Fill the cache
            cache.get(location_id).append(product.id)
        
        return proc_id
    
    def _compute_quantity(self, cr, uid, cycle_id, product_id, location_id, d_values=None, context=None):
        '''
        Compute the quantity of product to order like thid :
            [Delivery lead time (from supplier tab of the product or by default or manually overwritten) x Monthly Consumption]
            + Order coverage (number of months : 3 by default, manually overwritten) x Monthly consumption
            - Projected available quantity
        '''
        if d_values is None:
            d_values = {}
        product_obj = self.pool.get('product.product')
        supplier_info_obj = self.pool.get('product.supplierinfo')
        location_obj = self.pool.get('stock.location')
        cycle_obj = self.pool.get('stock.warehouse.order.cycle')
        review_obj = self.pool.get('monthly.review.consumption')
        review_line_obj = self.pool.get('monthly.review.consumption.line')
        
        product = product_obj.browse(cr, uid, product_id, context=context)
        location = location_obj.browse(cr, uid, location_id, context=context)

        
        # Get the delivery lead time
        delivery_leadtime = product.seller_delay and product.seller_delay != 'N/A' and round(int(product.seller_delay)/30.0, 2) or 1
        if 'leadtime' in d_values and d_values.get('leadtime', 0.00) != 0.00:
            delivery_leadtime = d_values.get('leadtime')
        else:
            sequence = False
            for supplier_info in product.seller_ids:
                if sequence and supplier_info.sequence < sequence:
                    sequence = supplier_info.sequence
                    delivery_leadtime = round(supplier_info.delay/30.0, 2)
                elif not sequence:
                    sequence = supplier_info.sequence
                    delivery_leadtime = round(supplier_info.delay/30.0, 2)
                
        # Get the monthly consumption
        monthly_consumption = 0.00
        
        if 'reviewed_consumption' in d_values and d_values.get('reviewed_consumption'):
            monthly_consumption = product.reviewed_consumption
        elif 'past_consumption' in d_values and d_values.get('past_consumption'):
            monthly_consumption = product.product_amc
        else:
            monthly_consumption = d_values.get('manual_consumption', 0.00)
            
        # Get the order coverage
        order_coverage = d_values.get('coverage', 3)
        
        # Get the projected available quantity
        available_qty = self.get_available(cr, uid, product_id, location_id, monthly_consumption, d_values)
        
        qty_to_order = (delivery_leadtime * monthly_consumption) + (order_coverage * monthly_consumption) - available_qty
        
        return round(self.pool.get('product.uom')._compute_qty(cr, uid, product.uom_id.id, qty_to_order, product.uom_id.id), 2)
        
        
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
        location_obj = self.pool.get('stock.location')
        move_obj = self.pool.get('stock.move')
        
        context.update({'location': location_id,
                        'compute_child': True, 
                        'from_date': time.strftime('%Y-%m-%d')})
        
        product = product_obj.browse(cr, uid, product_id, context=context)
        location_name = location_obj.browse(cr, uid, location_id, context=context).name

        ''' Set this part of algorithm as comments because this algorithm seems to be equal to virtual stock
        
            To do validate by Magali
            
            Picked reservation will be developed on future sprint
        ''' 
        
        # Get the available stock
        # Get the real stock
        picked_resa = product_obj.get_product_available(cr, uid, [product_id], context={'states': ['assigned'],
                                                                                       'what': ('in, out'), 
                                                                                       'location': location_id,
                                                                                       'compute_child': True, 
                                                                                       'from_date': time.strftime('%Y-%m-%d')})
        # Get the picked reservation
        ## TODO: To confirm by Magali
#        picked_reservation = 0.00
#        move_ids = []
#        for location in location_obj.search(cr, uid, [('location_id', 'child_of', [location_id])]):
#            for move_id in move_obj.search(cr, uid, [('product_id', '=', product_id), ('location_dest_id', '=', location), 
#                                                     ('state', '!=', 'draft'), ('move_dest_id', '!=', False)]):
#                move_ids.append(move_id)
#            
#        for move in move_obj.browse(cr, uid, move_ids):
#            picked_reservation += move.product_qty
            
        available_stock = product.qty_available - picked_resa.get(product.id)
        
        #available_stock = real_stock.get(product_id) - picked_reservation
        
        # Get the quantity on order
        ## TODO : To confirm by Magali
#        quantity_on_order = 0.00
#        move_ids = []
#        for location in location_obj.search(cr, uid, [('location_id', 'child_of', [location_id])]):
#            for move_id in move_obj.search(cr, uid, [('product_id', '=', product_id), ('location_dest_id', '=', location)]):
#                move_ids.append(move_id)
#            
#        for move in move_obj.browse(cr, uid, move_ids):
#            quantity_on_order += move.product_qty
            
        quantity_on_order = product_obj.get_product_available(cr, uid, [product_id], context={'states': ['confirmed'],
                                                                                              'what': ('in, out'), 
                                                                                              'location': location_id,
                                                                                              'compute_child': True, 
                                                                                              'from_date': time.strftime('%Y-%m-%d')})
           
        # Get the safety stock
        safety_stock = d_values.get('safety', 0)
        
        # Get the safety time
        safety_time = d_values.get('safety_time', 0)
        
        # Get the expiry quantity
        # Set as comment because expiry quantity will be developed in a future sprint
        expiry_quantity = product_obj.get_expiry_qty(cr, uid, product_id, location_id, monthly_consumption, d_values)
        expiry_quantity = expiry_quantity and available_stock - expiry_quantity or 0.00
        #expiry_quantity = 0.00

        # Set this part of algorithm as comments because this algorithm seems to be equal to virtual stock
        return available_stock + quantity_on_order.get(product.id) - safety_stock - (safety_time * monthly_consumption) - expiry_quantity

#        return product.virtual_available - safety_stock - (safety_time * monthly_consumption) - expiry_quantity
    
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
