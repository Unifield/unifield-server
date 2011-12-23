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
                sequence_id = picking_obj.read(cr, uid, [vals['picking_id']], ['sequence_id'], context=context)[0]['sequence_id'][0]
                line = seq_pool.get_id(cr, uid, sequence_id, test='id', context=context)
            # update values with line value
            vals.update({'line_number': line})
        
        # create the new object
        result = super(stock_move, self).create(cr, uid, vals, context=context)
        return result
    
    def get_mirror_move(self, cr, uid, ids, context=None):
        '''
        return a dictionary with IN for OUT and OUT for IN, if exists, False otherwise
        
        only one mirror object should exist for each object (to check)
        return objects which are not done
        
        IN: move -> po line -> procurement -> so line -> move
        OUT: move -> so line -> procurement -> po line -> move
        
        I dont use move.move_dest_id because of back orders both on OUT and IN sides
        '''
        if context is None:
            context = {}
            
        # objetcts
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
                        move_ids = self.search(cr, uid, [('state', 'in', ('assigned', 'confirmed')), ('sale_line_id', '=', so_line_ids[0])], context=context)
                        for move in self.browse(cr, uid, move_ids, context=context):
                            # move from draft picking or standard picking
                            # only one move should fit
                            integrity_check = []
                            if (move.picking_id.subtype == 'picking' and not move.picking_id.backorder_id) or (move.picking_id.subtype == 'standard') and move.picking_id.type == 'out':
                                integrity_check.append(move.id)
                        
                        # only one move should fit search criteria
                        assert len(integrity_check) <= 1, 'number of OUT moves is wrong - <= 1 - %s'%len(integrity_check)
                        if integrity_check:
                            res[obj.id] = integrity_check[0]
                
            if obj.type == 'out':
                # we are looking for corresponding IN from on_order purchase order
                assert False, 'This method is not implemented for OUT moves'
                
        return res
    
stock_move()


class stock_picking(osv.osv):
    '''
    do_partial modification
    '''
    _inherit = 'stock.picking'
    _columns = {'sequence_id': fields.many2one('ir.sequence', 'Moves Sequence', help="This field contains the information related to the numbering of the moves of this picking.", required=True, ondelete='cascade'),
                }
    
    def _stock_picking_action_process_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_process method from stock>stock.py>stock_picking
        
        - allow to modify the data for wizard display
        '''
        if context is None:
            context = {}
        res = super(stock_picking, self)._stock_picking_action_process_hook(cr, uid, ids, context=context, *args, **kwargs)
        wizard_obj = self.pool.get('wizard')
        res = wizard_obj.open_wizard(cr, uid, ids, type='update', context=dict(context,
                                                                               wizard_ids=[res['res_id']],
                                                                               wizard_name=res['name'],
                                                                               model=res['res_model'],
                                                                               step=res['default']))
        return res
    
    def create_sequence(self, cr, uid, vals, context=None):
        """
        Create new entry sequence for every new order
        @param cr: cursor to database
        @param user: id of current user
        @param ids: list of record ids to be process
        @param context: context arguments, like lang, time zone
        @return: return a result
        """
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')

        name = 'Stock Picking'
        code = 'stock.picking'

        types = {'name': name,
                 'code': code
                 }
        seq_typ_pool.create(cr, uid, types)

        seq = {'name': name,
               'code': code,
               'prefix': '',
               'padding': 0,
               }
        return seq_pool.create(cr, uid, seq)
    
    def create(self, cr, uid, vals, context=None):
        '''
        create from sale_order
        create the sequence for the numbering of the lines
        '''
        # object
        seq_pool = self.pool.get('ir.sequence')
        po_obj = self.pool.get('purchase.order')
        so_obj = self.pool.get('sale.order')
        
        new_seq_id = self.create_sequence(cr, uid, vals, context=context)
        vals.update({'sequence_id': new_seq_id,})
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
    
    def _update_mirror_move(self, cr, uid, ids, move, diff_qty, context=None):
        '''
        update the mirror move with difference quantity diff_qty
        
        if diff_qty < 0, the qty is increased
        if diff_qty > 0, the qty is decreased
        '''
        # stock move object
        move_obj = self.pool.get('stock.move')
        
        out_move_id = move_obj.get_mirror_move(cr, uid, [move.id], context=context)[move.id]
        if out_move_id:
            # decrease/increase depending on diff_qty sign the qty by diff_qty
            present_qty = move_obj.read(cr, uid, [out_move_id], ['product_qty'], context=context)[0]['product_qty']
            new_qty = max(present_qty - diff_qty, 0)
            move_obj.write(cr, uid, [out_move_id], {'product_qty' : new_qty,
                                                    'product_uos_qty': new_qty,}, context=context)
        # return updated move or False
        return out_move_id
    
    def do_incoming_shipment(self, cr, uid, ids, context=None):
        '''
        validate the picking ticket from selected stock moves
        
        move here the logic of validate picking
        available for picking loop
        '''
        assert context, 'context is not defined'
        assert 'partial_datas' in context, 'partial datas not present in context'
        partial_datas = context['partial_datas']
        
        # sequence object
        sequence_obj = self.pool.get('ir.sequence')
        # stock move object
        move_obj = self.pool.get('stock.move')
        # create picking object
        create_picking_obj = self.pool.get('create.picking')
        # workflow
        wf_service = netsvc.LocalService("workflow")
        
        for pick in self.browse(cr, uid, ids, context=context):
            # corresponding backorder object - not necessarily created
            backorder_id = None
            # treat moves
            move_ids = partial_datas[pick.id].keys()
            for move in move_obj.browse(cr, uid, move_ids, context=context):
                # qty selected
                count = 0
                # flag to update the first move - if split was performed during the validation, new stock moves are created
                first = True
                # force complete flag = validate all partial for the same move have the same force complete value
                force_complete = False
                # initial qty
                initial_qty = move.product_qty
                # log message for this move
                message = ''
                # partial list
                for partial in partial_datas[pick.id][move.id]:
                    # force complete flag
                    if first:
                        force_complete = partial['force_complete']
                    assert force_complete == partial['force_complete'], 'force complete is not equal for all splitted lines - %s - %s'%(force_complete,partial['force_complete'])
                    # the quantity
                    count = count + partial['product_qty']
                    if first:
                        first = False
                        # update existing move
                        move_obj.write(cr, uid, [move.id], {'product_id': partial['product_id'],
                                                            'product_qty': partial['product_qty'],
                                                            'prodlot_id': partial['prodlot_id'],
                                                            'product_uom': partial['product_uom'],
                                                            'asset_id': partial['asset_id']}, context=context)
                    else:
                        # split happened during the validation
                        # copy the stock move and set the quantity
                        new_move = move_obj.copy(cr, uid, move.id, {'product_id': partial['product_id'],
                                                                    'product_qty': partial['product_qty'],
                                                                    'prodlot_id': partial['prodlot_id'],
                                                                    'product_uom': partial['product_uom'],
                                                                    'asset_id': partial['asset_id'],
                                                                    'state': 'assigned',}, context=context)
                # decrement the initial move, cannot be less than zero
                diff_qty = initial_qty - count
                # the quantity after the process does not correspond to the incoming shipment quantity
                # the difference is written back to incoming shipment
                # is positive if some qty was removed during the process -> current incoming qty is modified
                #    if force_complete flag is checked for the move, will not be part of a possible backorder - decrease corresponding OUT move
                #    if not, create a backorder if does not exist, copy original move with difference qty in it # DOUBLE CHECK ORIGINAL FUNCTION BEHAVIOR !!!!!
                if diff_qty > 0:
                    if not force_complete:
                        if not backorder_id:
                            # create the backorder - with no lines
                            backorder_id = self.copy(cr, uid, pick.id, {'name': sequence_obj.get(cr, uid, 'stock.picking.%s'%(pick.type)),
                                                                        'move_lines' : [],
                                                                        'state':'draft',
                                                                        })
                        # create the corresponding move in the backorder - reset productionlot
                        defaults = {'product_qty': diff_qty,
                                    'product_uos_qty': diff_qty,
                                    'picking_id': backorder_id,
                                    'prodlot_id': False,
                                    'state': 'assigned',
                                    'move_dest_id': False,
                                    'price_unit': move.price_unit,
                                    }
                        move_obj.copy(cr, uid, move.id, defaults, context=context)
                    else:
                        # we update the corresponding OUT object if exists - if no out_move_id -> all are done already
                        self._update_mirror_move(cr, uid, ids, move, diff_qty, context=context)
                # is negative if some qty was added during the validation -> draft qty is increased
                if diff_qty < 0:
                    # we update the corresponding OUT object if exists - if no out_move_id -> all are done already
                    self._update_mirror_move(cr, uid, ids, move, diff_qty, context=context)
                        
            # At first we confirm the new picking (if necessary) - **corrected** inverse openERP logic !
            if backorder_id:
                wf_service.trg_validate(uid, 'stock.picking', backorder_id, 'button_confirm', cr)
                # Then we finish the good picking
                self.write(cr, uid, [backorder_id], {'backorder_id': pick.id}, context=context)
                self.action_move(cr, uid, [pick.id])
                wf_service.trg_validate(uid, 'stock.picking', pick.id, 'button_done', cr)
                wf_service.trg_write(uid, 'stock.picking', pick.id, cr)
            else:
                self.action_move(cr, uid, [pick.id])
                wf_service.trg_validate(uid, 'stock.picking', pick.id, 'button_done', cr)

        return {'type': 'ir.actions.act_window_close'}
    
stock_picking()


class purchase_order(osv.osv):
    '''
    add the id of the origin purchase order
    '''
    _inherit = 'purchase.order'
#    _columns = {'on_order_procurement_id': fields.many2one('procurement.order', string='On Order Procurement Reference', readonly=True,),
#                }
#    _defaults = {'on_order_procurement_id': False,}
    
purchase_order()


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
    
#    def po_values_hook(self, cr, uid, ids, context=None, *args, **kwargs):
#        '''
#        data for the purchase order creation
#        add a link to corresponding procurement order
#        '''
#        values = super(procurement_order, self).po_values_hook(cr, uid, ids, context=context, *args, **kwargs)
#        procurement = kwargs['procurement']
#        
#        values['on_order_procurement_id'] = procurement.id
#        
#        return values

    def po_line_values_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the make_po method from purchase>purchase.py>procurement_order
        
        - allow to modify the data for purchase order line creation
        '''
        line = super(procurement_order, self).po_line_values_hook(cr, uid, ids, context=context, *args, **kwargs)
        # give the purchase order line a link to corresponding procurement
        procurement = kwargs['procurement']
        line.update({'procurement_id': procurement.id,})
        return line
    
procurement_order()

