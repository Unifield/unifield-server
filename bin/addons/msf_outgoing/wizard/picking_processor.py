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

    def _get_moves_product_info(self, cr, uid, ids, field_name, args, context=None):
        """
        Returns True of False for each line if the line contains a dangerous or cold chain product
        """
        # Objects
        line_obj = self.pool.get(self._columns['move_ids']._obj)

        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}

        for wizard_id in ids:
            res[wizard_id] = {
                'contains_kc': False,
                'contains_dg': False,
                'forbidden_product': False
            }
            # CC
            kc_lines = line_obj.search(cr, uid, [
                ('wizard_id', '=', wizard_id),
                ('kc_check', '!=', ''),
            ], limit=1, order='NO_ORDER', context=context)
            if kc_lines:
                res[wizard_id]['contains_kc'] = True
            # DG
            dg_lines = line_obj.search(cr, uid, [
                ('wizard_id', '=', wizard_id),
                ('dg_check', '!=', ''),
            ], limit=1, order='NO_ORDER', context=context)
            if dg_lines:
                res[wizard_id]['contains_dg'] = True

            if self._columns['move_ids']._obj == 'stock.move.in.processor':
                list_forbidden = []
                cr.execute('''select
                    default_code
                from product_product p, product_template tmpl, stock_incoming_processor m, stock_move_in_processor l, product_status st
                where
                    l.product_id = p.id and
                    st.code = 'forbidden' and
                    st.id = tmpl.state and
                    tmpl.id = p.product_tmpl_id and
                    l.wizard_id = m.id and
                    m.id = %s
                limit 6''',
                           (wizard_id,))
                for x in cr.fetchall():
                    if len(list_forbidden) == 5:
                        list_forbidden.append('...')
                    else:
                        list_forbidden.append(x[0])
                if list_forbidden:
                    res[wizard_id]['forbidden_product'] = '''<p style="text-align: center; v-align: middle;">
                        <img src="/openerp/static/images/stock/gtk-dialog-warning.png" height="12" width="12" />
                        %s %s
                        <img src="/openerp/static/images/stock/gtk-dialog-warning.png" height="12" width="12" />
                    <p>''' % (_('Warning, you are processing product(s) which have "Forbidden" status, these should not be used. Please refer to your OC guidelines for their management: '), ', '.join(list_forbidden))

        return res

    _columns = {
        'date': fields.datetime(string='Date', required=True),
        'picking_id': fields.many2one(
            'stock.picking',
            string='Picking',
            required=True,
            readonly=True,
            select=True,
            ondelete='cascade',
            help="Picking (incoming, internal, outgoing, picking ticket, packing...) to process",
        ),
        'move_ids': fields.one2many(
            'stock.move.processor',
            'wizard_id',
            string='Moves',
        ),
        'forbidden_product': fields.function(_get_moves_product_info, method=True, string='List of forbidden', type='char', store=False,  multi='kc_dg'),
        'contains_dg': fields.function(
            _get_moves_product_info,
            method=True,
            string='Contains Dangerous goods',
            type='boolean',
            store=False,
            readonly=True,
            help="Is at least one line contains a Dangerous good product.",
            multi='kc_dg',
        ),
        'contains_kc': fields.function(
            _get_moves_product_info,
            method=True,
            string='Contains Cold Chain goods',
            type='boolean',
            store=False,
            readonly=True,
            help="Is at least one line contains a cool chain product.",
            multi='kc_dg',
        ),
        'alert_msl_mml': fields.char(size=512, string="Contains non-conform MML/MSL", readonly=1),
    }

    def default_get(self, cr, uid, fields_list=None, context=None, from_web=False):
        """
        Get default value for the object
        """
        if context is None:
            context = {}

        if fields_list is None:
            fields_list = []

        res = super(stock_picking_processor, self).default_get(cr, uid, fields_list=fields_list, context=context, from_web=from_web)

        res['date'] = time.strftime('%Y-%m-%d %H:%M:%S'),

        return res

    def copy_all(self, cr, uid, ids, context=None):
        """
        Fill all lines with the original quantity as quantity
        """
        if isinstance(ids, (int, long)):
            ids = [ids]

        if context is None:
            context = {}

        if not ids:
            raise osv.except_osv(
                _('Error'),
                _('No wizard found !'),
            )

        if self._name == 'stock.incoming.processor':
            line_obj = self.pool.get('stock.move.in.processor')
            dom = context.get('selected_domain', [])
            if dom:
                dom = ['&', ('wizard_id', '=', ids[0])] + dom
            else:
                dom = [('wizard_id', '=', ids[0])]
            lines_ids = line_obj.search(cr, uid, dom, context=context)
            for move in line_obj.browse(cr, uid, lines_ids, context=context):
                line_obj.write(cr, uid, [move.id], {'quantity': move.ordered_quantity}, context=context)
            return {
                'type': 'ir.actions.refresh_o2m',
                'o2m_refresh': 'move_ids'
            }

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

        if self._name == 'stock.incoming.processor':
            line_obj = self.pool.get('stock.move.in.processor')
            dom = context.get('selected_domain', [])
            if dom:
                dom = ['&', ('wizard_id', '=', ids[0])] + dom
            else:
                dom = [('wizard_id', '=', ids[0])]
            lines_ids = line_obj.search(cr, uid, dom, context=context)
            for move in line_obj.browse(cr, uid, lines_ids, context=context):
                line_obj.write(cr, uid, [move.id], {'quantity': 0}, context=context)
            return {
                'type': 'ir.actions.refresh_o2m',
                'o2m_refresh': 'move_ids'
            }

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

    def create_lines(self, cr, uid, ids, context=None):
        """
        For each moves in the linked stock picking, create
        a line in the wizard
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for wizard in self.browse(cr, uid, ids, context=context):
            line_obj = self.pool.get(wizard._columns['move_ids']._obj)
            wiz_lines_moves_ids = [line.move_id.id for line in wizard.move_ids]
            mml_alert = False
            msl_alert = False

            out_wizard_with_l2_alert = wizard.picking_id.type == 'out' and wizard.picking_id.subtype == 'standard' and not wizard.picking_id.sale_id
            for move in wizard.picking_id.move_lines:
                if move.state in ('draft', 'done', 'cancel', 'confirmed') or move.product_qty == 0.00\
                        or move.id in wiz_lines_moves_ids:
                    if move.id in wiz_lines_moves_ids and move.state == 'cancel':
                        line_ids = line_obj.search(cr, uid, [('move_id', '=', move.id)], context=context)
                        line_obj.unlink(cr, uid, line_ids, context=context)
                    continue

                if wizard.picking_id.type == 'in':
                    if not mml_alert and move.mml_status == 'F':
                        mml_alert = True
                    if not msl_alert and move.msl_status == 'F':
                        msl_alert = True
                if out_wizard_with_l2_alert and not mml_alert and move.mml_status == 'F':
                    mml_alert = True

                line_data = line_obj._get_line_data(cr, uid, wizard, move, context=context)
                if line_obj._name == 'stock.move.in.processor':
                    if wizard.fields_as_ro:
                        line_data['cost_as_ro'] = True

                    if move.pack_info_id:
                        line_data.update({
                            'from_pack': move.pack_info_id.parcel_from,
                            'to_pack': move.pack_info_id.parcel_to,
                            'weight': move.pack_info_id.total_weight,
                            'total_weight': move.pack_info_id.real_total_weight,
                            'volume': move.pack_info_id.total_volume,
                            'total_volume': move.pack_info_id.real_total_volume,
                            'height': move.pack_info_id.total_height,
                            'length': move.pack_info_id.total_length,
                            'width': move.pack_info_id.total_width,
                            'packing_list': move.pack_info_id.packing_list,
                            'ppl_name': move.pack_info_id.ppl_name,
                            'cost': move.price_unit,
                            'currency': move.price_currency_id.id,
                            'pack_info_id': move.pack_info_id.id,
                        })
                # IN sync message uses an already shipped IN
                if context.get('sync_message_execution') and wizard.picking_id.state == 'shipped':
                    line_data['quantity'] = move.product_qty
                line_obj.create(cr, uid, line_data, context=context)
            msg = False
            if mml_alert and msl_alert:
                msg = _('Document has lines that are not in the MSL / MML')
            elif mml_alert:
                msg = _('Document has lines that are not included in the MML')
            elif msl_alert:
                msg = _('Document has lines that are not included in the MSL')
            if msg:
                self.write(cr, uid, wizard.id, {'alert_msl_mml': msg}, context=context)
        return True

stock_picking_processor()


class stock_move_processor(osv.osv):
    """
    Generic stock move processing wizard
    """
    _name = 'stock.move.processor'
    _description = 'Wizard line to process a move'
    _rec_name = 'line_number'
    _order = 'line_number'

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
            if not line.move_id or not line.move_id.product_id:
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

            # UF-2426: point 1) If the source location is given in line, use it, not from the move
            if line.location_id and line.location_id.id:
                location_id = line.location_id.id
            else:
                location_id = line.move_id.location_id.id

            res[line.id] = {
                'ordered_product_id': line.move_id.product_id.id,
                'ordered_uom_id': line.move_id.product_uom.id,
                'ordered_uom_category': line.move_id.product_uom.category_id.id,
                'location_id': location_id,
                'location_supplier_customer_mem_out': loc_supplier or loc_cust or valid_pt,
                'type_check': line.move_id.picking_id.type,
                'comment': line.move_id.comment,
                'uom_rounding_is_pce': line.move_id.product_uom and line.move_id.product_uom.rounding == 1 or False,
            }

        return res

    def _get_product_info(self, cr, uid, ids, field_name, args, context=None):
        """
        Ticked some check boxes according to product parameters
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}

        move_dict = dict([(x['id'], x['product_id'][0]) for x in self.read(cr, uid, ids, ['id', 'product_id'], context=context)])
        product_module = self.pool.get('product.product')
        product_list_dict = product_module.read(cr, uid, move_dict.values(), ['batch_management', 'perishable', 'type',
                                                                              'subtype', 'is_kc', 'ssl_txt', 'dg_txt',
                                                                              'cs_txt'], context=context)
        procuct_dict = dict([(x['id'], x) for x in product_list_dict])

        for move_id, product_id in move_dict.items():
            if product_id in procuct_dict.keys():
                product = procuct_dict[product_id]
                res[move_id] = {
                    'lot_check': product['batch_management'],
                    'exp_check': product['perishable'],
                    'asset_check': product['type'] == 'product' and product['subtype'] == 'asset',
                    'kit_check': product['type'] == 'product' and product['subtype'] == 'kit',
                    'kc_check': product['is_kc'] and 'X',
                    'ssl_check': product['ssl_txt'],
                    'dg_check': product['dg_txt'],
                    'np_check': product['cs_txt'],
                }
            else:
                res[move_id] = {
                    'lot_check': False,
                    'exp_check': False,
                    'asset_check': False,
                    'kit_check': False,
                    'kc_check': '',
                    'ssl_check': '',
                    'dg_check': '',
                    'np_check': '',
                }
        return res

    def _batch_integrity(self, line, res='empty'):
        """
        Check integrity of the batch/expiry date management according to line values
        """
        lot_manda = line.product_id.batch_management
        perishable = line.product_id.perishable

        if (lot_manda or perishable) and line.prodlot_id and line.prodlot_id.product_id.id != line.product_id.id:
            res = 'lot_not_linked_to_prod'
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
            elif line.prodlot_id.type == 'standard':
                # Batch defined by type is not good
                res = 'wrong_lot_type_need_internal'
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
                res_value = self._batch_integrity(line, res_value)
                # Asset management check
                res_value = self._asset_integrity(line, res_value)
                # For internal or simple out, cannot process more than specified in stock move
                if line.wizard_id.picking_id.type in ['out', 'internal']:
                    proc_qty = uom_obj._compute_qty(cr, uid, line.uom_id.id, line.quantity, line.ordered_uom_id.id)
                    if proc_qty - line.ordered_quantity > 0.0001:
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
            select=True,
            ondelete='cascade',
        ),
        'move_id': fields.many2one(
            'stock.move',
            string='Move',
            required=True,
            readonly=True,
            select=True,
            help="Move to process",
            ondelete='cascade',
        ),
        'product_id': fields.many2one(
            'product.product',
            string='Product',
            required=True,
            readonly=True,
            help="Received product",
            ondelete='cascade',
        ),
        'ordered_product_id': fields.function(
            _get_move_info,
            method=True,
            string='Ordered product',
            type='many2one',
            relation='product.product',
            store={
                'stock.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
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
                'stock.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
            },
            readonly=True,
            help="Comment of the move",
            multi='move_info',
        ),
        'quantity': fields.float(
            string='Quantity',
            digits_compute=dp.get_precision('Product UoM'),
            required=True,
            related_uom='uom_id',
        ),
        'ordered_quantity': fields.float(
            string='Ordered quantity',
            digits_compute=dp.get_precision('Product UoM'),
            required=True,
            readonly=True,
            help="Expected quantity to receive",
            related_uom='ordered_uom_id',
        ),
        'uom_id': fields.many2one(
            'product.uom',
            string='UoM',
            required=True,
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
            },
            readonly=True,
            help="Category of the expected UoM to receive",
            multi='move_info'
        ),
        'uom_rounding_is_pce': fields.function(
            _get_move_info,
            method=True,
            type='boolean',
            string="UoM Rounding is PCE",
            store=False,
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
                'stock.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
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
                'stock.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
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
                'stock.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
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
                'stock.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="Ticked if the product is a Controlled Substance",
        ),
        'prodlot_id': fields.many2one(
            'stock.production.lot',
            string='Batch number',
            ondelete='set null',
        ),
        'expiry_date': fields.date(string='Expiry date'),
        'asset_id': fields.many2one(
            'product.asset',
            string='Asset',
            ondelete='set null',
        ),
        'composition_list_id': fields.many2one(
            'composition.kit',
            string='Kit',
            ondelete='set null',
        ),
        'cost': fields.float(
            string='Cost',
            digits_compute=dp.get_precision('Purchase Price Computation'),
            required=True,
            help="Unit Cost for this product line",
            en_thousand_sep=False,
        ),
        'currency': fields.many2one(
            'res.currency',
            string='Currency',
            readonly=True,
            help="Currency in which Unit cost is expressed",
            ondelete='set null',
        ),
        'change_reason': fields.char(size=256, string='Change reason'),
        'mml_status': fields.selection([('T', 'Yes'), ('F', 'No'), ('', '')], string='MML', readonly=True),
        'msl_status': fields.selection([('T', 'Yes'), ('F', 'No'), ('', '')], string='MSL', readonly=True),
    }

    _defaults = {
        'quantity': 0.00,
        'integrity_status': 'empty',
    }

    def copy(self, cr, uid, id, default=None, context=None):
        '''
        set the name corresponding to object subtype
        '''
        if default is None:
            default = {}
        if context is None:
            context = {}

        default['composition_list_id'] = False
        return super(stock_move_processor, self).copy(cr, uid, id, default=default, context=context)

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
        if not ids:
            return True
        vals = self._fill_expiry_date(cr, uid, vals.get('prodlot_id', False), vals.get('expiry_date', False), vals=vals, context=context)
        return super(stock_move_processor, self).write(cr, uid, ids, vals, context=context)

    def _get_line_data(self, cr, uid, wizard=False, move=False, context=None):
        """
        Return line data according to wizard, move and context
        """
        if not wizard:
            raise osv.except_osv(
                _('Error'),
                _('No wizard found')
            )

        if not move:
            raise osv.except_osv(
                _('Error'),
                _('No move found')
            )

        line_data = {
            'wizard_id': wizard.id,
            'move_id': move.id,
            'product_id': move.product_id.id,
            'ordered_quantity': move.product_qty,
            'uom_id': move.product_uom.id,
            'line_number': move.line_number,
            'asset_id': move.asset_id and move.asset_id.id,
            'composition_list_id': move.composition_list_id and move.composition_list_id.id,
            'prodlot_id': move.prodlot_id and move.prodlot_id.id,
            'cost': move.price_unit,
            'currency': move.price_currency_id.id,
            'location_id': move.location_id and move.location_id.id,
            'mml_status': move.mml_status or '',
            'msl_status': move.msl_status or '',
        }
        return line_data

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
            if new_qty > line.ordered_quantity:
                # Cannot select more than initial quantity
                raise osv.except_osv(
                    _('Error'),
                    _('Selected quantity (%0.1f %s) exceeds the initial quantity (%0.1f %s)') %
                    (new_qty, line.uom_id.name, line.ordered_quantity, line.uom_id.name),
                )
            elif new_qty == line.ordered_quantity:
                # Cannot select more than initial quantity
                raise osv.except_osv(
                    _('Error'),
                    _('Selected quantity (%0.1f %s) cannot be equal to the initial quantity (%0.1f %s)') %
                    (new_qty, line.uom_id.name, line.ordered_quantity, line.uom_id.name),
                )

            update_qty = line.ordered_quantity - new_qty
            wr_vals = {
                'quantity': line.quantity > update_qty and update_qty or line.quantity,
                'ordered_quantity': update_qty,
            }
            self._update_split_wr_vals(vals=wr_vals)  # w/o overriding, just return wr_vals
            self.write(cr, uid, [line.id], wr_vals, context=context)

            # Create a copy of the move_processor with the new quantity
            cp_vals = {
                'quantity': 0.00,
                'ordered_quantity': new_qty,
            }
            self._update_split_cp_vals(vals=cp_vals)  # w/o overriding, just return cp_vals
            self.copy(cr, uid, line.id, cp_vals, context=context)

        return pick_wiz_id

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

        status_map = {
            'no': 'F',
            'yes': 'T',
        }

        prod_data = self.pool.get('product.product').browse(cr, uid, product_id, fields_to_fetch=['is_mml_valid', 'is_msl_valid', 'international_status', 'nomen_manda_0'], context=context)
        if prod_data.international_status.code != 'unidata' or prod_data.nomen_manda_0.name != 'MED':
            mml_status = ''
            msl_status = ''
        else:
            mml_status = status_map.get(prod_data.is_mml_valid, '')
            msl_status = status_map.get(prod_data.is_msl_valid, '')
        wr_vals = {
            'change_reason': change_reason,
            'product_id': product_id,
            'prodlot_id': False,
            'expiry_date': False,
            'mml_status': mml_status,
            'msl_status': msl_status,
        }
        self.write(cr, uid, ids, wr_vals, context=context)

        pick_wiz_id = self.read(cr, uid, ids[0], ['wizard_id'], context=context)['wizard_id']

        return pick_wiz_id

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
            if not line.uom_id or line.uom_id.rounding != 1:
                new_qty.setdefault('value', {}).update({'uom_rounding_is_pce': False, 'composition_list_id': False})

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
            'value': {},
            'warning': {},
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
                    res['warning'].update({
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

        move_proc = self.browse(cr, uid, ids[0], context=context)

        change_wiz_id = wiz_obj.create(cr, uid, {
            'processor_line_id': ids[0],
            'processor_type': self._name,
            'move_location_ids': [move_proc.location_id.id],
        }, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': wiz_obj._name,
            'view_type': 'form',
            'view_mode': 'form',
            'nodestroy': True,
            'target': 'new',
            'res_id': change_wiz_id,
            'context': context,
        }

    def open_split_wizard(self, cr, uid, ids, context=None):
        """
        Open the split line wizard: the user can select the quantity for the new move
        """
        # Objects
        wiz_obj = self.pool.get('split.move.processor')

        if isinstance(ids, (int, long)):
            ids = [ids]

        split_wiz_id = wiz_obj.create(cr, uid, {
            'processor_line_id': ids[0],
            'processor_type': self._name,
        }, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': wiz_obj._name,
            'view_type': 'form',
            'view_mode': 'form',
            'nodestroy': True,
            'target': 'new',
            'res_id': split_wiz_id,
            'keep_open': 1,
            'context': context,
        }

    def get_selection(self, cr, uid, o, field):
        """
        Get the label of fields.selection
        """
        sel = self.pool.get(o._name).fields_get(cr, uid, [field])
        res = dict(sel[field]['selection']).get(getattr(o, field), getattr(o, field))
        name = '%s,%s' % (o._name, field)
        tr_ids = self.pool.get('ir.translation').search(cr, uid, [('type', '=', 'selection'), ('name', '=', name), ('src', '=', res)])
        if tr_ids:
            return self.pool.get('ir.translation').read(cr, uid, tr_ids, ['value'])[0]['value']
        else:
            return res

stock_move_processor()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
