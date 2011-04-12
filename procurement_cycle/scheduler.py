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

from osv import osv, fields
from datetime import datetime
from tools.translate import _
from mx.DateTime import *

import time
import pooler
import netsvc


# Cache for product/location
cache = {}

class procurement_order(osv.osv):
    _name = 'procurement.order'
    _inherit = 'procurement.order'
    
    def run_automatic_cycle(self, cr, uid, use_new_cursor=False, context={}):
        '''
        Create procurement on fixed date
        '''
        if use_new_cursor:
            cr = pooler.get_db(use_new_cursor).cursor()
            
        request_obj = self.pool.get('res.request')
        cycle_obj = self.pool.get('stock.warehouse.order.cycle')
        proc_obj = self.pool.get('procurement.order')
        product_obj = self.pool.get('product.product')
        
        cycle_ids = cycle_obj.search(cr, uid, [('next_date', '=', datetime.today().strftime('%Y-%m-%d')), ('product_id', '=', False)])
        
        created_proc = []
        report = []
        report_except = 0
        
        start_date = datetime.now()
        
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
                        'past_consumption': cycle.past_consumption,
                        'reviewed_consumption': cycle.reviewed_consumption,
                        'manual_consumption': cycle.manual_consumption,}
            not_products = []
            for p in cycle.product_ids:
                not_products.append(p.id)
            product_ids = product_obj.search(cr, uid, [('categ_id', 'child_of', cycle.category_id.id), ('id', 'not in', not_products)])
            
            for product in product_obj.browse(cr, uid, product_ids):
                proc_id = self.create_proc_cycle(cr, uid, cycle, product.id, location_id, d_values)
                
                if proc_id:
                    created_proc.append(proc_id)
        
        # Next, for one product automatic supply
        cycle_ids = cycle_obj.search(cr, uid, [('next_date', '=', datetime.today().strftime('%Y-%m-%d')), ('product_id', '!=', False)])
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
                        'past_consumption': cycle.past_consumption,
                        'reviewed_consumption': cycle.reviewed_consumption,
                        'manual_consumption': cycle.manual_consumption,}
            
            proc_id = self.create_proc_cycle(cr, uid, cycle, cycle.product_id.id, location_id, d_values)
            
            if proc_id:
                created_proc.append(proc_id)
                    
        for proc in proc_obj.browse(cr, uid, created_proc):
            if proc.state == 'exception':
                report.append('PROC %d: from stock - %3.2f %-5s - %s' % \
                               (proc.id, proc.product_qty, proc.product_uom.name,
                                proc.product_id.name,))
                report_except += 1
                
        end_date = datetime.now()
                
        summary = '''Here is the procurement scheduling report for Order Cycle

        Start Time: %s
        End Time: %s
        Total Procurements processed: %d
        Procurements with exceptions: %d

        Exceptions:\n'''% (start_date, end_date, len(created_proc), report_except)
        summary += '\n'.join(report)
        request_obj.create(cr, uid,
                {'name': "Procurement Processing Report.",
                 'act_from': uid,
                 'act_to': uid,
                 'body': summary,
                })
        
        if use_new_cursor:
            cr.commit()
            cr.close()
            
        return {}
    
    def create_proc_cycle(self, cr, uid, cycle, product_id, location_id, d_values={}, context={}):
        '''
        Creates a procurement order for a product and a location
        '''
        proc_obj = self.pool.get('procurement.order')
        cycle_obj = self.pool.get('stock.warehouse.order.cycle')
        product_obj = self.pool.get('product.product')
        wf_service = netsvc.LocalService("workflow")
        report = []
        proc_id = False
        
        if isinstance(product_id, (int, long)):
            product_id = [product_id]
        
        product = product_obj.browse(cr, uid, product_id[0])
        
        # Enter the stock location in cache to know which products has been already replenish for this location
        if not cache.get(location_id, False):
            cache.update({location_id: []})
        
        # If a rule already exist for the category of the product or for the product
        # itself for the same location, we don't create a procurement order 
        cycle_ids = cycle_obj.search(cr, uid, [('category_id', '=', product.categ_id.id), ('location_id', '=', location_id), ('id', '!=', cycle.id)])
        cycle2_ids = cycle_obj.search(cr, uid, [('product_id', '=', product.id), ('location_id', '=', location_id), ('id', '!=', cycle.id)])
        if cycle_ids or cycle2_ids:
            return False
        
        newdate = datetime.today()
        quantity_to_order = self._compute_quantity(cr, uid, product.id, location_id, d_values)
            
        if product.id not in cache.get(location_id):
            newdate = datetime.today()
            if quantity_to_order <= 0:
                return False
            else:
                proc_id = proc_obj.create(cr, uid, {
                                        'name': _('Automatic Supply: %s') % (cycle.name,),
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
                cycle_obj.write(cr, uid, [cycle.id], {'procurement_id': proc_id}, context=context)
            
            # Fill the cache
            cache.get(location_id).append(product.id)
        
        return proc_id
    
    def _compute_quantity(self, cr, uid, product_id, location_id, d_values={}, context={}):
        '''
        Compute the quantity of product to order like thid :
            [Delivery lead time (from supplier tab of the product or by default or manually overwritten) x Monthly Consumption]
            + Order coverage (number of months : 3 by default, manually overwritten) x Monthly consumption
            - Projected available quantity
        '''
        product_obj = self.pool.get('product.product')
        supplier_info_obj = self.pool.get('product.suplierinfo')
        location_obj = self.pool.get('stock.location')
        
        product = product_obj.browse(cr, uid, product_id)
        location = location_obj.browse(cr, uid, location_id)

        
        # Get the delivery lead time
        delivery_leadtime = product.procure_delay or 1
        if 'leadtime' in d_values and d_values.get('leadtime', False):
            delivery_leadtime = d_values.get('leadtime')/30 # We divided by 30 because the leadtime should be in months
        else:
            supplier_info_ids = supplier_info_obj.search(cr, uid, [('product_id', '=', product_id)], offset=0, limit=1, order='sequence')
            if supplier_info_ids:
                delivery_leadtime = supplier_info_obj.browse(cr, uid, supplier_info_ids)[0].delay
                
        # Get the monthly consumption
        monthly_consumption = 1.0
        if 'past_consumption' in d_values and d_values.get('past_consumption', False) \
            and 'reviewed_consumption' in d_values and d_values.get('reviewed_consumption', False):
            monthly_consumption = d_values.get('reviewed_consumption')
        else:
            monthly_consumption = d_values.get('manual_consumption')
            
        # Get the order coverage
        order_coverage = d_values.get('order_coverage', 3)
        
        # Get the projected available quantity
        available_qty = self.get_available(cr, uid, product_id, location_id, monthly_consumption, d_values)
        
        return (delivery_leadtime * monthly_consumption) + (order_coverage * monthly_consumption) - available_qty
        
        
    def get_available(self, cr, uid, product_id, location_id, monthly_consumption, d_values={}, context={}):
        '''
        Compute the projected available quantity like this :
            Available stock (real stock - picked reservation)
            + Quantity on order ("in pipe")
            - Safety stock [blank by default but can be overwritten for a product category or at product level]
            - Safety time [= X (= 0 by default) month x Monthly consumption (validated consumption by default or
                        manually overwritten for a product or at product level)]
            - Expiry quantities.
        '''
        product_obj = self.pool.get('product.product')
        location_obj = self.pool.get('stock.location')
        move_obj = self.pool.get('stock.move')
        
        # Get the available stock
        # Get the real stock
        real_stock = product_obj.get_product_available(cr, uid, [product_id], {'location': location_id, 'compute_child': True,})
        # Get the picked reservation
        ## TODO: To confirm by Magali
        picked_reservation = 0.00
        move_ids = []
        for location in location_obj.search(cr, uid, [('location_id', 'child_of', [location_id])]):
            for move_id in move_obj.search(cr, uid, [('product_id', '=', product_id), ('location_id', '=', location)]):
                move_ids.append(move_id)
            
        for move in move_obj.browse(cr, uid, move_ids):
            picked_reservation += move.product_qty
        
        available_stock = real_stock.get(product_id) - picked_reservation
        
        # Get the quantity on order
        ## TODO : To confirm by Magali
        quantity_on_order = 0.00
        move_ids = []
        for location in location_obj.search(cr, uid, [('location_id', 'child_of', [location_id])]):
            for move_id in move_obj.search(cr, uid, [('product_id', '=', product_id), ('location_dest_id', '=', location)]):
                move_ids.append(move_id)
            
        for move in move_obj.browse(cr, uid, move_ids):
            quantity_on_order += move.product_qty
            
        # Get the safety stock
        safety_stock = d_values.get('safety', 0)
        
        # Get the safety time
        safety_time = d_values.get('safety_time', 0)
        
        # Get the expiry quantity
        expiry_quantity = self.get_expiry_qty(cr, uid, product_id, location_id, monthly_consumption, d_values)
        
        return available_stock + quantity_on_order - safety_stock - (safety_time * monthly_consumption) - expiry_quantity
     
     
    def get_expiry_qty(self, cr, uid, product_id, location_id, monthly_consumption, d_values={}, context={}):
        '''
        Compute the expiry quantities
        '''
        product_obj = self.pool.get('product.product')
        stock_obj = self.pool.get('stock.location')
        batch_obj = self.pool.get('stock.production.lot')
        move_obj = self.pool.get('stock.move')
        
        res = 0.00
        
        location_ids = stock_obj.search(cr, uid, [('location_id', 'child_of', location_id)])
        available_stock = 0.00
        
        # Get all batches for this product
        batch_ids = batch_obj.search(cr, uid, [('product_id', '=', product_id)], offset=0, limit=None, order='life_date')
        if len(batch_ids) == 1:
            # Search all moves with this batch number
            for location in location_ids:
                context.update({'location_id': location})
                available_stock += batch_obj.browse(cr, uid, batch_ids, context=context)[0].stock_available
            expiry_date = batch_obj.browse(cr, uid, batch_ids)[0].life_date or time.strftime('%Y-%m-%d')
            nb_month = self.get_diff_date(expiry_date)
            res = available_stock - (nb_month * monthly_consumption)
        else:
            # Get the stock available for the product
            for location in location_ids:
                context.update({'location_id': location})
                for batch in batch_obj.browse(cr, uid, batch_ids, context=context):
                    available_stock += batch.stock_available
                    
            last_nb_month = 0
            sum_nb_month = 0
            res = 0
            for batch in batch_obj.browse(cr, uid, batch_ids):
                nb_month = self.get_diff_date(batch.life_date)
                if (nb_month - sum_nb_month) > 0:
                    tmp_qty = (nb_month - sum_nb_month) * monthly_consumption 
                    res += available_stock - (last_nb_month * monthly_consumption) - tmp_qty
                else:
                    break 
            
        return res
    
    def get_diff_date(self, date):
        '''
        Returns the number of month between the date in parameter and today
        '''
        date = Parser.DateFromString(date)
        today = today()
        
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