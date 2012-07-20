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
