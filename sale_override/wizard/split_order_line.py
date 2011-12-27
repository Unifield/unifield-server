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

from tools.translate import _


class split_sale_order_line_wizard(osv.osv_memory):
    _name = 'split.sale.order.line.wizard'
    _description = 'Split sale order lines'

    _columns = {
        'sale_line_id': fields.many2one('sale.order.line', string='Line Id', readonly=True),
        'original_qty': fields.float(digits=(16,2), string='Original Quantity', readonly=True),
        'old_line_qty': fields.float(digits=(16,2), string='Old line quantity', readonly=True),
        'new_line_qty': fields.float(digits=(16,2), string='New line quantity', required=True),
    }

    _defaults = {
        'new_line_qty': lambda *a: 0.00,
    }

    def split_line(self, cr, uid, ids, context={}):
        '''
        Create a new order line and change the quantity of the old line
        '''
        line_obj = self.pool.get('sale.order.line')

        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for split in self.browse(cr, uid, ids, context=context):
            # Check if the sum of new line and old line qty is equal to the original qty
            if split.old_line_qty  > split.original_qty:
                raise osv.except_osv(_('Error'), _('You cannot have a new quantity different than the original quantity !'))
            # Change the qty of the old line
            line_obj.write(cr, uid, [split.sale_line_id.id], {'product_uom_qty': split.original_qty - split.new_line_qty}, context=context)
            # Create the new line
            new_line_id = line_obj.copy(cr, uid, split.sale_line_id.id, {'parent_line_id': split.sale_line_id.id,
                                                                         'product_uom_qty': split.new_line_qty}, context=context)

        return {'type': 'ir.actions.act_window_close'}

    def line_qty_change(self, cr, uid, ids, original_qty, new_line_qty, context={}):
        '''
        Update the old line qty according to the new line qty
        '''
        if new_line_qty > original_qty:
            raise osv.except_osv(_('Error'), _('You cannot have a new line quantity bigger than the original quantity'))
        elif new_line_qty == original_qty:
            raise osv.except_osv(_('Error'), _('You cannot have a new line quantity equal to the original quantity'))

        res = {'old_line_qty': original_qty - new_line_qty}

        return {'value': res}

split_sale_order_line_wizard()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
