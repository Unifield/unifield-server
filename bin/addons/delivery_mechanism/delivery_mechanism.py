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

import netsvc
import time
from osv import osv, fields
from tools.translate import _
from order_types.stock import check_rw_warning
import logging
import tools


class stock_picking_processing_info(osv.osv_memory):
    _name = 'stock.picking.processing.info'

    _columns = {
        'picking_id': fields.many2one(
            'stock.picking',
            string='Picking',
            required=True,
            readonly=True,
        ),
        'progress_line': fields.char(
            size=64,
            string='Processing of lines',
            readonly=True,
        ),
        'create_invoice': fields.char(
            size=64,
            string='Create invoice',
            readonly=True,
        ),
        'create_bo': fields.char(
            size=64,
            string='Create Backorder',
            readonly=True,
        ),
        'close_in': fields.char(
            size=64,
            string='Close IN',
            readonly=True,
        ),
        'prepare_pick': fields.char(
            size=64,
            string='Prepare picking ticket',
            readonly=True,
        ),
        'start_date': fields.datetime(
            string='Date start',
            readonly=True,
        ),
        'end_date': fields.datetime(
            string='Date end',
            readonly=True,
        ),
        'error_msg': fields.text(
            string='Error',
            readonly=True,
        ),
    }

    _defaults = {
        'progress_line': _('Not started'),
        'create_invoice': _('Not started'),
        'create_bo': _('Not started'),
        'close_in': _('Not started'),
        'prepare_pick': _('Not started'),
        'end_date': False,
    }

    def refresh(self, cr, uid, ids, context=None):
        '''
        Just refresh the current page
        '''
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': ids[0],
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    def close(self, cr, uid, ids, context=None):
        '''
        Just close the page
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        mem_brw = self.browse(cr, uid, ids[0], context=context)
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'view_picking_in_form')[1]
        tree_view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'view_picking_in_tree')[1]
        src_view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'view_picking_in_search')[1]
        context.update({'picking_type': 'incoming', 'view_id': view_id})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_id': [view_id, tree_view_id],
            'view_type': 'form',
            'view_mode': 'form,tree',
            'search_view_id': src_view_id,
            'target': 'same',
            'domain': [('type', '=', 'in')],
            'res_id': [mem_brw.picking_id.id],
            'context': context,
        }

    def reset_incoming(self, cr, uid, ids, context=None):
        '''
        Delete the processing wizard and close the page
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = self.close(cr, uid, ids, context=context)

        self.unlink(cr, uid, ids, context=context)

        return res

stock_picking_processing_info()


class stock_move(osv.osv):
    '''
    new function to get mirror move
    '''
    _inherit = 'stock.move'

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

stock_move()


class stock_picking(osv.osv):
    '''
    do_partial modification
    '''
    _inherit = 'stock.picking'

    def _get_progress_memory(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns the ID of the stock.picking.processing.info osv_memory linked
        to the picking.
        '''
        mem_obj = self.pool.get('stock.picking.processing.info')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for pick_id in ids:
            res[pick_id] = {
                'progress_memory': -1,
                'progress_memory_not_done': 0,
                'progress_memory_error': 0,
            }
            mem_ids = mem_obj.search(cr, uid, [
                ('picking_id', '=', pick_id),
                ('picking_id.state', '!=', 'done'),
            ], order='start_date desc', context=context)
            if mem_ids:
                res[pick_id]['progress_memory'] = mem_ids[0]
                nd_ids = mem_obj.search(cr, uid, [
                    ('end_date', '=', False),
                    ('id', 'in', mem_ids),
                ], context=context)
                if nd_ids:
                    res[pick_id]['progress_memory_not_done'] = 1
                    for nd in mem_obj.read(cr, uid, nd_ids, ['error_msg'], context=context):
                        if nd['error_msg']:
                            res[pick_id]['progress_memory_error'] = 1
                            break

        return res


    _columns = {
        'move_sequence_id': fields.many2one(
            'ir.sequence',
            string='Moves Sequence',
            help="This field contains the information related to the numbering of the moves of this picking.",
            required=True,
            ondelete='cascade',
        ),
        'change_reason': fields.char(
            string='Change Reason',
            size=1024,
            readonly=True,
        ),
        'progress_memory': fields.function(
            _get_progress_memory,
            method=True,
            string='Has processing info',
            type='integer',
            store=False,
            readonly=True,
            multi='process',
        ),
        'progress_memory_not_done': fields.function(
            _get_progress_memory,
            method=True,
            string='Is in progress',
            type='boolean',
            store=False,
            readonly=True,
            multi='process',
        ),
        'progress_memory_error': fields.function(
            _get_progress_memory,
            method=True,
            string='Processing error',
            type='boolean',
            store=False,
            readonly=True,
            multi='process',
        ),
        'in_dpo': fields.boolean(
            string='Incoming shipment of a DPO',
            readonly=True,
        ),
    }

    def go_to_processing_wizard(self, cr, uid, ids, context=None):
        '''
        If the stock.picking has a stock.picking.processing.info linked to it,
        open this wizard.
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for picking in self.browse(cr, uid, ids, context=context):
            if picking.progress_memory > 0:
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'stock.picking.processing.info',
                    'res_id': int(picking.progress_memory),
                    'view_type': 'form',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': context,
                }

        raise osv.except_osv(
            _('Error'),
            _('The picking has no processing in progress or is already processed'),
        )

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
        res = wizard_obj.open_wizard(cr, uid, ids, w_type='update', context=dict(context,
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
                new_move_id = move_obj.copy(cr, uid, out_move_id, {'product_qty': diff_qty,
                                                                   'product_uom': data_back['product_uom'],
                                                                   'product_uos': data_back['product_uom'],
                                                                   'product_uos_qty': diff_qty, }, context=context)
                move_obj.action_confirm(cr, uid, [new_move_id], context=context)
            else:
                move_obj.write(cr, uid, [out_move_id], {'product_qty': new_qty,
                                                        'product_uom': data['product_uom'][0],
                                                        'product_uos': data['product_uom'][0],
                                                        'product_uos_qty': new_qty, }, context=context)

            # log the modification
            # log creation message
            msg_log = _('The Stock Move %s from %s has been updated to %s %s.') % (stock_move_name, picking_out_name, new_qty, uom_name)
            move_obj.log(cr, uid, out_move_id, msg_log)
        # return updated move or False
        return out_move_id

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
        esc_line_obj = self.pool.get('esc.invoice.line')
        tc_fin_obj = self.pool.get('finance_price.track_changes')

        if context is None:
            context = {}

        average_values = {}

        company_currency_id = move.company_id.currency_id.id

        if move.price_currency_id:
            move_currency_id = move.price_currency_id.id
        else:
            move_currency_id = move.company_id.currency_id.id
        context['currency_id'] = move_currency_id



        compute_finance_price = False
        if self.pool.get('unifield.setup.configuration').get_config(cr, uid, 'esc_line'):
            compute_finance_price = move.picking_id.partner_id.partner_type == 'esc' or move.dpo_line_id and move.purchase_line_id.from_dpo_esc or False

        qty = line.quantity
        if line.uom_id.id != line.product_id.uom_id.id:
            qty = uom_obj._compute_qty(cr, uid, line.uom_id.id, line.quantity, line.product_id.uom_id.id)

        product_availability.setdefault(line.product_id.id, line.product_id.qty_available)
        track_finance_price = []
        tc_fin_ids = []
        if qty > 0.00:
            if compute_finance_price:
                esc_dom = [('state','!=', 'done'), ('product_id', '=', line.product_id.id), ('po_name', '=', move.purchase_line_id.order_id.name)]
                # exact qty
                esc_ids = esc_line_obj.search(cr, uid, esc_dom + [('remaining_qty', '=', qty)], order='state, id', limit=1, context=context)
                if not esc_ids:
                    esc_ids = esc_line_obj.search(cr, uid, esc_dom, order='state, id', context=context)

                remaining_in_qty = qty
                total_price = 0
                for esc_line in esc_line_obj.browse(cr, uid, esc_ids, context=context):
                    if remaining_in_qty <= 0:
                        break
                    unit_iil_price = esc_line.price_unit
                    if esc_line.currency_id.id != company_currency_id:
                        unit_iil_price = currency_obj.compute(cr, uid, esc_line.currency_id.id, company_currency_id, unit_iil_price, round=False, context=context)

                    if esc_line.remaining_qty - remaining_in_qty >= 0.001:
                        total_price += unit_iil_price * remaining_in_qty

                        remaining_iil_qty = esc_line.remaining_qty - remaining_in_qty
                        if abs(remaining_iil_qty) <= 0.001:
                            esc_line_obj.write(cr, uid, esc_line.id, {'state': 'done', 'remaining_qty': 0}, context=context)
                        else:
                            esc_line_obj.write(cr, uid, esc_line.id, {'state': '0_open', 'remaining_qty': remaining_iil_qty}, context=context)
                        track_finance_price.append({'qty_processed': remaining_in_qty, 'price_unit': unit_iil_price, 'matching_type': 'iil', 'esc_invoice_line_id': esc_line.id})
                        remaining_in_qty = 0

                    else:
                        esc_line_obj.write(cr, uid, esc_line.id, {'state': 'done', 'remaining_qty': 0}, context=context)
                        total_price += unit_iil_price * esc_line.remaining_qty
                        remaining_in_qty -= esc_line.remaining_qty
                        track_finance_price.append({'qty_processed': esc_line.remaining_qty, 'price_unit': unit_iil_price, 'matching_type': 'iil', 'esc_invoice_line_id': esc_line.id})

                if remaining_in_qty > 0:
                    # all IIL used: take PO price
                    po_price = move.purchase_line_id.price_unit
                    if move.purchase_line_id.order_id.currency_id.id != company_currency_id:
                        po_price = currency_obj.compute(cr, uid,  move.purchase_line_id.order_id.currency_id.id, company_currency_id, po_price, round=False, context=context)
                    total_price += remaining_in_qty * po_price
                    track_finance_price.append({'qty_processed': remaining_in_qty, 'price_unit': po_price, 'matching_type': 'po', 'purchase_oder_line_id': move.purchase_line_id.id})


                # by remaining qty
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
                if compute_finance_price:
                    new_finance_price = round(total_price / float(qty), 5)
            else:
                # Get the current price in today's rate
                current_price = product_obj.price_get(cr, uid, [line.product_id.id], 'standard_price', context=context)[line.product_id.id]

                # Check no division by zero
                if product_availability[line.product_id.id]:
                    new_std_price = ((current_price * product_availability[line.product_id.id])
                                     + (new_price * qty)) / (product_availability[line.product_id.id] + qty)

                    if compute_finance_price:
                        # TODO : init finance_price
                        if not line.product_id.finance_price:
                            new_finance_price = round(total_price / float(qty), 5)
                        else:
                            new_finance_price = round((line.product_id.finance_price *  product_availability[line.product_id.id] + total_price) / (product_availability[line.product_id.id] + qty), 5)

            new_std_price = round(currency_obj.compute(cr, uid, line.currency.id, move.company_id.currency_id.id,
                                                       new_std_price, round=False, context=context), 5)

            # Write the field according to price type field
            prod_to_write = {'standard_price': new_std_price}
            if compute_finance_price:
                prod_to_write['finance_price'] = new_finance_price
                for tc_fin in track_finance_price:
                    tc_fin.update({'product_id': line.product_id.id, 'old_price': line.product_id.finance_price, 'new_price': new_finance_price, 'stock_before': product_availability.get(line.product_id.id, 0)})
                    tc_fin_ids.append(tc_fin_obj.create(cr, uid, tc_fin, context=context))
            product_obj.write(cr, uid, [line.product_id.id], prod_to_write)

            pchanged = False
            # Is price changed ?
            if line.cost and move.purchase_line_id:
                p_price = move.purchase_line_id.price_unit
                pchanged = abs(p_price - line.cost) > 10**-3
            sptc_values = {
                'standard_price': new_std_price,
                'old_price': line.product_id.standard_price,
                'manually_changed': pchanged,
            }

            # Record the values that were chosen in the wizard, so they can be
            # used for inventory valuation of real-time valuation is enabled.
            average_values = {
                'price_unit': new_price,
                'price_currency_id': line.currency.id,
            }

        return average_values, sptc_values, tc_fin_ids

    def _get_values_from_line(self, cr, uid, move, line, db_data, context=None):
        """
        Prepare the value for a processed move according to line values
        """
        # Objects
        uom_obj = self.pool.get('product.uom')
        pol_obj = self.pool.get('purchase.order.line')
        sol_obj = self.pool.get('sale.order.line')

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
            'asset_id': line.asset_id and line.asset_id.id or False,
            'change_reason': line.change_reason,
            'comment': line.comment or move.comment,
            # Values from incoming wizard
            'direct_incoming': line.wizard_id.direct_incoming,
            # Values for Direct Purchase Order
            'sync_dpo': move.dpo_line_id and True or move.sync_dpo,
            'dpo_line_id': False,
            'location_dest_id': move.location_dest_id.id,
        }
        if move.dpo_line_id:
            if isinstance(move.dpo_line_id, int):
                values['dpo_line_id'] = move.dpo_line_id
            else:
                values['dpo_line_id'] = move.dpo_line_id.id

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

        service_non_stock_ok = False
        if move.purchase_line_id and line.product_id.type in ('consu', 'service_recep'):
            sol_ids = pol_obj.get_sol_ids_from_pol_ids(cr, uid, [move.purchase_line_id.id], context=context)
            if not sol_ids:
                service_non_stock_ok = True
            for sol_brw in sol_obj.browse(cr, uid, sol_ids, context=context):
                if sol_brw.order_id.procurement_request:
                    service_non_stock_ok = True

        if wizard.picking_id and wizard.picking_id.type == 'in' and wizard.register_a_claim and wizard.claim_type in ('surplus', 'return'):
            values['location_dest_id'] = db_data.get('cd_loc')
        elif wizard.picking_id and wizard.picking_id.type == 'in' and line.product_id.type == 'service_recep':
            values['location_dest_id'] = db_data.get('service_loc')
            values['cd_from_bo'] = False
        elif wizard.dest_type == 'to_cross_docking' and not service_non_stock_ok:
            if db_data.get('setup').allocation_setup == 'unallocated':
                raise osv.except_osv(
                    _('Error'),
                    _('You cannot made moves from/to Cross-docking locations when the Allocated stocks configuration is set to \'Unallocated\'.'),
                )
            # Below, "source_type" is only used for the outgoing shipment. We set it to "None" because by default it is
            # "default" and we do not want that info on INCOMING shipment
            wizard.source_type = None
            values.update({
                'location_dest_id': db_data.get('cd_loc'),
                'cd_from_bo': False,
            })
        elif wizard.dest_type == 'to_stock' or service_non_stock_ok:
            # Below, "source_type" is only used for the outgoing shipment. We set it to "None because by default it is
            # "default" and we do not want that info on INCOMING shipment
            if line.product_id.type == 'consu':
                values['location_dest_id'] = db_data.get('non_stock')
            elif line.product_id.type == 'service_recep':
                values['location_dest_id'] = db_data.get('service_loc')
            else:
                # treat moves towards STOCK if NOT SERVICE
                values['location_dest_id'] = db_data.get('input_loc')

            values['cd_from_bo'] = False

        if wizard.dest_type != 'to_cross_docking':
            values['direct_incoming'] = wizard.direct_incoming

        return values

    def update_processing_info(self, cr, uid, picking_id, prog_id=False, values=None, context=None):
        '''
        Update the osv_memory processing info object linked to picking ID.

        :param cr: Cursor to the database
        :param uid: ID of the user that calls the method
        :param picking_id: ID of a stock.picking
        :param prog_id: ID of a stock.picking.processing.info to update
        :param values: Dictoionary that contains the values to put on picking
                       processing object
        :param context: Context of the call

        :return: The ID of the stock.picking.processing.info that have been
                 updated.
        '''
        prog_obj = self.pool.get('stock.picking.processing.info')

        if context is None:
            context = {}

        if context.get('sync_message_execution', False):
            return False

        if not prog_id:
            prog_ids = prog_obj.search(cr, uid, [('picking_id', '=', picking_id)], context=context)
            if prog_ids:
                prog_id = prog_ids[0]
            else:
                prog_id = prog_obj.create(cr, uid, {
                    'picking_id': picking_id,
                }, context=context)

        if not values:
            return prog_id
        prog_obj.write(cr, uid, [prog_id], values, context=context)

        return prog_id

    def do_incoming_shipment_new_cr(self, cr, uid, wizard_ids, context=None):
        """
        Call the do_incoming_shipment() method with a new cursor.
        """
        inc_proc_obj = self.pool.get('stock.incoming.processor')

        # Create new cursor
        import pooler
        new_cr = pooler.get_db(cr.dbname).cursor()

        res = True

        try:
            # Call do_incoming_shipment()
            res = self.do_incoming_shipment(new_cr, uid, wizard_ids, context=context)
            new_cr.commit()
        except Exception, e:
            new_cr.rollback()
            logging.getLogger('stock.picking').warn('Exception do_incoming_shipment', exc_info=True)
            for wiz in inc_proc_obj.read(new_cr, uid, wizard_ids, ['picking_id'], context=context):
                self.update_processing_info(new_cr, uid, wiz['picking_id'][0], False, {
                    'error_msg': _('Error: %s\n\nPlease reset the incoming shipment '\
                                   'processing and fix the source of the error '\
                                   'before re-try the processing.') % tools.ustr(e.value),
                }, context=context)
        finally:
            # Close the cursor
            new_cr.close(True)

        return res

    def do_incoming_shipment(self, cr, uid, wizard_ids, shipment_ref=False, context=None, with_ppl=False):
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
        cur_obj = self.pool.get('res.currency')
        sptc_obj = self.pool.get('standard.price.track.changes')
        picking_obj = self.pool.get('stock.picking')
        chained_loc = self.pool.get('stock.location.chained.options')
        wf_service = netsvc.LocalService("workflow")

        chained_cache = {}

        usb_entity = self._get_usb_entity_type(cr, uid)
        if context is None:
            context = {}

        if isinstance(wizard_ids, (int, long)):
            wizard_ids = [wizard_ids]

        db_data_dict = self._get_db_data_dict(cr, uid)

        # UF-1617: Get the sync_message case
        sync_in = context.get('sync_message_execution', False)
        if context.get('rw_sync', False):
            sync_in = False

        context['bypass_store_function'] = [
            ('stock.picking', ['overall_qty', 'line_state'])
        ]

        in_out_updated = True
        if sync_in or context.get('do_not_process_incoming'):
            in_out_updated = False

        process_avg_sysint = not sync_in and not context.get('do_not_process_incoming')

        backorder_id = False

        internal_loc = loc_obj.search(cr, uid, [('usage', '=', 'internal'), ('cross_docking_location_ok', '=', False)])
        context['location'] = internal_loc

        product_availability = {}
        picking_ids = []
        all_pack_info = {}

        for wizard in inc_proc_obj.browse(cr, uid, wizard_ids, context=context):
            if wizard.register_a_claim and wizard.claim_type in ['return', 'missing']:
                in_out_updated = False
            if not wizard.physical_reception_date:
                wizard.physical_reception_date = time.strftime('%Y-%m-%d %H:%M:%S')
            picking_id = wizard.picking_id.id

            in_forced = wizard.picking_id.state == 'assigned' and \
                not wizard.register_a_claim and \
                process_avg_sysint and \
                wizard.picking_id.purchase_id and \
                wizard.picking_id.purchase_id.partner_type in ('internal', 'section', 'intermission') and \
                wizard.picking_id.purchase_id.order_type != 'direct'

            picking_dict = picking_obj.read(cr, uid, picking_id, ['move_lines',
                                                                  'type',
                                                                  'purchase_id',
                                                                  'name'], context=context)

            picking_ids.append(picking_id)
            backordered_moves = []  # Moves that need to be put in a backorder
            done_moves = []  # Moves that are completed
            out_picks = set()
            processed_out_moves = []
            processed_out_moves_by_exp = {}
            track_changes_to_create = [] # list of dict that contains data on track changes to create at the method's end

            picking_move_lines = move_obj.browse(cr, uid, picking_dict['move_lines'],
                                                 context=context)

            total_moves = len(picking_move_lines)
            move_done = 0
            prog_id = self.update_processing_info(cr, uid, picking_id, False, {
                'progress_line': _('In progress (%s/%s)') % (move_done, total_moves),
                'start_date': time.strftime('%Y-%m-%d %H:%M:%S')
            }, context=context)

            po_line_qty = {}
            for move in picking_move_lines:
                move_done += 1
                prog_id = self.update_processing_info(cr, uid, picking_id, prog_id, {
                    'progress_line': _('In progress (%s/%s)') % (move_done, total_moves),
                }, context=context)
                # Get all processed lines that processed this stock move
                proc_ids = move_proc_obj.search(cr, uid, [('wizard_id', '=', wizard.id), ('move_id', '=', move.id)], context=context)
                # The processed quantity
                count = 0
                need_split = False

                data_back = move_obj.create_data_back(move)
                mirror_data = move_obj.get_mirror_move(cr, uid, [move.id], data_back, context=context)[move.id]
                out_moves = mirror_data['moves']
                average_values = {}
                move_sptc_values = []
                line = False

                if move.purchase_line_id and move.purchase_line_id.id not in po_line_qty:
                    po_line_qty[move.purchase_line_id.id] = move.purchase_line_id.regular_qty_remaining

                for line in move_proc_obj.browse(cr, uid, proc_ids, context=context):
                    values = self._get_values_from_line(cr, uid, move, line, db_data_dict, context=context)
                    if (sync_in or context.get('do_not_process_incoming')) and line.pack_info_id:
                        # we are processing auto import IN, we must register pack_info data
                        values['pack_info_id'] = line.pack_info_id.id

                    if not values.get('product_qty', 0.00):
                        continue

                    tc_ids = []
                    # Check if we must re-compute the price of the product
                    compute_average = process_avg_sysint and picking_dict['type'] == 'in' and line.product_id.cost_method == 'average'

                    if compute_average:
                        average_values, sptc_values, tc_ids = self._compute_average_values(cr, uid, move, line, product_availability, context=context)
                        values.update(average_values)
                        move_sptc_values.append(sptc_values)

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
                        values['purchase_line_id'] = move.purchase_line_id and move.purchase_line_id.id or False
                        context['keepLineNumber'] = True
                        new_move_id = move_obj.copy(cr, uid, move.id, values, context=context)
                        context['keepLineNumber'] = False
                        done_moves.append(new_move_id)

                    if tc_ids:
                        self.pool.get('finance_price.track_changes').write(cr, uid, tc_ids, {'stock_move_id': done_moves[-1]}, context=context)

                    values['processed_stock_move'] = False

                    out_values = values.copy()
                    # Remove sync. DPO fields
                    out_values.update({
                        'dpo_line_id': 0,
                        'sync_dpo': False,
                        'state': 'confirmed',
                        'pack_info_id': line.pack_info_id and line.pack_info_id.id or False,
                    })
                    if out_values.get('location_dest_id', False):
                        out_values.pop('location_dest_id')

                    if with_ppl and line.pack_info_id:
                        all_pack_info[line.pack_info_id.id] = True
                    remaining_out_qty = line.quantity

                    extra_qty = 0
                    extra_fo_qty = 0

                    if move.purchase_line_id:
                        if line.uom_id.id != move.purchase_line_id.product_uom.id:
                            in_qty_po_uom = uom_obj._compute_qty(cr, uid, line.uom_id.id, line.quantity, move.purchase_line_id.product_uom.id)
                        else:
                            in_qty_po_uom = line.quantity

                        if in_qty_po_uom > po_line_qty[move.purchase_line_id.id]:
                            extra_qty = in_qty_po_uom - po_line_qty[move.purchase_line_id.id]

                        po_line_qty[move.purchase_line_id.id] = max(0, po_line_qty[move.purchase_line_id.id] - in_qty_po_uom)

                    out_move = None

                    # Sort the OUT moves to get the closest quantities as the IN quantity
                    out_moves = sorted(out_moves, key=lambda x: abs(x.product_qty-line.quantity))
                    if not context.get('auto_import_ok') and not context.get('sync_message_execution') and not out_moves and extra_qty and move.purchase_line_id.linked_sol_id:
                        # extra qty, if no more out available create a new out line
                        pick_to_use = self.pool.get('sale.order.line').get_existing_pick(cr, uid, move.purchase_line_id.linked_sol_id.id, context=context)
                        move_data_n = self.pool.get('sale.order')._get_move_data(cr, uid, move.purchase_line_id.linked_sol_id.order_id, move.purchase_line_id.linked_sol_id, pick_to_use, context=context)
                        move_data_n.update({'product_qty': extra_qty, 'product_uos_qty': extra_qty, 'product_uos': line.uom_id.id, 'product_uom': line.uom_id.id})
                        move_ids = [self.pool.get('stock.move').create(cr, uid, move_data_n, context=context)]
                        out_moves = self.pool.get('stock.move').browse(cr, uid, move_ids, context=context)
                        extra_fo_qty = extra_qty
                    for lst_out_move in out_moves:
                        if remaining_out_qty <= 0.00:
                            break

                        out_move = move_obj.browse(cr, uid, lst_out_move.id, context=context)

                        # do not try to update OUT if OUT.src_loc != IN(T).dest_loc (compute chained loc ... INPUT > STOCK > MED / LOG
                        if values.get('location_dest_id') != out_move.location_id.id and values.get('location_dest_id') not in [x.id for x in out_move.location_id.child_ids]:
                            loca_dest_id = values.get('location_dest_id')
                            if loca_dest_id not in chained_cache:
                                next_loc = loc_obj.browse(cr, uid, loca_dest_id, fields_to_fetch=['chained_location_id'])
                                chained_cache[loca_dest_id] = next_loc.chained_location_id and next_loc.chained_location_id.id or loca_dest_id
                            next_loc = chained_cache.get(loca_dest_id, loca_dest_id)
                            chain_ids = chained_loc.search(cr, uid, [('nomen_id', '=', line.product_id.nomen_manda_0.id), ('location_id', '=', next_loc)])
                            ok_to_update_out = False

                            if chain_ids:
                                final_dest_id = chained_loc.browse(cr, uid, chain_ids[0], fields_to_fetch=['dest_location_id'])
                                if out_move.location_id.id == final_dest_id.dest_location_id.id or final_dest_id.dest_location_id.id in [x.id for x in out_move.location_id.child_ids]:
                                    ok_to_update_out = True
                            if not ok_to_update_out:
                                continue

                        if values.get('price_unit', False) and out_move.price_currency_id.id != move.price_currency_id.id:
                            price_unit = cur_obj.compute(
                                cr,
                                uid,
                                move.price_currency_id.id,
                                out_move.price_currency_id.id,
                                values.get('price_unit'),
                                round=False,
                                context=context
                            )
                            out_values['price_unit'] = price_unit
                            out_values['price_currency_id'] = out_move.price_currency_id.id

                        # List the Picking Ticket that need to be created from the Draft Picking Ticket
                        if out_move.picking_id.type == 'out':
                            out_values['purchase_line_id'] = False
                            if out_move.picking_id.subtype == 'picking' and out_move.picking_id.state == 'draft':
                                out_picks.add(out_move.picking_id.id)

                        if line.uom_id.id != out_move.product_uom.id:
                            uom_partial_qty = uom_obj._compute_qty(cr, uid, line.uom_id.id, remaining_out_qty, out_move.product_uom.id)
                        else:
                            uom_partial_qty = remaining_out_qty

                        # we need to check if the current IN has already been modified by this loop (out_move.id not in processed_out_moves)
                        # to not change again an already modifier qty
                        # split IN lines two times and set the whole original qty on the 3 lines (ie: extra qty received with split)
                        if uom_partial_qty < out_move.product_qty and out_move.id not in processed_out_moves:
                            # Splt the out move
                            out_values.update({
                                'product_qty': remaining_out_qty,
                                'product_uom': line.uom_id.id,
                                'in_out_updated': in_out_updated,
                            })
                            context['keepLineNumber'] = True
                            new_out_move_id = move_obj.copy(cr, uid, out_move.id, out_values, context=context)
                            context['keepLineNumber'] = False
                            remaining_out_qty = 0.00
                            move_values = {
                                'product_qty': out_move.product_qty - uom_partial_qty,
                                'product_uos_qty': out_move.product_qty - uom_partial_qty,
                            }
                            # search for sol that match with the updated move:
                            move_obj.write(cr, uid, [out_move.id], move_values, context=context)
                            processed_out_moves.append(new_out_move_id)
                            processed_out_moves_by_exp.setdefault(line.prodlot_id and line.prodlot_id.life_date or False, []).append(new_out_move_id)

                        elif uom_partial_qty == out_move.product_qty and out_move.id not in processed_out_moves:
                            out_values.update({
                                'product_qty': remaining_out_qty,
                                'product_uom': line.uom_id.id,
                                'in_out_updated': in_out_updated,
                            })
                            remaining_out_qty = 0.00
                            move_obj.write(cr, uid, [out_move.id], out_values, context=context)
                            processed_out_moves.append(out_move.id)
                            processed_out_moves_by_exp.setdefault(line.prodlot_id and line.prodlot_id.life_date or False, []).append(out_move.id)
                        elif uom_partial_qty > out_move.product_qty and out_move.id not in processed_out_moves:
                            if out_moves[out_moves.index(out_move)] != out_moves[-1]:
                                # Just update the out move with the value of the out move with UoM of IN
                                out_qty = out_move.product_qty
                                if line.uom_id.id != out_move.product_uom.id:
                                    out_qty = uom_obj._compute_qty(cr, uid, out_move.product_uom.id, out_move.product_qty, line.uom_id.id)
                                remaining_out_qty -= out_qty
                            else:
                                # last move we have extra qty
                                # extra: total IN - remanining OUT - already focred
                                if extra_qty > 0 and not context.get('auto_import_ok') and not context.get('sync_message_execution'):
                                    self.infolog(cr, uid, '%s, in line id %s Extra qty %s received' % (move.picking_id.name, move.id, extra_qty))
                                    # IN pre-processing : do not add extra qty in OUT, it will be added later on IN processing
                                    extra_fo_qty = extra_qty
                                    if out_move.product_uom.id != move.purchase_line_id.product_uom.id:
                                        out_qty = out_move.product_qty + uom_obj._compute_qty(cr, uid, move.purchase_line_id.product_uom.id, extra_qty, out_move.product_uom.id)
                                    else:
                                        out_qty = out_move.product_qty + extra_qty
                                    extra_qty = 0
                                else:
                                    out_qty = out_move.product_qty
                                remaining_out_qty = 0

                            out_values.update({
                                'product_qty': out_qty,
                                'product_uom': line.uom_id.id,
                                'in_out_updated': in_out_updated,
                            })
                            move_obj.write(cr, uid, [out_move.id], out_values, context=context)
                            processed_out_moves.append(out_move.id)
                            processed_out_moves_by_exp.setdefault(line.prodlot_id and line.prodlot_id.life_date or False, []).append(out_move.id)
                        else:
                            # OK all OUT lines processed and still have extra qty !
                            if extra_qty > 0 and not context.get('auto_import_ok') and not context.get('sync_message_execution'):
                                self.infolog(cr, uid, '%s, (2) in line id %s Extra qty %s received' % (move.picking_id.name, move.id, extra_qty))
                                extra_fo_qty = extra_qty
                                product_qty = move_obj.read(cr, uid, out_move.id, ['product_qty'], context=context)['product_qty']
                                if out_move.product_uom.id != move.purchase_line_id.product_uom.id:
                                    product_qty += uom_obj._compute_qty(cr, uid, move.purchase_line_id.product_uom.id, extra_qty, out_move.product_uom.id)
                                else:
                                    product_qty += extra_qty
                                move_obj.write(cr, uid, out_move.id, {'product_qty': product_qty}, context=context)
                                extra_qty = 0
                            remaining_out_qty = 0

                    if extra_fo_qty:
                        if move.purchase_line_id.sale_order_line_id:
                            self.infolog(cr, uid, '%s, in line id %s Extra qty %s received for %s' % (move.picking_id.name, move.id, extra_fo_qty, move.purchase_line_id.sale_order_line_id.order_id.name))
                            sol_extra = self.pool.get('sale.order.line').browse(cr, uid, move.purchase_line_id.sale_order_line_id.id, fields_to_fetch=['extra_qty', 'product_uom'], context=context)
                            if sol_extra.product_uom.id != move.purchase_line_id.product_uom.id:
                                extra_fo_qty = (sol_extra.extra_qty or 0) + uom_obj._compute_qty(cr, uid, move.purchase_line_id.product_uom.id, extra_fo_qty, sol_extra.product_uom.id)
                            else:
                                extra_fo_qty += sol_extra.extra_qty or 0
                            self.pool.get('sale.order.line').write(cr, uid, move.purchase_line_id.sale_order_line_id.id, {'extra_qty': extra_fo_qty}, context=context)
                        extra_fo_qty = 0


                # Decrement the inital move, cannot be less than zero
                diff_qty = move.product_qty - count
                # If there is remaining quantity for the move, put the ID of the move
                # and the remaining quantity to list of moves to put in backorder
                if diff_qty > 0.00 and move.state != 'cancel':
                    backordered_moves.append((move, diff_qty, average_values, data_back, move_sptc_values, line and line.product_id.id))
                    if process_avg_sysint:
                        move_obj.decrement_sys_init(cr, uid, count, pol_id=move.purchase_line_id and move.purchase_line_id.id or False, context=context)
                elif not wizard.register_a_claim or not wizard.claim_replacement_picking_expected:
                    for sptc_values in move_sptc_values:
                        # track change that will be created:
                        track_changes_to_create.append({
                            'product_id': line.product_id.id,
                            'transaction_name': _('Reception %s') % move.picking_id.name,
                            'sptc_values': sptc_values.copy(),
                        })
                    if process_avg_sysint:
                        # update SYS-INT:
                        # min(move.product_qty, count) used if more qty is received
                        move_obj.decrement_sys_init(cr, uid, min(move.product_qty, count), pol_id=move.purchase_line_id and move.purchase_line_id.id or False, context=context)

            # Set the Shipment Ref from the IN import
            pick_partner = wizard.picking_id.partner_id
            imp_shipment_ref = ''
            if not sync_in and wizard.imp_shipment_ref and (not pick_partner or pick_partner.partner_type in ['external', 'esc']):
                imp_shipment_ref = wizard.imp_shipment_ref

            prog_id = self.update_processing_info(cr, uid, picking_id, prog_id, {
                'progress_line': _('Done (%s/%s)') % (move_done, total_moves),
            }, context=context)
            # Create the backorder if needed
            if backordered_moves:
                prog_id = self.update_processing_info(cr, uid, picking_id, prog_id, {
                    'create_bo': _('In progress'),
                }, context=context)
                initial_vals_copy = {
                    'name':sequence_obj.get(cr, uid, 'stock.picking.%s' %
                                            (picking_dict['type'])),
                    'move_lines':[],
                    'state':'draft',
                    'in_dpo': context.get('for_dpo', False), # TODO used ?
                    'dpo_incoming': wizard.picking_id.dpo_incoming,
                    'physical_reception_date': wizard.physical_reception_date or False,
                }

                if usb_entity == self.REMOTE_WAREHOUSE and not context.get('sync_message_execution', False): # RW Sync - set the replicated to True for not syncing it again
                    initial_vals_copy.update({
                        'already_replicated': False,
                    })

                backorder_id = False
                backorder_ids = False
                if context.get('for_dpo', False) and picking_dict['purchase_id']:
                    # Look for an available IN for the same purchase order in case of DPO
                    backorder_ids = self.search(cr, uid, [
                        ('purchase_id', '=', picking_dict['purchase_id'][0]),
                        ('in_dpo', '=', True),
                        ('state', '=', 'assigned'),

                    ], limit=1, context=context)
                elif sync_in and picking_dict['purchase_id'] and shipment_ref:
                    backorder_ids = self.search(cr, uid, [
                        ('purchase_id', '=', picking_dict['purchase_id'][0]),
                        ('shipment_ref', '=', shipment_ref),
                        ('state', '=', 'shipped'),
                    ], limit=1, context=context)

                if backorder_ids:
                    backorder_id = backorder_ids[0]

                backorder_name = picking_dict['name']
                if not backorder_id:
                    backorder_id = self.copy(cr, uid, picking_id, initial_vals_copy, context=context)
                    backorder_name = self.read(cr, uid, backorder_id, ['name'], context=context)['name']

                    back_order_post_copy_vals = {}
                    if usb_entity == self.CENTRAL_PLATFORM and context.get('rw_backorder_name', False):
                        new_name = context.get('rw_backorder_name')
                        del context['rw_backorder_name']
                        back_order_post_copy_vals['name'] = new_name

                    if picking_dict['purchase_id']:
                        # US-111: in case of partial reception invoice was not linked to PO
                        # => analytic_distribution_supply/stock.py _invoice_hook
                        #    picking.purchase_id was False
                        back_order_post_copy_vals['purchase_id'] = picking_dict['purchase_id'][0]
                        back_order_post_copy_vals['from_wkf'] = True

                    if imp_shipment_ref:
                        back_order_post_copy_vals['shipment_ref'] = imp_shipment_ref

                    if wizard.imp_filename:
                        back_order_post_copy_vals['last_imported_filename'] = wizard.imp_filename

                    if back_order_post_copy_vals:
                        self.write(cr, uid, backorder_id, back_order_post_copy_vals, context=context)

                for bo_move, bo_qty, av_values, data_back, move_sptc_values, p_id in backordered_moves:
                    for sptc_values in move_sptc_values:
                        sptc_obj.track_change(cr, uid, p_id,
                                              _('Reception %s') % backorder_name,
                                              sptc_values, context=context)
                    if bo_move.product_qty != bo_qty:
                        # Create the corresponding move in the backorder - reset batch - reset asset_id
                        bo_values = {
                            'asset_id': data_back['asset_id'],
                            'product_qty': bo_qty,
                            'product_uos_qty': bo_qty,
                            'product_uom': data_back['product_uom'],
                            'product_uos': data_back['product_uom'],
                            'product_id': data_back['product_id'],
                            'location_dest_id': data_back['location_dest_id'],
                            'move_cross_docking_ok': data_back['move_cross_docking_ok'],
                            'prodlot_id': data_back['prodlot_id'],
                            'expired_date': data_back['expired_date'],
                            'state': 'assigned',
                            'move_dest_id': False,
                            'change_reason': False,
                            'processed_stock_move': True,
                            'dpo_line_id': bo_move.dpo_line_id,
                            'purchase_line_id': bo_move.purchase_line_id and bo_move.purchase_line_id.id or False,
                        }
                        bo_values.update(av_values)
                        if in_forced:
                            # set in_forced on remaining (assigned qty): used for future sync msg processing
                            bo_values['in_forced'] = True

                        context['keepLineNumber'] = True
                        context['from_button'] = False
                        new_bo_move_id = move_obj.copy(cr, uid, bo_move.id, bo_values, context=context)
                        context['keepLineNumber'] = False
                        # update linked INT move with new BO move id:
                        internal_move = move_obj.search(cr, uid, [('linked_incoming_move', '=', bo_move.id)], context=context)
                        move_obj.write(cr, uid, internal_move, {'linked_incoming_move': new_bo_move_id}, context=context)

                # Put the done moves in this new picking
                done_values = {'picking_id': backorder_id}
                if in_forced:
                    done_values['in_forced'] = True
                move_obj.write(cr, uid, done_moves, done_values, context=context)
                prog_id = self.update_processing_info(cr, uid, picking_id, prog_id, {
                    'create_bo': _('Done'),
                    'close_in': _('In progress'),
                }, context=context)
                # update track changes data linked to this moved moves:
                for tc_data in track_changes_to_create:
                    tc_data['transaction_name'] = _('Reception %s') % backorder_name

                if sync_in:
                    # UF-1617: When it is from the sync., then just send the IN to shipped, then return the backorder_id
                    if context.get('for_dpo', False):
                        wf_service.trg_validate(uid, 'stock.picking', backorder_id, 'button_confirm', cr)
                    else:
                        wf_service.trg_validate(uid, 'stock.picking', backorder_id, 'button_shipped', cr)
                    return backorder_id
                elif picking_dict['type'] == 'in' and context.get('do_not_process_incoming'):
                    wf_service.trg_validate(uid, 'stock.picking', backorder_id, 'updated', cr)
                    prog_id = self.update_processing_info(cr, uid, backorder_id, prog_id, {
                        'end_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                    }, context=context)
                    return backorder_id

                self.write(cr, uid, [picking_id], {'backorder_id': backorder_id, 'cd_from_bo': values.get('cd_from_bo', False)},
                           context=context)

                # Claim specific code
                current_backorder = picking_obj.read(cr, uid, backorder_id, ['backorder_id'], context=context)
                if wizard.register_a_claim and not current_backorder['backorder_id']:  # add backorder to the IN
                    picking_obj.write(cr, uid, backorder_id, ({'backorder_id': picking_dict['id']}), context=context)
                self._claim_registration(cr, uid, wizard, backorder_id, context=context)

                # Cancel missing IN instead of processing
                if wizard.register_a_claim and wizard.claim_type == 'missing':
                    move_ids = move_obj.search(cr, uid, [('picking_id', '=', backorder_id)])
                    move_obj.write(cr, uid, move_ids, {'purchase_line_id': False, 'state': 'cancel'})
                    self.action_cancel(cr, uid, [backorder_id], context=context)
                else:
                    wf_service.trg_validate(uid, 'stock.picking', backorder_id, 'button_confirm', cr)
                    # Then we finish the good picking
                    return_goods =  wizard.register_a_claim and wizard.claim_type in ('return', 'surplus')
                    self.action_move(cr, uid, [backorder_id], return_goods=return_goods, context=context)
                    if return_goods:
                        # check the OUT availability
                        out_domain = [('backorder_id', '=', backorder_id), ('type', '=', 'out')]
                        out_id = picking_obj.search(cr, uid, out_domain, order='id desc', limit=1, context=context)[0]
                        self.pool.get('picking.tools').check_assign(cr, uid, out_id, context=context)
                    wf_service.trg_validate(uid, 'stock.picking', backorder_id, 'button_done', cr)
                wf_service.trg_write(uid, 'stock.picking', picking_id, cr)
                prog_id = self.update_processing_info(cr, uid, picking_id, prog_id, {
                    'close_in': _('Done'),
                }, context=context)
                bo_name = self.read(cr, uid, backorder_id, ['name'], context=context)['name']
                self.infolog(cr, uid, "The Incoming Shipment id:%s (%s) has been processed. Backorder id:%s (%s) has been created." % (
                    backorder_id, bo_name, picking_id, picking_dict['name'],
                ))
            else:
                # no BO to create
                prog_id = self.update_processing_info(cr, uid, picking_id, prog_id, {
                    'create_bo': _('N/A'),
                    'close_in': _('In progress'),
                }, context=context)

                to_write = {}
                if wizard.physical_reception_date:
                    to_write.update({'physical_reception_date': wizard.physical_reception_date})
                if imp_shipment_ref:
                    to_write.update({'shipment_ref': imp_shipment_ref})
                if wizard.imp_filename:
                    to_write.update({'last_imported_filename': wizard.imp_filename})
                if to_write:
                    self.write(cr, uid, picking_id, to_write, context=context)

                # Claim specific code
                self._claim_registration(cr, uid, wizard, picking_id, context=context)

                if sync_in:  # If it's from sync, then we just send the pick to become Available Shippde, not completely close!
                    if context.get('for_dpo', False):
                        self.write(cr, uid, [picking_id], {'in_dpo': True}, context=context)
                    else:
                        self.write(cr, uid, [picking_id], {'state': 'shipped'}, context=context)
                    return picking_id
                elif picking_dict['type'] == 'in' and context.get('do_not_process_incoming'):
                    wf_service.trg_validate(uid, 'stock.picking', picking_id, 'updated', cr)
                    prog_id = self.update_processing_info(cr, uid, picking_id, prog_id, {
                        'end_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                    }, context=context)
                    return picking_id
                else:
                    # Cancel missing IN instead of processing
                    if wizard.register_a_claim and wizard.claim_type == 'missing':
                        move_ids = move_obj.search(cr, uid, [('picking_id', '=', picking_id)])
                        move_obj.write(cr, uid, move_ids, {'purchase_line_id': False, 'state': 'cancel'})
                        self.action_cancel(cr, uid, [picking_id], context=context)
                    else:
                        return_goods = wizard.register_a_claim and wizard.claim_type in ('return', 'surplus')
                        if not return_goods and in_forced:
                            move_ids = move_obj.search(cr, uid, [('picking_id', '=', picking_id), ('state', '=', 'assigned')])
                            if move_ids:
                                move_obj.write(cr, uid, move_ids, {'in_forced': True}, context=context)
                        self.action_move(cr, uid, [picking_id], return_goods=return_goods, context=context)
                        if return_goods:
                            out_domain = [('backorder_id', '=', picking_id), ('type', '=', 'out')]
                            out_id = picking_obj.search(cr, uid, out_domain, order='id desc', limit=1, context=context)[0]
                            self.pool.get('picking.tools').check_assign(cr, uid, out_id, context=context)
                        wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_done', cr)

                    if picking_dict['purchase_id']:
                        so_ids = self.pool.get('purchase.order').get_so_ids_from_po_ids(cr, uid, picking_dict['purchase_id'][0], context=context)
                        for so_id in so_ids:
                            wf_service.trg_write(uid, 'sale.order', so_id, cr)
                    if usb_entity == self.REMOTE_WAREHOUSE:
                        self.write(cr, uid, [picking_id], {'already_replicated': False}, context=context)
                prog_id = self.update_processing_info(cr, uid, picking_id, prog_id, {
                    'close_in': _('Done'),
                }, context=context)
                self.infolog(cr, uid, "The Incoming Shipment id:%s (%s) has been processed." % (
                    picking_id, picking_dict['name'],
                ))

            if not sync_in and wizard.claim_type not in ('scrap', 'quarantine', 'return', 'missing'):
                to_process = []
                for ed in sorted(processed_out_moves_by_exp.keys()):
                    to_process += processed_out_moves_by_exp[ed]
                move_obj.action_assign(cr, uid, to_process)

            # create track changes:
            for tc_data in track_changes_to_create:
                sptc_obj.track_change(cr, uid, tc_data['product_id'], tc_data['transaction_name'], tc_data['sptc_values'], context=context)

        if not out_picks:
            prog_id = self.update_processing_info(cr, uid, picking_id, prog_id, {
                'prepare_pick': _('N/A'),
            }, context=context)


        overall_to_compute = list(out_picks)
        # Create the first picking ticket if we are on a draft picking ticket
        if all_pack_info:
            for picking_id in list(out_picks):
                prog_id = self.update_processing_info(cr, uid, picking_id, prog_id, {
                    'prepare_pick': _('In progress'),
                }, context=context)
                pack_obj = self.pool.get('wizard.import.in.pack.simulation.screen')
                for pack in pack_obj.read_group(cr, uid, [('id', 'in', all_pack_info.keys())], ['packing_list'], ['packing_list'], offset=0, orderby='packing_list'):
                    pack_ids = pack_obj.search(cr, uid, pack['__domain'], context=context)

                    move_to_process_ids = self.pool.get('stock.move').search(cr, uid,
                                                                             [('picking_id', '=', picking_id), ('state', 'not in', ['draft', 'done', 'cancel', 'confirmed']), ('product_qty', '!=', 0),
                                                                              ('pack_info_id', 'in', pack_ids)],
                                                                             context=context)

                    if move_to_process_ids:
                        # sub pick creation
                        new_pick = self.do_create_picking(cr, uid, [picking_id], context=context, only_pack_ids=pack_ids).get('res_id')
                        overall_to_compute.append(new_pick)
                        if  pack['packing_list']:
                            self.write(cr, uid, [new_pick], {'packing_list': pack['packing_list']}, context=context)


                        # ppl creation
                        ppl_id = self.do_validate_picking(cr, uid, [new_pick], context=context, ignore_quick=True).get('res_id')
                        self.check_ppl_integrity(cr, uid, [ppl_id], context=context)
                        stock_issues_ids = self.pool.get('stock.move').search(cr, uid, [('picking_id', '=', ppl_id), ('integrity_error', '!=', 'empty')], context=context)
                        if stock_issues_ids:
                            error_data = []
                            error_string = dict(self.pool.get('stock.move')._columns['integrity_error'].selection)
                            for error_line in self.pool.get('stock.move').browse(cr, uid, stock_issues_ids, context=context):
                                error_data.append(_('From pack %s, to pack %s, error: %s') % (error_line.from_pack, error_line.to_pack, error_string.get(error_line.integrity_error)))
                            raise osv.except_osv(_('Error'), "\n".join(error_data))

                        # shipment creation (ppl step2)
                        step2_wiz_id = self.ppl_step2_run_wiz(cr, uid, [ppl_id], context=context).get('res_id')
                        self.do_ppl_step2(cr, uid, [step2_wiz_id], context=context)

                prog_id = self.update_processing_info(cr, uid, picking_id, prog_id, {
                    'prepare_pick': _('Done'),
                }, context=context)

        if overall_to_compute:
            self._store_set_values(cr, uid, overall_to_compute, ['overall_qty', 'line_state'], context)
        for picking_id in picking_ids:
            prog_id = self.update_processing_info(cr, uid, picking_id, prog_id, {
                'end_date': time.strftime('%Y-%m-%d %H:%M:%S')
            }, context=context)

        if context.get('from_simu_screen'):
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'view_picking_in_form')[1]
            tree_view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'view_picking_in_tree')[1]
            src_view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'view_picking_in_search')[1]
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'res_id': wizard.picking_id.id,
                'view_id': [view_id, tree_view_id],
                'search_view_id': src_view_id,
                'view_mode': 'form, tree',
                'view_type': 'form',
                'target': 'crush',
                'context': context}

        return {'type': 'ir.actions.act_window_close'}

    def _manual_create_rw_messages(self, cr, uid, context=None):
        return

    def enter_reason_cr(self, cr, uid, ids, context=None):
        return self.enter_reason(cr, uid, ids, context=context)

    @check_rw_warning
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
        pick = self.browse(cr, uid, ids[0], fields_to_fetch=['from_wkf_sourcing', 'dpo_incoming', 'type', 'state', 'partner_id'])
        if pick['type'] == 'in' and pick['dpo_incoming'] and not pick['from_wkf_sourcing']:
            context['in_from_dpo'] = True
        if pick['type'] == 'in' and not pick['dpo_incoming'] and pick['state'] == 'assigned' and pick.partner_id.partner_type not in ('esc', 'external'):
            if self.pool.get('stock.move').search_exists(cr, uid, [('picking_id', '=', pick.id), ('in_forced', '=', False), ('state', '!=', 'cancel')], context=context):
                context['display_warning'] = True
        # open the selected wizard
        return wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=dict(context, picking_id=ids[0]))

    def write(self, cr, uid, ids, vals, context=None):
        '''
        Return True in case of context contains "go_to_processing_wizard" because
        without that, the displaying of the wizard waits that the background
        process (SQL LOCK on row)
        '''
        if not ids:
            return True
        if context is None:
            context = {}

        if context.get('button', False) == 'go_to_processing_wizard':
            return True
        elif context.get('button', False) == 'enter_reason':
            mem_obj = self.pool.get('stock.picking.processing.info')
            mem_ids = mem_obj.search(cr, uid, [
                ('end_date', '=', False),
                ('picking_id', 'in', ids),
            ], context=context)
            if mem_ids:
                raise osv.except_osv(
                    _('Error'),
                    _('The processing of this picking is in progress - You can\'t cancel it.'),
                )

        return super(stock_picking, self).write(cr, uid, ids, vals, context=context)


stock_picking()
