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
        
        cylce_ids = cycle_obj.search(cr, uid, [('next_date', '=', datetime.today().strftime('%Y-%m-%d')), ('prodcut_id', '=', False)])
        
        created_proc = []
        report = []
        report_except = 0
        
        start_date = datetime.now()
        
        # We start with only category Automatic Supply
        for cycle in cycle_obj.browse(cr, uid, cycle_ids):
            # We define the replenish location
            location_id = False
            if not auto_sup.location_id or not auto_sup.location_id.id:
                location_id = auto_sup.warehouse_id.lot_input_id.id
            else:
                location_id = auto_sup.location_id.id
                
            d_values = {'leadtime': cycle.leadtime,
                        'coverage': cycle.order_coverage,
                        'safety_time': cycle.safety_stock_time,
                        'safety': cycle.safety_stock,}
            
            product_ids = product_obj.search(cr, uid, [('categ_id', '=', cycle.categ_id.id), ('id', 'not in', cycle.product_ids)])
            
            for product in product_obj.browse(cr, uid, product_ids):
                proc_id = self.create_proc_cycle(cr, uid, product.id, location_id, d_values)
                
                if proc_id:
                    created_proc.append(proc_id)
        
        # Next, for one product automatic supply
        cycle_ids = cycle_obj.search(cr, uid, [('next_date', '=', datetime.today().strftime('%Y-%m-%d')), ('product_id', '!=', False)])
        for cycle in cycle_obj.browse(cr, uid, cycle_ids):
            # We define the replenish location
            location_id = False
            if not auto_sup.location_id or not auto_sup.location_id.id:
                location_id = auto_sup.warehouse_id.lot_input_id.id
            else:
                location_id = auto_sup.location_id.id
                
            d_values = {'leadtime': cycle.leadtime,
                        'coverage': cycle.order_coverage,
                        'safety_time': cycle.safety_stock_time,
                        'safety': cycle.safety_stock,}
            
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
        
        if isintance(product_id, (int, long)):
            product_id = [product_id]
        
        product = product_obj.browse(cr, uid, product_id[0])
        
        # Enter the stock location in cache to know which products has been already replenish for this location
        if not cache.get(location_id, False):
            cache.update({location_id: []})
        
        # If a rule already exist for the category of the product or for the product
        # itself for the same location, we don't create a procurement order 
        cycle_ids = cycle_obj.search(cr, uid, [('category_id', '=', product.categ_id.id), ('location_id', '=', location_id)])
        cycle2_id = cycle_obj.search(cr, uid, [('product_id', '=', product.id), ('location_id', '=', location_id)])
        if cycle_ids or cycle2_ids:
            return False
        
        newdate = datetime.today()
        quantity_to_order = self._compute_quantity(cr, uid, product.id, location_id, d_values)
            
        if product_id.id not in cache.get(location_id):
            newdate = datetime.today()
            proc_id = proc_obj.create(cr, uid, {
                                        'name': _('Automatic Supply: %s') % (auto_sup.name,),
                                        'origin': auto_sup.name,
                                        'date_planned': newdate.strftime('%Y-%m-%d %H:%M:%S'),
                                        'product_id': product_id.id,
                                        'product_qty': qty,
                                        'product_uom': product_uom,
                                        'location_id': location_id,
                                        'procure_method': 'make_to_order',
                })
            wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_confirm', cr)
            wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_check', cr)
            auto_sup_obj.write(cr, uid, [auto_sup.id], {'procurement_id': proc_id}, context=context)
            
            # Fill the cache
            cache.get(location_id).append(product_id.id)
        
        return proc_id
    
    def _compute_quantity(self, cr, uid, product_id, location_id, d_values={}):
        '''
        Compute the quantity of product to order
        '''
        product_obj = self.pool.get('product.product')
        
        if isintance(product_id, (int, long)):
            product_id = [product_id]
            
        res = 0.0
        
        leadtime = d_values.get('leadtime', self._get_leadtime(cr, uid, product_id[0]))
        order_coverage = d_values.get('coverage', 3)
        # TODO: Monthly consumption will be develop in a future iteration (for the moment, product_consumption module is used)
        consumption = product_obj.browse(cr, uid, product_id[0]).monthly_consumption
        
        projected_available_qty = self._compute_available_qty(cr, uid, product_id, location_id, d_values)
                
        return res
    
    def _get_leadtime(self, cr, uid, product_id):
        '''
        Returns the leadtime of the main supplier for the product
        '''
        product_obj = self.pool.get('product.product')
        sup_info_obj = self.pool.get('product.supplierinfo')
        
        if isintance(product_id, (int, long)):
            product_id = [product_id]
        
        product = product_obj.browse(cr, uid, product_id[0])
        sup_info = sup_info_obj.search(cr, uid, [('product_id', '=', product_id[0])], 0, 'sequence asc', limit=1)
        
        return len(supinfo) > 0 and sup_info_obj.browse(cr, uid, sup_info[0]).leadtime or False
    
    def _compute_available_qty(self, cr, uid, product_id, location_id, d_values={}):
        '''
        Compute the available qty of the product according to time in d_values
        '''
        
        
procurement_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: