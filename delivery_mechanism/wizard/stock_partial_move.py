# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
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

from osv import fields, osv
from tools.translate import _
import time


class stock_partial_move_memory_out(osv.osv_memory):
    _inherit = "stock.move.memory.out"
    
    _columns = {'force_complete' : fields.boolean(string='Force Complete'),
                }
    _defaults = {'force_complete': False,}
    
stock_partial_move_memory_out()
    
class stock_partial_move_memory_in(osv.osv_memory):
    _inherit = "stock.move.memory.out"
    _name = "stock.move.memory.in"
    
stock_partial_move_memory_in()
    
    
class stock_partial_move(osv.osv_memory):
    _inherit = "stock.partial.move"
    
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
        partial_datas['move%s' % (move.id)].update({'force_complete': p_moves[move.id].force_complete,})
        
        return partial_datas

stock_partial_move()
