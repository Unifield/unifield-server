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
import datetime

import netsvc


class stock_move(osv.osv):
    '''
    new function to get mirror move
    '''
    _inherit = 'stock.move'
    _columns = {'line_number': fields.integer(string='Line', required=True),
                'change_reason': fields.char(string='Change Reason', size=1024, readonly=True),
                'in_out_updated': fields.boolean(string='IN update OUT'),
                }
    _defaults = {'line_number': 0,
                 'in_out_updated': False}
    _order = 'line_number, date_expected desc, id'
    
    def create(self, cr, uid, vals, context=None):
        '''
        add the corresponding line number
        
        if a corresponding purchase order line or sale order line exist
        we take the line number from there
        '''
        # objects
        picking_obj = self.pool.get('stock.picking')
        seq_pool = self.pool.get('ir.sequence')

        # line number correspondance to be checked with Magali
        if vals.get('picking_id', False):
            if not vals.get('line_number', False):
                # new number needed - gather the line number from the sequence
                sequence_id = picking_obj.read(cr, uid, [vals['picking_id']], ['move_sequence_id'], context=context)[0]['move_sequence_id'][0]
                line = seq_pool.get_id(cr, uid, sequence_id, test='id', context=context)
                # update values with line value
                vals.update({'line_number': line})
        
        # create the new object
        result = super(stock_move, self).create(cr, uid, vals, context=context)
        return result
    
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
                                                             ('in_out_updated', '=', False)], order="state desc", context=context)
                            # list of matching out moves
                            integrity_check = []
                            for move in self.browse(cr, uid, move_ids, context=context):
                                # move from draft picking or standard picking
                                if (move.product_qty != 0.00 and not move.processed_stock_move and move.picking_id.subtype == 'picking' and not move.picking_id.backorder_id and move.picking_id.state == 'draft') or (move.picking_id.subtype == 'standard') and move.picking_id.type == 'out':
                                    integrity_check.append(move)
                            # return the first one matching
                            if integrity_check:
                                if all([not move.processed_stock_move for move in integrity_check]):
                                    # the out stock moves (draft picking or std out) have not yet been processed, we can therefore update them
                                    res[obj.id]['move_id'] = integrity_check[0].id
                                    res[obj.id]['moves'] = integrity_check
                                    res[obj.id]['picking_id'] = integrity_check[0].picking_id.id
                                    res[obj.id]['picking_version'] = integrity_check[0].picking_id.update_version_from_in_stock_picking
                                    res[obj.id]['quantity'] = integrity_check[0].product_qty
                                else:
                                    # the corresponding OUT move have been processed completely or partially,, we do not update the OUT
                                    self.log(cr, uid, integrity_check[0].id, _('The Stock Move %s from %s has already been processed and is therefore not updated.')%(integrity_check[0].name, integrity_check[0].picking_id.name))
                                    
            else:
                # we are looking for corresponding IN from on_order purchase order
                assert False, 'This method is not implemented for OUT or Internal moves'
                
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
        vals.update({'move_sequence_id': new_seq_id,})
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
            seq_pool.write(cr, uid, [new_seq_id], {'number_next': seq_value,})
            
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
        
        return defaults
    
    def create_data_back(self, cr, uid, move, context=None):
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
                      'prodlot_id': False, # reset batch number
                      'asset_id': False, # reset asset
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
                                                                   'product_uos_qty': diff_qty,}, context=context)
                move_obj.action_confirm(cr, uid, [new_move_id], context=context)
#                if present_qty == 0.00:
#                    move_obj.write(cr, uid, [out_move_id], {'state': 'draft'})
#                    move_obj.unlink(cr, uid, out_move_id, context=context)
            else:
                move_obj.write(cr, uid, [out_move_id], {'product_qty' : new_qty,
                                                        'product_uom': data['product_uom'][0],
                                                        'product_uos': data['product_uom'][0],
                                                        'product_uos_qty': new_qty,}, context=context)
    
            # log the modification
            # log creation message
            move_obj.log(cr, uid, out_move_id, _('The Stock Move %s from %s has been updated to %s %s.')%(stock_move_name, picking_out_name, new_qty, uom_name))
        # return updated move or False
        return out_move_id
    
    def _do_incoming_shipment_first_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        hook to update values for stock move if first encountered
        '''
        values = kwargs.get('values')
        assert values is not None, 'missing values'
        return values
    
    def do_incoming_shipment(self, cr, uid, ids, context=None):
        '''
        validate the picking ticket from selected stock moves
        
        move here the logic of validate picking
        available for picking loop
        '''
        assert context, 'context is not defined'
        assert 'partial_datas' in context, 'partial datas not present in context'
        partial_datas = context['partial_datas']
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        # sequence object
        sequence_obj = self.pool.get('ir.sequence')
        # stock move object
        move_obj = self.pool.get('stock.move')
        product_obj = self.pool.get('product.product')
        currency_obj = self.pool.get('res.currency')
        uom_obj = self.pool.get('product.uom')
        # create picking object
        create_picking_obj = self.pool.get('create.picking')
        # workflow
        wf_service = netsvc.LocalService("workflow")
        internal_loc_ids = self.pool.get('stock.location').search(cr, uid, [('usage','=','internal'), ('cross_docking_location_ok', '=', False)])
        ctx_avg = context.copy()
        ctx_avg['location'] = internal_loc_ids
        for pick in self.browse(cr, uid, ids, context=context):
            # corresponding backorder object - not necessarily created
            backorder_id = None
            # treat moves
            move_ids = partial_datas[pick.id].keys()
            # all moves
            all_move_ids = [move.id for move in pick.move_lines]
            # related moves - swap if a backorder is created - openERP logic
            done_moves = []
            # OUT moves to assign
            to_assign_moves = []
            second_assign_moves = []
            
            # Link between IN and OUT moves
            backlinks = []
            
            # OUT/PICK to prepare
            out_picks = []
            pick_moves = []
            
            # average price computation
            product_avail = {}
            # increase picking version - all case where update_out is True + when the qty is bigger without split nor product change
            update_pick_version = False
            for move in move_obj.browse(cr, uid, move_ids, context=context):
                # keep data for back order creation
                data_back = self.create_data_back(cr, uid, move, context=context)
                # qty selected
                count = 0
                # flag to update the first move - if split was performed during the validation, new stock moves are created
                first = True
                # force complete flag = validate all partial for the same move have the same force complete value
                force_complete = False
                # initial qty
                initial_qty = move.product_qty
                # initial uom
                initial_uom = move.product_uom.id
                # corresponding out move
                mirror_data = move_obj.get_mirror_move(cr, uid, [move.id], data_back, context=context)[move.id]
                out_move_id = mirror_data['move_id']
                out_moves = mirror_data['moves']
                processed_moves = []
                # update out flag
                count_partial = len(partial_datas[pick.id][move.id])
                update_out = count_partial > 1
                # average price computation, new values - should be the same for every partial
                average_values = {}

                
                # partial list
                for partial in partial_datas[pick.id][move.id]:
                    # original openERP logic - average price computation - To be validated by Matthias
                    # Average price computation
                    # selected product from wizard must be tested
                    product = product_obj.browse(cr, uid, partial['product_id'], context=ctx_avg)
                    values = {'name': partial['name'],
                              'product_id': partial['product_id'],
                              'product_qty': partial['product_qty'],
                              'product_uos_qty': partial['product_qty'],
                              'prodlot_id': partial['prodlot_id'],
                              'product_uom': partial['product_uom'],
                              'product_uos': partial['product_uom'],
                              'asset_id': partial['asset_id'],
                              'change_reason': partial['change_reason'],
                              }
                    if 'product_price' in partial:
                        values.update({'price_unit': partial['product_price']})
                    elif 'product_uom' in partial and partial['product_uom'] != move.product_uom.id:
                        new_price = self.pool.get('product.uom')._compute_price(cr, uid, move.product_uom.id, move.price_unit, partial['product_uom'])
                        values.update({'price_unit': new_price})
                    values = self._do_incoming_shipment_first_hook(cr, uid, ids, context, values=values)
                    compute_average = pick.type == 'in' and product.cost_method == 'average' and not move.location_dest_id.cross_docking_location_ok
                    if values.get('location_dest_id'):
                        val_loc = self.pool.get('stock.location').browse(cr, uid, values.get('location_dest_id'), context=context)
                        compute_average = pick.type == 'in' and product.cost_method == 'average' and not val_loc.cross_docking_location_ok
                    
                    # why do not used get_picking_type: original do_partial do not use it
                    # when an incoming shipment has a avg product to Service, the average price computation is of no use
                    
                    if compute_average:
                        move_currency_id = move.company_id.currency_id.id
                        context['currency_id'] = move_currency_id
                        # datas from partial
                        product_uom = partial['product_uom']
                        product_qty = partial['product_qty']
                        product_currency = partial.get('product_currency', False)
                        product_price = partial.get('product_price', 0.0)
                        qty = uom_obj._compute_qty(cr, uid, product_uom, product_qty, product.uom_id.id)
    
                        if product.id in product_avail:
                            product_avail[product.id] += qty
                        else:
                            product_avail[product.id] = product.qty_available
    
                        if qty > 0:
                            new_price = currency_obj.compute(cr, uid, product_currency,
                                    move_currency_id, product_price, round=False, context=context)
                            new_price = uom_obj._compute_price(cr, uid, product_uom, new_price,
                                    product.uom_id.id)
                            if product.qty_available <= 0:
                                new_std_price = new_price
                            else:
                                # Get the standard price
                                amount_unit = product.price_get('standard_price', context)[product.id]
                                # check no division by zero
                                if product_avail[product.id] + qty:
                                    new_std_price = ((amount_unit * product_avail[product.id])\
                                        + (new_price * qty))/(product_avail[product.id] + qty)
                                else:
                                    new_std_price = 0.0
                                            
                            # Write the field according to price type field
                            product_obj.write(cr, uid, [product.id], {'standard_price': new_std_price})
    
                            # Record the values that were chosen in the wizard, so they can be
                            # used for inventory valuation if real-time valuation is enabled.
                            average_values = {'price_unit': product_price,
                                              'price_currency_id': product_currency}
                                        
                    # the quantity
                    count = count + uom_obj._compute_qty(cr, uid, partial['product_uom'], partial['product_qty'], initial_uom)
                    count_partial -= 1
                    asset_id = partial['asset_id']
                    
                    if first:
                        first = False
                        # line number does not need to be updated
                        # average computation - empty if not average
                        
                        values.update(average_values)
                        
#                        # if split happened, we update the corresponding OUT move
#                        if out_move_id:
#                            # UF-1690 : Remove the location_dest_id from values
#                            out_values = values.copy()
#                            if out_values.get('location_dest_id', False):
#                                out_values.pop('location_dest_id')
#                            second_assign_moves.append(out_move_id)
#                            if update_out:
#                                move_obj.write(cr, uid, [out_move_id], out_values, context=context)
#                            elif move.product_id.id != partial['product_id']:
#                                move_obj.write(cr, uid, [out_move_id], out_values, context=context)
#                                # we force update flag - out will be updated if qty is missing - possibly with the creation of a new move
#                                update_out = True
                        # we update the values with the _do_incoming_shipment_first_hook only if we are on an 'IN'
                        values = self._do_incoming_shipment_first_hook(cr, uid, ids, context, values=values)
                        # mark the done IN stock as processed
                        move_obj.write(cr, uid, [move.id], dict(values, processed_stock_move=True), context=context)
                        done_moves.append(move.id)
                                
                    else:
                        # split happened during the validation
                        # copy the stock move and set the quantity
                        # we keep original line number
                        values.update({'state': 'assigned'})
                        # average computation - empty if not average
                        values.update(average_values)
                        # mark the done IN stock as processed
                        new_move = move_obj.copy(cr, uid, move.id, dict(values, processed_stock_move=True), context=dict(context, keepLineNumber=True))
                        done_moves.append(new_move)
                        
                    out_values = values.copy()
                    out_values.update({'state': 'confirmed'})
                    if out_values.get('location_dest_id', False):
                        out_values.pop('location_dest_id')
                        
                    partial_qty = partial['product_qty']
                    count_out = len(out_moves)
                        
                    for out_move in out_moves:
                        if not partial_qty:
                            break
                        
                        out_pick = out_move.picking_id
                        if out_pick and out_pick.type == 'out' and out_pick.subtype == 'picking' and \
                           out_pick.state == 'draft' and out_pick.id not in out_picks:
                            out_picks.append(out_move.picking_id.id)
                        
                        out_move = move_obj.browse(cr, uid, out_move.id, context=context)
                        count_out -= 1
                        
                        uom_partial_qty = self.pool.get('product.uom')._compute_qty(cr, uid, partial['product_uom'], partial_qty, out_move.product_uom.id)
                        if count_partial or uom_partial_qty < out_move.product_qty:
                            # Split the out move
                            new_move = move_obj.copy(cr, uid, out_move.id, dict(out_values, product_qty=partial_qty, product_uom=partial['product_uom'], in_out_updated=True), context=dict(context, keepLineNumber=True))
                            # Update the initial out move qty
                            move_obj.write(cr, uid, [out_move.id], {'product_qty': out_move.product_qty - uom_partial_qty}, context=context)
                            backlinks.append((move.id, new_move))
                            partial_qty = 0.00
#                            if not count_out:
#                                backlinks.append((move.id, out_move.id))
                        elif not count_out or uom_partial_qty == out_move.product_qty:
                            # Update the initial out move qty with the processed qty
                            move_obj.write(cr, uid, [out_move.id], dict(out_values, product_qty=partial_qty, product_uom=partial['product_uom'], in_out_updated=True), context=context)
                            backlinks.append((move.id, out_move.id))
                            processed_moves.append(out_move.id)
                            partial_qty = 0.00
                        else:
                            # Just update the data of the initial out move
                            move_obj.write(cr, uid, [out_move.id], dict(out_values, product_qty=out_move.product_qty, product_uom=partial['product_uom'], in_out_updated=True), context=context)
                            backlinks.append((move.id, out_move.id))
                            processed_moves.append(out_move.id)
                            partial_qty -= out_move.product_qty
                            
                    
                    if asset_id:
                        # UF-993: generate an asset event when validating an IN        
                        asset_event_obj = self.pool.get('product.asset.event')
                        asset_event_values = {
                            'date': move.date, # actual delivery date
                            'location': pick.company_id.name,
                            'event_type': 'reception', # always 'reception' for an IN
                            'asset_id': asset_id,
                            }
                        asset_event_obj.create(cr, uid, asset_event_values, context=context)
                    
                # decrement the initial move, cannot be less than zero
                diff_qty = initial_qty - count
                # the quantity after the process does not correspond to the incoming shipment quantity
                # the difference is written back to incoming shipment - and possibilty to OUT if split happened
                # is positive if some qty was removed during the process -> current incoming qty is modified
                #    create a backorder if does not exist, copy original move with difference qty in it # DOUBLE CHECK ORIGINAL FUNCTION BEHAVIOR !!!!!
                #    if split happened, update the corresponding out move with diff_qty
                if diff_qty > 0:
                    if not backorder_id:
                        # create the backorder - with no lines
                        backorder_id = self.copy(cr, uid, pick.id, {'name': sequence_obj.get(cr, uid, 'stock.picking.%s'%(pick.type)),
                                                                    'move_lines' : [],
                                                                    'state':'draft',
                                                                    })
                    # create the corresponding move in the backorder - reset productionlot - reset asset_id
                    defaults = {'name': data_back['name'],
                                'product_id': data_back['product_id'],
                                'product_uom': data_back['product_uom'],
                                'asset_id': False,
                                'product_qty': diff_qty,
                                'product_uos_qty': diff_qty,
                                'picking_id': pick.id, # put in the current picking which will be the actual backorder (OpenERP logic)
                                'prodlot_id': False,
                                'state': 'assigned',
                                'move_dest_id': False,
                                'price_unit': move.price_unit,
                                'change_reason': False,
                                'processed_stock_move': (move.processed_stock_move or count != 0) and True or False, # count == 0 means not processed. will not be updated by the synchro anymore if already completely or partially processed
                                }
                    # average computation - empty if not average
                    defaults.update(average_values)
                    new_back_move = move_obj.copy(cr, uid, move.id, defaults, context=dict(context, keepLineNumber=True))
                    #move_obj.write(cr, uid, [out_move_id], {'product_qty': diff_qty}, context=context)
                    # if split happened
                    #if update_out:
#                        if out_move_id in to_assign_moves:
#                            to_assign_moves.remove(out_move_id)
#                            second_assign_moves.append(out_move_id)
                        # update out move - quantity is increased, to match the original qty
                        # diff_qty = quantity originally in OUT move - count
                    #    out_diff_qty = mirror_data['quantity'] - count
                    #    self._update_mirror_move(cr, uid, ids, data_back, out_diff_qty, out_move=out_move_id, context=dict(context, keepLineNumber=True))
                # is negative if some qty was added during the validation -> draft qty is increased
#                if diff_qty < 0:
#                    # we update the corresponding OUT object if exists - we want to increase the qty if no split happened
#                    # if split happened and quantity is bigger, the quantities are already updated with stock moves creation
#                    if not update_out:
##                        if out_move_id in to_assign_moves:
##                            to_assign_moves.remove(out_move_id)
##                            second_assign_moves.append(out_move_id)
#                        update_qty = -diff_qty
#                        self._update_mirror_move(cr, uid, ids, data_back, update_qty, out_move=out_move_id, context=dict(context, keepLineNumber=True))
#                        # no split nor product change but out is updated (qty increased), force update out for update out picking
#                        update_out = True
                
                # we got an update_out, we set the flag
                update_pick_version = update_pick_version or (update_out and mirror_data['picking_id'])
                
            # clean the picking object - removing lines with 0 qty - force unlink
            # this should not be a problem as IN moves are not referenced by other objects, only OUT moves are referenced
            # no need of skipResequencing as the picking cannot be draft
            for move in pick.move_lines:
                if not move.product_qty and move.state not in ('done', 'cancel'):
                    done_moves.remove(move.id)
                    move.unlink(context=dict(context, call_unlink=True))
                    
            # At first we confirm the new picking (if necessary) - **corrected** inverse openERP logic !
            if backorder_id:
                # done moves go to new picking object
                move_obj.write(cr, uid, done_moves, {'picking_id': backorder_id}, context=context)
                wf_service.trg_validate(uid, 'stock.picking', backorder_id, 'button_confirm', cr)
                # Then we finish the good picking
                self.write(cr, uid, [pick.id], {'backorder_id': backorder_id,'cd_from_bo':values.get('cd_from_bo',False)}, context=context)
                self.action_move(cr, uid, [backorder_id])
                wf_service.trg_validate(uid, 'stock.picking', backorder_id, 'button_done', cr)
                wf_service.trg_write(uid, 'stock.picking', pick.id, cr)
            else:
                self.action_move(cr, uid, [pick.id], context)
                wf_service.trg_validate(uid, 'stock.picking', pick.id, 'button_done', cr)
                
            for move, out_move in backlinks:
                if move in done_moves:
                    move_obj.write(cr, uid, [move], {'state': 'done'}, context=context)
                    move_obj.action_assign(cr, uid, [out_move])
                    pick_moves.append(out_move)
            
            # update the out version
            if update_pick_version:
                self.write(cr, uid, [update_pick_version], {'update_version_from_in_stock_picking': mirror_data['picking_version']+1}, context=context)
                
                
            # Create the first picking ticket if we are on a draft picking ticket
            for picking in self.browse(cr, uid, out_picks, context=context):
                if picking.type == 'out' and picking.subtype == 'picking' and picking.state == 'draft':
                    wiz = self.create_picking(cr, uid, [picking.id], context=context)
                    wiz_obj = self.pool.get(wiz['res_model'])
                    moves_picking = wiz_obj.browse(cr, uid, wiz['res_id'], context=wiz['context']).product_moves_picking
                    # We delete the lines which is not from the IN
                    for line in moves_picking:
                        if line.move_id.id not in pick_moves:
                            self.pool.get('stock.move.memory.picking').unlink(cr, uid, [line.id], context=context)
                    if wiz_obj.browse(cr, uid, wiz['res_id'], context=wiz['context']).product_moves_picking:
                        # We copy all data in lines
                        wiz_obj.copy_all(cr, uid, [wiz['res_id']], context=wiz['context'])
                        # We process the creation of the picking
                        wiz_obj.do_create_picking(cr, uid, [wiz['res_id']], context=wiz['context'])

            # Assign all updated out moves
#            for move in move_obj.browse(cr, uid, to_assign_moves):
#                if not move.product_qty and move.state not in ('done', 'cancel'):
#                    to_assign_moves.remove(move.id)
#                    move.unlink(context=dict(context, call_unlink=True))
#            for move in move_obj.browse(cr, uid, second_assign_moves):
#                if not move.product_qty and move.state not in ('done', 'cancel'):
#                    second_assign_moves.remove(move.id)
#                    move.unlink(context=dict(context, call_unlink=True))
#            move_obj.action_assign(cr, uid, second_assign_moves)
#            move_obj.action_assign(cr, uid, to_assign_moves)

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
                data_back = self.create_data_back(cr, uid, move, context=context)
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
                                                                ('processed_stock_move', '=', True),], context=context)
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
                purchase_obj.log(cr, uid, obj.purchase_id.id, _('The Purchase Order %s is %s%% received.')%(obj.purchase_id.name, round(obj.purchase_id.shipped_rate,2)))
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
    _columns= {'procurement_id': fields.many2one('procurement.order', string='Procurement Reference', readonly=True,),
               }
    _defaults = {'procurement_id': False,}
    
purchase_order_line()


class purchase_order(osv.osv):
    '''
    hook to modify created In moves
    '''
    _inherit = 'purchase.order'
    
    def _hook_action_picking_create_stock_picking(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        modify data for stock move creation
        - line number of stock move is taken from purchase order line
        '''
        if context is None:
            context = {}
        move_values = super(purchase_order, self)._hook_action_picking_create_stock_picking(cr, uid, ids, context=context, *args, **kwargs)
        order_line = kwargs['order_line']
        move_values.update({'line_number': order_line.line_number})
        return move_values
    
purchase_order()


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
        line.update({'procurement_id': procurement.id,})
        # for Internal Request (IR) on make_to_order we update PO line data according to the data of the IR (=sale_order)
        sale_order_line_ids = sale_obj.search(cr, uid, [('procurement_id','=', procurement.id)], context=context)
        for sol in sale_obj.browse(cr, uid, sale_order_line_ids, context=context):
            if sol.order_id.procurement_request and not sol.product_id and sol.comment:
                line.update({'product_id': False,
                             'name': 'Description: %s' %sol.comment,
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

