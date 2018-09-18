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

from osv import fields, osv
from tools.translate import _
import time

from msf_outgoing import INTEGRITY_STATUS_SELECTION


class stock_partial_move_memory_out(osv.osv_memory):
    _inherit = "stock.move.memory.out"
    
    def _validate_item_out(self, cr, uid, id, context=None):
        '''
        validate the from stock objects for lot and expiry date
        
        - lot AND expiry date are mandatory for batch management products
        - expiry date is mandatory for perishable products
        
        return corresponding key error for selection
        
        out, picking, ppl,.. need different validation function, validate_item function can be overriden in inherited classes
        '''
        # objects
        prod_obj = self.pool.get('product.product')
        lot_obj = self.pool.get('stock.production.lot')
        uom_obj = self.pool.get('product.uom')
        # browse the object
        item = self.browse(cr, uid, id, context=context)
        # picking type
        picking_real_type = item.move_id.picking_id.type
        # by default we return empty result
        result = 'empty'
        # validation is only needed if the line has been selected (qty > 0)
        if item.quantity != 0:
            # product management type - cannot use hidden checks, because validate is called within get_vals function, would result in infinite loop
            data = prod_obj.read(cr, uid, [item.product_id.id], ['batch_management', 'perishable', 'type', 'subtype'], context=context)[0]
            management = data['batch_management']
            perishable = data['perishable']
            type = data['type']
            subtype = data['subtype']
            if management:
                if not item.prodlot_id:
                    # lot is needed
                    result = 'missing_lot'
                else:
                    data = lot_obj.read(cr, uid, [item.prodlot_id.id], ['life_date','name','type'], context=context)
                    lot_type = data and data[0]['type']
                    if lot_type != 'standard':
                        result = 'wrong_lot_type_need_standard'
            elif perishable:
                if not item.expiry_date:
                    # expiry date is needed
                    result = 'missing_date'
            else:
                # no lot needed
                if item.prodlot_id:
                    result = 'no_lot_needed'
            # asset check - asset is not mandatory for moves performed internally
            if type == 'product' and subtype == 'asset':
                if picking_real_type in ['out', 'in']:
                    if not item.asset_id:
                        result = 'missing_asset'
            else:
                if item.asset_id:
                    result = 'not_asset_needed'
            # quantity check cannot be negative
            if item.quantity <= 0:
                result = 'must_be_greater_than_0'
            # for internal or simple out, cannot process more than specified in stock move
            if picking_real_type in ['out', 'internal']:
                proc_qty = uom_obj._compute_qty(cr, uid, item.product_uom.id, item.quantity, item.uom_ordered.id)
                if abs(proc_qty - item.ordered_quantity) > 0.0001:
                    result = 'greater_than_available'
                
        # we return the found result
        return result
    
    def validate_item(self, cr, uid, id, context=None):
        '''
        validation interface to allow modifying behavior in inherited classes
        '''
        return self._validate_item_out(cr, uid, id, context=context)
    
    def _vals_get_stock_override(self, cr, uid, ids, fields, arg, context=None):
        '''
        multi fields function method
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {}
            # integrity_status_func_substitute_item
            result[obj.id].update({'integrity_status_func_stock_memory_move': self.validate_item(cr, uid, obj.id, context=context)})

        return result
    
    _columns = {'integrity_status_func_stock_memory_move': fields.function(_vals_get_stock_override, method=True, type='selection', selection=INTEGRITY_STATUS_SELECTION, string=' ', multi='get_vals_stock_override', store=False, readonly=True),
                }
    
stock_partial_move_memory_out()
    
class stock_partial_move_memory_in(osv.osv_memory):
    _inherit = "stock.move.memory.out"
    _name = "stock.move.memory.in"
    
stock_partial_move_memory_in()
    
class stock_partial_move(osv.osv_memory):
    _inherit = "stock.partial.move"
    _description = "Partial Move with hook"


    def _hook_move_state(self):
        res = super(stock_partial_move, self)._hook_move_state()
        res.append('confirmed')
        return res
    
    def do_partial_hook(self, cr, uid, context, *args, **kwargs):
        '''
        add hook to do_partial
        '''
        partial_datas = kwargs.get('partial_datas')
        assert partial_datas, 'partial_datas missing'
        
        return partial_datas
        
    
    
    # @@@override stock>wizard>stock_partial_move.py
    def do_partial(self, cr, uid, ids, context=None):
        """ Makes partial moves and pickings done.
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param fields: List of fields for which we want default values
        @param context: A standard dictionary
        @return: A dictionary which of fields with values.
        """
    
        if context is None:
            context = {}
        move_obj = self.pool.get('stock.move')
        
        move_ids = context.get('active_ids', False)
        partial = self.browse(cr, uid, ids[0], context=context)
        partial_datas = {
            'delivery_date' : partial.date
        }
        
        p_moves = {}
        picking_type = self.__get_picking_type(cr, uid, move_ids)
        
        moves_list = picking_type == 'product_moves_in' and partial.product_moves_in  or partial.product_moves_out
        for product_move in moves_list:
            p_moves[product_move.move_id.id] = product_move
            
        moves_ids_final = []
        for move in move_obj.browse(cr, uid, move_ids, context=context):
            if move.state in ('done', 'cancel'):
                continue
            if not p_moves.get(move.id):
                continue
            partial_datas['move%s' % (move.id)] = {
                'product_id' : p_moves[move.id].product_id.id,
                'product_qty' : p_moves[move.id].quantity,
                'product_uom' :p_moves[move.id].product_uom.id,
                'prodlot_id' : p_moves[move.id].prodlot_id.id,
            }
            
            moves_ids_final.append(move.id)
            if (move.picking_id.type == 'in') and (move.product_id.cost_method == 'average') and not move.location_dest_id.cross_docking_location_ok:
                partial_datas['move%s' % (move.id)].update({
                    'product_price' : p_moves[move.id].cost,
                    'product_currency': p_moves[move.id].currency.id,
                })
                
            # override : add hook call
            partial_datas = self.do_partial_hook(cr, uid, context, move=move, p_moves=p_moves, partial_datas=partial_datas)
                
            
        move_obj.do_partial(cr, uid, moves_ids_final, partial_datas, context=context)
        return {'type': 'ir.actions.act_window_close'}
    #@@@override end

stock_partial_move()
