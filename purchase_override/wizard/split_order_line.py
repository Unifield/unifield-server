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

from tools.translate import _
import netsvc

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

        # objects
        sol_obj = self.pool.get('sale.order.line')

        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {}
            # corresponding_so_line_id_split_po_line_wizard
            sol_ids = []
            if obj.purchase_line_id:
                if obj.purchase_line_id.procurement_id:
                    # look for corresponding sale order line
                    sol_ids = sol_obj.search(cr, uid, [('procurement_id', '=', obj.purchase_line_id.procurement_id.id)], context=context)
                    assert len(sol_ids) <= 1, 'split purchase line: the number of corresponding sale order line is greater than 1: %s'%len(sol_ids)
            # true if we get some sale order lines
            result[obj.id].update({'corresponding_so_line_id_split_po_line_wizard': sol_ids and sol_ids[0] or False})
            # corresponding_so_id_split_po_line_wizard
            so_id = False
            if sol_ids:
                datas = sol_obj.read(cr, uid, sol_ids, ['order_id'], context=context)
                for data in datas:
                    if data['order_id']:
                        so_id = data['order_id'][0]
            # write the value
            result[obj.id].update({'corresponding_so_id_split_po_line_wizard': so_id})
        return result

    _columns = {
        'purchase_line_id': fields.many2one('purchase.order.line', string='Line Id', readonly=True),
        'original_qty': fields.float(digits=(16,2), string='Original Quantity', readonly=True),
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
        # objects
        wf_service = netsvc.LocalService("workflow")
        po_line_obj = self.pool.get('purchase.order.line')
        so_line_obj = self.pool.get('sale.order.line')
        so_obj = self.pool.get('sale.order')
        move_obj = self.pool.get('stock.move')
        proc_obj = self.pool.get('procurement.order')

        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

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
                # Change the qty of the old line
                po_line_obj.write(cr, uid, [split.purchase_line_id.id], {'product_qty': split.original_qty - split.new_line_qty,
                                                                         'price_unit': split.purchase_line_id.price_unit,}, context=context)
                # Change the qty on the linked procurement order
                #if split.purchase_line_id.procurement_id:
                #    proc_obj.write(cr, uid, [split.purchase_line_id.procurement_id.id], {'product_qty': split.original_qty - split.new_line_qty})

                # we treat two different cases
                # 1) the check box impact corresponding Fo is checked
                #    we create a Fo line by copying related Fo line. we then execute procurement creation function, and process the procurement
                #    the merge into the actual Po is forced
                # if Internal Request, we do not update corresponding Internal Request
                link_wiz = split.corresponding_so_line_id_split_po_line_wizard
                external_ir = link_wiz and link_wiz.order_id and (not link_wiz.order_id.procurement_request or link_wiz.order_id.location_requestor_id.usage == 'customer')
                if split.corresponding_so_line_id_split_po_line_wizard and split.impact_so_split_po_line_wizard and external_ir:
                    # copy the original sale order line, reset po_cft to 'po' (we don't want a new tender if any)
                    so_copy_data = {'line_number': split.corresponding_so_line_id_split_po_line_wizard.line_number, # the Fo is not draft anyway, following sequencing policy, split Fo line maintains original one
                                    'po_cft': 'po',
                                    'product_uom_qty': split.new_line_qty,
                                    'product_uos_qty': split.new_line_qty,
                                    'so_back_update_dest_po_id_sale_order_line': split.purchase_line_id.order_id.id,
                                    'so_back_update_dest_pol_id_sale_order_line': split.purchase_line_id.id,
                                    }
                    new_so_line_id = so_line_obj.copy(cr, uid, split.corresponding_so_line_id_split_po_line_wizard.id, so_copy_data, context=dict(context, keepDateAndDistrib=True))
                    so_line_obj.write(cr, uid, new_so_line_id, {
                        'supplier': split.corresponding_so_line_id_split_po_line_wizard.supplier.id,
                        'type': 'make_to_order',
                        'is_line_split': True,
                    }, context=context)
                    # change the initial qty on the initial FO line
                    so_line_obj.write(cr, uid, split.corresponding_so_line_id_split_po_line_wizard.id, {
                        'product_uom_qty': split.original_qty - split.new_line_qty,
                        'product_uos_qty': split.original_qty - split.new_line_qty,
                    }, context=dict(context, keepDateAndDistrib=True))
                    # call the new procurement creation method
                    so_obj.action_ship_proc_create(cr, uid, [split.corresponding_so_id_split_po_line_wizard.id], context=context)
                    # run the procurement, the make_po function detects the link to original po
                    # and force merge the line to this po (even if it is not draft anymore)
                    # run the procurement, the make_po function detects the link to original po
                    # and force merge the line to this po (even if it is not draft anymore)
                    new_data_so = so_line_obj.read(cr, uid, [new_so_line_id], ['procurement_id', 'line_number', 'sync_order_line_db_id'], context=context)
                    new_proc_id = new_data_so[0]['procurement_id'][0]

                    if external_ir and split.purchase_line_id and split.purchase_line_id.move_dest_id:
                        move = move_obj.browse(cr, uid, split.purchase_line_id.move_dest_id.id, context=context)
                        proc_move_id = proc_obj.read(cr, uid, new_proc_id, ['move_id'], context=context)['move_id'][0]
                        new_move_id = move.id

                        if move.product_qty > split.new_line_qty:
                            new_move_id = move_obj.copy(cr, uid, move.id, {'product_qty': split.new_line_qty,
                                                                           'product_uos_qty': split.new_line_qty,
                                                                           'line_number': new_data_so[0]['line_number'],
                                                                           'sale_line_id': new_so_line_id}, context=context)
                            move_obj.action_confirm(cr, uid, [new_move_id], context=context)

                            move_obj.write(cr, uid, [move.id], {'product_qty': move.product_qty - split.new_line_qty,
                                                                'product_uos_qty': move.product_qty - split.new_line_qty}, context=context)
                        else:
                            # No update of OUT when IN is received to avoid more qty than expected
                            move_obj.write(cr, uid, [move.id], {'processed_stock_move': True}, context=context)

                        move_obj.write(cr, uid, proc_move_id, {'state': 'draft'}, context=context)
                        proc_obj.write(cr, uid, [new_proc_id], {'close_move': False, 'move_id': new_move_id}, context=context)
                        move_obj.unlink(cr, uid, proc_move_id, context=context)

                    if link_wiz.order_id.partner_id.partner_type != 'external':
                        self.pool.get('sync.sale.order.line.split').create(cr, uid, {
                            'partner_id': link_wiz.order_id.partner_id.id,
                            'old_sync_order_line_db_id': link_wiz.sync_order_line_db_id,
                            'new_sync_order_line_db_id': new_data_so[0]['sync_order_line_db_id'],
                            'new_line_qty': split.new_line_qty,
                            'old_line_qty': split.original_qty,
                        }, context=context)

                    wf_service.trg_validate(uid, 'procurement.order', new_proc_id, 'button_check', cr)
                    new_po_ids = po_line_obj.search(cr, uid, [('procurement_id', '=', new_proc_id)], context=context)
                    if context.get('split_sync_order_line_db_id'):
                        po_line_obj.write(cr, uid, new_po_ids, {'sync_order_line_db_id': context.get('split_sync_order_line_db_id')}, context=context)
                    # if original po line is confirmed, we action_confirm new line
                    if split.purchase_line_id.state == 'confirmed':
                        # the correct line number according to new line number policy is set in po_line_values_hook of order_line_number/order_line_number.py/procurement_order
                        po_line_obj.action_confirm(cr, uid, new_po_ids, context=context)
                        if context.get('from_simu_screen'):
                            return new_po_ids[0]
                else:
                    # 2) the check box impact corresponding Fo is not check or does not apply (po from scratch or from replenishment),
                    #    a new line is simply created
                    # Create the new line
                    move_dest_id = split.purchase_line_id.move_dest_id and split.purchase_line_id.move_dest_id.id or False
                    sale_line_id = split.corresponding_so_line_id_split_po_line_wizard and split.corresponding_so_line_id_split_po_line_wizard.id or False
                    proc_id = split.corresponding_so_line_id_split_po_line_wizard.procurement_id and split.corresponding_so_line_id_split_po_line_wizard.procurement_id.id or False
                    if split.purchase_line_id.procurement_id and move_dest_id and not link_wiz.order_id.procurement_request:
                        new_dest_id = move_obj.copy(cr, uid, move_dest_id, {'product_qty': split.new_line_qty}, context=context)
                        move_obj.action_confirm(cr, uid, [new_dest_id])
                        move_obj.write(cr, uid, [move_dest_id], {'product_qty': split.original_qty - split.new_line_qty}, context=context)
                        move_dest_id = new_dest_id

                        new_proc_id = proc_obj.copy(cr, uid, split.purchase_line_id.procurement_id.id, {
                            'product_qty': split.new_line_qty,
                            'purchase_id': split.purchase_line_id.order_id.id,
                            'move_id': new_dest_id,
                            'from_splitted_po_line': True,
                        }, context=context)
                        proc_obj.write(cr, uid, [split.purchase_line_id.procurement_id.id], {
                            'product_qty': split.original_qty - split.new_line_qty,
                        }, context=context)
                        wf_service.trg_validate(uid, 'procurement.order', new_proc_id, 'button_confirm', cr)
                        wf_service.trg_validate(uid, 'procurement.order', new_proc_id, 'button_check', cr)
                        proc_id = new_proc_id

                    po_copy_data = {'is_line_split': True, # UTP-972: Indicate only that the line is a split one
                                    'change_price_manually': split.purchase_line_id.change_price_manually,
                                    'price_unit': split.purchase_line_id.price_unit,
                                    'move_dest_id': move_dest_id,
                                    'sale_line_id': sale_line_id,
                                    'procurement_id': proc_id,
                                    'product_qty': split.new_line_qty}
                    # following new sequencing policy, we check if resequencing occur (behavior 1).
                    # if not (behavior 2), the split line keeps the same line number as original line
                    if not po_line_obj.allow_resequencing(cr, uid, [split.purchase_line_id.id], context=context):
                        # set default value for line_number as the same as original line
                        po_copy_data.update({'line_number': split.purchase_line_id.line_number})

                    new_line_ids = []
                    if split.purchase_line_id.procurement_id and move_dest_id and not link_wiz.order_id.procurement_request:
                        new_line_ids = po_line_obj.search(cr, uid, [('procurement_id', '=', new_proc_id)], context=context)
                        po_line_obj.write(cr, uid, new_line_ids, po_copy_data, context=context)
                    else:
                        # copy original line
                        new_line_id = po_line_obj.copy(cr, uid, split.purchase_line_id.id, po_copy_data, context=context)
                        new_line_ids.append(new_line_id)
                    # if original po line is confirmed, we action_confirm new line
                    if split.purchase_line_id.state == 'confirmed':
                        po_line_obj.action_confirm(cr, uid, new_line_ids, context=context)

                    if context.get('from_simu_screen'):
                        return new_line_ids[0]

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
