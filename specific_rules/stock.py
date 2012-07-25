# -*- coding: utf-8 -*-
##############################################################################
#
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

class initial_stock_inventory(osv.osv):
    _name = 'initial.stock.inventory'
    _inherit = 'stock.inventory'
    
    _columns = {
        'inventory_line_id': fields.one2many('initial.stock.inventory.line', 'inventory_id', string='Inventory lines'),
    }
    
initial_stock_inventory()


class initial_stock_inventory_line(osv.osv):
    _name = 'initial.stock.inventory.line'
    _inherit = 'stock.inventory.line'
    
    def _get_error_msg(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = ''
            if line.hidden_batch_management_mandatory and not line.prod_lot_id:
                res[line.id] = 'You must define a batch number'
            elif line.hidden_perishable_mandatory and not line.expiry_date:
                res[line.id] = 'You must define an expiry date'
        
        return res
    
    _columns = {
        'inventory_id': fields.many2one('initial.stock.inventory', string='Inventory'),
        'average_cost': fields.float(digits=(16,2), string='Initial average cost', required=True),
        'currency_id': fields.many2one('res.currency', string='Functional currency', readonly=True),
        'err_msg': fields.function(_get_error_msg, method=True, type='char', string='Comment', store=False),
    }
    
    _defaults = {
        'currency_id': lambda obj, cr, uid, c: obj.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id,
        'average_cost': lambda *a: 0.00,
        'product_qty': lambda *a: 0.00,
        'reason_type_id': lambda obj, cr, uid, c: obj.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_discrepancy')[1]
    }
    
    def product_change(self, cr, uid, ids, product_id):
        '''
        Set the UoM with the default UoM of the product
        '''
        value = {'product_uom': False,
                 'hidden_perishable_mandatory': False,
                 'hidden_batch_management_mandatory': False}
        
        if product_id:
            product = self.pool.get('product.product').browse(cr, uid, product_id)
            value.update({'product_uom': product.uom_id.id})
            value.update({'hidden_perishable_mandatory': product.perishable,
                          'hidden_batch_management_mandatory': product.batch_management})
            
        return {'value': value}
        
    def create(self, cr, uid, vals, context=None):
        '''
        Set the UoM with the default UoM of the product
        '''
        if vals.get('product_id', False):
            vals['product_uom'] = self.pool.get('product.product').browse(cr, uid, vals['product_id'], context=context).uom_id.id
        
        return super(initial_stock_inventory_line, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        Set the UoM with the default UoM of the product
        '''
        if vals.get('product_id', False):
            vals['product_uom'] = self.pool.get('product.product').browse(cr, uid, vals['product_id'], context=context).uom_id.id
            
        return super(initial_stock_inventory_line, self).write(cr, uid, ids, vals, context=context)
    
initial_stock_inventory_line()
