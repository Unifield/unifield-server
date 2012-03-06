
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

from osv import fields, osv
from tools.translate import _
import time

class stock_partial_picking(osv.osv_memory):
    _inherit = "stock.partial.picking"
    
    def integrity_check_do_incoming_shipment(self, cr, uid, ids, data, context=None):
        '''
        integrity for incoming shipment wizard
        
        - values cannot be negative
        - at least one partial data !
        '''
        total_qty = 0
        for move_dic in data.values():
            for arrays in move_dic.values():
                for partial_dic in arrays:
                    total_qty += partial_dic['product_qty']
        if not total_qty:
            raise osv.except_osv(_('Warning !'), _('Selected list to process cannot be empty.'))
        return True
    
    def do_incoming_shipment(self, cr, uid, ids, context=None):
        '''
        create the incoming shipment from selected stock moves
        -> only related to 'in' type stock.picking
        
        - transform data from wizard
        - need to re implement batch creation
        '''
        # integrity check
        assert context, 'no context, method call is wrong'
        assert 'active_ids' in context, 'No picking ids in context. Action call is wrong'
        if isinstance(ids, (int, long)):
            ids = [ids]
        # picking ids
        picking_ids = context['active_ids']
        # partial data from wizard
        partial = self.browse(cr, uid, ids[0], context=context)
        
        pick_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')
        prodlot_obj = self.pool.get('stock.production.lot')

        # partial datas
        partial_datas = {}
        
        for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
            # for each picking
            partial_datas[pick.id] = {}
            # picking type openERP bug passion logic
            picking_type = super(stock_partial_picking, self).get_picking_type(cr, uid, pick, context=context)
            # out moves for delivery
            memory_moves_list = getattr(partial, 'product_moves_%s'%picking_type)
            # organize data according to move id
            for move in memory_moves_list:
                # by default prodlot_id comes from the wizard
                prodlot_id = move.prodlot_id.id
                # treat internal batch to be created# if only expiry date mandatory, and not batch management
                if move.expiry_date_check and not move.batch_number_check:        
                    # if no production lot
                    if not move.prodlot_id:
                        if move.expiry_date:
                            # if it's an incoming shipment
                            if move.type_check == 'in':
                                # double check to find the corresponding prodlot
                                prodlot_ids = prodlot_obj.search(cr, uid, [('life_date', '=', move.expiry_date),
                                                                           ('type', '=', 'internal'),
                                                                           ('product_id', '=', move.product_id.id)], context=context)
                                # no prodlot, create a new one
                                if not prodlot_ids:
                                    vals = {'product_id': move.product_id.id,
                                            'life_date': move.expiry_date,
                                            #'name': datetime.datetime.strptime(move.expiry_date, '%Y-%m-%d').date().strftime('%d/%m/%Y'),
                                            'name': self.pool.get('ir.sequence').get(cr, uid, 'stock.lot.serial'),
                                            'type': 'internal',
                                            }
                                    prodlot_id = prodlot_obj.create(cr, uid, vals, context)
                                else:
                                    prodlot_id = prodlot_ids[0]
                            else:
                                # should not be reached thanks to UI checks
                                raise osv.except_osv(_('Error !'), _('No Batch Number with Expiry Date for Expiry Date Mandatory and not Incoming Shipment should not happen. Please hold...'))
                # fill partial data
                partial_datas[pick.id].setdefault(move.move_id.id, []).append({'name': move.product_id.partner_ref,
                                                                               'product_id': move.product_id.id,
                                                                               'product_qty': move.quantity,
                                                                               'product_uom': move.product_uom.id,
                                                                               'prodlot_id': prodlot_id,
                                                                               'asset_id': move.asset_id.id,
                                                                               'force_complete': move.force_complete,
                                                                               'change_reason': move.change_reason,
                                                                               })
            # treated moves
            move_ids = partial_datas[pick.id].keys()
            # all moves
            all_move_ids = [move.id for move in pick.move_lines]
            # these moves will be set to 0 - not present in the wizard - create partial objects with qty 0
            missing_move_ids = [x for x in all_move_ids if x not in move_ids]
            # missing moves (deleted memory moves) are replaced by a corresponding partial with qty 0
            for missing_move in move_obj.browse(cr, uid, missing_move_ids, context=context):
                partial_datas[pick.id].setdefault(missing_move.id, []).append({'name': move.product_id.partner_ref,
                                                                               'product_id': missing_move.product_id.id,
                                                                               'product_qty': 0,
                                                                               'product_uom': missing_move.product_uom.id,
                                                                               'prodlot_id': False,
                                                                               'asset_id': False,
                                                                               'force_complete': False,
                                                                               'change_reason': False,
                                                                               })
            
        # integrity check on wizard data
        if not self.integrity_check_do_incoming_shipment(cr, uid, ids, partial_datas, context=context):
            # inline integrity status not yet implemented - will trigger the wizard update
            pass
        # call stock_picking method which returns action call
        return pick_obj.do_incoming_shipment(cr, uid, picking_ids, context=dict(context, partial_datas=partial_datas))
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        change the function name to do_incoming_shipment
        '''
        res = super(stock_partial_picking, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
        picking_obj = self.pool.get('stock.picking')
        picking_id = context.get('active_ids')
        if picking_id:
            picking_id = picking_id[0]
            picking_type = picking_obj.read(cr, uid, [picking_id], ['type'], context=context)[0]['type']
            if picking_type == 'in':
                # replace call to do_partial by do_incoming_shipment
                res['arch'] = res['arch'].replace('do_partial', 'do_incoming_shipment')
        return res
    
    def __create_partial_picking_memory(self, picking, pick_type):
        '''
        add the asset_id
        NOTE: the name used here : picking is WRONG. it is in fact a stock.move object
        '''
        move_memory = super(stock_partial_picking, self).__create_partial_picking_memory(picking, pick_type)
        assert move_memory is not None
        
        move_memory.update({'line_number' : picking.line_number})
        
        return move_memory
        
stock_partial_picking()

