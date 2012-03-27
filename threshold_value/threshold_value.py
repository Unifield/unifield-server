#!/usr/bin/env python
# -*- encoding: utf-8 -*-
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


class threshold_value(osv.osv):
    _name = 'threshold.value'
    _description = 'Threshold value'
    
    _columns = {
        'name': fields.char(size=128, string='Name', required=True),
        'active': fields.boolean(string='Active'),
        'category_id': fields.many2one('product.category', string='Category'),
        'product_id': fields.many2one('product.product', string='Product'),
        'uom_id': fields.many2one('product.uom', string='UoM'),
        'warehouse_id': fields.many2one('stock.warehouse', string='Warehouse'),
        'location_id': fields.many2one('stock.location', string='Location', required=True),
        'threshold_value': fields.float(digits=(16,2), string='Threshold Value (in UoM)', required=True),
        'threshold_manual_ok': fields.boolean(string='Manual threshold value'),
        'qty_to_order': fields.float(digits=(16,2), string='Quantity to Order (in UoM)', required=True),
        'qty_order_manual_ok': fields.boolean(string='Manual quantity to order'),
        'frequency': fields.float(digits=(16,2), string='Order frequency'),
        'safety_month': fields.float(digits=(16,2), string='Safety Stock in months'),
        'lead_time': fields.float(digits=(16,2), string='Fixed Lead Time in months'),
        'supplier_lt': fields.boolean(string='Product\'s supplier LT'),
    }
    
    _defaults = {
        'name': lambda obj, cr, uid, context=None: obj.pool.get('ir.sequence').get(cr, uid, 'threshold.value') or '',
        'active': lambda *a: True,
        'threshold_manual_ok': lambda *a: False,
        'qty_order_manual_ok': lambda *a: False,
    }
    
    def compute_threshold_qty_order(self, cr, uid, ids, category_id, product_id, location_id, frequency, lead_time, supplier_lt, safety_month, threshold_manual_ok, qty_order_manual_ok, context=None):
        '''
        Computes the threshold value and quantity to order according to parameters
        
        Threshold value = fixed manually or AMC * (LT + SS)
        Order quantity = fixed manually or AMC * (OF + LT + SS) - Real Stock - Back orders
        
        IMPORTANT :
        ###########
        If the threshold value is defined for an entire product category, the calculation of computed values
        couldn't be displayed on form but they will be used on scheduler
        
        Explanations :
        ##############
            * AMC : Average Monthly Consumption (expressed in standard unit of distribution) (see consumption_calcution 
        module for more explanations).
            * OF : Order frequency (expressed in months)
            * LT : Lead Time (expressed in months)
            * SS : Security Stock (expressed in months)
            * Real Stock : inventory (expressed in standard unit of distribution)
            * Back orders : product quantities ordered but not yet delivered (expressed in standard unit of distribution)
        '''
        v = {}
        m = {}
        if context is None:
            context = {}
        if location_id:
            context.update({'location_id': location_id})
        
        if product_id:
            product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            amc = self.pool.get('product.product').compute_amc(cr, uid, product_id, context=context)
            
            # The supplier lead time is priority if the checkbox was checked
            if supplier_lt:
                lead_time = product.seller_id.delay and product.seller_id.delay != 'N/A' and float(product.seller_id.delay) or lead_time
            
            # If the user hasn't fill manually the threshold value, compute them
            if not threshold_manual_ok:                
                threshold_value = amc * (lead_time + safety_month)
                threshold_value = self.pool.get('product.uom')._compute_qty(cr, uid, product.uom_id.id, threshold_value, product.uom_id.id)
            
                v.update({'threshold_value': threshold_value})
            
            # If the user hasn't fill manually the qty to order value, compute them
            if not qty_order_manual_ok:
                qty_order = amc * (lead_time + safety_month + frequency) - product.real_available + product.incoming_qty - product.outgoing_qty
                qty_order = self.pool.get('product.uom')._compute_qty(cr, uid, product.uom_id.id, qty_order, product.uom_id.id)
                
                v.update({'qty_to_order': qty_order})
        
        # Reset all values if no product
        if not product_id:
            v.update({'threshold_value': 0.00,
                      'qty_to_order': 0.00})
            
        
        return {'value': v,}
    
    def product_on_change(self, cr, uid, ids, product_id=False, context=None):
        '''
        Update the UoM when the product change
        
        If no product, remove the UoM value
        '''
        v = {}
        
        if not product_id:
            v.update({'uom_id': False})
        else:
            uom_id = self.pool.get('product.product').browse(cr, uid, product_id, context=context).uom_id.id
            v.update({'uom_id': uom_id,
                      'thresold_value': 0.00,
                      'qty_to_order': 0.00,
                      'lead_time': 0.00,
                      'safety_month': 0.00,
                      'frequency': 0.00})
            
        return {'value': v}
    
    def category_on_change(self, cr, uid, ids, category_id=False, context=None):
        '''
        If a category is selected, remove values for product and uom on the form
        '''
        v = m = {}
        
        if category_id:
            v.update({'product_id': False,
                      'uom_id': False})
            # If the threshold form is for an entire product category, display an explanation message
            m = {'title': 'Warning',
                 'message': '''If you define a threshold rule for an entire category, the values for threshold and order quantities
will can\'t be displayed on this form for each product of the category, but it will be used when the scheduler will compute reorder products !'''}
            
        return {'value': v, 'warning': m}
    
    def onchange_warehouse_id(self, cr, uid, ids, warehouse_id, context=None):
        """ Finds default stock location id for changed warehouse.
        @param warehouse_id: Changed id of warehouse.
        @return: Dictionary of values.
        """
        if warehouse_id:
            w = self.pool.get('stock.warehouse').browse(cr, uid, warehouse_id, context=context)
            v = {'location_id': w.lot_stock_id.id}
            return {'value': v}
        return {}
    
threshold_value()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

