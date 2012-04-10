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


class stock_partial_move_memory_out(osv.osv_memory):
    _inherit = "stock.move.memory.out"
    
    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
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
            result[obj.id] = {'kit_mem_check': False}
            # we want the possibility to link a composition list if
            # - the product is a kit AND
            # - the product is not perishable nor batch management
            product = obj.product_id
            if product.type == 'product' and product.subtype == 'kit' and not product.perishable:
                result[obj.id].update({'kit_mem_check': True})
        return result
    
    _columns = {'composition_list_id': fields.many2one('composition.kit', string='Kit'),
                'kit_mem_check' : fields.function(_vals_get, method=True, string='Kit Mem Check', type='boolean', readonly=True, multi='get_vals'),
                }
    
stock_partial_move_memory_out()
    
class stock_partial_move_memory_in(osv.osv_memory):
    _inherit = "stock.move.memory.out"
    _name = "stock.move.memory.in"
    
stock_partial_move_memory_in()
    
    
class stock_partial_move(osv.osv_memory):
    _inherit = "stock.partial.move"
    
    def __create_partial_move_memory(self, move):
        '''
        add the composition_list_id
        '''
        move_memory = super(stock_partial_move, self).__create_partial_move_memory(move)
        assert move_memory is not None
        
        move_memory.update({'composition_list_id' : move.composition_list_id.id})
        
        return move_memory
    
    def do_partial_hook(self, cr, uid, context, *args, **kwargs):
        '''
        add hook to do_partial
        '''
        # call to super
        partial_datas = super(stock_partial_move, self).do_partial_hook(cr, uid, context, *args, **kwargs)
        assert partial_datas, 'partial_datas missing'
        
        move = kwargs.get('move')
        assert move, 'move is missing'
        p_moves = kwargs.get('p_moves')
        assert p_moves, 'p_moves is missing'
        
        # update composition_list_id
        partial_datas['move%s' % (move.id)].update({'composition_list_id': p_moves[move.id].composition_list_id.id,})
        
        return partial_datas

stock_partial_move()
