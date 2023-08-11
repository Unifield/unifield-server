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

class internal_picking_processor(osv.osv):
    """
    Internal move processing wizard
    """
    _name = 'internal.picking.processor'
    _inherit = 'stock.picking.processor'
    _description = 'Wizard to process Internal move'

    def _get_chained_picking(self, cr, uid, ids, field_name, args, context=None):
        """
        Get the value of the field 'chained_from_in_stock_picking' of the stock.picking
        """
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        res = {}

        for pick in self.browse(cr, uid, ids, context=context):
            res[pick.id] = pick.picking_id.chained_from_in_stock_picking

        return res

    _columns = {
        'move_ids': fields.one2many(
            'internal.move.processor',
            'wizard_id',
            string='Moves',
        ),
        'register_a_claim': fields.boolean(
            string='Register a Claim to Supplier',
        ),
        'claim_in_has_partner_id': fields.boolean(
            string='IN has Partner specified.',
            readonly=True,
        ),
        'claim_partner_id': fields.many2one(
            'res.partner',
            string='Supplier',
            required=False,
        ),
        'claim_type': fields.selection(
            lambda s, cr, uid, context={}: s.pool.get('return.claim').get_claim_event_type(),
            string='Claim Type',
        ),
        'claim_replacement_picking_expected': fields.boolean(
            string='Replacement expected for Claim ?',
            help="An Incoming Shipment will be automatically created corresponding to returned products.",
        ),
        'claim_description': fields.text(
            string='Claim Description',
        ),
        'chained_from_in_stock_picking': fields.function(
            _get_chained_picking,
            method=True,
            string='Chained Internal Picking from IN',
            type='boolean',
            readonly=True,
        ),
        'draft': fields.boolean('Draft'),
    }

    def default_get(self, cr, uid, fields_list=None, context=None, from_web=False):
        """
        Get default value for the object
        """
        if context is None:
            context = {}

        if fields_list is None:
            fields_list = []

        res = super(internal_picking_processor, self).default_get(cr, uid, fields_list=fields_list, context=context, from_web=from_web)

        res.update({
            'register_a_claim': False,
            'claim_replacement_picking_expected': False,
        })

        return res

    """
    Model methods
    """
    def create(self, cr, uid, vals, context=None):
        """
        Add default values
        """
        # Objects
        pick_obj = self.pool.get('stock.picking')

        vals['claim_in_has_partner_id'] = False

        if vals.get('picking_id', False):
            picking = pick_obj.browse(cr, uid, vals.get('picking_id'), context=context)
            if not vals.get('claim_partner_id', False):
                if picking.chained_from_in_stock_picking:
                    vals['claim_partner_id'] = picking.corresponding_in_picking_stock_picking.partner_id2.id

            if not vals.get('claim_in_has_partner_id', False):
                if picking.chained_from_in_stock_picking:
                    vals['claim_in_has_partner_id'] = picking.corresponding_in_picking_stock_picking.partner_id2 and True or False

        return super(internal_picking_processor, self).create(cr, uid, vals, context=context)


    def check_destination_location(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        for wizard in self.browse(cr, uid, ids, context=context):
            for line in wizard.move_ids:
                if line.move_id and not line.move_id.location_dest_id.active:
                    raise osv.except_osv(_('Error'), _('Warning, destination location is no longer active, please select an active location'))

        return True


    def do_partial(self, cr, uid, ids, context=None):
        """
        Made some integrity check on lines and run the do_incoming_shipment of stock.picking
        """
        # Objects
        picking_obj = self.pool.get('stock.picking')

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        if not ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        # disable "save as draft":
        self.write(cr, uid, ids, {'draft': False}, context=context)

        wizard_brw_list = self.browse(cr, uid, ids, context=context)

        if wizard_brw_list[0].picking_id.type != 'internal':
            raise osv.except_osv(
                _('Error'),
                _('This object: %s is not an Internal Move') % (wizard_brw_list[0].picking_id.name)
            )

        self.integrity_check_quantity(cr, uid, wizard_brw_list, context)
        self.integrity_check_prodlot(cr, uid, wizard_brw_list, context=context)
        self.check_destination_location(cr, uid, ids, context=context)
        # call stock_picking method which returns action call
        res = picking_obj.do_partial(cr, uid, ids, context=context)
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

        if isinstance(ids, int):
            ids = [ids]

        if not ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        view_by_pick_type = {
            'in': ('view_picking_in_form', _('Incoming Shipments')),
            'internal': ('view_picking_form', _('Internal Moves')),
            'out': ('view_picking_out_form', _('Delivery Orders')),
            'picking': ('view_picking_ticket_form', _('Picking Tickets')),
        }

        # Res
        res = kwargs['res']

        for wizard in self.browse(cr, uid, ids, context=context):
            if wizard.register_a_claim:
                # id of treated picking (can change according to backorder or not)
                pick_id = list(res.values())[0]['delivered_picking']
                pick = self.pool.get('stock.picking').browse(cr, uid, pick_id, context=context)
                pick_type = pick.type
                if pick_type == 'out' and pick.subtype == 'picking':
                    pick_type = pick.subtype
                    pick_view = view_by_pick_type.get(pick_type, [False])[0]
                    view_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', pick_view)
                else:
                    view_id = data_obj.get_object_reference(cr, uid, 'stock', view_by_pick_type.get(pick_type, [False])[0])
                view_id = view_id and view_id[1] or False
                return {'name': view_by_pick_type.get(pick_type, [None, _('Delivery Orders')])[1],
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

    def integrity_check_prodlot(self, cr, uid, wizards, context=None):
        """
        Check if the processed quantities are not larger than the available quantities

        :ptype wizards: A browse_record_list or a browse_record
        """
        # Objects
        uom_obj = self.pool.get('product.uom')
        lot_obj = self.pool.get('stock.production.lot')

        if context is None:
            context = {}

        if not isinstance(wizards, list):
            wizards = [wizards]

        if not wizards:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        lot_integrity = {}

        for wizard in wizards:
            for line in wizard.move_ids:
                if line.quantity <= 0.00:
                    continue

                if line.prodlot_id:
                    if line.location_id:
                        context['location_id'] = line.location_id.id
                    lot = lot_obj.browse(cr, uid, line.prodlot_id.id, context=context)

                if line.location_id and line.prodlot_id:
                    lot_integrity.setdefault(line.prodlot_id.id, {})
                    lot_integrity[line.prodlot_id.id].setdefault(line.location_id.id, 0.00)

                    if line.uom_id.id != line.prodlot_id.product_id.uom_id.id:
                        product_qty = uom_obj._compute_qty(cr, uid, line.uom_id.id, line.quantity, line.prodlot_id.product_id.uom_id.id)
                    else:
                        product_qty = line.quantity

                    lot_integrity[line.prodlot_id.id][line.location_id.id] += product_qty

                    if lot.stock_available < product_qty:
                        raise osv.except_osv(
                            _('Processing Error'),
                            _('Processing quantity %d %s for %s is larger than the available quantity in Batch Number %s (%d) !') \
                            % (line.quantity, line.uom_id.name, line.product_id.name, lot.name, lot.stock_available)
                        )

        # Check batches quantity integrity
        for lot in lot_integrity:
            for location in lot_integrity[lot]:
                tmp_lot = lot_obj.browse(cr, uid, lot, context={'location_id': location})
                lot_qty = tmp_lot.stock_available
                if lot_qty < lot_integrity[lot][location]:
                    raise osv.except_osv(
                        _('Processing Error'), \
                        _('Processing quantity %d for %s is larger than the available quantity in Batch Number %s (%d) !')\
                        % (lot_integrity[lot][location], tmp_lot.product_id.name, tmp_lot.name, lot_qty
                           ))

        return True

    def integrity_check_quantity(self, cr, uid, wizards, context=None):
        """
        Check if the processed quantities are not larger than the available quantities
        in lots.

        :ptype wizards: A browse_record_list or a browse_record
        """
        # Objects
        proc_line_obj = self.pool.get(self._columns['move_ids']._obj)

        if context is None:
            context = {}

        if not isinstance(wizards, list):
            wizards = [wizards]

        if not wizards:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        res = {}
        partial_and_signed = False
        to_unlink = []

        for proc in wizards:
            total_qty = 0.00

            l_ids = []
            for line in proc.move_ids:
                l_ids.append(line.id)
                # if no quantity, don't process the move
                if not line.quantity:
                    to_unlink.append(line.id)
                    continue

                if line.integrity_status != 'empty':
                    raise osv.except_osv(
                        _('Processing Error'),
                        _('Line %s: %s') % (line.line_number, proc_line_obj.get_selection(cr, uid, line, 'integrity_status'))
                    )

                # We cannot change the product on create picking wizard
                if line.product_id.id != line.move_id.product_id.id:
                    raise osv.except_osv(
                        _('Processing Error'),
                        _('Line %s: The product is wrong - Should be the same as initial move') % line.line_number,
                    )

                total_qty += line.quantity

            if not total_qty:
                raise osv.except_osv(
                    _('Processing Error'),
                    _('You have to enter the quantities you want to process before processing the move.'),
                )

            # Add the warning if there's a signed signature during partial processing
            if self._name == 'outgoing.delivery.processor' and l_ids and proc.picking_id.signature_id \
                    and not proc.partial_process_sign:
                cr.execute("""
                    SELECT mp.id FROM outgoing_delivery_move_processor mp 
                            LEFT JOIN outgoing_delivery_processor op ON mp.wizard_id = op.id 
                            LEFT JOIN stock_picking p ON op.picking_id = p.id
                        , signature s LEFT JOIN signature_line sl ON sl.signature_id = s.id
                    WHERE s.signature_res_id = p.id AND s.signature_res_model = 'stock.picking' AND s.signature_res_id = %s 
                        AND mp.id IN %s AND sl.signed = 't' AND op.picking_id = %s 
                        AND mp.quantity < mp.ordered_quantity LIMIT 1
                """, (proc.picking_id.id, tuple(l_ids), proc.picking_id.id))
                if cr.fetchone():
                    partial_and_signed = True
                    self.write(cr, uid, proc.id, {'partial_process_sign': True}, context=context)
                    res = {
                        'type': 'ir.actions.act_window',
                        'res_model': self._name,
                        'res_id': proc.id,
                        'view_type': 'form',
                        'view_mode': 'form',
                        'target': 'new',
                        'view_id': [self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_outgoing',
                                                                                        'outgoing_delivery_processor_form_view')[1]],
                        'context': context,
                    }

        # Remove non-used lines if the lines are not partially processed when the document is signed
        if to_unlink and not partial_and_signed:
            proc_line_obj.unlink(cr, uid, to_unlink, context=context)

        return res

    def do_reset(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        if not ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        pick_id = []
        for proc in self.browse(cr, uid, ids, context=context):
            pick_id = proc['picking_id']['id']

        self.write(cr, uid, ids, {'draft': False}, context=context)

        return self.pool.get('stock.picking').action_process(cr, uid, pick_id, context=context)

    def do_save_draft(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        if not ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        self.write(cr, uid, ids, {'draft': True}, context=context)

        return {}

internal_picking_processor()


class internal_move_processor(osv.osv):
    """
    Internal picking moves processing wizard
    """
    _name = 'internal.move.processor'
    _inherit = 'stock.move.processor'
    _description = 'Wizard lines for internal picking processor'

    def _get_integrity_status(self, cr, uid, ids, field_name, args, context=None):
        """
        Check the integrity of the processed move according to entered data
        """
        # Objects
        uom_obj = self.pool.get('product.uom')

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        res = super(internal_move_processor, self)._get_integrity_status(cr, uid, ids, field_name, args, context=context)

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
        return super(internal_move_processor, self)._get_move_info(cr, uid, ids, field_name, args, context=context)

    def _get_product_info(self, cr, uid, ids, field_name, args, context=None):
        return super(internal_move_processor, self)._get_product_info(cr, uid, ids, field_name, args, context=context)

    _columns = {
        # Parent wizard
        'wizard_id': fields.many2one(
            'internal.picking.processor',
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
                'internal.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
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
                'internal.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
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
                'internal.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
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
                'internal.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
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
                'internal.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
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
                'internal.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
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
                'internal.move.processor': (
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
                'internal.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
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
                'internal.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
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
                'internal.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
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
                'internal.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
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
                'internal.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
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
                'internal.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
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
                'internal.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
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
                'internal.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="Ticked if the product is a Dangerous Good",
        ),
        'np_check': fields.function(
            _get_product_info,
            method=True,
            sstring='CS',
            type='char',
            size=8,
            store={
                'internal.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="Ticked if the product is a Controlled Substance",
        ),
    }

internal_move_processor()

