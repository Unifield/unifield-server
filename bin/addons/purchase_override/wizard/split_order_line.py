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

from osv import osv, fields
from product._common import rounding
import netsvc

from tools.translate import _

class split_purchase_order_line_wizard(osv.osv_memory):
    _name = 'split.purchase.order.line.wizard'
    _description = 'Split purchase order lines'

    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        multi fields function method
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            linked_sol = obj.purchase_line_id and obj.purchase_line_id.linked_sol_id or False
            result[obj.id] = {
                'corresponding_so_line_id_split_po_line_wizard': linked_sol and linked_sol.id or False,
                'corresponding_so_id_split_po_line_wizard': linked_sol and linked_sol.order_id.id or False,
            }

        return result

    _columns = {
        'purchase_line_id': fields.many2one('purchase.order.line', string='Line Id', readonly=True),
        'original_qty': fields.float(string='Original Quantity', readonly=True),
        'old_line_qty': fields.float(digits=(16,2), string='Old line quantity', readonly=True),
        'new_line_qty': fields.float(digits=(16,2), string='New line quantity', required=True),
        'impact_so_split_po_line_wizard': fields.boolean('Impact Field Order', help='Impact corresponding Field Order by creating a corresponding Field Order line.'),
        'corresponding_so_line_id_split_po_line_wizard': fields.function(_vals_get, method=True, type='many2one', relation='sale.order.line', string='Corresponding Fo line', multi='get_vals_split_po_line', store=False, readonly=True),
        'corresponding_so_id_split_po_line_wizard': fields.function(_vals_get, method=True, type='many2one', relation='sale.order', string='Corresponding Fo', multi='get_vals_split_po_line', store=False, readonly=True),
    }

    _defaults = {
        'new_line_qty': lambda *a: 0.00,
        'impact_so_split_po_line_wizard': True,
    }

    def split_line(self, cr, uid, ids, context=None):
        '''
        Create a new order line and change the quantity of the old line
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        wf_service = netsvc.LocalService('workflow')

        context.update({'split_line': True})
        context.update({'keepDateAndDistrib': True})

        for split in self.browse(cr, uid, ids, context=context):
            # Check if the sum of new line and old line qty is equal to the original qty
            if split.new_line_qty > split.original_qty:
                raise osv.except_osv(_('Error'), _('You cannot have a new quantity greater than the original quantity !'))
            elif split.new_line_qty <= 0.00:
                raise osv.except_osv(_('Error'), _('The new quantity must be positive !'))
            elif split.new_line_qty == split.original_qty:
                raise osv.except_osv(_('Error'), _('The new quantity must be different than the original quantity !'))
            elif split.new_line_qty != rounding(split.new_line_qty, split.purchase_line_id.product_uom.rounding):
                raise osv.except_osv(_('Error'), _('The new quantity must be a multiple of %s !') % split.purchase_line_id.product_uom.rounding)
            else:
                self.infolog(cr, uid, "The PO line id:%s (line number: %s) has been split" % (
                    split.purchase_line_id.id, split.purchase_line_id.line_number,
                ))

                # Change the qty of the old line
                self.pool.get('purchase.order.line').write(cr, uid, [split.purchase_line_id.id], {
                    'product_qty': split.original_qty - split.new_line_qty,
                    'price_unit': split.purchase_line_id.price_unit,
                }, context=context)

            move_dest_id = split.purchase_line_id.move_dest_id and split.purchase_line_id.move_dest_id.id or False
            sale_line_id = split.corresponding_so_line_id_split_po_line_wizard and split.corresponding_so_line_id_split_po_line_wizard.id or False
            po_copy_data = {
                'is_line_split': True, # UTP-972: Indicate only that the line is a split one
                'original_line_id': split.purchase_line_id.id,
                'change_price_manually': split.purchase_line_id.change_price_manually,
                'price_unit': split.purchase_line_id.price_unit,
                'move_dest_id': move_dest_id,
                'sale_line_id': sale_line_id,
                'product_qty': split.new_line_qty,
                'origin': split.purchase_line_id.origin,
                'line_number': split.purchase_line_id.line_number,
            }

            # copy original line
            new_line_id = self.pool.get('purchase.order.line').copy(cr, uid, split.purchase_line_id.id, po_copy_data, context=context)

            if split.purchase_line_id.state == 'validated':
                wf_service.trg_validate(uid, 'purchase.order.line', new_line_id, 'validated', cr)

            if split.purchase_line_id.state in ['draft', 'validated', 'validated_n'] and split.purchase_line_id.linked_sol_id:
                self.pool.get('purchase.order.line').update_fo_lines(cr, uid, split.purchase_line_id.id, context=context)

                new_sol = self.pool.get('purchase.order.line').browse(cr, uid, new_line_id, fields_to_fetch=['linked_sol_id'], context=context).linked_sol_id.id
                wf_service.trg_validate(uid, 'sale.order.line', new_sol, 'sourced_v', cr)

            if context.get('from_simu_screen') or context.get('return_new_line_id'):
                return new_line_id

        if context.get('from_simu_screen'):
            return False

        return {'type': 'ir.actions.act_window_close'}

    def line_qty_change(self, cr, uid, ids, original_qty, new_line_qty, context=None):
        '''
        Update the old line qty according to the new line qty
        '''
        value = {'old_line_qty': original_qty - new_line_qty}
        result = {'value': value}

        if ids:
            line = self.browse(cr, uid, ids[0], context=context)
            result = self.pool.get('product.uom')._change_round_up_qty(cr, uid, line.purchase_line_id.product_uom.id, new_line_qty, 'new_line_qty', result=result)

        return result

split_purchase_order_line_wizard()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
