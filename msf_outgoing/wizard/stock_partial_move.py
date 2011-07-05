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

class stock_partial_move_memory_picking(osv.osv_memory):
    '''
    add the split method
    '''
    _name = "stock.move.memory.picking"
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

stock_partial_move_memory_picking()


class stock_partial_move_memory_ppl(osv.osv_memory):
    '''
    memory move for ppl step
    '''
    _name = "stock.move.memory.ppl"
    _inherit = "stock.move.memory.picking"
    _columns = {'qty_per_pack': fields.integer(string='Qty p.p'),
                'from_pack': fields.integer(string='From p.'),
                'to_pack': fields.integer(string='To p.'),
                }

stock_partial_move_memory_ppl()


class stock_partial_move_memory_families(osv.osv_memory):
    '''
    view corresponding to pack families
    '''
    _name = "stock.move.memory.families"
    _rec_name = 'from_pack'
    _columns = {
        'from_pack' : fields.integer(string="From p.", required=True),
        'to_pack' : fields.integer(string="To p.", required=True),
        'pack_type': fields.many2one('pack.type', 'Pack Type'),
        'length' : fields.float(digits=(16,2), string='Length [cm]'),
        'width' : fields.float(digits=(16,2), string='Width [cm]'),
        'height' : fields.float(digits=(16,2), string='Height [cm]'),
        'weight' : fields.float(digits=(16,2), string='Weight p.p [kg]', required=True),
        'wizard_id' : fields.many2one('stock.partial.move', string="Wizard"),
    }
    
stock_partial_move_memory_families()
