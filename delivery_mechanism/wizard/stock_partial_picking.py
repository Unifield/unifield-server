
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
        - 
        '''
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
                partial_datas[pick.id].setdefault(move.move_id.id, []).append({'product_id': move.product_id.id,
                                                                               'product_qty': move.quantity,
                                                                               'product_uom': move.product_uom.id,
                                                                               'prodlot_id': prodlot_id,
                                                                               'asset_id': move.asset_id.id,
                                                                               'force_complete': move.force_complete,
                                                                               })
                
        # call stock_picking method which returns action call
        return pick_obj.do_incoming_shipment(cr, uid, picking_ids, context=dict(context, partial_datas=partial_datas))
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        change the function name to do_incoming_shipment
        '''
        res = super(stock_partial_picking, self).fields_view_get(cr, uid, view_id=view_id, view_type='form', context=context, toolbar=toolbar, submenu=submenu)
        picking_obj = self.pool.get('stock.picking')
        picking_id = context.get('active_ids')
        if picking_id:
            picking_id = picking_id[0]
            picking_type = picking_obj.read(cr, uid, [picking_id], ['type'], context=context)[0]['type']
            if picking_type == 'in':
                # replace call to do_partial by do_incoming_shipment
                res['arch'] = res['arch'].replace('do_partial', 'do_incoming_shipment')
        return res
        
stock_partial_picking()

