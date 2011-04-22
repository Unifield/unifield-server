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

class stock_warehouse_order_cycle(osv.osv):
    _name = 'stock.warehouse.order.cycle'
    _description = 'Order Cycle'
    
    def create(self, cr, uid, data, context={}):
        '''
        Checks if a frequence was choosen for the cycle
        '''
        if not 'button' in context and (not 'frequence_id' in data or not data.get('frequence_id', False)):
            raise osv.except_osv(_('Error'), _('You should choose a frequence for this rule !'))
        
        return super(stock_warehouse_order_cycle, self).create(cr, uid, data, context=context)
        
    def write(self, cr, uid, ids, data, context={}):
        '''
        Checks if a frequence was choosen for the cycle
        '''
        if not 'button' in context and (not 'frequence_id' in data or not data.get('frequence_id', False)):
            raise osv.except_osv(_('Error'), _('You should choose a frequence for this rule !')) 
        
        return super(stock_warehouse_order_cycle, self).write(cr, uid, ids, data, context=context)
        
    
    def _get_frequence_change(self, cr, uid, ids, context={}):
        '''
        Returns ids when the frequence change
        '''
        res = {}
        for frequence in self.pool.get('stock.frequence').browse(cr, uid, ids, context=context):
            for cycle in frequence.order_cycle_ids:
                res[cycle.id] = True
        
        return res.keys()
    
    def _get_frequence_name(self, cr, uid, ids, field_name, arg, context={}):
        '''
        Returns the name_get value of the frequence
        '''
        res = {}
        for proc in self.browse(cr, uid, ids):
            res[proc.id] = self.pool.get('stock.frequence').name_get(cr, uid, [proc.frequence_id.id])[0][1]
            
        return res
    
    _columns = {
        'name': fields.char(size=64, string='Name', required=True),
        'category_id': fields.many2one('product.category', string='Category'),
        'product_id': fields.many2one('product.product', string='Specific product'),
        'warehouse_id': fields.many2one('stock.warehouse', string='Warehouse', required=True),
        'location_id': fields.many2one('stock.location', string='Location'),
        'frequence_name': fields.function(_get_frequence_name, method=True, string='Frequence', type='char'),
        'frequence_id': fields.many2one('stock.frequence', string='Frequence'),
        'product_ids': fields.many2many('product.product', 'order_cycle_product_rel', 'order_cycle_id', 'product_id', string="Products"),
        'company_id': fields.many2one('res.company','Company',required=True),
        'active': fields.boolean('Active', help="If the active field is set to False, it will allow you to hide the automatic supply without removing it."),
        # Parameters for quantity calculation
        'leadtime': fields.integer(string='Delivery lead time to consider'),
        'order_coverage': fields.integer(string='Order coverage'),
        'safety_stock_time': fields.integer(string='Safety stock in time'),
        'safety_stock': fields.integer(string='Safety stock (quantity'),
        'past_consumption': fields.boolean(string='Past monthly consumption'),
        'reviewed_consumption': fields.boolean(string='Reviewed monthly consumption'),
        'manual_consumption': fields.float(digits=(16,2), string='Manual monthly consumption'),
        'next_date': fields.related('frequence_id', 'next_date', string='Next scheduled date', readonly=True, type='date',
                                    store={'stock.warehouse.order.cycle': (lambda self, cr, uid, ids, context={}: ids, ['frequence_id'], 20),
                                           'stock.frequence': (_get_frequence_change, None, 20)}),
    }
    
    _defaults = {
        'past_consumption': lambda *a: 1,
        'active': lambda *a: 1,
        'name': lambda x,y,z,c: x.pool.get('ir.sequence').get(y,z,'stock.order.cycle') or '',
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'stock.warehouse.order.cycle', context=c),
        'order_coverage': lambda *a: 3,
    }
    
    def consumption_method_change(self, cr, uid, ids, past_consumption, reviewed_consumption, field='past'):
        '''
        Uncheck a box when the other is checked
        '''
        v = {}
        if field == 'past' and past_consumption:
            v.update({'reviewed_consumption': 0})
        elif field == 'past' and not past_consumption:
            v.update({'reviewed_consumption': 1})
        elif field == 'review' and reviewed_consumption:
            v.update({'past_consumption': 0})
        elif field == 'review' and not reviewed_consumption:
            v.update({'past_consumption': 1})
            
        return {'value': v}
    
    def choose_change_frequence(self, cr, uid, ids, context={}):
        '''
        Open a wizard to define a frequency for the order cycle
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
                        'active_model': 'stock.warehouse.order.cycle',
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
        obj = self.read(cr, uid, id, ['frequence_id'])
        if obj['frequence_id']:
            default['frequence_id'] = self.pool.get('stock.frequence').copy(cr, uid, obj['frequence_id'][0], context=context)

        default.update({
            'name': self.pool.get('ir.sequence').get(cr, uid, 'stock.order.cycle') or '',
        })
        return super(stock_warehouse_order_cycle, self).copy(cr, uid, id, default, context=context)
    
stock_warehouse_order_cycle()

class stock_frequence(osv.osv):
    _name = 'stock.frequence'
    _inherit = 'stock.frequence'
    
    _columns = {
        'order_cycle_ids': fields.one2many('stock.warehouse.order.cycle', 'frequence_id', string='Order Cycle'),
    }

    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default['order_cycle_ids'] = False
        return super(stock_frequence, self).copy(cr, uid, id, default, context)

    def choose_frequency(self, cr, uid, ids, context={}):
        '''
        Adds the support of order cycles on choose frequency method
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        if not context.get('res_ok', False) and 'active_id' in context and 'active_model' in context and \
            context.get('active_model') == 'stock.warehouse.order.cycle':
            self.pool.get('stock.warehouse.order.cycle').write(cr, uid, [context.get('active_id')], {'frequence_id': ids[0]})
            
        return super(stock_frequence, self).choose_frequency(cr, uid, ids, context=context)
    
stock_frequence()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
