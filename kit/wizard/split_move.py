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


class split_move(osv.osv_memory):
    '''
    wizard called to split a stock move from create kitting order
    '''
    _name = "split.move"
    _description = "Split Move"
    _columns = {'quantity': fields.float('Quantity',digits_compute=dp.get_precision('Product UOM')),
                }
    _defaults = {'quantity': lambda *x: 0,
                 }

    def split(self, cr, uid, ids, context=None):
        # quick integrity check
        assert context, 'No context defined, problem on method call'
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        # objects
        move_obj = self.pool.get('stock.move')
        # memory moves selected
        move_ids = context['active_ids']
        # quantity input
        selected_qty = self.browse(cr, uid, ids[0], context=context).quantity
        for move in move_obj.browse(cr, uid, move_ids, context=context):
            # quantity from memory move
            available_qty = move.product_qty
            # leave quantity must be greater than zero
            if selected_qty <= 0:
                raise osv.except_osv(_('Error!'),  _('Selected quantity must be greater than 0.0.'))
            # cannot select more than available
            if selected_qty > available_qty:
                raise osv.except_osv(_('Error!'),  _('Selected quantity (%0.1f %s) exceeds the available quantity (%0.1f %s)')%(selected_qty, move.product_uom.name, available_qty, move.product_uom.name))
            # cannot select all available
            if selected_qty == available_qty:
                raise osv.except_osv(_('Error !'),_('Selected quantity is equal to available quantity (%0.1f %s).')%(available_qty, move.product_uom.name))
            
            # quantity difference for new stock move
            new_qty = available_qty - selected_qty
            # update the selected move
            values = {'product_qty': new_qty, 'product_uos_qty': new_qty}
            # update the object    
            move_obj.write(cr, uid, [move.id], values, context=context)
            # create new move - reset productionlot and location
            location_id = move.kit_creation_id_stock_move.default_location_src_id_kit_creation.id
            new_move_id = move_obj.copy(cr, uid, move.id, {'state': 'confirmed',
                                                           'product_qty': selected_qty,
                                                           'product_uos_qty': selected_qty,
                                                           'prodlot_id': False,
                                                           'asset_id': False,
                                                           'location_id': location_id}, context=context)
        
        return {'type': 'ir.actions.act_window_close'}
    
split_move()
