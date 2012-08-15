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

from tools.translate import _

import time

class initial_stock_inventory(osv.osv):
    _name = 'initial.stock.inventory'
    _inherit = 'stock.inventory'
    
    def unlink(self, cr, uid, ids, context=None):
        '''
        Prevent the deletion of a non-draft/cancel initial inventory
        '''
        for inv in self.browse(cr, uid, ids, context=context):
            if inv.state == 'done':
                raise osv.except_osv(_('Error'), _('You cannot remove an initial inventory which is done'))
            
        return super(initial_stock_inventory, self).unlink(cr, uid, ids, context=context)
    
    _columns = {
        'inventory_line_id': fields.one2many('initial.stock.inventory.line', 'inventory_id', string='Inventory lines'),
        'move_ids': fields.many2many('stock.move', 'initial_stock_inventory_move_rel', 'inventory_id', 'move_id', 'Created Moves'),
        'sublist_id': fields.many2one('product.list', string='List/Sublist'),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type'),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group'),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family'),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root'),
    }
    
    def _inventory_line_hook(self, cr, uid, inventory_line, move_vals):
        '''
        Add the price in the stock move
        '''
        move_vals['price_unit'] = inventory_line.average_cost
        return super(initial_stock_inventory, self)._inventory_line_hook(cr, uid, inventory_line, move_vals)
    
    def action_confirm(self, cr, uid, ids, context=None):
        '''
        Override the action_confirm method to check the batch mgmt/perishable data
        '''
        product_dict = {}
        
        for inventory in self.browse(cr, uid, ids, context=context):
            for inventory_line in inventory.inventory_line_id:
                if inventory_line.product_id.id not in product_dict:
                    product_dict.update({inventory_line.product_id.id: inventory_line.average_cost})
                elif product_dict[inventory_line.product_id.id] != inventory_line.average_cost:
                    raise osv.except_osv(_('Error'), _('You cannot have two lines for the same product with different average cost.'))
                
                # Returns error if the line is batch mandatory or perishable without prodlot
                if inventory_line.product_id.batch_management:
                        if not inventory_line.prod_lot_id or inventory_line.prod_lot_id.type != 'standard':
                            raise osv.except_osv(_('Error'), _('You must assign a Batch Number which corresponds to Batch Number Mandatory Products.'))
                        
                if inventory_line.product_id.perishable and not inventory_line.product_id.batch_management:
                    if (not inventory_line.prod_lot_id and not inventory_line.expiry_date) or (inventory_line.prod_lot_id and inventory_line.prod_lot_id.type != 'internal'):
                            raise osv.except_osv(_('Error'), _('The selected product is neither Batch Number Mandatory nor Expiry Date Mandatory'))
                        
                if inventory_line.prod_lot_id:
                    if not inventory_line.product_id.perishable and not inventory_line.product_id.batch_management:
                            raise osv.except_osv(_('Error'), _('You must assign a Batch Number which corresponds to Expiry Date Mandatory Products.'))
        
        return super(initial_stock_inventory, self).action_confirm(cr, uid, ids, context=context)
    
    def action_done(self, cr, uid, ids, context=None):
        """ Finish the inventory
        @return: True
        """
        if context is None:
            context = {}
        move_obj = self.pool.get('stock.move')
        prod_obj = self.pool.get('product.product')
        for inv in self.browse(cr, uid, ids, context=context):
            for move in inv.move_ids:
                new_std_price = move.price_unit
                prod_obj.write(cr, uid, move.product_id.id, {'standard_price': new_std_price}, context=context)
                move_obj.action_done(cr, uid, move.id, context=context)

            self.write(cr, uid, [inv.id], {'state':'done', 'date_done': time.strftime('%Y-%m-%d %H:%M:%S')}, context=context)
        return True
    
    def fill_lines(self, cr, uid, ids, context=None):
        '''
        Fill all lines according to defined nomenclature level and sublist
        '''
        if context is None:
            context = {}
            
        location_id = False
        wh_ids = self.pool.get('stock.warehouse').search(cr, uid, [])
        if wh_ids:
            location_id = self.pool.get('stock.warehouse').browse(cr, uid, wh_ids[0]).lot_stock_id.id
        for inventory in self.browse(cr, uid, ids, context=context):
            product_ids = []
            products = []

            nom = False
            # Get all products for the defined nomenclature
            if inventory.nomen_manda_3:
                nom = inventory.nomen_manda_3.id
                field = 'nomen_manda_3'
            elif inventory.nomen_manda_2:
                nom = inventory.nomen_manda_2.id
                field = 'nomen_manda_2'
            elif inventory.nomen_manda_1:
                nom = inventory.nomen_manda_1.id
                field = 'nomen_manda_1'
            elif inventory.nomen_manda_0:
                nom = inventory.nomen_manda_0.id
                field = 'nomen_manda_0'
            if nom:
                product_ids.extend(self.pool.get('product.product').search(cr, uid, [(field, '=', nom)], context=context))

            # Get all products for the defined list
            if inventory.sublist_id:
                for line in inventory.sublist_id.product_ids:
                    product_ids.append(line.name.id)

            # Check if products in already existing lines are in domain
            products = []
            for line in inventory.inventory_line_id:
                if line.product_id.id in product_ids:
                    products.append(line.product_id.id)
                else:
                    self.pool.get('initial.stock.inventory.line').unlink(cr, uid, line.id, context=context)

            c = context.copy()
            c.update({'location_id': location_id, 'compute_child': False})
            for product in self.pool.get('product.product').browse(cr, uid, product_ids, context=c):
                # Check if the product is not already on the report
                if product.id not in products:
                    batch_mandatory = product.batch_management or product.perishable
                    date_mandatory = not product.batch_management and product.perishable
                    values = {'product_id': product.id,
                              'uom_id': product.uom_id.id,
                              'location_id': location_id,
                              'product_qty': product.qty_available,
                              'average_cost': product.standard_price,
                              'hidden_batch_management_mandatory': batch_mandatory,
                              'hidden_perishable_mandatory': date_mandatory,
                              'inventory_id': inventory.id,}
                    v = self.pool.get('initial.stock.inventory.line').on_change_product_id(cr, uid, [], location_id, product.id, product.uom_id.id, False)['value']
                    values.update(v)
                    if batch_mandatory:
                        values.update({'err_msg': 'You must assign a batch number'})
                    if date_mandatory:
                        values.update({'err_msg': 'You must assign an expiry date'})
                    self.pool.get('initial.stock.inventory.line').create(cr, uid, values)
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'initial.stock.inventory',
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': ids[0],
                'target': 'dummy',
                'context': context}
        
    def get_nomen(self, cr, uid, id, field):
        return self.pool.get('product.nomenclature').get_nomen(cr, uid, self, id, field, context={'withnum': 1})

    def onChangeSearchNomenclature(self, cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, context=None):
        return self.pool.get('product.product').onChangeSearchNomenclature(cr, uid, 0, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, False, context={'withnum': 1})
    
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
        'inventory_id': fields.many2one('initial.stock.inventory', string='Inventory', ondelete='cascade'),
        'average_cost': fields.float(digits=(16,2), string='Initial average cost', required=True),
        'currency_id': fields.many2one('res.currency', string='Functional currency', readonly=True),
        'err_msg': fields.function(_get_error_msg, method=True, type='char', string='Message', store=False),
    }
    
    _defaults = {
        'currency_id': lambda obj, cr, uid, c: obj.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id,
        'average_cost': lambda *a: 0.00,
        'product_qty': lambda *a: 0.00,
        'reason_type_id': lambda obj, cr, uid, c: obj.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_discrepancy')[1]
    }
    
    def _check_batch_management(self, cr, uid, ids, context=None):
        '''
        check for batch management
        '''
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.product_id.batch_management and obj.inventory_id.state != 'draft':
                if not obj.prod_lot_id or obj.prod_lot_id.type != 'standard':
                    return False
        return True
    
    def _check_perishable(self, cr, uid, ids, context=None):
        """
        check for perishable ONLY
        """
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.product_id.perishable and not obj.product_id.batch_management and obj.inventory_id.state != 'draft':
                if (not obj.prod_lot_id and not obj.expiry_date) or (obj.prod_lot_id and obj.prod_lot_id.type != 'internal'):
                    return False
        return True
    
    def _check_prodlot_need(self, cr, uid, ids, context=None):
        """
        If the inv line has a prodlot but does not need one, return False.
        """
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.prod_lot_id and obj.inventory_id.state != 'draft':
                if not obj.product_id.perishable and not obj.product_id.batch_management:
                    return False
        return True
    
    _constraints = [(_check_batch_management,
                 'You must assign a Batch Number which corresponds to Batch Number Mandatory Products.',
                 ['prod_lot_id']),
                (_check_perishable,
                 'You must assign a Batch Numbre which corresponds to Expiry Date Mandatory Products.',
                 ['prod_lot_id']),
                (_check_prodlot_need,
                 'The selected product is neither Batch Number Mandatory nor Expiry Date Mandatory',
                 ['prod_lot_id']),
                ]
    
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
    
    def change_lot(self, cr, uid, ids, location_id, product, prod_lot_id, uom=False, to_date=False,):
        res = super(initial_stock_inventory_line, self).change_lot(cr, uid, ids, location_id, product, prod_lot_id, uom=uom, to_date=to_date)
        if 'warning' not in res:
            if 'value' not in res:
                res.update({'value': {}})
                
            res['value'].update({'err_msg': ''})
        
        return res
    
    def change_expiry(self, cr, uid, id, expiry_date, product_id, type_check, context=None):
        res = super(initial_stock_inventory_line, self).change_expiry(cr, uid, id, expiry_date, product_id, type_check, context=None)
        if 'warning' not in res:
            if 'value' not in res:
                res.udptae({'value': {}})
                
            res['value'].update({'err_msg': ''})
        
        return res
        
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

class stock_cost_reevaluation(osv.osv):
    _name = 'stock.cost.reevaluation'
    _description = 'Cost reevaluation'
    
    _columns = {
    }
    
stock_cost_reevaluation()

class stock_cost_reevaluation_line(osv.osv):
    _name = 'stock.cost.reevaluation.line'
    _description = 'Cost reevaluation line'
    
    _columns = {
        'product_id': fields.many2one('product.product', string='Product', required=True),
        'average_cost': fields.float(digits=(16,2), string='Average cost', required=True),
        'currency_id': fields.many2one('res.currency', string='Currency', readonly=True),
    }
    
    _defaults = {
        'currency_id': lambda obj, cr, uid, c={}: obj.poo.get('res.users').browse(cr, uid, uid).company_id.currency_id.id,
    }
    
stock_cost_reevaluation_line()
