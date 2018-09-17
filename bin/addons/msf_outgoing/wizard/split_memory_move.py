# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Copyright (C) 2011 MSF, TeMPO Consulting.
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
import decimal_precision as dp


class split_memory_move(osv.osv_memory):
    '''
    wizard called to split a memory stock move from create picking wizard
    '''
    _name = "split.memory.move"
    _description = "Split Memory Move"
    _columns = {
        'quantity': fields.float('Quantity',digits_compute=dp.get_precision('Product UOM'), related_uom='uom_id'),
        'uom_id': fields.many2one('product.uom', string='UoM', readonly=True),
    }

    def default_get(self, cr, uid, fields, context=None):
        '''
        Get the UoM from the line
        '''
        if not context:
            context = {}

        res = super(split_memory_move, self).default_get(cr, uid, fields, context=context)

        move_id = context.get('memory_move_ids', [])
        if move_id:
            res['uom_id'] = self.pool.get(context.get('class_name')).browse(cr, uid, move_id[0]).product_uom.id

        res['quantity'] = 0.00
        
        return res

    def change_uom(self, cr, uid, ids, uom_id, qty):
        '''
        Check the round of the qty according to the UoM
        '''
        return self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_id, qty, 'quantity')
    
    def cancel(self, cr, uid, ids, context=None):
        '''
        return to picking creation wizard
        '''
        # we need the context for the wizard switch
        assert context, 'no context defined'
        
        wiz_obj = self.pool.get('wizard')
        
        # no data for type 'back'
        return wiz_obj.open_wizard(cr, uid, context['active_ids'], w_type='back', context=context)

    def split(self, cr, uid, ids, context=None):
        # quick integrity check
        assert context, 'No context defined, problem on method call'
        assert context['class_name'], 'No class name defined'
        class_name = context['class_name']

        wiz_obj = self.pool.get('wizard')
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        # memory moves selected
        memory_move_ids = context['memory_move_ids']
        memory_move_obj = self.pool.get(class_name)
        # quantity input
        leave_qty = self.browse(cr, uid, ids[0], context=context).quantity
        for memory_move in memory_move_obj.browse(cr, uid, memory_move_ids, context=context):
            
            # quantity from memory move

            available_qty = memory_move.ordered_quantity
            available_qty_to_process = memory_move.quantity
            
            # leave quantity must be greater than zero
            if leave_qty <= 0:
                raise osv.except_osv(_('Error!'),  _('Selected quantity must be greater than 0.0.'))

            # cannot select more than available
            if leave_qty > available_qty:
                raise osv.except_osv(_('Error!'),  _('Selected quantity (%0.1f %s) exceeds the available quantity (%0.1f %s)')%(leave_qty, memory_move.product_uom.name, available_qty, memory_move.product_uom.name))
            
            # cannot select all available
            if leave_qty == available_qty:
                raise osv.except_osv(_('Error !'),_('Selected quantity is equal to available quantity (%0.1f %s).')%(available_qty, memory_move.product_uom.name))
            
            # quantity difference for new memory stock move
            new_qty = available_qty - leave_qty
            
            # update the selected memory move
            if class_name == 'stock.move.memory.ppl':
                values = {'quantity': new_qty, 'ordered_quantity': new_qty}
            else:
                values = {'ordered_quantity': new_qty}

            if available_qty_to_process > 0.0 and class_name != 'stock.move.memory.ppl':
                if not context.get('import_in_progress'):
                    values['quantity'] = 0.0
            # update the object    
            memory_move_obj.write(cr, uid, [memory_move.id], values)
            
            # create new memory move - copy for memory is not implemented
            default_val = {'line_number': memory_move.line_number,
                           'product_id': memory_move.product_id.id,
                           'ordered_quantity': leave_qty,
                           'force_complete': memory_move.force_complete,
                           'product_uom': memory_move.product_uom.id,
                           'uom_ordered': memory_move.product_uom.id,
                           'prodlot_id': memory_move.prodlot_id.id,
                           'move_id': memory_move.move_id.id,
                           'wizard_pick_id': memory_move.wizard_pick_id and memory_move.wizard_pick_id.id,
                           'wizard_id': memory_move.wizard_id and memory_move.wizard_id.id,
                           'cost': memory_move.cost,
                           'currency': memory_move.currency.id,
                           'asset_id': memory_move.asset_id.id,
                           }
            if class_name == 'stock.move.memory.ppl':
                default_val['quantity'] = leave_qty

            if available_qty_to_process > 0.0 and class_name != 'stock.move.memory.ppl':
                default_val['quantity'] = 0.0

            new_memory_move = memory_move_obj.create(cr, uid, default_val, context=context)
            context.update({'new_memory_move_id': new_memory_move})
        
        # no data for type 'back'
        return wiz_obj.open_wizard(cr, uid, context['active_ids'], w_type='back', context=context)
    
split_memory_move()
