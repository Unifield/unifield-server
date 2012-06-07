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
                }
    _defaults = {'line_number': 0,}
    _order = 'line_number'
    
    def create(self, cr, uid, vals, context=None):
        '''
        add the corresponding line number
        
        if a corresponding purchase order line or sale order line exist
        we take the line number from there
        '''
        # object
        picking_obj = self.pool.get('stock.picking')
        pol_obj = self.pool.get('purchase.order.line')
        sol_obj = self.pool.get('sale.order.line')
        seq_pool = self.pool.get('ir.sequence')

        # line number correspondance to be checked with Magali
        if vals.get('picking_id'):
            if vals.get('purchase_line_id') and False:
                # from purchase order line
                line = pol_obj.read(cr, uid, [vals.get('purchase_line_id')], ['line_number'], context=context)[0]['line_number']
            elif vals.get('sale_line_id') and False:
                # from sale order line
                line = sol_obj.read(cr, uid, [vals.get('sale_line_id')], ['line_number'], context=context)[0]['line_number']
            else:
                # new numbers - gather the line number from the sequence
                sequence_id = picking_obj.read(cr, uid, [vals['picking_id']], ['move_sequence_id'], context=context)[0]['move_sequence_id'][0]
                line = seq_pool.get_id(cr, uid, sequence_id, test='id', context=context)
            # update values with line value
            vals.update({'line_number': line})
        
        # create the new object
        result = super(stock_move, self).create(cr, uid, vals, context=context)
        return result
    
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
            res[obj.id] = False
            if obj.picking_id and obj.picking_id.type == 'in':
                # we are looking for corresponding OUT move from sale order line
                if obj.purchase_line_id:
                    # linekd to a po
                    if obj.purchase_line_id.procurement_id:
                        # on order
                        procurement_id = obj.purchase_line_id.procurement_id.id
                        # find the corresponding sale order line
                        so_line_ids = so_line_obj.search(cr, uid, [('procurement_id', '=', procurement_id)], context=context)
                        assert len(so_line_ids) == 1, 'number of so line is wrong - 1 - %s'%len(so_line_ids)
                        # find the corresponding OUT move
                        # move_ids = self.search(cr, uid, [('product_id', '=', obj.product_id.id), ('product_qty', '=', obj.product_qty), ('state', 'in', ('assigned', 'confirmed')), ('sale_line_id', '=', so_line_ids[0])], context=context)
                        move_ids = self.search(cr, uid, [('product_id', '=', data_back['product_id']), ('state', 'in', ('assigned', 'confirmed')), ('sale_line_id', '=', so_line_ids[0])], context=context)
                        # list of matching out moves
                        integrity_check = []
                        for move in self.browse(cr, uid, move_ids, context=context):
                            # move from draft picking or standard picking
                            if (move.picking_id.subtype == 'picking' and not move.picking_id.backorder_id and move.picking_id.state == 'draft') or (move.picking_id.subtype == 'standard') and move.picking_id.type == 'out':
                                integrity_check.append(move.id)
                        # return the first one matching
                        if integrity_check:
                            res[obj.id] = integrity_check[0]
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
        # object
        seq_pool = self.pool.get('ir.sequence')
        po_obj = self.pool.get('purchase.order')
        so_obj = self.pool.get('sale.order')
        
        new_seq_id = self.create_sequence(cr, uid, vals, context=context)
        vals.update({'move_sequence_id': new_seq_id,})
        # if from order, we udpate the sequence to match the order's one
        # line number correspondance to be checked with Magali
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
        out_move_id = move_obj.get_mirror_move(cr, uid, [data_back['id']], data_back, context=context)[data_back['id']]
        if not out_move_id and out_move:
            # copy existing out_move with move properties: - update the name of the stock move
            # the state is confirmed, we dont know if available yet - should be in input location before stock
            values = {'name': data_back['name'],
                      'product_id': data_back['product_id'],
                      'product_qty': 0,
                      'product_uos_qty': 0,
                      'product_uom': data_back['product_uom'],
                      'state': 'confirmed',
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
            move_obj.write(cr, uid, [out_move_id], {'product_qty' : new_qty,
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
       
        internal_loc_ids = self.pool.get('stock.location').search(cr, uid, [('usage','=','internal')])
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
            # average price computation
            product_avail = {}
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
                # corresponding out move
                out_move_id = move_obj.get_mirror_move(cr, uid, [move.id], data_back, context=context)[move.id]
                # update out flag
                update_out = (len(partial_datas[pick.id][move.id]) > 1)
                # average price computation, new values - should be the same for every partial
                average_values = {}
                # partial list
                for partial in partial_datas[pick.id][move.id]:
                    # original openERP logic - average price computation - To be validated by Matthias
                    # Average price computation
                    # selected product from wizard must be tested
                    product = product_obj.browse(cr, uid, partial['product_id'], context=ctx_avg)
                    if (pick.type == 'in') and (product.cost_method == 'average'):
                        move_currency_id = move.company_id.currency_id.id
                        context['currency_id'] = move_currency_id
                        # datas from partial
                        product_uom = partial['product_uom']
                        product_qty = partial['product_qty']
                        product_currency = partial['product_currency']
                        product_price = partial['product_price']
                        qty = uom_obj._compute_qty(cr, uid, product_uom, product_qty, product.uom_id.id)
    
                        if product.id in product_avail:
                            product_avail[product.id] += qty
                        else:
                            product_avail[product.id] = product.qty_available
    
                        if qty > 0:
                            new_price = currency_obj.compute(cr, uid, product_currency,
                                    move_currency_id, product_price)
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
                    count = count + partial['product_qty']
                    if first:
                        first = False
                        # update existing move
                        values = {'name': partial['name'],
                                  'product_id': partial['product_id'],
                                  'product_qty': partial['product_qty'],
                                  'product_uos_qty': partial['product_qty'],
                                  'prodlot_id': partial['prodlot_id'],
                                  'product_uom': partial['product_uom'],
                                  'asset_id': partial['asset_id'],
                                  'change_reason': partial['change_reason'],
                                  }
                        # average computation - empty if not average
                        values.update(average_values)
                        values = self._do_incoming_shipment_first_hook(cr, uid, ids, context, values=values)
                        move_obj.write(cr, uid, [move.id], values, context=context)
                        done_moves.append(move.id)
                        # if split happened, we update the corresponding OUT move
                        if out_move_id:
                            if update_out:
                                move_obj.write(cr, uid, [out_move_id], values, context=context)
                            elif move.product_id.id != partial['product_id']:
                                # no split but product changed, we have to update the corresponding out move
                                move_obj.write(cr, uid, [out_move_id], values, context=context)
                                # we force update flag - out will be updated if qty is missing - possibly with the creation of a new move
                                update_out = True
                    else:
                        # split happened during the validation
                        # copy the stock move and set the quantity
                        values = {'name': partial['name'],
                                  'product_id': partial['product_id'],
                                  'product_qty': partial['product_qty'],
                                  'product_uos_qty': partial['product_qty'],
                                  'prodlot_id': partial['prodlot_id'],
                                  'product_uom': partial['product_uom'],
                                  'asset_id': partial['asset_id'],
                                  'change_reason': partial['change_reason'],
                                  'state': 'assigned',
                                  }
                        # average computation - empty if not average
                        values.update(average_values)
                        new_move = move_obj.copy(cr, uid, move.id, values, context=context)
                        done_moves.append(new_move)
                        if out_move_id:
                            new_out_move = move_obj.copy(cr, uid, out_move_id, values, context=context)
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
                    # create the corresponding move in the backorder - reset productionlot
                    defaults = {'name': data_back['name'],
                                'product_id': data_back['product_id'],
                                'product_uom': data_back['product_uom'],
                                'product_qty': diff_qty,
                                'product_uos_qty': diff_qty,
                                'picking_id': pick.id, # put in the current picking which will be the actual backorder (OpenERP logic)
                                'prodlot_id': False,
                                'state': 'assigned',
                                'move_dest_id': False,
                                'price_unit': move.price_unit,
                                'change_reason': False,
                                }
                    # average computation - empty if not average
                    defaults.update(average_values)
                    new_back_move = move_obj.copy(cr, uid, move.id, defaults, context=context)
                    # if split happened
                    if update_out:
                        # update out move - quantity is increased, to match the original qty
                        self._update_mirror_move(cr, uid, ids, data_back, diff_qty, out_move=out_move_id, context=context)
                # is negative if some qty was added during the validation -> draft qty is increased
                if diff_qty < 0:
                    # we update the corresponding OUT object if exists - we want to increase the qty if no split happened
                    # if split happened and quantity is bigger, the quantities are already updated with stock moves creation
                    if not update_out:
                        update_qty = -diff_qty
                        self._update_mirror_move(cr, uid, ids, data_back, update_qty, out_move=out_move_id, context=context)
            # clean the picking object - removing lines with 0 qty - force unlink
            # this should not be a problem as IN moves are not referenced by other objects, only OUT moves are referenced
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
                self.write(cr, uid, [pick.id], {'backorder_id': backorder_id}, context=context)
                self.action_move(cr, uid, [backorder_id])
                wf_service.trg_validate(uid, 'stock.picking', backorder_id, 'button_done', cr)
                wf_service.trg_write(uid, 'stock.picking', pick.id, cr)
            else:
                self.action_move(cr, uid, [pick.id])
                wf_service.trg_validate(uid, 'stock.picking', pick.id, 'button_done', cr)

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
                # update corresponding out move
                out_move_id = self._update_mirror_move(cr, uid, ids, data_back, diff_qty, out_move=False, context=context)
                # for out cancellation, two points:
                # - if pick/pack/ship: check that nothing is in progress
                # - if nothing in progress, and the out picking is canceled, trigger the so to correct the corresponding so manually
                if out_move_id:
                    out_move = move_obj.browse(cr, uid, out_move_id, context=context)
                    cond1 = out_move.picking_id.subtype == 'standard'
                    cond2 = out_move.picking_id.subtype == 'picking' and not out_move.picking_id.has_picking_ticket_in_progress(context=context)[out_move.picking_id.id]
                    if (cond1 or cond2) and out_move.picking_id.type == 'out' and not out_move.product_qty:
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
        line = super(procurement_order, self).po_line_values_hook(cr, uid, ids, context=context, *args, **kwargs)
        # give the purchase order line a link to corresponding procurement
        procurement = kwargs['procurement']
        line.update({'procurement_id': procurement.id,})
        return line
    
procurement_order()

