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

class stock_warehouse_automatic_supply(osv.osv):
    _name = 'stock.warehouse.automatic.supply'
    _description = 'Automatic Supply'
    _order = 'sequence, id'
    
    def _get_next_date_from_frequence(self, cr, uid, ids, name, args, context={}):
        '''
        Returns the next date of the frequency
        '''
        res = {}
        
        for proc in self.browse(cr, uid, ids):
            if proc.frequence_id and proc.frequence_id.next_date:
                res[proc.id] = proc.frequence_id.next_date
            else:
                res[proc.id] = False
                
        return res
    
    def _get_frequence_change(self, cr, uid, ids, context={}):
        '''
        Returns Auto. Sup. ids when frequence change
        '''
        result = {}
        for frequence in self.pool.get('stock.frequence').browse(cr, uid, ids, context=context):
            for sup_id in frequence.auto_sup_ids:
                result[sup_id.id] = True
                
        return result.keys()
    
    def _get_frequence_name(self, cr, uid, ids, field_name, arg, context={}):
        '''
        Returns the name_get value of the frequence
        '''
        res = {}
        for proc in self.browse(cr, uid, ids):
            res[proc.id] = self.pool.get('stock.frequence').name_get(cr, uid, [proc.frequence_id.id])[0][1]
            
        return res
    
    _columns = {
        'sequence': fields.integer(string='Order', required=True, help='A higher order value means a low priority'),
        'name': fields.char(size=64, string='Name', required=True),
        'category_id': fields.many2one('product.category', string='Category'),
        'product_id': fields.many2one('product.product', string='Specific product'),
        'product_uom_id': fields.many2one('product.uom', string='Product UoM'),
        'product_qty': fields.float(digits=(16,2), string='Qty'),
        'warehouse_id': fields.many2one('stock.warehouse', string='Warehouse', required=True),
        'location_id': fields.many2one('stock.location', string='Location'),
        'frequence_name': fields.function(_get_frequence_name, method=True, string='Frequence', type='char'),
        'frequence_id': fields.many2one('stock.frequence', string='Frequence'),
        'line_ids': fields.one2many('stock.warehouse.automatic.supply.line', 'supply_id', string="Products"),
        'company_id': fields.many2one('res.company','Company',required=True),
        'active': fields.boolean('Active', help="If the active field is set to False, it will allow you to hide the automatic supply without removing it."),
        'procurement_id': fields.many2one('procurement.order', string='Last procurement', readonly=True),
        'next_date': fields.function(_get_next_date_from_frequence, method=True, string='Next scheduled date', type='date', 
                                     store={'stock.warehouse.automatic.supply': (lambda self, cr, uid, ids, c={}: ids, ['frequence_id'],20),
                                            'stock.frequence': (_get_frequence_change, None, 20)}),
    }
    
    _defaults = {
        'sequence': lambda *a: 10,
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
    
    def onchange_product_id(self, cr, uid, ids, product_id, context=None):
        """ Finds uom for changed product.
        @param product_id: Changed id of product.
        @return: Dictionary of values.
        """
        if product_id:
            w = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            v = {'product_uom_id': w.uom_id.id}
            return {'value': v}
        return {}
   
    def unlink(self, cr, uid, ids, context):
        if isinstance(ids, (int, long)):
            ids = [ids]
        freq_ids = []
        for auto in self.read(cr, uid, ids, ['frequence_id']):
            if auto['frequence_id']:
                freq_ids.append(auto['frequence_id'][0])
        if freq_ids:
            self.pool.get('stock.frequence').unlink(cr, uid, freq_ids, context)
        return super(stock_warehouse_automatic_supply, self).unlink(cr, uid, ids, context=context)

    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        obj = self.read(cr, uid, id, ['frequence_id'])
        if obj['frequence_id']:
            default['frequence_id'] = self.pool.get('stock.frequence').copy(cr, uid, obj['frequence_id'][0], context=context)
        default.update({
            'name': self.pool.get('ir.sequence').get(cr, uid, 'stock.automatic.supply') or '',
            'procurement_id': False,
        })
        return super(stock_warehouse_automatic_supply, self).copy(cr, uid, id, default, context=context)
 
    def _check_frequency(self, cr, uid, ids, context={}):
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        if context.get('button') == 'choose_change_frequence':
            return True

        for auto in self.read(cr, uid, ids, ['frequence_id']):
            if not auto['frequence_id']:
                raise osv.except_osv(_('Error !'), _('Frequence is mandatory, please add one by clicking on the "Change/Choose Frequency" button.'))
        return True

    def create(self, cr, uid, vals, context={}):
        id = super(stock_warehouse_automatic_supply, self).create(cr, uid, vals, context=context)
        self._check_frequency(cr, uid, [id], context)
        return id

    def write(self, cr, uid, ids, vals, context={}):
        ret = super(stock_warehouse_automatic_supply, self).write(cr, uid, ids, vals, context=context)
        self._check_frequency(cr, uid, ids, context)
        return ret

stock_warehouse_automatic_supply()

class stock_warehouse_automatic_supply_line(osv.osv):
    _name = 'stock.warehouse.automatic.supply.line'
    _description = 'Automatic Supply Line'
    _rec_name = 'product_id'
    
    _columns = {
        'product_id': fields.many2one('product.product', string='Product', required=True),
        'product_uom_id': fields.many2one('product.uom', string='Product UoM', required=True),
        'product_qty': fields.float(digit=(16,2), string='Quantity to order', required=True),
        'supply_id': fields.many2one('stock.warehouse.automatic.supply', string='Supply', ondelete='cascade')
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
    
stock_warehouse_automatic_supply_line()

class stock_frequence(osv.osv):
    _name = 'stock.frequence'
    _inherit = 'stock.frequence'
    
    _columns = {
        'auto_sup_ids': fields.one2many('stock.warehouse.automatic.supply', 'frequence_id', string='Auto. Sup.'),
    }
    
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
    
    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default['auto_sup_ids'] = False
        return super(stock_frequence, self).copy(cr, uid, id, default, context)

stock_frequence()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
