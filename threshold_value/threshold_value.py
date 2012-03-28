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

from mx.DateTime import *

class threshold_value(osv.osv):
    _name = 'threshold.value'
    _description = 'Threshold value'
    
    _columns = {
        'name': fields.char(size=128, string='Name', required=True),
        'active': fields.boolean(string='Active'),
        'warehouse_id': fields.many2one('stock.warehouse', string='Warehouse'),
        'location_id': fields.many2one('stock.location', string='Location', required=True),
        'compute_method': fields.selection([('fixed', 'Fixed values'), ('computed', 'Computed values')],
                                           string='Method of computation', required=True,
                                           help="""If 'Fixed values', the scheduler will compare stock of product with the threshold value of the line. \n
                                           If 'Computed values', the threshold value and the ordered quantity will be calculated according to defined parameters"""),
        'consumption_method': fields.selection([('amc', 'Average Monthly Consumption'), ('fmc', 'Forecasted Monthly Consumption')],
                                               string='Consumption Method'),
        'consumption_period_from': fields.date(string='Period of calculation', 
                                             help='This period is a number of past months the system has to consider for AMC calculation.'\
                                             'By default this value is equal to the frequency in the Threshold.'),
        'consumption_period_to': fields.date(string='-'),
        'frequency': fields.float(digits=(16,2), string='Order frequency'),
        'safety_month': fields.float(digits=(16,2), string='Safety Stock in months'),
        'lead_time': fields.float(digits=(16,2), string='Fixed Lead Time in months'),
        'supplier_lt': fields.boolean(string='Product\'s supplier LT'),
        'line_ids': fields.one2many('threshold.value.line', 'threshold_value_id', string="Products"),
        'fixed_line_ids': fields.one2many('threshold.value.line', 'threshold_value_id2', string="Products"),
        'sublist_id': fields.many2one('product.list', string='List/Sublist'),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type'),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group'),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family'),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root'),
    }
    
    _defaults = {
        'name': lambda obj, cr, uid, context=None: obj.pool.get('ir.sequence').get(cr, uid, 'threshold.value') or '',
        'active': lambda *a: True,
        'frequency': lambda *a: 3,
        'consumption_method': lambda *a: 'amc',
        'consumption_period_from': lambda *a: (now() + RelativeDate(day=1, months=-2)).strftime('%Y-%m-%d'),
        'consumption_period_to': lambda *a: (now() + RelativeDate(day=1)).strftime('%Y-%m-%d'),
    }
    
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
    
    def on_change_method(self, cr, uid, ids, method):
        '''
        Unfill the consumption period if the method is FMC
        '''
        res = {}
        
        if method and method == 'fmc':
            res.update({'consumption_period_from': False, 'consumption_period_to': False})
        
        return {'value': res}
    
    def on_change_period(self, cr, uid, ids, from_date, to_date):
        '''
        Check if the from date is younger than the to date
        '''
        warn = {}
        val = {}
        
        if from_date and to_date and from_date > to_date:
            warn = {'title': 'Issue on date',
                    'message': 'The start date must be younger than end date'}
            
        if from_date:
            val.update({'consumption_period_from': (DateFrom(from_date) + RelativeDate(day=1)).strftime('%Y-%m-%d')})
            
        if to_date:
            val.update({'consumption_period_to': (DateFrom(to_date) + RelativeDate(months=1, day=1, days=-1)).strftime('%Y-%m-%d')})
        
        return {'value': val, 'warning': warn}
    
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
        
    def dummy(self, cr, uid, ids, context=None):
        return True

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
    
    def create(self, cr, uid, vals, context=None):
        '''
        Add the second link to the threshold value rule
        '''
        if 'threshold_value_id' in vals:
            vals.update({'threshold_value_id2': vals['threshold_value_id']})
        elif 'threshold_value_id2' in vals:
            vals.update({'threshold_value_id': vals['threshold_value_id2']})
        
        return super(threshold_value_line, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        Add the second link to the threshold value rule
        '''
        if 'threshold_value_id' in vals:
            vals.update({'threshold_value_id2': vals['threshold_value_id']})
        elif 'threshold_value_id2' in vals:
            vals.update({'threshold_value_id': vals['threshold_value_id2']})
        
        return super(threshold_value_line, self).write(cr, uid, ids, vals, context=context)
    
    def _get_values(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Compute and return the threshold value and qty to order
        '''
        res = {}
        if context is None:
            context = {}
        
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {'threshold_value': 0.00, 'product_qty': 0.00}
            
            rule = line.threshold_value_id
            context.update({'location_id': rule.location_id.id, 'compute_child': True})
            product = self.pool.get('product.product').browse(cr, uid, line.product_id.id, context=context)
            res[line.id] = self._get_threshold_value(cr, uid, line.id, product, rule.compute_method, rule.consumption_method, 
                                                     rule.consumption_period_from, rule.consumption_period_to, rule.frequency, 
                                                     rule.safety_month, rule.lead_time, rule.supplier_lt, line.product_uom_id.id, context)
        
        return res
    
    _columns = {
        'product_id': fields.many2one('product.product', string='Product', required=True),
        'product_uom_id': fields.many2one('product.uom', string='Product UoM', required=True),
        'product_qty': fields.function(_get_values, method=True, type='float', string='Quantity to order', multi='values'),
        'threshold_value': fields.function(_get_values, method=True, type='float', string='Threshold value', multi='values'),
        'fixed_product_qty': fields.float(digits=(16,2), string='Quantity to order'),
        'fixed_threshold_value': fields.float(digits=(16,2), string='Threshold value'),
        'threshold_value_id': fields.many2one('threshold.value', string='Threshold', ondelete='cascade', required=True),
        'threshold_value_id2': fields.many2one('threshold.value', string='Threshold', ondelete='cascade', required=True)
    }
    
    def _get_threshold_value(self, cr, uid, line_id, product, compute_method, consumption_method,
                                consumption_period_from, consumption_period_to, frequency,
                                safety_month, lead_time, supplier_lt, uom_id, context=None):
        '''
        Return the threshold value and ordered qty of a product line
        '''
        cons = 0.00
        threshold_value = 0.00
        qty_to_order = 0.00
        if compute_method == 'computed':
            # Get the product available before change the context (from_date and to_date in context)
            product_available = product.qty_available
            
            # Change the context to compute consumption
            c = context.copy()
            c.update({'from_date': consumption_period_from, 'to_date': consumption_period_to})
            product = self.pool.get('product.product').browse(cr, uid, product.id, context=c)
            cons = consumption_method == 'fmc' and product.reviewed_consumption or product.product_amc
            
            # Set lead time according to choices in threshold rule (supplier or manual lead time)
            lt = supplier_lt and float(product.seller_delay)/30.0 or lead_time
                
            # Compute the threshold value
            threshold_value = cons * (lt + safety_month)
            threshold_value = self.pool.get('product.uom')._compute_qty(cr, uid, product.uom_id.id, threshold_value, product.uom_id.id)
                
            # Compute the quantity to re-order
            qty_to_order = cons * (frequency + lt + safety_month)\
                            - product_available - product.incoming_qty + product.outgoing_qty 
            qty_to_order = self.pool.get('product.uom')._compute_qty(cr, uid, uom_id or product.uom_id.id, \
                                                                     qty_to_order, product.uom_id.id)
            qty_to_order = qty_to_order > 0.00 and qty_to_order or 0.00
        elif line_id:
            line = self.browse(cr, uid, line_id, context=context)
            threshold_value = line.fixed_threshold_value
            qty_to_order = line.fixed_product_qty
            
        return {'threshold_value': threshold_value, 'product_qty': qty_to_order}

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
