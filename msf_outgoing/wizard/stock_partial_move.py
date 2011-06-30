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
    '''
    add the split method
    '''
    _inherit = "stock.move.memory.out"
    
    def split(self, cr, uid, ids, context=None):
        '''
        open the split wizard, the user can select the qty to leave in the stock move
        '''
        # we need the context for the wizard switch
        if context is None:
            context = {}
        # create the memory object - passing the wizard id to it through context
        split_id = self.pool.get("split.memory.move").create(
            cr, uid, {}, context=dict(context, memory_move_ids=ids))
        # call action to wizard view
        return {
            'name':_("Split Selected Stock Move"),
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'res_model': 'split.memory.move',
            'res_id': split_id,
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'domain': '[]',
            'context': dict(context, memory_move_ids=ids, split_wizard_ids=[split_id])
        }
    
    
    
stock_partial_move_memory_out()
