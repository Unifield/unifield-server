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

from msf_outgoing import INTEGRITY_STATUS_SELECTION

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
        'draft': fields.boolean('Draft'),
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

        # disable "save as draft":
        self.write(cr, uid, ids, {'draft': False}, context=context)

        wizard_brw_list = self.browse(cr, uid, ids, context=context)

        qty_check_res = self.integrity_check_quantity(cr, uid, wizard_brw_list, context)
        if qty_check_res and qty_check_res.get('view_id'):
            return qty_check_res
        self.integrity_check_prodlot(cr, uid, wizard_brw_list, context=context)
        # call stock_picking method which returns action call
        res = picking_obj.do_partial_out(cr, uid, ids, context=context)
        return self.return_hook_do_partial(cr, uid, ids, context=context, res=res)

    def return_hook_do_partial(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.

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

    def do_reset(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        pick_id = []
        for proc in self.browse(cr, uid, ids, context=context):
            pick_id = proc['picking_id']['id']

        self.write(cr, uid, ids, {'draft': False, 'partial_process_sign': False}, context=context)

        return self.pool.get('stock.picking').action_process(cr, uid, pick_id, context=context)

    def do_save_draft(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        self.write(cr, uid, ids, {'draft': True}, context=context)

        return {}

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

    def _get_move_info(self, cr, uid, ids, field_name, args, context=None):
        return super(outgoing_delivery_move_processor, self)._get_move_info(cr, uid, ids, field_name, args, context=context)

    def _get_product_info(self, cr, uid, ids, field_name, args, context=None):
        return super(outgoing_delivery_move_processor, self)._get_product_info(cr, uid, ids, field_name, args, context=context)

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
        'ordered_product_id': fields.function(
            _get_move_info,
            method=True,
            string='Ordered product',
            type='many2one',
            relation='product.product',
            store={
                'outgoing.delivery.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
            },
            readonly=True,
            help="Expected product to receive",
            multi='move_info',
        ),
        'comment': fields.function(
            _get_move_info,
            method=True,
            string='Comment',
            type='text',
            store={
                'outgoing.delivery.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
            },
            readonly=True,
            help="Comment of the move",
            multi='move_info',
        ),
        'ordered_uom_id': fields.function(
            _get_move_info,
            method=True,
            string='Ordered UoM',
            type='many2one',
            relation='product.uom',
            store={
                'outgoing.delivery.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
            },
            readonly=True,
            help="Expected UoM to receive",
            multi='move_info',
        ),
        'ordered_uom_category': fields.function(
            _get_move_info,
            method=True,
            string='Ordered UoM category',
            type='many2one',
            relation='product.uom.categ',
            store={
                'outgoing.delivery.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
            },
            readonly=True,
            help="Category of the expected UoM to receive",
            multi='move_info'
        ),
        'location_id': fields.function(
            _get_move_info,
            method=True,
            string='Location',
            type='many2one',
            relation='stock.location',
            store={
                'outgoing.delivery.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
            },
            readonly=True,
            help="Source location of the move",
            multi='move_info'
        ),
        'location_supplier_customer_mem_out': fields.function(
            _get_move_info,
            method=True,
            string='Location Supplier Customer',
            type='boolean',
            store={
                'outgoing.delivery.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
            },
            readonly=True,
            multi='move_info',
            help="",
        ),
        'integrity_status': fields.function(
            _get_integrity_status,
            method=True,
            string='',
            type='selection',
            selection=INTEGRITY_STATUS_SELECTION,
            store={
                'outgoing.delivery.move.processor': (
                    lambda self, cr, uid, ids, c=None: ids,
                    ['product_id', 'wizard_id', 'quantity', 'asset_id', 'prodlot_id', 'expiry_date'],
                    20
                ),
            },
            readonly=True,
            help="Integrity status (e.g: check if a batch is set for a line with a batch mandatory product...)",
        ),
        'type_check': fields.function(
            _get_move_info,
            method=True,
            string='Picking Type Check',
            type='char',
            size=32,
            store={
                'outgoing.delivery.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
            },
            readonly=True,
            help="Return the type of the picking",
            multi='move_info',
        ),
        'lot_check': fields.function(
            _get_product_info,
            method=True,
            string='B.Num',
            type='boolean',
            store={
                'outgoing.delivery.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="A batch number is required on this line",
        ),
        'exp_check': fields.function(
            _get_product_info,
            method=True,
            string='Exp.',
            type='boolean',
            store={
                'outgoing.delivery.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="An expiry date is required on this line",
        ),
        'asset_check': fields.function(
            _get_product_info,
            method=True,
            string='Asset',
            type='boolean',
            store={
                'outgoing.delivery.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="An asset is required on this line",
        ),
        'kit_check': fields.function(
            _get_product_info,
            method=True,
            string='Kit',
            type='boolean',
            store={
                'outgoing.delivery.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="A kit is required on this line",
        ),
        'kc_check': fields.function(
            _get_product_info,
            method=True,
            string='CC',
            type='char',
            size=8,
            store={
                'outgoing.delivery.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="Ticked if the product is a Cold Chain Item",
        ),
        'ssl_check': fields.function(
            _get_product_info,
            method=True,
            string='SSL',
            type='char',
            size=8,
            store={
                'outgoing.delivery.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="Ticked if the product is a Short Shelf Life product",
        ),
        'dg_check': fields.function(
            _get_product_info,
            method=True,
            string='DG',
            type='char',
            size=8,
            store={
                'outgoing.delivery.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="Ticked if the product is a Dangerous Good",
        ),
        'np_check': fields.function(
            _get_product_info,
            method=True,
            string='CS',
            type='char',
            size=8,
            store={
                'outgoing.delivery.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="Ticked if the product is a Controlled Substance",
        ),
    }

outgoing_delivery_move_processor()

