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
    
    def _get_checks_asset(self, cr, uid, ids, name, arg, context=None):
        '''
        complete asset boolean
        '''
        result = {}
        for id in ids:
            result[id] = False
            
        for out in self.browse(cr, uid, ids, context=context):
            result[out.id] = out.product_id.subtype == 'asset'
            
        return result
    
    _columns = {
        'asset_id' : fields.many2one('product.asset', string="Asset"),
        'asset_check' : fields.function(_get_checks_asset, method=True, string='Asset Check', type='boolean', readonly=True),
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
        add the asset_id
        '''
        move_memory = super(stock_partial_move, self).__create_partial_move_memory(move)
        assert move_memory is not None
        
        move_memory.update({'asset_id' : move.asset_id.id})
        
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
        
        # update asset_id
        partial_datas['move%s' % (move.id)].update({'asset_id': p_moves[move.id].asset_id.id,})
        
        return partial_datas

stock_partial_move()
