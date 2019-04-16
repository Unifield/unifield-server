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

from tools.translate import _

from msf_outgoing import INTEGRITY_STATUS_SELECTION


class validate_picking_processor(osv.osv):
    """
    Wizard used to create a Packing List from a validate picking ticket
    """
    _name = 'validate.picking.processor'
    _inherit = 'stock.picking.processor'
    _description = 'Wizard to process the second step of the P/P/S'

    _columns = {
        'move_ids': fields.one2many(
            'validate.move.processor',
            'wizard_id',
            string='Moves to process',
        ),
        'draft': fields.boolean('Draft'),
    }

    def do_validate_picking(self, cr, uid, ids, context=None):
        """
        Made some integrity checks and launch the do_validate_picking method
        of the stock.picking object
        """
        # Objects
        picking_obj = self.pool.get('stock.picking')
        proc_line_obj = self.pool.get('validate.move.processor')

        if context is None:
            context = {}

        # disable "save as draft":
        self.write(cr, uid, ids, {'draft': False}, context=context)

        to_unlink = []
        for proc in self.browse(cr, uid, ids, context=context):
            total_qty = 0.00

            for line in proc.move_ids:
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

        # Delete non-used lines
        if to_unlink:
            proc_line_obj.unlink(cr, uid, to_unlink, context=context)

        self.integrity_check_prodlot(cr, uid, ids, context=context)
        # call stock_picking method which returns action call

        return picking_obj.do_validate_picking(cr, uid, ids, context=context)

    def integrity_check_prodlot(self, cr, uid, ids, context=None):
        """
        Check if the processed quantities are not larger than the available quantities
        """
        # Objects
        uom_obj = self.pool.get('product.uom')
        lot_obj = self.pool.get('stock.production.lot')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        lot_integrity = {}

        for wizard in self.browse(cr, uid, ids, context=context):
            for line in wizard.move_ids:
                if line.prodlot_id:
                    if line.location_id:
                        context['location_id'] = line.location_id.id
                    lot = lot_obj.browse(cr, uid, line.prodlot_id.id, context=context)

                if line.location_id and line.prodlot_id:
                    lot_integrity.setdefault(line.prodlot_id.id, {})
                    lot_integrity[line.prodlot_id.id].setdefault(line.location_id.id, 0.00)

                    if line.uom_id.id != line.prodlot_id.product_id.uom_id.id:
                        product_qty = uom_obj._compute_qty(cr, uid, line.uom_id.id, line.quantity, line.prodlot_id.uom_id.id)
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

        self.write(cr, uid, ids, {'draft': False}, context=context)

        return self.pool.get('stock.picking').validate_picking(cr, uid, pick_id, context=context)


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

validate_picking_processor()


class validate_move_processor(osv.osv):
    """
    Wizard line used to create a Packing List from a validate picking ticket move
    """
    _name = 'validate.move.processor'
    _inherit = 'stock.move.processor'
    _description = 'Wizard lines for validate picking processor'

    def _get_move_info(self, cr, uid, ids, field_name, args, context=None):
        return super(validate_move_processor, self)._get_move_info(cr, uid, ids, field_name, args, context=context)

    def _get_product_info(self, cr, uid, ids, field_name, args, context=None):
        return super(validate_move_processor, self)._get_product_info(cr, uid, ids, field_name, args, context=context)

    def _get_integrity_status(self, cr, uid, ids, field_name, args, context=None):
        return super(validate_move_processor, self)._get_integrity_status(cr, uid, ids, field_name, args, context=context)

    _columns = {
        'wizard_id': fields.many2one(
            'validate.picking.processor',
            string='Wizard ID',
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
                'validate.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
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
                'validate.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
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
                'validate.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
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
                'validate.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
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
                'validate.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
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
                'validate.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
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
                'validate.move.processor': (
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
                'validate.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
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
                'validate.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
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
                'validate.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
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
                'validate.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
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
                'validate.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="A kit is required on this line",
        ),
        'kc_check': fields.function(
            _get_product_info,
            method=True,
            string='KC',
            type='char',
            size=8,
            store={
                'validate.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="Ticked if the product is a Heat Sensitive Item",
        ),
        'ssl_check': fields.function(
            _get_product_info,
            method=True,
            string='SSL',
            type='char',
            size=8,
            store={
                'validate.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
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
                'validate.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
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
                'validate.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="Ticked if the product is a Controlled Substance",
        ),
    }

validate_move_processor()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
