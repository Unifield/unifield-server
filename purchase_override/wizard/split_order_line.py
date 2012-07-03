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
            # has_corresponding_so_line_split_po_line_wizard
            sol_ids = []
            if obj.purchase_line_id:
                if obj.purchase_line_id.procurement_id:
                    # look for corresponding sale order line
                    sol_ids = sol_obj.search(cr, uid, [('procurement_id', '=', obj.purchase_line_id.procurement_id.id)], context=context)
            # true if we get some sale order lines
            result[obj.id].update({'has_corresponding_so_line_split_po_line_wizard': sol_ids and True or False})
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
        'has_corresponding_so_line_split_po_line_wizard': fields.function(_vals_get, method=True, type='boolean', string='Has Corresponding So', multi='get_vals_split_po_line', store=False, readonly=True),
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
        line_obj = self.pool.get('purchase.order.line')

        if not context:
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
                line_obj.write(cr, uid, [split.purchase_line_id.id], {'product_qty': split.original_qty - split.new_line_qty,
                                                                      'price_unit': split.purchase_line_id.price_unit,}, context=context)
                # we treat two different cases
                # 1) the check box impact corresponding Fo is checked
                #    we create a Fo line by copying related Fo line. we then execute procurement creation function, and process the procurement
                #    the merge into the actual Po is forced
                bool = split.has_corresponding_so_line_split_po_line_wizard
                
                # 2) the check box impatc corresponding Fo is not check or does not apply (po from scratch or from replenishment),
                #    a new line is simply created
                # Create the new line
                new_line_id = line_obj.copy(cr, uid, split.purchase_line_id.id, {'parent_line_id': split.purchase_line_id.id,
                                                                                 'change_price_manually': split.purchase_line_id.change_price_manually,
                                                                                 'price_unit': split.purchase_line_id.price_unit,
                                                                                 'line_number': None,
                                                                                 'product_qty': split.new_line_qty}, context=context)

        return {'type': 'ir.actions.act_window_close'}

    def line_qty_change(self, cr, uid, ids, original_qty, new_line_qty, context=None):
        '''
        Update the old line qty according to the new line qty
        '''
        res = {'old_line_qty': original_qty - new_line_qty}

        return {'value': res}

split_purchase_order_line_wizard()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
