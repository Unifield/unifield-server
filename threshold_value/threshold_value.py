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
        'line_ids': fields.one2many('threshold.value.line', 'threshold_value_id', string="Products"),
        'sublist_id': fields.many2one('product.list', string='List/Sublist'),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type'),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group'),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family'),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root'),
    }
    
    _defaults = {
        'name': lambda obj, cr, uid, context={}: obj.pool.get('ir.sequence').get(cr, uid, 'threshold.value') or '',
        'active': lambda *a: True,
        'threshold_manual_ok': lambda *a: False,
        'qty_order_manual_ok': lambda *a: False,
        'threshold_value':0,
        'qty_to_order':0,
    }
    
    def compute_threshold_qty_order(self, cr, uid, ids, category_id, product_id, location_id, frequency, lead_time, supplier_lt, safety_month, threshold_manual_ok, qty_order_manual_ok, context={}):
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
    
    def product_on_change(self, cr, uid, ids, product_id=False, context={}):
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
    
    def category_on_change(self, cr, uid, ids, category_id=False, context={}):
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
##############################################################################################################################
# The code below aims to enable filtering products regarding their sublist or their nomenclature.
# Then, we fill lines of the one2many object 'threshold.value.line' according to the filtered products
##############################################################################################################################
    def onChangeSearchNomenclature(self, cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, context=None):
        return self.pool.get('product.product').onChangeSearchNomenclature(cr, uid, 0, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, False, context={'withnum': 1})

    def fill_lines(self, cr, uid, ids, context=None):
        '''
        Fill all lines according to defined nomenclature level and sublist
        '''
        if context is None:
            context = {}
        for report in self.browse(cr, uid, ids, context=context):
            product_ids = []
            products = []
            nom = False
            field = False
            # Get all products for the defined nomenclature
            if report.nomen_manda_3:
                nom = report.nomen_manda_3.id
                field = 'nomen_manda_3'
            elif report.nomen_manda_2:
                nom = report.nomen_manda_2.id
                field = 'nomen_manda_2'
            elif report.nomen_manda_1:
                nom = report.nomen_manda_1.id
                field = 'nomen_manda_1'
            elif report.nomen_manda_0:
                nom = report.nomen_manda_0.id
                field = 'nomen_manda_0'
            if nom:
                product_ids.extend(self.pool.get('product.product').search(cr, uid, [(field, '=', nom)], context=context))

            # Get all products for the defined list
            if report.sublist_id:
                for line in report.sublist_id.product_ids:
                    product_ids.append(line.name.id)

            # Check if products in already existing lines are in domain
            products = []
            for line in report.line_ids:
                if line.product_id.id in product_ids:
                    products.append(line.product_id.id)
                else:
                    self.pool.get('threshold.value.line').unlink(cr, uid, line.id, context=context)

            for product in self.pool.get('product.product').browse(cr, uid, product_ids, context=context):
                # Check if the product is not already on the report
                if product.id not in products:
                    self.pool.get('threshold.value.line').create(cr, uid, {'product_id': product.id,
                                                                                            'product_uom_id': product.uom_id.id,
                                                                                            'product_qty': 1.00,
                                                                                            'threshold_value_id': report.id})
        return {'type': 'ir.actions.act_window',
                'res_model': 'threshold.value',
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': ids[0],
                'target': 'dummy',
                'context': context}

    def get_nomen(self, cr, uid, id, field):
        return self.pool.get('product.nomenclature').get_nomen(cr, uid, self, id, field, context={'withnum': 1})

    def write(self, cr, uid, ids, vals, context=None):
        if vals.get('sublist_id',False):
            vals.update({'nomen_manda_0':False,'nomen_manda_1':False,'nomen_manda_2':False,'nomen_manda_3':False})
        if vals.get('nomen_manda_0',False):
            vals.update({'sublist_id':False})
        ret = super(threshold_value, self).write(cr, uid, ids, vals, context=context)
        return ret

threshold_value()

class threshold_value_line(osv.osv):
    _name = 'threshold.value.line'
    _description = 'Threshold Value Line'
    _rec_name = 'product_id'
    
    _columns = {
        'product_id': fields.many2one('product.product', string='Product', required=True),
        'product_uom_id': fields.many2one('product.uom', string='Product UoM', required=True),
        'product_qty': fields.float(digit=(16,2), string='Quantity to order', required=True),
        'threshold_value_id': fields.many2one('threshold.value', string='Threshold', ondelete='cascade', required=True)
    }
    
    _defaults = {
        'product_qty': lambda *a: 1.00,
    }
    
    _sql_constraints = [
        ('product_qty_check', 'CHECK( product_qty > 0 )', 'Product Qty must be greater than zero.'),
    ]
    
    def onchange_product_id(self, cr, uid, ids, product_id, context=None):
        """ Finds UoM for changed product.
        @param product_id: Changed id of product.
        @return: Dictionary of values.
        """
        if product_id:
            prod = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            v = {'product_uom_id': prod.uom_id.id}
            return {'value': v}
        return {}
    
threshold_value_line()