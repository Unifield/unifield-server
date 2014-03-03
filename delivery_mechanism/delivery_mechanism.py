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
import time

from tools.translate import _
from dateutil.relativedelta import relativedelta
from datetime import datetime

import netsvc


class stock_move(osv.osv):
    '''
    new function to get mirror move
    '''
    _inherit = 'stock.move'
    _columns = {'line_number': fields.integer(string='Line', required=True),
                'change_reason': fields.char(string='Change Reason', size=1024, readonly=True),
                'in_out_updated': fields.boolean(string='IN update OUT'),
                'original_qty_partial': fields.integer(string='Original Qty for Partial process - only for sync and partial processed line', required=False),
                }
    _defaults = {'line_number': 0,
                 'in_out_updated': False,
                 'original_qty_partial':-1}
    _order = 'line_number, date_expected desc, id'

    def copy_data(self, cr, uid, id, defaults=None, context=None):
        '''
        If the line_number is not in the defaults, we set it to False.
        If we are on an Incoming Shipment: we reset purchase_line_id field
        and we set the location_dest_id to INPUT.
        '''
        if defaults is None:
            defaults = {}
        if context is None:
            context = {}

        # we set line_number, so it will not be copied in copy_data - keepLineNumber - the original Line Number will be kept
        if 'line_number' not in defaults and not context.get('keepLineNumber', False):
            defaults.update({'line_number': False})
        # the tag 'from_button' was added in the web client (openerp/controllers/form.py in the method duplicate) on purpose
        if context.get('from_button'):
            # UF-1797: when we duplicate a doc we delete the link with the poline
            defaults.update(purchase_line_id=False)
            if context.get('subtype', False) == 'incoming':
                # we reset the location_dest_id to 'INPUT' for the 'incoming shipment'
                input_loc = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_input')[1]
                defaults.update(location_dest_id=input_loc)
        return super(stock_move, self).copy_data(cr, uid, id, defaults, context=context)

    def unlink(self, cr, uid, ids, context=None):
        '''
        check the numbering on deletion
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # objects
        tools_obj = self.pool.get('sequence.tools')

        if not context.get('skipResequencing', False):
            # re sequencing only happen if purchase order is draft (behavior 1)
            # get ids with corresponding po at draft state
            draft_not_wkf_ids = self.allow_resequencing(cr, uid, ids, context=context)
            tools_obj.reorder_sequence_number_from_unlink(cr, uid, draft_not_wkf_ids, 'stock.picking', 'move_sequence_id', 'stock.move', 'picking_id', 'line_number', context=context)

        return super(stock_move, self).unlink(cr, uid, ids, context=context)

    def allow_resequencing(self, cr, uid, ids, context=None):
        '''
        define if a resequencing has to be performed or not

        return the list of ids for which resequencing will can be performed

        linked to Picking + Picking draft + not linked to Po/Fo
        '''
        # objects
        pick_obj = self.pool.get('stock.picking')

        resequencing_ids = [x.id for x in self.browse(cr, uid, ids, context=context) if x.picking_id and pick_obj.allow_resequencing(cr, uid, x.picking_id, context=context)]
        return resequencing_ids

    def _create_chained_picking_move_values_hook(self, cr, uid, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_process method from stock>stock.py>stock_picking

        - set the line number of the original picking, could have used the keepLineNumber flag, but used hook to modify original class minimally
        '''
        if context is None:
            context = {}
        move_data = super(stock_move, self)._create_chained_picking_move_values_hook(cr, uid, context=context, *args, **kwargs)
        # get move reference
        move = kwargs['move']
        # set the line number from original stock move
        move_data.update({'line_number': move.line_number})
        return move_data

    def _get_location_for_internal_request(self, cr, uid, context=None, **kwargs):
        '''
        Get the requestor_location_id in case of IR to update the location_dest_id of each move
        '''
        location_dest_id = False
        sol_obj = self.pool.get('sale.order.line')
        so_obj = self.pool.get('sale.order')
        move = kwargs['move']
        if move.purchase_line_id:
            proc = move.purchase_line_id.procurement_id
            if proc and proc.sale_order_line_ids and proc.sale_order_line_ids[0].order_id and proc.sale_order_line_ids[0].order_id.procurement_request:
                location_dest_id = proc.sale_order_line_ids[0].order_id.location_requestor_id.id
        return location_dest_id

    def _do_partial_hook(self, cr, uid, ids, context, *args, **kwargs):
        '''
        hook to update defaults data

        - update the line number, keep original line number
        >> performed for all cases (too few (copy - new numbering policy), complete (simple update - no impact), to many (simple update - no impact)
        '''
        # variable parameters
        move = kwargs.get('move', False)
        assert move, 'delivery_mechanism.py >> stock_move: _do_partial_hook - missing move'

        # calling super method
        defaults = super(stock_move, self)._do_partial_hook(cr, uid, ids, context, *args, **kwargs)
        assert defaults is not None, 'delivery_mechanism.py >> stock_move: _do_partial_hook - missing defaults'
        # update the line number, copy original line_number value
        defaults.update({'line_number': move.line_number})

        return defaults

    def get_mirror_move(self, cr, uid, ids, data_back, context=None):
        '''
        return a dictionary with IN for OUT and OUT for IN, if exists, False otherwise

        only one mirror object should exist for each object (to check)
        return objects which are not done

        same sale_line_id/purchase_line_id - same product - same quantity

        IN: move -> po line -> procurement -> so line -> move
        OUT: move -> so line -> procurement -> po line -> move

        I dont use move.move_dest_id because of back orders both on OUT and IN sides
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # objects
        so_line_obj = self.pool.get('sale.order.line')

        res = {}
        for obj in self.browse(cr, uid, ids, context=context):
            res[obj.id] = {'move_id': False, 'picking_id': False, 'picking_version': 0, 'quantity': 0, 'moves': []}
            if obj.picking_id and obj.picking_id.type == 'in':
                # we are looking for corresponding OUT move from sale order line
                if obj.purchase_line_id:
                    # linekd to a po
                    if obj.purchase_line_id.procurement_id:
                        # on order
                        procurement_id = obj.purchase_line_id.procurement_id.id
                        # find the corresponding sale order line
                        so_line_ids = so_line_obj.search(cr, uid, [('procurement_id', '=', procurement_id)], context=context)
                        # if the procurement comes from replenishment rules, there will be a procurement, but no associated sale order line
                        # we therefore do not raise an exception, but handle the case only if sale order lines are found
                        if so_line_ids:
                            # find the corresponding OUT move
                            # move_ids = self.search(cr, uid, [('product_id', '=', obj.product_id.id), ('product_qty', '=', obj.product_qty), ('state', 'in', ('assigned', 'confirmed')), ('sale_line_id', '=', so_line_ids[0])], context=context)
                            move_ids = self.search(cr, uid, [('product_id', '=', data_back['product_id']),
                                                             ('state', 'in', ('assigned', 'confirmed')),
                                                             ('sale_line_id', '=', so_line_ids[0]),
                                                             ('in_out_updated', '=', False),
                                                             ('picking_id.type', '=', 'out'),
                                                             ('processed_stock_move', '=', False),
                                                             ], order="state desc", context=context)
                            # list of matching out moves
                            integrity_check = []
                            for move in self.browse(cr, uid, move_ids, context=context):
                                # move from draft picking or standard picking
                                if (move.product_qty != 0.00 and move.picking_id.subtype == 'picking' and not move.picking_id.backorder_id and move.picking_id.state == 'draft') or (move.picking_id.subtype == 'standard'):
                                    integrity_check.append(move)
                            # return the first one matching
                            if integrity_check:
                                if all([not move.processed_stock_move for move in integrity_check]):
                                    # the out stock moves (draft picking or std out) have not yet been processed, we can therefore update them
                                    res[obj.id].update({
                                        'move_id': integrity_check[0].id,
                                        'moves': integrity_check,
                                        'picking_id': integrity_check[0].picking_id.id,
                                        'picking_version': integrity_check[0].picking_id.update_version_from_in_stock_picking,
                                        'quantity': integrity_check[0].product_qty,
                                    })
                                else:
                                    # the corresponding OUT move have been processed completely or partially,, we do not update the OUT
                                    self.log(cr, uid, integrity_check[0].id, _('The Stock Move %s from %s has already been processed and is therefore not updated.') % (integrity_check[0].name, integrity_check[0].picking_id.name))

            else:
                # we are looking for corresponding IN from on_order purchase order
                assert False, 'This method is not implemented for OUT or Internal moves'

        return res

    def create_data_back(self, move):
        '''
        build data_back dictionary
        '''
        res = {'id': move.id,
               'name': move.product_id.partner_ref,
               'product_id': move.product_id.id,
               'product_uom': move.product_uom.id,
               'product_qty': move.product_qty,
               }
        return res

    def hook__create_chained_picking(self, cr, uid, pick_values, picking):
        res = super(stock_move, self).hook__create_chained_picking(cr, uid, pick_values, picking)

        if picking:
            res['auto_picking'] = picking.type == 'in' and picking.move_lines[0]['direct_incoming']

        return res

stock_move()


class stock_picking(osv.osv):
    '''
    do_partial modification
    '''
    _inherit = 'stock.picking'
    _columns = {'move_sequence_id': fields.many2one('ir.sequence', string='Moves Sequence', help="This field contains the information related to the numbering of the moves of this picking.", required=True, ondelete='cascade'),
                'change_reason': fields.char(string='Change Reason', size=1024, readonly=True),
                }

    def _stock_picking_action_process_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_process method from stock>stock.py>stock_picking

        - allow to modify the data for wizard display
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = super(stock_picking, self)._stock_picking_action_process_hook(cr, uid, ids, context=context, *args, **kwargs)
        wizard_obj = self.pool.get('wizard')
        res = wizard_obj.open_wizard(cr, uid, ids, type='update', context=dict(context,
                                                                               wizard_ids=[res['res_id']],
                                                                               wizard_name=res['name'],
                                                                               model=res['res_model'],
                                                                               step='default'))
        return res

    def create(self, cr, uid, vals, context=None):
        '''
        create the sequence for the numbering of the lines
        '''
        if not vals:
            vals = {}
        # object
        seq_pool = self.pool.get('ir.sequence')
        po_obj = self.pool.get('purchase.order')
        so_obj = self.pool.get('sale.order')

        new_seq_id = self.create_sequence(cr, uid, vals, context=context)
        vals.update({'move_sequence_id': new_seq_id, })
        # if from order, we udpate the sequence to match the order's one
        # line number correspondance to be checked with Magali
        # I keep that code deactivated, as when the picking is wkf, hide_new_button must always be true
        seq_value = False
        if vals.get('purchase_id') and False:
            seq_id = po_obj.read(cr, uid, [vals.get('purchase_id')], ['sequence_id'], context=context)[0]['sequence_id'][0]
            seq_value = seq_pool.read(cr, uid, [seq_id], ['number_next'], context=context)[0]['number_next']
        elif vals.get('sale_id') and False:
            seq_id = po_obj.read(cr, uid, [vals.get('sale_id')], ['sequence_id'], context=context)[0]['sequence_id'][0]
            seq_value = seq_pool.read(cr, uid, [seq_id], ['number_next'], context=context)[0]['number_next']

        if seq_value:
            # update sequence value of stock picking to match order's one
            seq_pool.write(cr, uid, [new_seq_id], {'number_next': seq_value, })

        return super(stock_picking, self).create(cr, uid, vals, context=context)

    def allow_resequencing(self, cr, uid, pick_browse, context=None):
        '''
        allow resequencing criteria
        '''
        if pick_browse.state == 'draft' and not pick_browse.purchase_id and not pick_browse.sale_id:
            return True
        return False

    def _do_partial_hook(self, cr, uid, ids, context, *args, **kwargs):
        '''
        hook to update defaults data
        '''
        # variable parameters
        move = kwargs.get('move')
        assert move, 'delivery_mechanism.py >> stock_picking: _do_partial_hook - missing move'

        # calling super method
        defaults = super(stock_picking, self)._do_partial_hook(cr, uid, ids, context, *args, **kwargs)
        assert defaults is not None, 'delivery_mechanism.py >> stock_picking: _do_partial_hook - missing defaults'
        # update the line number, copy original line_number value
        defaults.update({'line_number': move.line_number})

        # UTP-972: Set the original total qty of the original move to the new partial move, for sync purpose only
        orig_qty = move.product_qty
        if move.original_qty_partial and move.original_qty_partial != -1:
            orig_qty = move.original_qty_partial
        defaults.update({'original_qty_partial': orig_qty})

        return defaults

    def _update_mirror_move(self, cr, uid, ids, data_back, diff_qty, out_move=False, context=None):
        '''
        update the mirror move with difference quantity diff_qty

        if out_move is provided, it is used for copy if another cannot be found (meaning the one provided does
        not fit anyhow)

        # NOTE: the price is not update in OUT move according to average price computation. this is an open point.

        if diff_qty < 0, the qty is decreased
        if diff_qty > 0, the qty is increased
        '''
        # stock move object
        move_obj = self.pool.get('stock.move')
        product_obj = self.pool.get('product.product')
        # first look for a move - we search even if we get out_move because out_move
        # may not be valid anymore (product changed) - get_mirror_move will validate it or return nothing
        out_move_id = move_obj.get_mirror_move(cr, uid, [data_back['id']], data_back, context=context)[data_back['id']]['move_id']
        if not out_move_id and out_move:
            # copy existing out_move with move properties: - update the name of the stock move
            # the state is confirmed, we dont know if available yet - should be in input location before stock
            values = {'name': data_back['name'],
                      'product_id': data_back['product_id'],
                      'product_qty': 0,
                      'product_uos_qty': 0,
                      'product_uom': data_back['product_uom'],
                      'state': 'confirmed',
                      'prodlot_id': False,  # reset batch number
                      'asset_id': False,  # reset asset
                      }
            out_move_id = move_obj.copy(cr, uid, out_move, values, context=context)
        # update quantity
        if out_move_id:
            # decrease/increase depending on diff_qty sign the qty by diff_qty
            data = move_obj.read(cr, uid, [out_move_id], ['product_qty', 'picking_id', 'name', 'product_uom'], context=context)[0]
            picking_out_name = data['picking_id'][1]
            stock_move_name = data['name']
            uom_name = data['product_uom'][1]
            present_qty = data['product_qty']
            new_qty = max(present_qty + diff_qty, 0)
            if new_qty > 0.00 and present_qty != 0.00:
                new_move_id = move_obj.copy(cr, uid, out_move_id, {'product_qty' : diff_qty,
                                                                   'product_uom': data_back['product_uom'],
                                                                   'product_uos': data_back['product_uom'],
                                                                   'product_uos_qty': diff_qty, }, context=context)
                move_obj.action_confirm(cr, uid, [new_move_id], context=context)
#                if present_qty == 0.00:
#                    move_obj.write(cr, uid, [out_move_id], {'state': 'draft'})
#                    move_obj.unlink(cr, uid, out_move_id, context=context)
            else:
                move_obj.write(cr, uid, [out_move_id], {'product_qty' : new_qty,
                                                        'product_uom': data['product_uom'][0],
                                                        'product_uos': data['product_uom'][0],
                                                        'product_uos_qty': new_qty, }, context=context)

            # log the modification
            # log creation message
            move_obj.log(cr, uid, out_move_id, _('The Stock Move %s from %s has been updated to %s %s.') % (stock_move_name, picking_out_name, new_qty, uom_name))
        # return updated move or False
        return out_move_id

    def _do_incoming_shipment_first_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        hook to update values for stock move if first encountered
        '''
        values = kwargs.get('values')
        assert values is not None, 'missing values'
        return values

    def _get_db_data_dict(self, cr, uid):
        """
        Get some data from data.xml file (like stock locations, Unifield setup...)
        """
        # Objects
        data_obj = self.pool.get('ir.model.data')
        loc_obj = self.pool.get('stock.location')

        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)

        cd_loc = loc_obj.get_cross_docking_location(cr, uid)
        service_loc = loc_obj.get_service_location(cr, uid)
        non_stock = loc_obj.search(cr, uid, [('non_stockable_ok', '=', True)])
        if non_stock:
            non_stock = non_stock[0]
        input_loc = data_obj.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_input')[1]

        db_data = {
            'setup': setup,
            'cd_loc': cd_loc,
            'service_loc': service_loc,
            'non_stock': non_stock,
            'input_loc': input_loc
        }

        return db_data

    def _compute_average_values(self, cr, uid, move, line, product_availability, context=None):
        """
        Compute the average price of the product according to processed quantities
        """
        # Objects
        uom_obj = self.pool.get('product.uom')
        currency_obj = self.pool.get('res.currency')
        product_obj = self.pool.get('product.product')

        if context is None:
            context = {}

        average_values = {}

        move_currency_id = move.company_id.currency_id.id
        context['currency_id'] = move_currency_id

        qty = line.quantity
        if line.uom_id.id != line.product_id.uom_id.id:
            qty = uom_obj._compute_qty(cr, uid, line.uom_id.id, line.quantity, line.product_id.uom_id.id)

        product_availability.setdefault(line.product_id.id, line.product_id.qty_available)
        product_availability[line.product_id.id] += qty

        if qty > 0.00:
            new_price = line.cost
            # Recompute unit price if the currency used is not the functional currency
            if line.currency.id != move_currency_id:
                new_price = currency_obj.compute(cr, uid, line.currency.id, move_currency_id,
                    new_price, round=False, context=context)

            # Recompute unit price if the UoM received is not the default UoM of the product
            if line.uom_id.id != line.product_id.uom_id.id:
                new_price = uom_obj._compute_price(cr, uid, line.uom_id.id, new_price,
                    line.product_id.uom_id.id)

            new_std_price = 0.00
            if line.product_id.qty_available <= 0.00:
                new_std_price = new_price
            else:
                # Get the current price
                current_price = product_obj.price_get(cr, uid, [line.product_id.id], ['standard_price'], context=context)[line.product_id.id]
                # Check no division by zero
                if product_availability[line.product_id.id]:
                    new_std_price = ((current_price * product_availability[line.product_id.id])\
                        + (new_price * qty)) / (product_availability[line.product_id.id] + qty)

            # Write the field according to price type field
            product_obj.write(cr, uid, [line.product_id.id], {'standard_price': new_std_price})

            # Record the values that were chosen in the wizard, so they can be
            # used for inventory valuation of real-time valuation is enabled.
            average_values = {
              'price_unit': new_price,
              'price_currency_id': line.currency_id.id,
            }

        return average_values

    def _get_values_from_line(self, cr, uid, move, line, db_data, context=None):
        """
        Prepare the value for a processed move according to line values
        """
        # Objects
        uom_obj = self.pool.get('product.uom')

        if context is None:
            context = {}

        wizard = line.wizard_id

        values = {
            'name': line.product_id.partner_ref,
            'product_id': line.product_id.id,
            'original_qty_partial': move.product_qty,
            'product_qty': line.quantity,
            'product_uom': line.uom_id.id,
            'product_uos_qty': line.quantity,
            'product_uos': line.uom_id.id,
            'prodlot_id': line.prodlot_id and line.prodlot_id.id or False,
            # 'asset_id': line.asset_id and line.asset_id.id or False,
            'change_reason': line.change_reason,
            # Values from incoming wizard
            'direct_incoming': line.wizard_id.direct_incoming,
            # Values for Direct Purchase Order
            'sync_dpo': move.dpo_line_id and True or move.sync_dpo,
            'dpo_line_id': move.dpo_line_id and move.dpo_line_id.id or False,
        }

        # UTP-872: Don't change the quantity if the move is canceled
        # If the quantity is changed to 0.00, a backorder is created
        # for canceled moves
        if move.state == 'cancel':
            values.update({
                'product_qty': move.product_qty,
                'product_uos_qty': move.product_uos_qty
            })

        # UTP-872: Added also the state into the move line if the state comes from the sync
        if line.state:
            values['state'] = line.state

        if line.cost:
            values['price_unit'] = line.cost
        elif line.uom_id.id != move.product_uom.id:
            new_price = uom_obj._compute_price(cr, uid, move.product_uom.id, move.price_unit, line.uom_id.id)
            values['price_unit'] = new_price

        # We check the dest_type for INCOMING shipment (and not the source_type which is reserved for OUTGOING shipment)
        if wizard.dest_type == 'to_cross_docking':
            if db_data.get('setup').allocation_setup == 'unallocated':
                raise osv.except_osv(
                        _('Error'),
                        _('You cannot made moves from/to Cross-docking locations when the Allocated stocks configuration is set to \'Unallocated\'.')
                )
            # Below, "source_type" is only used for the outgoing shipment. We set it to "None" because by default it is
            # "default" and we do not want that info on INCOMING shipment
            wizard.source_type = None
            values.update({
                'location_dest_id': db_data.get('cd_loc'),
                'cd_from_bo': True,
            })
        elif wizard.dest_type == 'to_stock':
            # Below, "source_type" is only used for the outgoing shipment. We set it to "None because by default it is
            # "default" and we do not want that info on INCOMING shipment
            if line.product_id.product_type == 'consu':
                values['location_dest_id'] = db_data.get('non_stock')
            elif line.product_id.product_type == 'service_recep':
                values['location_dest_id'] = db_data.get('service_loc')
            else:
                # treat moves towards STOCK if NOT SERVICE
                values['location_dest_id'] = db_data.get('input_loc')

            values['cd_from_bo'] = False

        if wizard.dest_type != 'to_cross_docking':
            values['direct_incoming'] = wizard.direct_incoming

        return values

    def do_incoming_shipment(self, cr, uid, wizard_ids, context=None):
        """
        Take the data in wizard_ids and lines of stock.incoming.processor and
        do the split of stock.move according to the data.
        """
        # Objects
        inc_proc_obj = self.pool.get('stock.incoming.processor')
        move_proc_obj = self.pool.get('stock.move.in.processor')
        loc_obj = self.pool.get('stock.location')
        uom_obj = self.pool.get('product.uom')
        move_obj = self.pool.get('stock.move')
        sequence_obj = self.pool.get('ir.sequence')
        wf_service = netsvc.LocalService("workflow")

        if context is None:
            context = {}

        if isinstance(wizard_ids, (int, long)):
            wizard_ids = [wizard_ids]

        db_data_dict = self._get_db_data_dict(cr, uid)

        # UF-1617: Get the sync_message case
        sync_in = context.get('sync_message_execution', False)

        internal_loc = loc_obj.search(cr, uid, [('usage', '=', 'internal'), ('cross_docking_location_ok', '=', False)])
        context['location'] = internal_loc

        product_availability = {}

        for wizard in inc_proc_obj.browse(cr, uid, wizard_ids, context=context):
            picking = wizard.picking_id
            backordered_moves = []  # Moves that need to be put in a backorder
            done_moves = []  # Moves that are completed
            out_picks = set()

            for move in picking.move_lines:
                # Get all processed lines that processed this stock move
                proc_ids = move_proc_obj.search(cr, uid, [('wizard_id', '=', wizard.id), ('move_id', '=', move.id)], context=context)
                # The processed quantity
                count = 0
                need_split = False

                data_back = move_obj.create_data_back(move)
                mirror_data = move_obj.get_mirror_move(cr, uid, [move.id], data_back, context=context)[move.id]
                out_moves = mirror_data['moves']
                processed_out_moves = []
                average_values = {}

                for line in move_proc_obj.browse(cr, uid, proc_ids, context=context):
                    values = self._get_values_from_line(cr, uid, move, line, db_data_dict, context=context)

                    # Check if we must re-compute the price of the product
                    compute_average = False
                    if values.get('location_dest_id', False):
                        dest_loc = loc_obj.browse(cr, uid, values['location_dest_id'], context=context)
                        compute_average = picking.type == 'in' and line.product_id.cost_method == 'average' and dest_loc.cross_docking_location_ok

                    if compute_average:
                        average_values = self._compute_average_values(cr, uid, move, line, product_availability, context=context)
                        values.update(average_values)

                    # The quantity
                    if line.uom_id.id != move.product_uom.id:
                        count += uom_obj._compute_qty(cr, uid, line.uom_id.id, line.quantity, move.product_uom.id)
                    else:
                        count += line.quantity

                    values['processed_stock_move'] = True
                    if not need_split:
                        need_split = True
                        # Mark the done IN stock move as processed
                        move_obj.write(cr, uid, [move.id], values, context=context)
                        done_moves.append(move.id)
                    else:
                        values['state'] = 'assigned'
                        context['keepLineNumber'] = True
                        new_move_id = move_obj.copy(cr, uid, values, context=context)
                        context['keepLineNumber'] = False
                        done_moves.append(new_move_id)

                    values['processed_stock_move'] = False

                    out_values = values.copy()
                    # Remove sync. DPO fields
                    out_values.update({
                        'dpo_line_id': 0,
                        'sync_dpo': False,
                        'state': 'confirmed',
                        'location_dest_id': False,
                    })

                    remaining_out_qty = line.quantity
                    out_move = None
                    for out_move in out_moves:
                        out_move = move_obj.browse(cr, uid, out_move.id, context=context)

                        # List the Picking Ticket that need to be created from the Draft Picking Ticket
                        if out_move.picking_id.type == 'out' \
                           and out_move.picking_id.subtype == 'picking' \
                           and out_move.picking_id.state == 'draft':
                            out_picks.add(out_move.picking_id.id)

                        if line.uom_id.id != out_move.product_uom.id:
                            uom_partial_qty = uom_obj._compute_qty(cr, uid, line.uom_id.id, remaining_out_qty, out_move.product_uom.id)
                        else:
                            uom_partial_qty = remaining_out_qty

                        if uom_partial_qty < out_move.product_qty:
                            # Splt the out move
                            out_values.update({
                                'product_qty': remaining_out_qty,
                                'product_uom': line.uom_id.id,
                                'in_out_updated': sync_in and False or True,
                            })
                            context['keepLineNumber'] = True
                            move_obj.copy(cr, uid, out_move.id, out_values, context=context)
                            context['keepLineNumber'] = False
                            remaining_out_qty = 0.00
                        elif uom_partial_qty == out_move.product_qty:
                            out_values.update({
                                'product_qty': remaining_out_qty,
                                'product_uom': line.uom_id.id,
                                'in_out_updated': sync_in and False or True,
                            })
                            move_obj.write(cr, uid, [out_move.id], out_values, context=context)
                            processed_out_moves.append(out_move.id)
                        else:
                            # Just update the data of the initial out move
                            out_values.update({
                                'product_qty': out_move.product_qty,
                                'product_uom': line.uom_id.id,
                                'in_out_updated': sync_in and False or True
                            })
                            move_obj.write(cr, uid, [out_move.id], out_values, context=context)
                            processed_out_moves.append(out_move.id)

                # Decrement the inital move, cannot be less than zero
                diff_qty = move.product_qty - count
                # If there is remaining quantity for the move, put the ID of the move
                # and the remaining quantity to list of moves to put in backorder
                if diff_qty > 0.00 and move.state != 'cancel':
                    backordered_moves.append((move, diff_qty, average_values))

            # Create the backorder if needed
            if backordered_moves:
                backorder_id = self.copy(cr, uid, picking.id, {
                    'name': sequence_obj.get(cr, uid, 'stock.picking.%s' % (picking.type)),
                    'move_lines': [],
                    'state': 'draft',
                }, context=context)

                for bo_move, bo_qty, av_values in backordered_moves:
                    # Create the corresponding move in the backorder - reset batch - reset asset_id
                    bo_values = {
                        'asset_id': False,
                        'product_qty': bo_qty,
                        'product_uos_qty': bo_qty,
                        'prodlot_id': False,
                        'state': 'assigned',
                        'move_dest_id': False,
                        'change_reason': False,
                        'processed_stock_move': True,
                    }
                    bo_values.update(av_values)
                    context['keepLineNumber'] = True
                    move_obj.copy(cr, uid, move.id, bo_values, context=context)
                    context['keepLineNumber'] = False

                # Put the done moves in this new picking
                move_obj.write(cr, uid, done_moves, {
                    'picking_id': backorder_id,
                    'dpo_line_id': 0,
                }, context=context)


                if sync_in:
                    # UF-1617: When it is from the sync., then just send the IN to shipped, then return the backorder_id
                    wf_service.trg_validate(uid, 'stock.picking', backorder_id, 'button_shipped', cr)
                    return backorder_id


                wf_service.trg_validate(uid, 'stock.picking', backorder_id, 'button_confirm', cr)
                # Then we finish the good picking
                self.write(cr, uid, [picking.id], {
                    'backorder_id': backorder_id,
                    'cd_from_bo': values.get('cd_from_bo', False),
                }, context=context)
                self.action_move(cr, uid, [backorder_id])
                wf_service.trg_validate(uid, 'stock.picking', backorder_id, 'button_done', cr)
                wf_service.trg_write(uid, 'stock.picking', picking.id, cr)
            else:
                if sync_in:  # If it's from sync, then we just send the pick to become Available Shippde, not completely close!
                    self.write(cr, uid, [picking.id], {'state': 'shipped'}, context=context)
                    return picking.id
                else:
                    self.action_move(cr, uid, [picking.id], context=context)
                    wf_service.trg_validate(uid, 'stock.picking', picking.id, 'button_done', cr)

        # Create the first picking ticket if we are on a draft picking ticket
        for picking in self.browse(cr, uid, list(out_picks), context=context):
            wiz = self.create_picking(cr, uid, [picking.id], context=context)
            wiz_obj = self.pool.get(wiz['res_model'])
            moves_picking = wiz_obj.browse(cr, uid, wiz['res_id'], context=wiz['context']).product_moves_picking
            nb_lines = len(moves_picking)
            # We delete the lines which is not from the IN
#            for line in moves_picking:
#                if line.move_id.id not in pick_moves:
#                    self.pool.get('stock.move.memeroy.picking').unlink(cr, uid, [line.id], context=context)
#                    nb_lines -= 1

            if nb_lines:
                # We copy all data in lines
                wiz_obj.copy_all(cr, uid, [wiz['res_id']], context=wiz['context'])
                # We process the creation of the picking
                wiz_obj.do_create_picking(cr, uid, [wiz['res_id']], context=wiz['context'])

        if context.get('from_simu_screen'):
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'view_picking_in_form')[1]
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'res_id': picking.id,
                'view_id': [view_id],
                'view_mode': 'form, tree',
                'view_type': 'form',
                'target': 'crush',
                'context': context}

        return {'type': 'ir.actions.act_window_close'}

    def enter_reason(self, cr, uid, ids, context=None):
        '''
        open reason wizard
        '''
        # we need the context for the wizard switch
        if context is None:
            context = {}
        # data
        name = _("Enter a Reason for Incoming cancellation")
        model = 'enter.reason'
        step = 'default'
        wiz_obj = self.pool.get('wizard')
        # open the selected wizard
        return wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=dict(context, picking_id=ids[0]))

    def cancel_and_update_out(self, cr, uid, ids, context=None):
        '''
        update corresponding out picking if exists and cancel the picking
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # objects
        move_obj = self.pool.get('stock.move')
        purchase_obj = self.pool.get('purchase.order')
        # workflow
        wf_service = netsvc.LocalService("workflow")

        for obj in self.browse(cr, uid, ids, context=context):
            # corresponding sale ids to be manually corrected after purchase workflow trigger
            sale_ids = []
            for move in obj.move_lines:
                data_back = self.create_data_back(move)
                diff_qty = -data_back['product_qty']
                # update corresponding out move - no move created, no need to handle line sequencing policy
                out_move_id = self._update_mirror_move(cr, uid, ids, data_back, diff_qty, out_move=False, context=context)
                # for out cancellation, two points:
                # - if pick/pack/ship: check that nothing is in progress
                # - if nothing in progress, and the out picking is canceled, trigger the so to correct the corresponding so manually
                if out_move_id:
                    out_move = move_obj.browse(cr, uid, out_move_id, context=context)
                    cond1 = out_move.picking_id.subtype == 'standard'
                    cond2 = out_move.picking_id.subtype == 'picking' and out_move.picking_id.has_picking_ticket_in_progress(context=context)[out_move.picking_id.id]
                    if out_move.picking_id.subtype in ('standard', 'picking') and out_move.picking_id.type == 'out' and not out_move.product_qty:
                        # replace the stock move in the procurement order by the non cancelled stock move
                        if (cond1 or cond2) and out_move.picking_id and out_move.picking_id.sale_id:
                            sale_id = out_move.picking_id.sale_id.id
                            move_id = move_obj.search(cr, uid, [('picking_id.type', '=', 'out'),
                                                                ('picking_id.subtype', 'in', ('standard', 'picking')),
                                                                ('picking_id.sale_id', '=', sale_id),
                                                                ('state', 'not in', ('done', 'cancel')),
                                                                ('processed_stock_move', '=', True), ], context=context)
                            if move_id:
                                proc_id = self.pool.get('procurement.order').search(cr, uid, [('move_id', '=', out_move_id)], context=context)
                                self.pool.get('procurement.order').write(cr, uid, proc_id, {'move_id': move_id[0]}, context=context)
                        # the corresponding move can be canceled - the OUT picking workflow is triggered automatically if needed
                        move_obj.action_cancel(cr, uid, [out_move_id], context=context)
                        # open points:
                        # - when searching for open picking tickets - we should take into account the specific move (only product id ?)
                        # - and also the state of the move not in (cancel done)
                        # correct the corresponding so manually if exists - could be in shipping exception
                        if out_move.picking_id and out_move.picking_id.sale_id:
                            if out_move.picking_id.sale_id.id not in sale_ids:
                                sale_ids.append(out_move.picking_id.sale_id.id)

            # correct the corresponding po manually if exists - should be in shipping exception
            if obj.purchase_id:
                wf_service.trg_validate(uid, 'purchase.order', obj.purchase_id.id, 'picking_ok', cr)
                purchase_obj.log(cr, uid, obj.purchase_id.id, _('The Purchase Order %s is %s%% received.') % (obj.purchase_id.name, round(obj.purchase_id.shipped_rate, 2)))
            # correct the corresponding so
            for sale_id in sale_ids:
                wf_service.trg_validate(uid, 'sale.order', sale_id, 'ship_corrected', cr)

        return True

stock_picking()


class purchase_order_line(osv.osv):
    '''
    add the link to procurement order
    '''
    _inherit = 'purchase.order.line'
    _columns = {'procurement_id': fields.many2one('procurement.order', string='Procurement Reference', readonly=True,),
               }
    _defaults = {'procurement_id': False, }

purchase_order_line()


class procurement_order(osv.osv):
    '''
    inherit po_values_hook
    '''
    _inherit = 'procurement.order'

    def po_line_values_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the make_po method from purchase>purchase.py>procurement_order

        - allow to modify the data for purchase order line creation
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        sale_obj = self.pool.get('sale.order.line')
        line = super(procurement_order, self).po_line_values_hook(cr, uid, ids, context=context, *args, **kwargs)
        # give the purchase order line a link to corresponding procurement
        procurement = kwargs['procurement']
        line.update({'procurement_id': procurement.id, })
        # for Internal Request (IR) on make_to_order we update PO line data according to the data of the IR (=sale_order)
        sale_order_line_ids = sale_obj.search(cr, uid, [('procurement_id', '=', procurement.id)], context=context)
        for sol in sale_obj.browse(cr, uid, sale_order_line_ids, context=context):
            if sol.order_id.procurement_request and not sol.product_id and sol.comment:
                line.update({'product_id': False,
                             'name': 'Description: %s' % sol.comment,
                             'comment': sol.comment,
                             'product_qty': sol.product_uom_qty,
                             'price_unit': sol.price_unit,
                             'date_planned': sol.date_planned,
                             'product_uom': sol.product_uom.id,
                             'nomen_manda_0': sol.nomen_manda_0.id,
                             'nomen_manda_1': sol.nomen_manda_1.id or False,
                             'nomen_manda_2': sol.nomen_manda_2.id or False,
                             'nomen_manda_3': sol.nomen_manda_3.id or False,
                             'nomen_sub_0': sol.nomen_sub_0.id or False,
                             'nomen_sub_1': sol.nomen_sub_1.id or False,
                             'nomen_sub_2': sol.nomen_sub_2.id or False,
                             'nomen_sub_3': sol.nomen_sub_3.id or False,
                             'nomen_sub_4': sol.nomen_sub_4.id or False,
                             'nomen_sub_5': sol.nomen_sub_5.id or False})
        return line

procurement_order()

