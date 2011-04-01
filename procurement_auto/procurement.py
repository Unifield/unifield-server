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

import time
from tools.translate import _

class stock_frequence(osv.osv):
    _name = 'stock.frequence'
    _inherit = 'stock.frequence'
    
    _columns = {
#        'automatic_ids': fields.one2many('stock.warehouse.automatic.supply', 'frequence_id', string='Automatic Supplies'),
    }
    
    def name_get(self, cr, uid, ids, context={}):
        '''
        Returns a description of the frequence
        '''
        res = super(stock_frequence, self).name_get(cr, uid, ids, context=context)
        
        # TODO: Modif of name_get method to return a comprehensive name for frequence
#        res = []
#        
#        for freq in self.browse(cr, uid, ids):
#            title = 'tot'
#            res.append((freq.id, title))
        
        return res
    
    def choose_frequency(self, cr, uid, ids, context={}):
        '''
        Adds the support of automatic supply on choose frequency method
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        if not context.get('res_ok', False) and 'active_id' in context and 'active_model' in context and \
            context.get('active_model') == 'stock.warehouse.automatic.supply':
            self.pool.get('stock.warehouse.automatic.supply').write(cr, uid, [context.get('active_id')], {'frequence_id': ids[0]})
            
        return super(stock_frequence, self).choose_frequency(cr, uid, ids, context=context)
    
stock_frequence()

class stock_warehouse_automatic_supply(osv.osv):
    _name = 'stock.warehouse.automatic.supply'
    _description = 'Automatic Supply'
    
    _columns = {
        'name': fields.char(size=64, string='Name', required=True),
        'category_id': fields.many2one('product.category', string='Category'),
        'product_id': fields.many2one('product.product', string='Specific product'),
        'warehouse_id': fields.many2one('stock.warehouse', string='Warehouse', required=True),
        'location_id': fields.many2one('stock.location', string='Location'),
        'frequence_id': fields.many2one('stock.frequence', string='Frequence'),
        'next_date': fields.related('frequence_id', 'next_date', string='Next scheduled date', readonly=True, type='date'),
        'line_ids': fields.one2many('stock.warehouse.automatic.supply.line', 'supply_id', string="Products"),
        'company_id': fields.many2one('res.company','Company',required=True),
        'active': fields.boolean('Active', help="If the active field is set to False, it will allow you to hide the automatic supply without removing it."),
    }
    
    _defaults = {
        'active': lambda *a: 1,
        'name': lambda x,y,z,c: x.pool.get('ir.sequence').get(y,z,'stock.automatic.supply') or '',
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'stock.warehouse.automatic.supply', context=c)
    }
    
    def choose_change_frequence(self, cr, uid, ids, context={}):
        '''
        Open a wizard to define a frequency for the automatic supply
        or open a wizard to modify the frequency if frequency already exists
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        frequence_id = False
        res_id = False
        res_ok = False
            
        for proc in self.browse(cr, uid, ids):
            res_id = proc.id
            if proc.frequence_id and proc.frequence_id.id:
                frequence_id = proc.frequence_id.id
                res_ok = True
            
        context.update({'active_id': res_id, 
                        'active_model': 'stock.warehouse.automatic.supply',
                        'res_ok': res_ok})
            
        return {'type': 'ir.actions.act_window',
                'target': 'new',
                'res_model': 'stock.frequence',
                'view_type': 'form',
                'view_model': 'form',
                'context': context,
                'res_id': frequence_id}
    
    def onchange_warehouse_id(self, cr, uid, ids, warehouse_id, context=None):
        """ Finds location id for changed warehouse.
        @param warehouse_id: Changed id of warehouse.
        @return: Dictionary of values.
        """
        if warehouse_id:
            w = self.pool.get('stock.warehouse').browse(cr, uid, warehouse_id, context=context)
            v = {'location_id': w.lot_stock_id.id}
            return {'value': v}
        return {}
    
    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({
            'name': self.pool.get('ir.sequence').get(cr, uid, 'stock.automatic.supply') or '',
        })
        return super(stock_warehouse_automatic_supply, self).copy(cr, uid, id, default, context=context)
    
stock_warehouse_automatic_supply()

class stock_warehouse_automatic_supply_line(osv.osv):
    _name = 'stock.warehouse.automatic.supply.line'
    _description = 'Automatic Supply Line'
    _rec_name = 'product_id'
    
    _columns = {
        'product_id': fields.many2one('product.product', string='Product', required=True),
        'product_uom_id': fields.many2one('product.uom', string='Product UoM', required=True),
        'product_qty': fields.float(digit=(16,2), string='Quantity to order', required=True),
        'supply_id': fields.many2one('stock.warehouse.automatic.supply', string='Supply')
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
            v = {'product_uom': prod.uom_id.id}
            return {'value': v}
        return {}
    
stock_warehouse_automatic_supply_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: