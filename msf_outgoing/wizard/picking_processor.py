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

import time

from osv import fields
from osv import osv
from tools.translate import _

import decimal_precision as dp
from msf_outgoing import INTEGRITY_STATUS_SELECTION


class stock_picking_processor(osv.osv):
    """
    Generic picking processing wizard
    """
    _name = 'stock.picking.processor'
    _description = 'Wizard to process a picking ticket'
    _rec_name = 'date'

    _columns = {
        'date': fields.datetime(string='Date', required=True),
        'picking_id': fields.many2one(
            'stock.picking',
            string='Picking',
            required=True,
            readonly=True,
            help="Picking (incoming, internal, outgoing, picking ticket, packing...) to process",
            ),
        'move_ids': fields.one2many(
            'stock.move.processor',
            'wizard_id',
            string='Moves',
        ),
    }

    def default_get(self, cr, uid, fields_list=None, context=None):
        """
        Get default value for the object
        """
        if context is None:
            context = {}

        if fields_list is None:
            fields_list = []

        res = super(stock_picking_processor, self).default_get(cr, uid, fields_list=fields_list, context=context)

        res['date'] = time.strftime('%Y-%m-%d %H:%M:%S')

        return res

    def copy_all(self, cr, uid, ids, context=None):
        """
        Fill all lines with the original quantity as quantity
        """
        if isinstance(ids, (int, long)):
            ids = [ids]

        if not ids:
            raise osv.except_osv(
                _('Error'),
                _('No wizard found !'),
            )

        for wizard in self.browse(cr, uid, ids, context=context):
            for move in wizard.move_ids:
                self.pool.get(move._name).write(cr, uid, [move.id], {'quantity': move.ordered_quantity}, context=context)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Products to Process'),
            'res_model': wizard._name,
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
            'res_id': ids[0],
            'nodestroy': True,
            'context': context,
        }

    def uncopy_all(self, cr, uid, ids, context=None):
        """
        Fill all lines with 0.00 as quantity
        """
        if isinstance(ids, (int, long)):
            ids = [ids]

        if not ids:
            raise osv.except_osv(
                _('Error'),
                _('No wizard found !'),
            )

        for wizard in self.browse(cr, uid, ids, context=context):
            move_obj = wizard.move_ids[0]._name
            move_ids = [x.id for x in wizard.move_ids]
            self.pool.get(move_obj).write(cr, uid, move_ids, {'quantity': 0.00}, context=context)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Products to Process'),
            'res_model': wizard._name,
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
            'res_id': ids[0],
            'nodestroy': True,
            'context': context,
        }

stock_picking_processor()


class stock_move_processor(osv.osv):
    """
    Generic stock move processing wizard
    """
    _name = 'stock.move.processor'
    _description = 'Wizard line to process a move'
    _rec_name = 'line_number'

    def _get_move_info(self, cr, uid, ids, field_name, args, context=None):
        """
        Get some information about the move to process
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}

        for line in self.browse(cr, uid, ids, context=context):
            # Return an error if the move has no product defined
            if not line.move_id.product_id:
                raise osv.except_osv(
                    _('Data Error'),
                    _('The move you are trying to process has no product defined - Please set a product on it before process it.')
                )

            # Return an error if the move has no UoM
            if not line.move_id.product_uom:
                raise osv.except_osv(
                    _('Data Error'),
                    _('The move you are trying to process has no UoM defined - Please set an UoM on it before process it.')
                )

            loc_supplier = line.move_id.location_id.usage == 'supplier'
            loc_cust = line.move_id.location_dest_id.usage == 'customer'
            valid_pt = line.move_id.picking_id.type == 'out' and line.move_id.picking_id.subtype == 'picking' and line.move_id.picking_id.state != 'draft'

            res[line.id] = {
                'ordered_product_id': line.move_id.product_id.id,
                'ordered_quantity': line.move_id.product_qty,
                'ordered_uom_id': line.move_id.product_uom.id,
                'ordered_uom_category': line.move_id.product_uom.category_id.id,
                'location_id': line.move_id.location_id.id,
                'type_check': line.move_id.picking_id.type,
                'location_supplier_customer_mem_out': loc_supplier or loc_cust or valid_pt,
            }

        return res

    def _get_product_info(self, cr, uid, ids, field_name, args, context=None):
        """
        Ticked some checkboxes according to product parameters
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}

        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {
                'lot_check': False,
                'exp_check': False,
#                'asset_check': False,
                'kit_check': False,
                'kc_check': False,
                'ssl_check': False,
                'dg_check': False,
                'np_check': False,
            }

            if line.product_id:
                res[line.id] = {
                    'lot_check': line.product_id.batch_management,
                    'exp_check': line.product_id.perishable,
#                    'asset_check': line.product_id.type == 'product' and line.product_id.subtype == 'asset',
                    'kit_check': line.product_id.type == 'product' and line.product_id.subtype == 'kit' and not line.product_id.perishable,
                    'kc_check': line.product_id.heat_sensitive_item and True or False,
                    'ssl_check': line.product_id.short_shelf_life,
                    'dg_check': line.product_id.dangerous_goods,
                    'np_check': line.product_id.narcotic,
                }

        return res

    def _batch_integrity(self, line, res='empty'):
        """
        Check integrity of the batch/expiry date management according to line values
        """
        lot_manda = line.product_id.batch_management
        perishable = line.product_id.perishable
        if lot_manda:
            # Batch mandatory
            if not line.prodlot_id:
                # No batch defined
                res = 'missing_lot'
            elif line.prodlot_id.type != 'standard':
                # Batch defined by type is not good
                res = 'wrong_lot_type_need_standard'
            elif perishable:
                # Expiry date mandatory
                if not line.expiry_date:
                    # No expiry date defined
                    res = 'missing_date'
            elif line.prodlot_id:
                res = 'no_lot_needed'

        return res

    def _asset_integrity(self, line, res='empty'):
        """
        Check integrity of the asset management according to line values
        """
        # Asset is not mandatory for moves performed internally
        asset_mandatory = False
        if line.wizard_id.picking_id.type in ['out', 'in'] \
           and line.product_id.type == 'product' \
           and line.product_id.subtype == 'asset':
            asset_mandatory = True

        if asset_mandatory and not line.asset_id:
            res = 'missing_asset'
        elif not asset_mandatory and line.asset_id:
            res = 'not_asset_needed'

        return res

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

        res = {}

        for line in self.browse(cr, uid, ids, context=context):
            res_value = 'empty'
            # Validation is only needed if the line has been selected (qty > 0)
            if line.quantity > 0.00:
                # Batch management check
                # res_value = self._batch_integrity(line, res_value)
                # Asset management check
                # res_value = self._asset_integrity(line, res_value)
                # For internal or simple out, cannot process more than specified in stock move
                if line.wizard_id.picking_id.type in ['out', 'internal']:
                    proc_qty = uom_obj._compute_qty(cr, uid, line.uom_id.id, line.quantity, line.ordered_uom_id.id)
                    if proc_qty > line.ordered_quantity:
                        res_value = 'greater_than_available'
            elif line.quantity < 0.00:
                # Quantity cannot be negative
                res_value = 'must_be_greater_than_0'

            res[line.id] = res_value
        return res

    _columns = {
        'line_number': fields.integer(string='Line', required=True, readonly=True),
        # Parent wizard
        'wizard_id': fields.many2one(
            'stock.picking.processor',
            string='Wizard',
            required=True,
            readonly=True,
        ),
        'move_id': fields.many2one(
            'stock.move',
            string='Move',
            required=True,
            readonly=True,
            help="Move to process",
        ),
        'product_id': fields.many2one(
            'product.product',
            string='Product',
            required=True,
            readonly=True,
            help="Received product",
        ),
        'ordered_product_id': fields.function(
            _get_move_info,
            method=True,
            string='Ordered product',
            type='many2one',
            relation='product.product',
            store={
                'stock.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
            },
            readonly=True,
            help="Expected product to receive",
            multi='move_info',
        ),
        'quantity': fields.float(
            string='Quantity',
            digits_compute=dp.get_precision('Product UoM'),
            required=True,
        ),
        'ordered_quantity': fields.function(
            _get_move_info,
            method=True,
            string='Ordered quantity',
            type='float',
            store={
                'stock.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
            },
            readonly=True,
            help="Expected quantity to receive",
            multi='move_info',
        ),
        'uom_id': fields.many2one(
            'product.uom',
            string='UoM',
            required=True,
            readonly=True,
            help="Received UoM",
        ),
        'ordered_uom_id': fields.function(
            _get_move_info,
            method=True,
            string='Ordered UoM',
            type='many2one',
            relation='product.uom',
            store={
                'stock.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
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
                'stock.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
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
                'stock.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
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
                'stock.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
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
                'stock.move.processor': (
                    lambda self, cr, uid, ids, c=None: ids,
                    ['product_id', 'wizard_id', 'quantity', 'asset_id', 'prodlot_id', 'expiry_date'],
                    20
                ),
                'stock.move.in.processor': (
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
                'stock.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
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
                'stock.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
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
                'stock.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
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
                'stock.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
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
                'stock.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="A kit is required on this line",
        ),
        'kc_check': fields.function(
            _get_product_info,
            method=True,
            string='KC',
            type='boolean',
            store={
                'stock.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="Ticked if the product is a Heat Sensitive Item",
        ),
        'ssl_check': fields.function(
            _get_product_info,
            method=True,
            string='SSL',
            type='boolean',
            store={
                'stock.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="Ticked if the product is a Short Shelf Life product",
        ),
        'dg_check': fields.function(
            _get_product_info,
            method=True,
            string='DG',
            type='boolean',
            store={
                'stock.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="Ticked if the product is a Dangerous Good",
        ),
        'np_check': fields.function(
            _get_product_info,
            method=True,
            string='NP',
            type='boolean',
            store={
                'stock.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="Ticked if the product is a Narcotic",
        ),
        'prodlot_id': fields.many2one(
            'stock.production.lot',
            string='Batch number',
        ),
        'expiry_date': fields.date(string='Expiry date'),
#        'asset_id': fields.many2one(
#            'product.asset',
#            string='Asset',
#        ),
#        'composition_list_id': fields.many2one(
#            'composition.kit',
#            string='Kit',
#        ),
        'cost': fields.float(
            string='Cost',
            digits_compute=dp.get_precision('Purchase Price Computation'),
            required=True,
            help="Unit Cost for this product line",
        ),
        'currency': fields.many2one(
            'res.currency',
            string='Currency',
            readonly=True,
            help="Currency in which Unit cost is expressed",
        ),
        'change_reason': fields.char(size=256, string='Change reason'),
    }

    _defaults = {
        'quantity': 0.00,
    }

    def _fill_expiry_date(self, cr, uid, prodlot_id=False, expiry_date=False, vals=None, context=None):
        """
        Fill the expiry date with the expiry date of the batch if any
        """
        # Objects
        lot_obj = self.pool.get('stock.production.lot')

        if context is None:
            context = {}

        if vals is None:
            vals = {}

        if prodlot_id and not expiry_date:
            vals['expiry_date'] = lot_obj.read(cr, uid, prodlot_id, ['life_date'], context=context)['life_date']

        return vals

    def _update_split_wr_vals(self, vals):
        """
        Allow other modules to override the write values when split a line
        """
        return vals

    def _update_split_cp_vals(self, vals):
        """
        Allow other modules to override the copy values when split a line
        """
        return vals

    def _update_change_product_wr_vals(self, vals):
        """
        Allow other modules to override the write values when change product on a line
        """
        return vals

    """
    Model methods
    """
    def create(self, cr, uid, vals, context=None):
        """
        If a batch number is specified and the expiry date is empty, fill the expiry date
        with the expiry date of the batch
        """
        vals = self._fill_expiry_date(cr, uid, vals.get('prodlot_id', False), vals.get('expiry_date', False), vals=vals, context=context)
        return super(stock_move_processor, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        If a batch number is specified and the expiry date is empty, fill the expiry date
        with the expiry date of the batch
        """
        vals = self._fill_expiry_date(cr, uid, vals.get('prodlot_id', False), vals.get('expiry_date', False), vals=vals, context=context)
        return super(stock_move_processor, self).write(cr, uid, ids, vals, context=context)

    def split(self, cr, uid, ids, new_qty=0.00, uom_id=False, context=None):
        """
        Split the line according to new parameters
        """
        if isinstance(ids, (int, long)):
            ids = [ids]

        if not ids:
            raise osv.except_osv(
                _('Error'),
                _('No line to split !'),
            )

        # New quantity must be greater than 0.00
        if new_qty <= 0.00:
            raise osv.except_osv(
                _('Error'),
                _('Selected quantity must be greater than 0.00 !'),
            )

        pick_wiz_id = False
        for line in self.browse(cr, uid, ids, context=context):
            pick_wiz_id = line.wizard_id.id
            if new_qty > line.quantity_ordered:
                # Cannot select more than initial quantity
                raise osv.except_osv(
                    _('Error'),
                    _('Selected quantity (%0.1f %s) exceeds the initial quantity (%0.1f %s)') %
                    (new_qty, line.uom_id.name, line.quantity_ordered, line.uom_id.name),
                )
            elif new_qty == line.quantity_ordered:
                # Cannot select more than initial quantity
                raise osv.except_osv(
                    _('Error'),
                    _('Selected quantity (%0.1f %s) cannot be equal to the initial quantity (%0.1f %s)') %
                    (new_qty, line.uom_id.name, line.quantity_ordered, line.uom_id.name),
                )

            update_qty = line.quantity_ordered - new_qty
            wr_vals = {
                'quantity': line.quantity > update_qty and update_qty or line.quantity,
                'quantity_ordered': update_qty,
            }
            self._update_split_wr_vals(vals=wr_vals)  # w/o overriding, just return wr_vals
            self.write(cr, uid, [line.id], wr_vals, context=context)

            # Create a copy of the move_processor with the new quantity
            cp_vals = {
                'quantity': 0.00,
                'quantity_ordered': new_qty,
            }
            self._update_split_cp_vals(vals=cp_vals)  # w/o overriding, just return cp_vals
            self.copy(cr, uid, line.id, cp_vals, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking.processor',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': pick_wiz_id,
            'context': context,
        }

    def change_product(self, cr, uid, ids, change_reason='', product_id=False, context=None):
        """
        Change the product of the move processor
        """
        if isinstance(ids, (int, long)):
            ids = [ids]

        if not ids:
            raise osv.except_osv(
                _('Error'),
                _('No line to modify'),
            )

        if not change_reason or not product_id:
            raise osv.except_osv(
                _('Error'),
                _('You must select a new product and specify a reason.'),
            )

        wr_vals = {
            'change_reason': change_reason,
            'product_id': product_id,
        }
        self._update_change_product_wr_vals(vals=wr_vals)  # w/o overriding, just return wr_vals
        self.write(cr, uid, ids, wr_vals, context=context)

        pick_wiz_id = self.read(cr, uid, ids[0], ['wizard_id'], context=context)['wizard_id']

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking.processor',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': pick_wiz_id[0],
            'context': context,
        }

    """
    Controller methods
    """
    def onchange_uom_qty(self, cr, uid, ids, uom_id=False, quantity=0.00):
        """
        Check the round of the quantity according to the Unit Of Measure
        """
        # Objects
        uom_obj = self.pool.get('product.uom')

        if isinstance(ids, (int, long)):
            ids = [ids]

        new_qty = uom_obj._change_round_up_qty(cr, uid, uom_id, quantity, 'quantity')

        for line in self.browse(cr, uid, ids):
            cost = uom_obj._compute_price(cr, uid, line.uom_id.id, line.cost, to_uom_id=uom_id)
            new_qty.setdefault('value', {}).setdefault('cost', cost)

        return new_qty

    def change_lot(self, cr, uid, ids, lot_id, qty=0.00, location_id=False, uom_id=False, context=None):
        """
        If the batch number is changed, update the expiry date with the expiry date of the selected batch
        """
        # Objects
        lot_obj = self.pool.get('stock.production.lot')
        uom_obj = self.pool.get('product.uom')

        if context is None:
            context = {}

        res = {
            'value': {},
            'warning': {},
        }

        if uom_id:
            res = uom_obj._change_round_up_qty(cr, uid, uom_id, qty, 'quantity')

        qty = res.get('value', {}).get('quantity', 0.00)

        if not lot_id:
            res['value']['expiry_date'] = False
        else:
            # Change context
            if location_id:
                tmp_loc_id = context.get('location_id', False)
                context['location_id'] = location_id

            lot = lot_obj.browse(cr, uid, lot_id, context=context)
            res['value']['expiry_date'] = lot.life_date

            if qty and lot.stock_available < qty:
                res['warning'].update({
                    'title': _('Quantity error'),
                    'message': _('The quantity to process is larger than the available quantity in Batch %s') % lot.name,
                })

            # Reset the context with old values
            if location_id:
                context['location_id'] = tmp_loc_id

        return res

    def change_expiry(self, cr, uid, ids, expiry_date=False, product_id=False, type_check=False, context=None):
        """
        If the expiry date is changed, find the corresponding internal batch number
        """
        # Objects
        lot_obj = self.pool.get('stock.production.lot')

        res = {
            'value': {}
        }

        if expiry_date and product_id:
            lot_ids = lot_obj.search(cr, uid, [
                ('life_date', '=', expiry_date),
                ('type', '=', 'internal'),
                ('product_id', '=', product_id),
                ], context=context)
            if not lot_ids:
                if type_check == 'in':
                    # The corresponding production lot will be created afterwards
                    res['warning'].update({
                        'title': _('Information'),
                        'message': _('The selected Expiry Date does not exist in the system. It will be created during validation process.'),
                    })
                    # Clear batch number
                    res['value']['prodlot_id'] = False
                else:
                    # Display warning message
                    res['waring'].update({
                        'title': _('Error'),
                        'message': _('The selected Expiry Date does not exist in the system.'),
                    })
                    # Clear expiry date
                    res['value'].update({
                        'expiry_date': False,
                        'prodlot_id': False,
                    })
            else:
                # Return the first batch number
                res['value']['prodlot_id'] = lot_ids[0]
        else:
            # If the expiry date is clear, clear also the batch number
            res['value']['prodlot_id'] = False

        return res

    def open_change_product_wizard(self, cr, uid, ids, context=None):
        """
        Open the wizard to change the product: the user can select a new product
        """
        # Objects
        wiz_obj = self.pool.get('change.product.move.processor')

        if isinstance(ids, (int, long)):
            ids = [ids]

        change_wiz_id = wiz_obj.create(cr, uid, {'move_id': ids[0]}, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': wiz_obj._name,
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': change_wiz_id,
            'context': context,
        }

    def open_split_wizard(self, cr, uid, ids, context=None):
        """
        Open the split line wizard: the user can select the quantity for the new move
        """
        # Objects
        wiz_obj = self.pool.get('split.memory.move')

        if isinstance(ids, (int, long)):
            ids = [ids]

        split_wiz_id = wiz_obj.create(cr, uid, {'move_id': ids[0]}, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': wiz_obj._name,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': split_wiz_id,
            'context': context,
        }

stock_move_processor()


class stock_incoming_processor(osv.osv):
    """
    Incoming shipment processing wizard
    """
    _name = 'stock.incoming.processor'
    _inherit = 'stock.picking.processor'
    _description = 'Wizard to process an incoming shipment'
    
    _columns = {
        'move_ids': fields.one2many(
            'stock.move.in.processor',
            'wizard_id',
            string='Moves',
        ),
        'dest_type': fields.selection([
            ('to_cross_docking', 'To Cross Docking'),
            ('to_stock', 'To Stock'),
            ('default', 'Other Types'),
            ],
            string='Destination Type',
            readonly=False,
            help="The default value is the one set on each stock move line.",
        ),
        'source_type': fields.selection([
            ('from_cross_docking', 'From Cross Docking'),
            ('from_stock', 'From stock'),
            ('default', 'Default'),
            ],
            string='Source Type',
            readonly=False,
        ),
        'direct_incoming': fields.boolean(
            string='Direct to Stock ?',
        ),
    }

    _defaults = {
        'dest_type': 'default',
    }
    
    # Models methods
    def _get_prodlot_from_expiry_date(self, cr, uid, expiry_date, product_id, context=None):
        """
        Search if an internal batch exists in the system with this expiry date.
        If no, create the batch. 
        """
        # Objects
        lot_obj = self.pool.get('stock.production.lot')
        seq_obj = self.pool.get('ir.sequence')
        
        # Double check to find the corresponding batch
        lot_ids = lot_obj.search(cr, uid, [
                            ('life_date', '=', expiry_date),
                            ('type', '=', 'internal'),
                            ('product_id', '=', product_id),
                            ], context=context)
                            
        # No batch found, create a new one
        if not lot_ids:
            vals = {
                'product_id': product_id,
                'life_date': expiry_date,
                'name': seq_obj.get(cr, uid, 'stock.lot.serial'),
                'type': 'internal',
            }
            lot_id = lot_obj.create(cr, uid, vals, context)
        else:
            lot_id = lot_ids[0]
            
        return lot_id
        
    def do_incoming_shipment(self, cr, uid, ids, context=None):
        """
        Made some integrity check on lines and run the do_incoming_shipment of stock.picking
        """
        # Objects
        in_proc_obj = self.pool.get('stock.move.in.processor')
        picking_obj = self.pool.get('stock.picking')
        
        process_data = {}
        picking_ids = []
        to_unlink = []
        
        for proc in self.browse(cr, uid, ids, context=context):
            process_data.setdefault(proc.picking_id.id, [])
            picking_ids.append(proc.picking_id.id)
            total_qty = 0.00
            
            for line in proc.move_ids:
                # if no quantity, don't process the move
                if not line.quantity:
                    to_unlink.append(line.id)
                    continue
                
                total_qty += line.quantity
                
                if line.exp_check \
                   and not line.lot_check \
                   and not line.prodlot_id \
                   and line.expiry_date:
                    if line.check_type == 'in':
                        prodlot_id = self._get_prodlot_from_expiry_date(cr, uid, line.expiry_date, context=context)
                        in_proc_obj.write(cr, uid, [line.id], {'prodlot_id': prodlot_id}, context=context)
                    else:
                        # Should not be reached thanks to UI checks
                        raise osv.except_osv(
                            _('Error !'),
                            _('No Batch Number with Expiry Date for Expiry Date Mandatory and not Incoming Shipment should not happen. Please hold...')
                        )
                
            if not total_qty:
                raise osv.except_osv(
                    _('Processing Error'),
                    _("You have to enter the quantities you want to process before processing the move")
                )

        if to_unlink:
            in_proc_obj.unlink(cr, uid, to_unlink, context=context)
            
        return picking_obj.do_incoming_shipment_new(cr, uid, ids, context=context)
    
stock_incoming_processor()


class stock_move_in_processor(osv.osv):
    """
    Incoming moves processing wizard
    """
    _name = 'stock.move.in.processor'
    _inherit = 'stock.move.processor'
    _description = 'Wizard lines for incoming shipment processing'

    _columns = {
        # Parent wizard
        'wizard_id': fields.many2one(
            'stock.incoming.processor',
            string='Wizard',
            required=True,
            readonly=True,
        ),
        'state': fields.char(size=32, string='State', readonly=True),
    }
    
stock_move_in_processor()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
