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
    _order = 'sequence, id'

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
            for proc in self.browse(cr, uid, ids):
                if not proc.frequence_id:
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
        'sequence': fields.integer(string='Order', required=True, help='A higher order value means a low priority'),
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
        'leadtime': fields.float(digits=(16,2), string='Delivery lead time to consider', help='Delivery lead time in month'),
        'order_coverage': fields.float(digits=(16,2), string='Order coverage'),
        'safety_stock_time': fields.float(digits=(16,2), string='Safety stock in time'),
        'safety_stock': fields.integer(string='Safety stock (quantity'),
        'past_consumption': fields.boolean(string='Average monthly consumption'),
        'reviewed_consumption': fields.boolean(string='Forecasted monthly consumption'),
        'manual_consumption': fields.float(digits=(16,2), string='Manual monthly consumption'),
        'next_date': fields.related('frequence_id', 'next_date', string='Next scheduled date', readonly=True, type='date',
                                    store={'stock.warehouse.order.cycle': (lambda self, cr, uid, ids, context={}: ids, ['frequence_id'], 20),
                                           'stock.frequence': (_get_frequence_change, None, 20)}),
        'sublist_id': fields.many2one('product.list', string='List/Sublist'),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type'),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group'),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family'),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root'),
    }
    
    _defaults = {
        'sequence': lambda *a: 10,
        'past_consumption': lambda *a: 1,
        'active': lambda *a: 1,
        'name': lambda x,y,z,c: x.pool.get('ir.sequence').get(y,z,'stock.order.cycle') or '',
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'stock.warehouse.order.cycle', context=c),
        'order_coverage': lambda *a: 3,
    }
    

    def onChangeSearchNomenclature(self, cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, context=None):
        return self.pool.get('product.product').onChangeSearchNomenclature(cr, uid, 0, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, False, context={'withnum': 1})

    def fill_lines(self, cr, uid, ids, context={}):
        '''
        Fill all lines according to defined nomenclature level and sublist
        '''
        self.write(cr, uid, ids, {'created_ok': True})    
        for report in self.browse(cr, uid, ids, context=context):
            product_ids = []
            products = []

            nom = False
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
                    self.pool.get('stock.warehouse.automatic.supply.line').unlink(cr, uid, line.id, context=context)

            for product in self.pool.get('product.product').browse(cr, uid, product_ids, context=context):
                # Check if the product is not already on the report
                if product.id not in products:
                    batch_mandatory = product.batch_management or product.perishable
                    date_mandatory = not product.batch_management and product.perishable
                    self.pool.get('product.product').create(cr, uid, {'product_id': product.id,
                                                                                    'uom_id': product.uom_id.id,
                                                                                    'consumed_qty': 0.00,
                                                                                    'batch_mandatory': batch_mandatory,
                                                                                    'date_mandatory': date_mandatory,
                                                                                    'rac_id': report.id})
        
        self.write(cr, uid, ids, {'created_ok': False})    
        return {'type': 'ir.actions.act_window',
                'res_model': 'product.product',
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': ids[0],
                'target': 'dummy',
                'context': context}

    def get_nomen(self, cr, uid, id, field):
        return self.pool.get('product.nomenclature').get_nomen(cr, uid, self, id, field, context={'withnum': 1})

    def consumption_method_change(self, cr, uid, ids, past_consumption, reviewed_consumption, manual_consumption, product_id, field='past'):
        '''
        Uncheck a box when the other is checked
        '''
        v = {}
        if field == 'past' and past_consumption:
            v.update({'reviewed_consumption': 0, 'manual_consumption': 0.00})
        elif field == 'past' and not past_consumption:
            v.update({'reviewed_consumption': 1, 'manual_consumption': 0.00})
        elif field == 'review' and reviewed_consumption:
            v.update({'past_consumption': 0, 'manual_consumption': 0.00})
        elif field == 'review' and not reviewed_consumption:
            v.update({'past_consumption': 1, 'manual_consumption': 0.00})
        elif field == 'manual' and manual_consumption != 0.00 and product_id:
            v.update({'reviewed_consumption': 0, 'past_consumption': 0})
        elif field == 'manual' and (manual_consumption == 0.00 or not product_id):
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
    
    def unlink(self, cr, uid, ids, context):
        if isinstance(ids, (int, long)):
            ids = [ids]
        freq_ids = []
        for auto in self.read(cr, uid, ids, ['frequence_id']):
            if auto['frequence_id']:
                freq_ids.append(auto['frequence_id'][0])
        if freq_ids:
            self.pool.get('stock.frequence').unlink(cr, uid, freq_ids, context)
        return super(stock_warehouse_order_cycle, self).unlink(cr, uid, ids, context=context)
    
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
