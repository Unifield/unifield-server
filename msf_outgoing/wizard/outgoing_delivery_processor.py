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
import time

class outgoing_delivery_processor(osv.osv):
    """
    Outgoing delivery processing wizard
    """
    _name = 'outgoing.delivery.processor'
    _inherit = 'internal.picking.processor'
    _description = 'Wizard to process Outgoing Delivery'

    _columns = {
        'move_ids': fields.one2many(
            'outgoing.delivery.move.processor',
            'wizard_id',
            string='Moves',
        ),
    }

    """
    Model methods
    """
    def do_partial(self, cr, uid, ids, context=None):
        """
        Made some integrity check on lines and run the do_incoming_shipment of stock.picking
        """
        # Objects
        picking_obj = self.pool.get('stock.picking')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if not ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        wizard_brw_list = self.browse(cr, uid, ids, context=context)

        self.integrity_check_quantity(cr, uid, wizard_brw_list, context)
        self.integrity_check_prodlot(cr, uid, wizard_brw_list, context=context)
        # call stock_picking method which returns action call
        res = picking_obj.do_partial(cr, uid, ids, context=context)
        return self.return_hook_do_partial(cr, uid, ids, context=context, res=res)

    def return_hook_do_partial(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the do_partial method from stock_override>wizard>stock_partial_picking.py>stock_partial_picking

        - allow to modify returned value from button method
        '''
        # Objects
        data_obj = self.pool.get('ir.model.data')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if not ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        # Res
        res = kwargs['res']

        for wizard in self.browse(cr, uid, ids, context=context):
            if wizard.register_a_claim:
                view_id = data_obj.get_object_reference(cr, uid, 'stock', 'view_picking_out_form')
                view_id = view_id and view_id[1] or False
                # id of treated picking (can change according to backorder or not)
                pick_id = res.values()[0]['delivered_picking']
                return {'name': _('Delivery Orders'),
                        'view_mode': 'form,tree',
                        'view_id': [view_id],
                        'view_type': 'form',
                        'res_model': 'stock.picking',
                        'res_id': pick_id,
                        'type': 'ir.actions.act_window',
                        'target': 'crash',
                        'domain': '[]',
                        'context': context}

        return {'type': 'ir.actions.act_window_close'}

outgoing_delivery_processor()


class outgoing_delivery_move_processor(osv.osv):
    """
    Outgoing delivery moves processing wizard
    """
    _name = 'outgoing.delivery.move.processor'
    _inherit = 'internal.move.processor'
    _description = 'Wizard lines for outgoing delivery processor'

    def _get_integrity_status(self, cr, uid, ids, field_name, args, context=None):
        """
        Check the integrity of the processed move according to entered data
        """
        # Objects
        uom_obj = self.pool.get('product.uom')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = super(outgoing_delivery_move_processor, self)._get_integrity_status(cr, uid, ids, field_name, args, context=context)

        for line in self.browse(cr, uid, ids, context=context):
            res_value = res[line.id]
            move = line.move_id

            if line.quantity <= 0.00:
                continue

            if line.uom_id.id != move.product_uom.id:
                quantity = uom_obj._compute_qty(cr, uid, line.uom_id.id, line.quantity, line.ordered_uom_id.id)
            else:
                quantity = line.quantity

            if quantity > move.product_qty:
                res_value = 'too_many'

            res[line.id] = res_value

        return res

    _columns = {
        # Parent wizard
        'wizard_id': fields.many2one(
            'outgoing.delivery.processor',
            string='Wizard',
            required=True,
            readonly=True,
            select=True,
            ondelete='cascade',
        ),
    }

outgoing_delivery_move_processor()

