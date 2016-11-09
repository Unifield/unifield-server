
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

class stock_partial_picking(osv.osv_memory):
    _inherit = "stock.partial.picking"
    
    def __create_partial_picking_memory(self, picking, pick_type):
        '''
        add the composition_list_id
        NOTE: the name used here : picking is WRONG. it is in fact a stock.move object
        '''
        move_memory = super(stock_partial_picking, self).__create_partial_picking_memory(picking, pick_type)
        assert move_memory is not None
        
        move_memory.update({'composition_list_id' : picking.composition_list_id.id})
        
        return move_memory
    
    def do_partial_hook(self, cr, uid, context, *args, **kwargs):
        '''
        add hook to do_partial
        '''
        # call to super
        partial_datas = super(stock_partial_picking, self).do_partial_hook(cr, uid, context, *args, **kwargs)
        assert partial_datas, 'partial_datas missing'
        
        move = kwargs.get('move')
        assert move, 'move is missing'
        
        # update composition_list_id
        partial_datas['move%s' % (move.move_id.id)].update({'composition_list_id': move.composition_list_id.id,})
        
        return partial_datas

stock_partial_picking()
