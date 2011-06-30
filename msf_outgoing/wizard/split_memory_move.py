# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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
        'quantity': fields.float('Quantity',digits_compute=dp.get_precision('Product UOM')),
    }
    _defaults = {
        'quantity': lambda *x: 0,
    }
    
    def cancel(self, cr, uid, ids, context=None):
        '''
        return to picking creation wizard
        '''
        return {
            'name':_("Create Picking Ticket"),
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'res_model': 'create.picking',
            'res_id': context['create_wizard_ids'][0],
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'domain': '[]',
            'context': context
        }

    def split(self, cr, uid, ids, context=None):
        # quick integrity check
        assert context, 'No context defined, problem on method call'
        assert ids == context['split_wizard_ids'], 'No split wizard id in context, problem on action creation'
        # memory moves selected
        memory_move_ids = context['memory_move_ids']
        memory_move_obj = self.pool.get('stock.move.memory.out')
        # quantity input
        leave_qty = self.browse(cr, uid, ids[0], context=context).quantity
        for memory_move in memory_move_obj.browse(cr, uid, memory_move_ids, context=context):
            # integrity check on create picking wizard id
            assert memory_move.wizard_id.id == context['create_wizard_ids'][0]
            
            # quantity from memory move
            available_qty = memory_move.quantity
            
            # leave quantity must be greater than zero
            if leave_qty <= 0:
                raise osv.except_osv(_('Error!'),  _('Selected quantity to leave must be greater than 0.0.'))

            # cannot select more than available
            if leave_qty > available_qty:
                raise osv.except_osv(_('Error!'),  _('Selected quantity to leave in the current stock move (%0.1f) exceeds the available quantity (%0.1f)'%(leave_qty, available_qty)))
            
            # cannot select all available
            if leave_qty == available_qty:
                raise osv.except_osv(_('Error !'),_('Selected quantity to leave in the current stock move is equal to available quantity (%i).'%(available_qty)))
            
            # quantity difference for new memory stock move
            new_qty = available_qty - leave_qty
            
            # update the selected memory move
            memory_move_obj.write(cr, uid, [memory_move.id], {
                'quantity': leave_qty,
            })
            
            # create new memory move
            default_val = {'product_id': memory_move.product_id.id,
                           'quantity': new_qty,
                           'product_uom': memory_move.product_uom.id,
                           'prodlot_id': memory_move.prodlot_id.id,
                           'move_id': memory_move.move_id.id,
                           'wizard_id': memory_move.wizard_id.id,
                           'cost': memory_move.cost,
                           'currency': memory_move.currency.id,
                           'asset_id': memory_move.asset_id.id,
            }
            new_memory_move = memory_move_obj.create(cr, uid, default_val, context=context)
                        
        # go back to previous wizard (create picking)
        return {
            'name':_("Create Picking Ticket"),
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'res_model': 'create.picking',
            'res_id': context['create_wizard_ids'][0],
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'domain': '[]',
            'context': context
        }
    
split_memory_move()

