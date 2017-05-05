
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

# xml parser
from lxml import etree

class stock_partial_picking(osv.osv_memory):
    _inherit = "stock.partial.picking"
    
    def integrity_check_do_incoming_shipment(self, cr, uid, ids, picking_type, data, context=None):
        '''
        integrity must be OK
        
        'integrity_status_func_stock_memory_move'
        
        - at least one partial data !
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        # check if not empty wizard  
        if data:
            total_qty = 0
            for move_dic in data.values():
                for arrays in move_dic.values():
                    for partial_dic in arrays:
                        total_qty += partial_dic['product_qty']
            if not total_qty:
                raise osv.except_osv(_('Warning !'), _('Selected list to process cannot be empty.'))
        
        # checking line integrity field
        for obj in self.browse(cr, uid, ids, context=context):
            for item in getattr(obj, 'product_moves_%s'%picking_type):
                # integrity is not met
                if item.integrity_status_func_stock_memory_move != 'empty':
                    return False
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
            total_qty = 0.00
            # for each picking
            partial_datas[pick.id] = {}
            # picking type openERP bug passion logic
            picking_type = super(stock_partial_picking, self).get_picking_type(cr, uid, pick, context=context)
            # out moves for delivery
            memory_moves_list = getattr(partial, 'product_moves_%s'%picking_type)
            # organize data according to move id
            for move in memory_moves_list:
                total_qty += move.quantity
                # if no quantity, don't process the move
                if not move.quantity:
                    continue
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
                values = {'name': move.product_id.partner_ref,
			  'product_id': move.product_id.id,
                          'product_qty': move.quantity,
                          'product_uom': move.product_uom.id,
                          'prodlot_id': prodlot_id,
                          'asset_id': move.asset_id.id,
                          'force_complete': move.force_complete,
                          'change_reason': move.change_reason,
                          }
                # average computation from original openerp
                if (picking_type == 'in') and (move.product_id.cost_method == 'average'):
                    values.update({'product_price' : move.cost,
                                   'product_currency': move.currency.id,
                                   })
                partial_datas[pick.id].setdefault(move.move_id.id, []).append(values)

            if not total_qty:
                raise osv.except_osv(_('Processing Error'), _("You have to enter the quantities you want to process before processing the move"))
            # treated moves
            move_ids = partial_datas[pick.id].keys()
            # all moves
            all_move_ids = [move.id for move in pick.move_lines]
            # these moves will be set to 0 - not present in the wizard - create partial objects with qty 0
            missing_move_ids = [x for x in all_move_ids if x not in move_ids]
            # missing moves (deleted memory moves) are replaced by a corresponding partial with qty 0
            for missing_move in move_obj.browse(cr, uid, missing_move_ids, context=context):
                values = {'name': move.product_id.partner_ref,
			  'product_id': missing_move.product_id.id,
                          'product_qty': 0,
                          'product_uom': missing_move.product_uom.id,
                          'prodlot_id': False,
                          'asset_id': False,
                          'force_complete': False,
                          'change_reason': False,
                          }
                # average computation from original openerp
                if (picking_type == 'in') and (missing_move.product_id.cost_method == 'average') and not missing_move.location_dest_id.cross_docking_location_ok:
                    values.update({'product_price' : missing_move.product_id.standard_price,
                                   'product_currency': missing_move.product_id.company_id and missing_move.product_id.company_id.currency_id and missing_move.product_id.company_id.currency_id.id or False,
                                   })
                partial_datas[pick.id].setdefault(missing_move.id, []).append(values)
            
            # integrity constraint
            integrity_check = self.integrity_check_do_incoming_shipment(cr, uid, ids, picking_type, partial_datas, context=context)
            if not integrity_check:
                # the windows must be updated to trigger tree colors
                return self.pool.get('wizard').open_wizard(cr, uid, picking_ids, w_type='update', context=context)
        # call stock_picking method which returns action call
        return pick_obj.do_incoming_shipment(cr, uid, picking_ids, context=dict(context, partial_datas=partial_datas))
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        change the function name to do_incoming_shipment
        '''
        result = super(stock_partial_picking, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
        picking_obj = self.pool.get('stock.picking')
        picking_ids = context.get('active_ids')
        if picking_ids:
            picking_type = picking_obj.read(cr, uid, picking_ids, ['type'], context=context)[0]['type']
            if picking_type == 'in' and view_type == 'form':
                # load the xml tree
                root = etree.fromstring(result['arch'])
                list = ['//button[@name="do_partial"]']
                for xpath in list:
                    fields = root.xpath(xpath)
                    if not fields:
                        raise osv.except_osv(_('Warning !'), _('Element %s not found.')%xpath)
                    for field in fields:
                        # replace call to do_partial by do_incoming_shipment
                        field.set('name', 'do_incoming_shipment')
                result['arch'] = etree.tostring(root)
                
        return result
    
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

