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
import decimal_precision as dp

from msf_outgoing import INTEGRITY_STATUS_SELECTION


class stock_partial_move_memory_out(osv.osv_memory):
    '''
    add split method to base out object
    '''
    _inherit = "stock.move.memory.out"
    
    def split(self, cr, uid, ids, context=None):
        '''
        open the split wizard, the user can select the qty for the new move
        '''
        # we need the context for the wizard switch
        assert context, 'no context defined'
        if isinstance(ids, (int, long)):
            ids = [ids]
        wiz_obj = self.pool.get('wizard')
        
        # data - no step needed for present split wizard
        name = _("Split Selected Stock Move")
        model = 'split.memory.move'
        # we need to get the memory move id to know which line to split
        # and class name, to know which type of moves
        return wiz_obj.open_wizard(cr, uid, context['active_ids'], name=name, model=model, type='create', context=dict(context, memory_move_ids=ids, class_name=self._name))
    
    def change_product(self, cr, uid, ids, context=None):
        '''
        open the change product wizard, the user can select the new product
        '''
        # we need the context for the wizard switch
        assert context, 'no context defined'
        if isinstance(ids, (int, long)):
            ids = [ids]
        # objects
        wiz_obj = self.pool.get('wizard')
        # data - no step needed for present split wizard
        name = _("Change Product of Selected Stock Move")
        model = 'change.product.memory.move'
        # we need to get the memory move id to know which line to split
        # and class name, to know which type of moves
        data = self.read(cr, uid, ids, ['product_id', 'product_uom'], context=context)[0]
        product_id = data['product_id']
        uom_id = data['product_uom']
        return wiz_obj.open_wizard(cr, uid, context['active_ids'], name=name, model=model,
                                   type='create', context=dict(context,
                                                               memory_move_ids=ids,
                                                               class_name=self._name,
                                                               product_id=product_id,
                                                               uom_id=uom_id))
    
    _columns={'integrity_status': fields.selection(string=' ', selection=INTEGRITY_STATUS_SELECTION, readonly=True),
              'force_complete' : fields.boolean(string='Force'),
              'line_number': fields.integer(string='Line'),
              'change_reason': fields.char(string='Change Reason', size=1024),
              }
    _defaults = {'integrity_status': 'empty',
                 'force_complete': False,
                 }
    _order = 'line_number asc'

stock_partial_move_memory_out()


class stock_partial_move_memory_in(osv.osv_memory):
    _name = "stock.move.memory.in"
    _inherit = "stock.move.memory.out"
    
stock_partial_move_memory_in()


class stock_partial_move_memory_picking(osv.osv_memory):
    '''
    add the split method
    '''
    _name = "stock.move.memory.picking"
    _inherit = "stock.move.memory.out"
    
stock_partial_move_memory_picking()


class stock_partial_move_memory_returnproducts(osv.osv_memory):
    '''
    memory move for ppl return products step
    '''
    _name = "stock.move.memory.returnproducts"
    _inherit = "stock.move.memory.picking"
    _columns = {'qty_to_return': fields.float(string='Qty to return', digits_compute=dp.get_precision('Product UoM') ),
                }
    
    _defaults = {
        'qty_to_return': 0.0,
    }

stock_partial_move_memory_returnproducts()


class stock_partial_move_memory_ppl(osv.osv_memory):
    '''
    memory move for ppl step
    '''
    _name = "stock.move.memory.ppl"
    _inherit = "stock.move.memory.picking"
    
    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        get functional values
        '''
        result = {}
        for memory_move in self.browse(cr, uid, ids, context=context):
            values = {'num_of_packs': 0,
                      'qty_per_pack': 0,
                      }
            result[memory_move.id] = values
            # number of packs with from/to values
            num_of_packs = memory_move.to_pack - memory_move.from_pack + 1
            values['num_of_packs'] = num_of_packs
            qty_per_pack = memory_move.quantity / num_of_packs
            values['qty_per_pack'] = qty_per_pack
                    
        return result
    
    _columns = {'from_pack': fields.integer(string='From p.'),
                'to_pack': fields.integer(string='To p.'),
                # functions
                'num_of_packs': fields.function(_vals_get, method=True, type='integer', string='#Packs', multi='get_vals',),
                'qty_per_pack': fields.function(_vals_get, method=True, type='float', string='Qty p.p.', multi='get_vals_X',), # old_multi get_vals
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
    
    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        get functional values
        '''
        result = {}
        for memory_move in self.browse(cr, uid, ids, context=context):
            values = {'num_of_packs': 0,
                      'selected_weight': 0.0,
                      }
            result[memory_move.id] = values
            # number of packs with from/to values
            num_of_packs = memory_move.to_pack - memory_move.from_pack + 1
            values['num_of_packs'] = num_of_packs
            selected_weight = memory_move.weight * memory_move.selected_number
            values['selected_weight'] = selected_weight
                    
        return result
    
    _columns = {'sale_order_id': fields.many2one('sale.order', string="Sale Order Ref"),
                'ppl_id': fields.many2one('stock.picking', string="PPL Ref"), 
                'draft_packing_id': fields.many2one('stock.picking', string="Draft Packing Ref"),
                'selected_number': fields.integer(string='Selected Number'),
                # functions
                'num_of_packs': fields.function(_vals_get, method=True, type='integer', string='#Packs', multi='get_vals',),
                'selected_weight' : fields.function(_vals_get, method=True, type='float', string='Selected Weight [kg]', multi='get_vals_X',), # old_multi get_vals
    }
    
stock_partial_move_memory_shipment_create()


class stock_partial_move_memory_shipment_returnpacks(osv.osv_memory):
    '''
    view corresponding to pack families for packs return
    
    integrity constraint 
    '''
    _name = "stock.move.memory.shipment.returnpacks"
    _inherit = "stock.move.memory.shipment.create"
    
stock_partial_move_memory_shipment_returnpacks()


class stock_partial_move_memory_shipment_returnpacksfromshipment(osv.osv_memory):
    '''
    view corresponding to pack families for packs return from shipment
    
    integrity constraint 
    '''
    _name = "stock.move.memory.shipment.returnpacksfromshipment"
    _inherit = "stock.move.memory.shipment.returnpacks"
    _columns = {
                'return_from' : fields.integer(string="Return From"),
                'return_to' : fields.integer(string="Return To"),
    }
    
    def split(self, cr, uid, ids, context=None):
        # quick integrity check
        assert context, 'No context defined, problem on method call'
        # objects
        wiz_obj = self.pool.get('wizard')
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        for memory_move in self.browse(cr, uid, ids, context=context):
            # create new memory move - copy for memory is not implemented
            fields = self.fields_get(cr, uid, context=context)
            values = {}
            for key in fields.keys():
                type= fields[key]['type']
                if type not in ('one2many', 'many2one', 'one2one'):
                    values[key] = getattr(memory_move, key)
                elif type in ('many2one'):
                    tmp = getattr(memory_move, key)
                    values[key] = getattr(tmp, "id")
                else:
                    assert False, 'copy of %s value is not implemented'%type

            new_memory_move = self.create(cr, uid, values, context=context)
        
        # udpate the original wizard
        return wiz_obj.open_wizard(cr, uid, context['active_ids'], type='update', context=context)
    
    
stock_partial_move_memory_shipment_returnpacksfromshipment()
