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
    _columns = {
        'line_number': fields.integer(string='Line', required=True),
        'change_reason': fields.char(string='Change Reason', size=1024, readonly=True),
        'in_out_updated': fields.boolean(string='IN update OUT'),
        'original_qty_partial': fields.integer(string='Original Qty for Partial process - only for sync and partial processed line', required=False),
        'pack_info_id': fields.many2one('wizard.import.in.pack.simulation.screen', 'Pack Info'),
    }
    _defaults = {
        'line_number': 0,
        'in_out_updated': False,
        'original_qty_partial': -1,
    }
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

        if 'pack_info_id' not in defaults:
            defaults['pack_info_id'] = False

        # the tag 'from_button' was added in the web client (openerp/controllers/form.py in the method duplicate) on purpose
        if context.get('from_button'):
            # UF-1797: when we duplicate a doc we delete the link with the poline
            if 'purchase_line_id' not in defaults and not context.get('keepPoLine', False):
                defaults.update(purchase_line_id=False)
            if context.get('subtype', False) == 'incoming':
                # we reset the location_dest_id to 'INPUT' for the 'incoming shipment'
                input_loc = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_input')[1]
                defaults.update(location_dest_id=input_loc)
        return super(stock_move, self).copy_data(cr, uid, id, defaults, context=context)

    def unlink(self, cr, uid, ids, context=None, force=False):
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
            tools_obj.reorder_sequence_number_from_unlink(
                cr,
                uid,
                draft_not_wkf_ids,
                'stock.picking',
                'move_sequence_id',
                'stock.move',
                'picking_id',
                'line_number',
                context=context,
            )

        return super(stock_move, self).unlink(cr, uid, ids, context=context,
                                              force=force)

    def allow_resequencing(self, cr, uid, ids, context=None):
        '''
        define if a resequencing has to be performed or not

        return the list of ids for which resequencing will can be performed

        linked to Picking + Picking draft + not linked to Po/Fo
        '''
        # objects
        pick_obj = self.pool.get('stock.picking')

        resequencing_ids = [x.id for x in self.browse(cr, uid, ids, context=context)
                            if x.picking_id and pick_obj.allow_resequencing(cr, uid, x.picking_id, context=context)]
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
        location_dest_id = super(stock_move, self)._get_location_for_internal_request(cr, uid, context=context, **kwargs)
        move = kwargs['move']
        linked_sol = move.purchase_line_id.linked_sol_id or False
        if linked_sol and linked_sol.order_id.procurement_request and linked_sol.order_id.location_requestor_id.usage != 'customer':
            location_dest_id = linked_sol.order_id.location_requestor_id.id

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
        res = {}
        for obj in self.browse(cr, uid, ids, context=context,
                               fields_to_fetch=['picking_id', 'purchase_line_id', 'id', 'sale_line_id']):
            res[obj.id] = {'move_id': False, 'picking_id': False, 'picking_version': 0, 'quantity': 0, 'moves': []}
            if obj.picking_id and obj.picking_id.type == 'in':
                move_ids = False
                # we are looking for corresponding OUT move from sale order line
                if obj.purchase_line_id and obj.purchase_line_id.linked_sol_id:
                    # find the corresponding OUT move
                    move_ids = self.search(cr, uid, [('product_id', '=', data_back['product_id']),
                                                     ('state', 'in', ('assigned', 'confirmed')),
                                                     ('sale_line_id', '=', obj.purchase_line_id.linked_sol_id.id),
                                                     ('in_out_updated', '=', False),
                                                     ('picking_id.type', '=', 'out'),
                                                     ('processed_stock_move', '=', False),
                                                     ], order="state desc", context=context)
                elif obj.sale_line_id and ('replacement' in obj.picking_id.name or 'missing' in obj.picking_id.name):
                    # find the corresponding OUT move if SO line id
                    move_ids = self.search(cr, uid, [('product_id', '=', data_back['product_id']),
                                                     ('state', 'in', ('assigned', 'confirmed')),
                                                     ('sale_line_id', '=', obj.sale_line_id.id),
                                                     ('in_out_updated', '=', False),
                                                     ('picking_id.type', '=', 'out'),
                                                     ('processed_stock_move', '=', False),
                                                     ], order="state desc", context=context)

                if move_ids:
                    # list of matching out moves
                    integrity_check = []
                    for move in self.browse(cr, uid, move_ids, context=context):
                        pick = move.picking_id
                        cond1 = move.picking_id.subtype == 'standard'
                        cond2 = move.product_qty != 0.00 and pick.subtype == 'picking' and (not pick.backorder_id or pick.backorder_id.subtype == 'standard') and pick.state == 'draft'
                        # move from draft picking or standard picking
                        if cond2 or cond1:
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
                            msg_log = _('The Stock Move %s from %s has already been processed and is '
                                        'therefore not updated.') % (integrity_check[0].name, integrity_check[0].picking_id.name)
                            self.log(cr, uid, integrity_check[0].id, msg_log)

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
               'prodlot_id': move.prodlot_id and move.prodlot_id.id or False,
               'asset_id': move.asset_id and move.asset_id.id or False,
               'expired_date': move.expired_date or False,
               'location_dest_id': move.location_dest_id.id,
               'move_cross_docking_ok': move.move_cross_docking_ok,
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

        if move.price_currency_id:
            move_currency_id = move.price_currency_id.id
        else:
            move_currency_id = move.company_id.currency_id.id
        context['currency_id'] = move_currency_id

        qty = line.quantity
        if line.uom_id.id != line.product_id.uom_id.id:
            qty = uom_obj._compute_qty(cr, uid, line.uom_id.id, line.quantity, line.product_id.uom_id.id)

        product_availability.setdefault(line.product_id.id, line.product_id.qty_available)

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
                current_price = product_obj.price_get(cr, uid, [line.product_id.id], 'standard_price', context=context)[line.product_id.id]
                # Check no division by zero
                if product_availability[line.product_id.id]:
                    new_std_price = ((current_price * product_availability[line.product_id.id])
                                     + (new_price * qty)) / (product_availability[line.product_id.id] + qty)

            new_std_price = currency_obj.compute(cr, uid, line.currency.id, move.company_id.currency_id.id,
                                                 new_std_price, round=True, context=context)

            # Write the field according to price type field
            product_obj.write(cr, uid, [line.product_id.id], {'standard_price': new_std_price})
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

        return average_values, sptc_values

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
            for sol_brw in sol_obj.browse(cr, uid, sol_ids, context=context):
                if sol_brw.order_id.procurement_request:
                    service_non_stock_ok = True

        # We check the dest_type for INCOMING shipment (and not the source_type which is reserved for OUTGOING shipment)
        if wizard.dest_type == 'to_cross_docking' and not service_non_stock_ok:
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
                    'error_msg': '%s\n\nPlease reset the incoming shipment '\
                                 'processing and fix the source of the error'\
                                 'before re-try the processing.' % str(e),
                }, context=context)
        finally:
            # Close the cursor
            new_cr.close(True)

        return res

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
        cur_obj = self.pool.get('res.currency')
        sptc_obj = self.pool.get('standard.price.track.changes')
        picking_obj = self.pool.get('stock.picking')
        wf_service = netsvc.LocalService("workflow")
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

        in_out_updated = True
        if sync_in or context.get('do_not_process_incoming'):
            in_out_updated = False

        backorder_id = False

        internal_loc = loc_obj.search(cr, uid, [('usage', '=', 'internal'), ('cross_docking_location_ok', '=', False)])
        context['location'] = internal_loc

        product_availability = {}
        picking_ids = []
        all_pack_info = {}

        for wizard in inc_proc_obj.browse(cr, uid, wizard_ids, context=context):
            picking_id = wizard.picking_id.id
            picking_dict = picking_obj.read(cr, uid, picking_id, ['move_lines',
                                                                  'type',
                                                                  'purchase_id',
                                                                  'name'], context=context)

            picking_ids.append(picking_id)
            backordered_moves = []  # Moves that need to be put in a backorder
            done_moves = []  # Moves that are completed
            out_picks = set()
            processed_out_moves = []
            track_changes_to_create = [] # list of dict that contains data on track changes to create at the method's end

            picking_move_lines = move_obj.browse(cr, uid, picking_dict['move_lines'],
                                                 context=context)

            total_moves = len(picking_move_lines)
            move_done = 0
            prog_id = self.update_processing_info(cr, uid, picking_id, False, {
                'progress_line': _('In progress (%s/%s)') % (move_done, total_moves),
                'start_date': time.strftime('%Y-%m-%d %H:%M:%S')
            }, context=context)
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
                for line in move_proc_obj.browse(cr, uid, proc_ids, context=context):
                    values = self._get_values_from_line(cr, uid, move, line, db_data_dict, context=context)
                    if context.get('do_not_process_incoming') and line.pack_info_id:
                        # we are processing auto import IN, we must register pack_info data
                        values['pack_info_id'] = line.pack_info_id.id

                    if not values.get('product_qty', 0.00):
                        continue
                    # Check if we must re-compute the price of the product
                    compute_average = not sync_in and picking_dict['type'] == 'in' and line.product_id.cost_method
                    if not sync_in and values.get('location_dest_id', False):
                        compute_average = picking_dict['type'] == 'in' and line.product_id.cost_method == 'average'

                    if compute_average:
                        average_values, sptc_values = self._compute_average_values(cr, uid, move, line, product_availability, context=context)
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

                    if line.pack_info_id:
                        all_pack_info[line.pack_info_id.id] = True
                    remaining_out_qty = line.quantity
                    out_move = None

                    # Sort the OUT moves to get the closest quantities as the IN quantity
                    out_moves = sorted(out_moves, key=lambda x: abs(x.product_qty-line.quantity))

                    for lst_out_move in out_moves:
                        if remaining_out_qty <= 0.00:
                            break

                        out_move = move_obj.browse(cr, uid, lst_out_move.id, context=context)

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
                        if out_move.picking_id.type == 'out' \
                           and out_move.picking_id.subtype == 'picking' \
                           and out_move.picking_id.state == 'draft':
                            out_picks.add(out_move.picking_id.id)

                        if line.uom_id.id != out_move.product_uom.id:
                            uom_partial_qty = uom_obj._compute_qty(cr, uid, line.uom_id.id, remaining_out_qty, out_move.product_uom.id)
                        else:
                            uom_partial_qty = remaining_out_qty

                        # Manage OUT BO moves already processed (forced)
                        bo_moves = []
                        minus_qty = 0.00
                        if out_move.picking_id and out_move.picking_id.backorder_id:
                            bo_moves = move_obj.search(cr, uid, [
                                ('picking_id', '=', out_move.picking_id.backorder_id.id),
                                ('sale_line_id', '=', out_move.sale_line_id.id),
                                ('state', '=', 'done'),
                                ('in_out_updated', '=', False),
                            ], context=context)
                            while bo_moves:
                                boms = move_obj.browse(cr, uid, bo_moves, context=context)
                                bo_moves = []
                                for bom in boms:
                                    if bom.product_uom.id != out_move.product_uom.id:
                                        minus_qty += uom_obj._compute_qty(cr, uid, bom.product_uom.id, bom.product_qty, out_move.product_uom.id)
                                    else:
                                        minus_qty += bom.product_qty
                                    if bom.picking_id and bom.picking_id.backorder_id:
                                        bo_moves.extend(move_obj.search(cr, uid, [
                                            ('picking_id', '=', bom.picking_id.backorder_id.id),
                                            ('sale_line_id', '=', bom.sale_line_id.id),
                                            ('state', '=', 'done'),
                                            ('in_out_updated', '=', False),
                                        ], context=context))

                        if uom_partial_qty < out_move.product_qty:
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
                            sol_to_relink = self.pool.get('sale.order.line').search(cr, uid, [
                                ('order_id', '=', out_move.sale_line_id.order_id.id),
                                ('product_uom_qty', '=', out_move.product_qty - uom_partial_qty),
                                ('line_number', '=', out_move.sale_line_id.line_number),
                                ('order_id', '=', out_move.picking_id.sale_id.id),
                            ], context=context)
                            if sol_to_relink:
                                move_values.update({'sale_line_id': sol_to_relink[0],})
                            move_obj.write(cr, uid, [out_move.id], move_values, context=context)
                            if sol_to_relink:
                                if self.pool.get('sale.order.line').browse(cr, uid, sol_to_relink[0], context=context).state.startswith('cancel'):
                                    move_obj.action_cancel(cr, uid, [out_move.id], context=context)
                            processed_out_moves.append(new_out_move_id)
                        elif uom_partial_qty == out_move.product_qty:
                            out_values.update({
                                'product_qty': remaining_out_qty,
                                'product_uom': line.uom_id.id,
                                'in_out_updated': in_out_updated,
                            })
                            remaining_out_qty = 0.00
                            move_obj.write(cr, uid, [out_move.id], out_values, context=context)
                            processed_out_moves.append(out_move.id)
                        elif uom_partial_qty > out_move.product_qty and out_moves[out_moves.index(out_move)] != out_moves[-1]:
                            # Just update the out move with the value of the out move with UoM of IN
                            out_qty = out_move.product_qty
                            if line.uom_id.id != out_move.product_uom.id:
                                out_qty = uom_obj._compute_qty(cr, uid, out_move.product_uom.id, out_move.product_qty, line.uom_id.id)

                            out_values.update({
                                'product_qty': out_qty,
                                'product_uom': line.uom_id.id,
                                'in_out_updated': in_out_updated,
                            })
                            remaining_out_qty -= out_qty
                            move_obj.write(cr, uid, [out_move.id], out_values, context=context)
                            processed_out_moves.append(out_move.id)
                        else:
                            # Just update the data of the initial out move
                            processed_qty = lst_out_move is out_moves[-1] and uom_partial_qty - minus_qty or out_move.product_qty
                            out_values.update({
                                'product_qty': processed_qty,
                                'product_uom': line.uom_id.id,
                                'in_out_updated': in_out_updated,
                            })
                            move_obj.write(cr, uid, [out_move.id], out_values, context=context)
                            processed_out_moves.append(out_move.id)

                            if line.uom_id.id != out_move.product_uom.id:
                                uom_processed_qty = uom_obj._compute_qty(cr, uid, out_move.product_uom.id, processed_qty, line.uom_id.id)
                            else:
                                uom_processed_qty = processed_qty

                            remaining_out_qty -= uom_processed_qty


                # Decrement the inital move, cannot be less than zero
                diff_qty = move.product_qty - count
                # If there is remaining quantity for the move, put the ID of the move
                # and the remaining quantity to list of moves to put in backorder
                if diff_qty > 0.00 and move.state != 'cancel':
                    backordered_moves.append((move, diff_qty, average_values, data_back, move_sptc_values, line and line.product_id.id))
                    if not sync_in:
                        # decrement qty of linked INTernal move:
                        internal_move = self.pool.get('stock.move').search(cr, uid, [('linked_incoming_move', '=', move.id)], context=context)
                        if internal_move:
                            move_obj.write(cr, uid, internal_move, {'product_qty': diff_qty, 'product_uos_qty': diff_qty}, context=context)
                else:
                    for sptc_values in move_sptc_values:
                        # track change that will be created:
                        track_changes_to_create.append({
                            'product_id': line.product_id.id,
                            'transaction_name': _('Reception %s') % move.picking_id.name,
                            'sptc_values': sptc_values.copy(),
                        })
                    if not sync_in:
                        # cancel linked INTernal move (INT):
                        internal_move = self.pool.get('stock.move').search(cr, uid, [('linked_incoming_move', '=', move.id)], context=context)
                        if internal_move:
                            move_obj.action_cancel(cr, uid, internal_move, context=context)

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
                    'in_dpo': context.get('for_dpo', False),
                }

                if usb_entity == self.REMOTE_WAREHOUSE and not context.get('sync_message_execution', False): # RW Sync - set the replicated to True for not syncing it again
                    initial_vals_copy.update({
                        'already_replicated': False,
                    })

                backorder_id = False
                if context.get('for_dpo', False) and picking_dict['purchase_id']:
                    # Look for an available IN for the same purchase order in case of DPO
                    backorder_ids = self.search(cr, uid, [
                        ('purchase_id', '=', picking_dict['purchase_id'][0]),
                        ('in_dpo', '=', True),
                        ('state', '=', 'assigned'),
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
                        context['keepLineNumber'] = True
                        context['from_button'] = False
                        new_bo_move_id = move_obj.copy(cr, uid, bo_move.id, bo_values, context=context)
                        context['keepLineNumber'] = False
                        # update linked INT move with new BO move id:
                        internal_move = move_obj.search(cr, uid, [('linked_incoming_move', '=', bo_move.id)], context=context)
                        move_obj.write(cr, uid, internal_move, {'linked_incoming_move': new_bo_move_id}, context=context)

                # Put the done moves in this new picking
                done_values = {'picking_id': backorder_id}
                if not context.get('for_dpo'):
                    done_values['dpo_line_id'] = 0
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
                    move_obj.action_cancel(cr, uid, move_ids, context=context)
                    self.action_cancel(cr, uid, [backorder_id], context=context)
                else:
                    wf_service.trg_validate(uid, 'stock.picking', backorder_id, 'button_confirm', cr)
                    # Then we finish the good picking
                    if wizard.register_a_claim and wizard.claim_type in ('return', 'surplus'):
                        if wizard.claim_replacement_picking_expected:
                            move_ids = move_obj.search(cr, uid, [('picking_id', '=', backorder_id)])
                            for move in move_obj.browse(cr, uid, move_ids, context=context):
                                if move.purchase_line_id:
                                    new_qty = move.purchase_line_id.product_qty - move.product_qty
                                    self.pool.get('purchase.order.line').write(cr, uid, [move.purchase_line_id.id], {'product_qty': new_qty}, context=context)
                        # To cancel the created INT
                        self.action_move(cr, uid, [backorder_id], return_goods=True, context=context)
                        # check the OUT availability
                        out_domain = [('backorder_id', '=', backorder_id), ('type', '=', 'out')]
                        out_id = picking_obj.search(cr, uid, out_domain, order='id desc', limit=1, context=context)[0]
                        self.pool.get('picking.tools').check_assign(cr, uid, out_id, context=context)
                    else:
                        self.action_move(cr, uid, [backorder_id], context=context)
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
                prog_id = self.update_processing_info(cr, uid, picking_id, prog_id, {
                    'create_bo': _('N/A'),
                    'close_in': _('In progress'),
                }, context=context)

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
                        move_obj.action_cancel(cr, uid, move_ids, context=context)
                        self.action_cancel(cr, uid, [picking_id], context=context)
                    else:
                        if wizard.register_a_claim and wizard.claim_type in ('return', 'surplus'):
                            if wizard.claim_replacement_picking_expected:
                                move_ids = move_obj.search(cr, uid, [('picking_id', '=', picking_id)])
                                for move in move_obj.browse(cr, uid, move_ids, context=context):
                                    if move.purchase_line_id:
                                        new_qty = move.purchase_line_id.product_qty - move.product_qty
                                        if new_qty:
                                            self.pool.get('purchase.order.line').write(cr, uid, [move.purchase_line_id.id], {'product_qty': new_qty}, context=context)
                                        else:
                                            wf_service.trg_validate(uid, 'purchase.order.line', move.purchase_line_id.id, 'cancel', cr)
                            # To cancel the created INT
                            self.action_move(cr, uid, [picking_id], return_goods=True, context=context)
                            # check the OUT availability
                            out_domain = [('backorder_id', '=', picking_id), ('type', '=', 'out')]
                            out_id = picking_obj.search(cr, uid, out_domain, order='id desc', limit=1, context=context)[0]
                            self.pool.get('picking.tools').check_assign(cr, uid, out_id, context=context)
                        else:
                            self.action_move(cr, uid, [picking_id], context=context)
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
                move_obj.action_assign(cr, uid, processed_out_moves)

            # create track changes:
            for tc_data in track_changes_to_create:
                sptc_obj.track_change(cr, uid, tc_data['product_id'], tc_data['transaction_name'], tc_data['sptc_values'], context=context)

        if not out_picks:
            prog_id = self.update_processing_info(cr, uid, picking_id, prog_id, {
                'prepare_pick': _('N/A'),
            }, context=context)


        # Create the first picking ticket if we are on a draft picking ticket
        if all_pack_info:
            for picking_id in list(out_picks):
                prog_id = self.update_processing_info(cr, uid, picking_id, prog_id, {
                    'prepare_pick': _('In progress'),
                }, context=context)

                move_to_process_ids = self.pool.get('stock.move').search(cr, uid,
                                                                         [('picking_id', '=', picking_id), ('state', 'not in', ['draft', 'done', 'cancel', 'confirmed']), ('product_qty', '!=', 0),
                                                                          ('pack_info_id', 'in', all_pack_info.keys())],
                                                                         context=context)

                if move_to_process_ids:
                    proc_obj = self.pool.get('create.picking.processor')
                    proc_id = proc_obj.create(cr, uid, {'picking_id': picking_id}, context=context)
                    proc_bro = proc_obj.browse(cr, uid, proc_id, context=context)
                    for move_to_process in self.pool.get('stock.move').browse(cr, uid, move_to_process_ids, context=context):
                        line_data = self.pool.get('create.picking.move.processor')._get_line_data(cr, uid, proc_bro, move_to_process, context=context)
                        self.pool.get('create.picking.move.processor').create(cr, uid, line_data, context=context)

                    wiz_context = {}
                    #UF-2531: Pass the name of PICKxxx-y when creating a Pick from crossdocking from an IN partial
                    if context.get('associate_pick_name', False) and context.get('sync_message_execution', False):
                        wiz_context['associate_pick_name'] = context.get('associate_pick_name')
                        del context['associate_pick_name']
                    # We copy all data in lines
                    proc_obj.copy_all(cr, uid, [proc_id], context=wiz_context)

                    # We process the creation of the picking
                    res_wiz = proc_obj.do_create_picking(cr, uid, [proc_id], context=wiz_context)

                    # Validate sub pick
                    new_pick = res_wiz['res_id']
                    pick_val_wiz = self.pool.get('stock.picking').validate_picking(cr, uid, [new_pick], context=context)
                    self.pool.get(pick_val_wiz['res_model']).copy_all(cr, uid, [pick_val_wiz['res_id']], context=context)
                    ppl_val_wiz = self.pool.get(pick_val_wiz['res_model']).do_validate_picking(cr, uid, [pick_val_wiz['res_id']], context=context)

                    # validate PPL
                    ppl_wiz = self.ppl(cr, uid, [ppl_val_wiz['res_id']], context=context)
                    pack_created = {}
                    for ppl_line in self.pool.get('ppl.processor').browse(cr, uid, ppl_wiz['res_id'], context=context).move_ids:
                        if ppl_line.move_id.pack_info_id:
                            if ppl_line.move_id.pack_info_id.id not in pack_created:
                                pack_created[ppl_line.move_id.pack_info_id.id] = self.pool.get('ppl.family.processor').create(cr, uid, {
                                    'wizard_id': ppl_wiz['res_id'],
                                    'from_pack': ppl_line.move_id.pack_info_id.parcel_from,
                                    'to_pack': ppl_line.move_id.pack_info_id.parcel_to,
                                    'length': ppl_line.move_id.pack_info_id.total_length,
                                    'width': ppl_line.move_id.pack_info_id.total_width,
                                    'height': ppl_line.move_id.pack_info_id.total_height,
                                    'weight': ppl_line.move_id.pack_info_id.total_weight,

                                })
                            ppl_line.write({'from_pack': ppl_line.move_id.pack_info_id.parcel_from, 'to_pack': ppl_line.move_id.pack_info_id.parcel_to, 'pack_id': pack_created[ppl_line.move_id.pack_info_id.id]})
                    self.pool.get('ppl.processor').do_check_ppl(cr, uid, ppl_wiz['res_id'], context=context)
                    error_lines_ids = self.pool.get('ppl.move.processor').search(cr, uid, [('wizard_id', '=', ppl_wiz['res_id']), ('integrity_status', '!=', 'empty')], context=context)
                    if error_lines_ids:
                        error_data = []
                        error_string = dict(self.pool.get('ppl.move.processor')._columns['integrity_status'].selection)
                        for error_line in self.pool.get('ppl.move.processor').browse(cr, uid, error_lines_ids, context=context):
                            error_data.append(_('From pack %s, to pack %s, error: %s') % (error_line.from_pack, error_line.to_pack, error_string.get(error_line.integrity_status)))
                        raise osv.except_osv(_('Error'), "\n".join(error_data))

                    self.do_ppl_step2(cr, uid, [ppl_wiz['res_id']])

                prog_id = self.update_processing_info(cr, uid, picking_id, prog_id, {
                    'prepare_pick': _('Done'),
                }, context=context)

        for picking_id in picking_ids:
            prog_id = self.update_processing_info(cr, uid, picking_id, prog_id, {
                'end_date': time.strftime('%Y-%m-%d %H:%M:%S')
            }, context=context)

        # UF-2531: Run the creation of message if it's at RW at some important point
        if usb_entity == self.REMOTE_WAREHOUSE and not context.get('sync_message_execution', False):
            self._manual_create_rw_messages(cr, uid, context=context)

        if context.get('rw_sync', False):
            prog_id = self.update_processing_info(cr, uid, picking_id, prog_id, {
                'end_date': time.strftime('%Y-%m-%d %H:%M:%S')
            }, context=context)
            if backorder_id:
                return backorder_id
            return wizard.picking_id.id

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
                data_back = move_obj.create_data_back(move)
                diff_qty = -data_back['product_qty']
                # update corresponding out move - no move created, no need to handle line sequencing policy
                out_move_id = self._update_mirror_move(cr, uid, ids, data_back, diff_qty, out_move=False, context=context)
                # for out cancellation, two points:
                # - if pick/pack/ship: check that nothing is in progress
                # - if nothing in progress, and the out picking is canceled, trigger the so to correct the corresponding so manually
                if out_move_id:
                    out_move = move_obj.browse(cr, uid, out_move_id, context=context)
                    if out_move.picking_id.subtype in ('standard', 'picking') and out_move.picking_id.type == 'out' and not out_move.product_qty:
                        move_id = False
                        if out_move.picking_id and out_move.sale_line_id:
                            # replace the stock move in the procurement order by the non cancelled stock move
                            sale_id = out_move.picking_id.sale_id.id
                            move_domain = [
                                ('picking_id.type', '=', 'out'),
                                ('picking_id.subtype', 'in', ('standard', 'picking')),
                                #('picking_id.sale_id', '=', sale_id),
                                ('sale_line_id', '=', out_move.sale_line_id.id),
                                ('id', '!=', out_move_id),
                                ('processed_stock_move', '=', True),
                            ]
                            move_domain_not_done = move_domain
                            move_domain_not_cancel = move_domain
                            move_domain_not_done.append(('state', 'not in', ['done', 'cancel']))
                            move_domain_not_cancel.append(('state', '!=', 'cancel'))

                            move_id = move_obj.search(cr, uid, move_domain_not_done, context=context)
                            if not move_id:
                                move_id = move_obj.search(cr, uid, move_domain_not_cancel, context=context)

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

                    # UFTP-345: Check if all lines from the original pick are either closed or cancel and qty is 0, then close this PICK
                    mirror_pick = out_move.picking_id
                    if mirror_pick and mirror_pick.id:
                        ptc = self.browse(cr, uid, mirror_pick.id, context=context)
                        if all(m.product_qty == 0.00 and m.state in ('done', 'cancel') for m in ptc.move_lines):
                            ptc.action_done(context=context)
                        elif mirror_pick.subtype == 'picking' and ptc.state == 'draft':
                            # If there are still some lines available with qty 0, then check if any in progress PICK, if all complete, then close the PICK
                            self.validate(cr, uid, [mirror_pick.id], context=context)

            # correct the corresponding po manually if exists - should be in shipping exception
            if obj.purchase_id:
                wf_service.trg_validate(uid, 'purchase.order', obj.purchase_id.id, 'picking_ok', cr)
                msg_log = _('The Purchase Order %s is %s%% received.') % (obj.purchase_id.name, round(obj.purchase_id.shipped_rate, 2))
                purchase_obj.log(cr, uid, obj.purchase_id.id, msg_log)

            # correct the corresponding so
            for sale_id in sale_ids:
                wf_service.trg_write(uid, 'sale.order', sale_id, cr)
                wf_service.trg_validate(uid, 'sale.order', sale_id, 'ship_corrected', cr)

        return True

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


class purchase_order_line(osv.osv):
    '''
    add the link to procurement order
    '''
    _inherit = 'purchase.order.line'
    _columns = {
        'procurement_id': fields.many2one(
            'procurement.order',
            string='Procurement Reference',
            readonly=True,
        ),
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
            if (sol.order_id.procurement_request or procurement.supplier.partner_type == 'esc') and not sol.product_id and sol.comment:
                line.update({'product_id': False,
                             'name': 'Description: %s' % sol.comment,
                             'comment': procurement.tender_line_id and procurement.tender_line_id.comment or sol.comment,
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

        if procurement.tender_line_id and procurement.tender_line_id.purchase_order_line_id and procurement.tender_line_id.purchase_order_line_id.comment:
            line['comment'] = procurement.tender_line_id.purchase_order_line_id.comment

        return line

procurement_order()
