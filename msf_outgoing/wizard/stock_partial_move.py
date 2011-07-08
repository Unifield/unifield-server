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
        assert context, 'no context defined'
        
        pick_obj = self.pool.get('stock.picking')
        
        # data - no step needed for present split wizard
        name = _("Split Selected Stock Move")
        model = 'split.memory.move'
        # we need to get the memory move id to know which line to split
        # and class name, to know which type of moves
        return pick_obj.open_wizard(cr, uid, context['active_ids'], name=name, model=model, type='create', context=dict(context, memory_move_ids=ids, class_name=self._name))

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
    
    def create(self, cr, uid, vals, context=None):
        '''
        default value of qty_per_pack to quantity
        of from_pack and to_pack to 1
        
        those fields have a constraint assigned to them, and must
        therefore be completed with default value at creation
        '''
        if 'qty_per_pack' not in vals:
            vals.update(qty_per_pack=vals['quantity'])
        
        if 'from_pack' not in vals:
            vals.update(from_pack=1)
            
        if 'to_pack' not in vals:
            vals.update(to_pack=1)
            
        return super(stock_partial_move_memory_ppl, self).create(cr, uid, vals, context)
        
    
    def _check_qty_per_pack(self, cr, uid, ids, context=None):
        """ Checks if qty_per_pack is assigned to memory move or not.
        @return: True or False
        """
        for move in self.browse(cr, uid, ids, context=context):
            if not move.qty_per_pack:
                return False
        return True
    
    def _check_from_pack(self, cr, uid, ids, context=None):
        """ Checks if from_pack is assigned to memory move or not.
        @return: True or False
        """
        for move in self.browse(cr, uid, ids, context=context):
            if not move.from_pack:
                return False
        return True
    
    def _check_to_pack(self, cr, uid, ids, context=None):
        """ Checks if to_pack is assigned to memory move or not.
        @return: True or False
        """
        for move in self.browse(cr, uid, ids, context=context):
            if not move.to_pack:
                return False
        return True
    
    # existence integrity
    # the constraint are at memory.move level for ppl1 because we do not
    # want to wait until the end of ppl2 and stock.move update to validate
    # the data of this wizard. this is possible because we set default values
    # for qty_per_pack, from_pack and to_pack different from 0
    _constraints = [
        (_check_qty_per_pack,
            'You must assign a positive "quantity per pack" value',
            ['qty_per_pack']),
        (_check_from_pack,
            'You must assign a positive "from pack" value',
            ['from_pack']),
        (_check_to_pack,
            'You must assign a positive "to pack" value',
            ['to_pack']),]

stock_partial_move_memory_ppl()


class stock_partial_move_memory_families(osv.osv_memory):
    '''
    view corresponding to pack families
    
    integrity constraint 
    '''
    _name = "stock.move.memory.families"
    _rec_name = 'from_pack'
    _columns = {
        'from_pack' : fields.integer(string="From p."),
        'to_pack' : fields.integer(string="To p."),
        'pack_type': fields.many2one('pack.type', 'Pack Type'),
        'length' : fields.float(digits=(16,2), string='Length [cm]'),
        'width' : fields.float(digits=(16,2), string='Width [cm]'),
        'height' : fields.float(digits=(16,2), string='Height [cm]'),
        'weight' : fields.float(digits=(16,2), string='Weight p.p [kg]'),
        'wizard_id' : fields.many2one('stock.partial.move', string="Wizard"),
    }
    
stock_partial_move_memory_families()


class stock_partial_move_memory_shipment_create(osv.osv_memory):
    '''
    view corresponding to pack families for shipment create
    
    integrity constraint 
    '''
    _name = "stock.move.memory.shipment.create"
    _inherit = "stock.move.memory.families"
    _rec_name = 'from_pack'
    _columns = {'sale_order_id': fields.many2one('sale.order', string="Sale Order Ref"),
                'ppl_id': fields.many2one('stock.picking', string="PPL Ref"), 
                'draft_packing_id': fields.many2one('stock.picking', string="Draft Packing Ref"),
                'num_of_packs': fields.integer(string='#Packs'),
                'num_to_ship': fields.integer(string='Number to ship'),
                'weight_to_ship' : fields.float(digits=(16,2), string='Weight to ship [kg]'),
    }
    
stock_partial_move_memory_shipment_create()
