# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 TeMPO Consulting, MSF
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

from osv import fields
from osv import osv

import netsvc


class sale_order(osv.osv):
    """
    Override the sale.order object to add some feature
    of the Order Sourcing Tool
    """
    _name = 'sale.order'
    _inherit = 'sale.order'

    _columns = {
        'sourcing_trace_ok': fields.boolean(
            string='Display sourcing logs',
        ),
        'sourcing_trace': fields.text(
            string='Sourcing logs',
            readonly=True,
        ),
    }

    def copy(self, cr, uid, order_id, default=None, context=None):
        """
        Copy the sale.order. When copy the sale.order, re-set the
        sourcing logs.

        :param cr: Cursor to the database
        :param uid: ID of the user that launches the method
        :param order_id: ID of the sale.order to copy
        :param default: Default values to put on the new sale.order
        :param context: Context of the call

        :return ID of the new sale.order
        :rtype integer
        """
        if context is None:
            context = {}

        if default is None:
            default = {}

        default.update({
            'sourcing_trace': '',
            'sourcing_trace_ok': False,
        })

        return super(sale_order, self).copy(cr, uid, order_id, default, context)

    # TODO: TO REFACTORE
    def _hook_ship_create_procurement_order(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_ship_create method from sale>sale.py

        - allow to modify the data for procurement order creation
        '''
        result = super(sale_order, self)._hook_ship_create_procurement_order(cr, uid, ids, context=context, *args, **kwargs)
        line = kwargs['line']

        # new field representing selected partner from sourcing tool
        result['supplier'] = line.supplier and line.supplier.id or False
        if line.po_cft:
            result.update({'po_cft': line.po_cft})
        # uf-583 - the location defined for the procurementis input instead of stock if the procurement is on order
        # if from stock, the procurement search from products in the default location: Stock
        order = kwargs['order']
        if line.type == 'make_to_order':
            result['location_id'] = order.shop_id.warehouse_id.lot_input_id.id,

        return result

    # TODO: TO REFACTORE
    def _hook_procurement_create_line_condition(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_ship_create method from sale>sale.py

        - allow to customize the execution condition
        '''
        line = kwargs['line']
        result = super(sale_order, self)._hook_procurement_create_line_condition(cr, uid, ids, context=context, *args, **kwargs)

        # if make_to_stock and procurement_request, no procurement is created
        return result and not(line.type == 'make_to_stock' and line.order_id.procurement_request)

    # TODO: TO REFACTORE
    def do_order_confirm_method(self, cr, uid, ids, context=None):
        '''
        trigger the workflow
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # objects
        wf_service = netsvc.LocalService("workflow")
        sol_obj = self.pool.get('sale.order.line')

        # we confirm (validation in unifield) the sale order
        # we set all line state to 'sourced' of the original Fo
        for obj in self.browse(cr, uid, ids, context=context):
            for line in obj.order_line:
                sol_obj.write(cr, uid, [line.id], {'state': 'sourced'}, context=context)
            # trigger workflow signal
            wf_service.trg_validate(uid, 'sale.order', obj.id, 'order_confirm', cr)

        return True

sale_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
