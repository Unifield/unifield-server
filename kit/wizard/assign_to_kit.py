# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Copyright (C) 2011 MSF, TeMPO Consulting.
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
import netsvc
import decimal_precision as dp
from datetime import datetime, timedelta

from msf_outgoing import INTEGRITY_STATUS_SELECTION

class assign_to_kit(osv.osv_memory):
    '''
    substitute wizard
    '''
    _name = "assign.to.kit"
    
    
    def do_assign_to_kit(self, cr, uid, ids, context=None):
        '''
        - for each kit, we look for the corresponding item (or create it)
          and update the corresponding qty
        '''
        # objects
        item_obj = self.pool.get('composition.item')
        to_consume_obj = self.pool.get('kit.creation.to.consume')
        move_obj = self.pool.get('stock.move')
        obj_data = self.pool.get('ir.model.data')
        loc_obj = self.pool.get('stock.location')
        kit_obj = self.pool.get('composition.kit')
        data_tools_obj = self.pool.get('data.tools')
        # load data into the context
        data_tools_obj.load_common_data(cr, uid, ids, context=context)
        # stock move id
        stock_move_ids = context.get('active_ids', False)
        if not stock_move_ids:
            return {'type': 'ir.actions.act_window_close'}
        
        for obj in self.browse(cr, uid, ids, context=context):
            # empty to consume lines will be deleted
            to_consume_ids = []
            # list of items to be deleted (the qty assigned has been set to 0.0)
            item_list = []
            # all kits, we check if some kits were deleted in the wizard, if yes, the corresponding items are deleted
            kit_list = kit_obj.search(cr, uid, [('composition_kit_creation_id', '=', obj.kit_creation_id_assign_to_kit.id)], context=context)
            for mem in obj.kit_ids_assign_to_kit:
                # we pop the kit id from the list of all ids
                kit_list.remove(mem.kit_id_assign_to_kit_line.id)
                # does this stock move exist in the kit
                # check product uom for integrity TODO
                item_ids = item_obj.search(cr, uid, [('item_stock_move_id', 'in', stock_move_ids),('item_kit_id', '=', mem.kit_id_assign_to_kit_line.id)], context=context)
                if item_ids:
                    # an item already exist for this stock move in this kit
                    # if the assigned qty is 0.0, we delete the item
                    if mem.assigned_qty_assign_to_kit_line == 0.0:
                        item_list.extend(item_ids) # item_ids should anyway be of length 1
                    # else we set the selected qty
                    else:
                        item_obj.write(cr, uid, item_ids, {'item_qty': mem.assigned_qty_assign_to_kit_line}, context=context)
                elif mem.assigned_qty_assign_to_kit_line > 0.0:
                    # we create the corresponding item
                    item_values = {'item_module': False,
                                   'item_product_id': obj.product_id_assign_to_kit.id,
                                   'item_qty': mem.assigned_qty_assign_to_kit_line,
                                   'item_uom_id': obj.uom_id_assign_to_kit.id,
                                   'item_lot': obj.prodlot_id_assign_to_kit and obj.prodlot_id_assign_to_kit.name or False,
                                   'item_exp': obj.expiry_date_assign_to_kit or False,
                                   'item_kit_id': mem.kit_id_assign_to_kit_line.id,
                                   'item_description': 'Kitting Order',
                                   'item_stock_move_id': stock_move_ids[0],
                                   }
                    item_obj.create(cr, uid, item_values, context=context)
            # if kit_list is not empty, the user deleted some lines and we therefore delete the items corresponding to the deleted kits
            if kit_list:
                item_ids = item_obj.search(cr, uid, [('item_stock_move_id', 'in', stock_move_ids), ('item_kit_id', 'in', kit_list)], context=context)
                item_list.extend(item_ids)
            # delete empty items
            item_obj.unlink(cr, uid, item_list, context=context)
        return {'type': 'ir.actions.act_window_close'}
    
    def default_get(self, cr, uid, fields, context=None):
        '''
        fill the lines with default values
        '''
        # Some verifications
        if context is None:
            context = {}
        # objects
        move_obj = self.pool.get('stock.move')
        
        res = super(assign_to_kit, self).default_get(cr, uid, fields, context=context)
        stock_move_ids = context.get('active_ids', False)
        if not stock_move_ids:
            return res

        result = []
        for obj in move_obj.browse(cr, uid, stock_move_ids, context=context):
            for kit in obj.kit_creation_id_stock_move.kit_ids_kit_creation:
                if kit.state == 'in_production':
                    # qty already assigned in kits for this stock move
                    # we therefore have a complete picture of assign state for this stock move
                    # because it could be assigned in multiple rounds
                    assigned_qty = 0.0
                    for item in kit.composition_item_ids:
                        # if the item comes from this stock move, we take the qty into account
                        if item.item_stock_move_id.id in stock_move_ids:
                            assigned_qty += item.item_qty
                    # load the kit data
                    values = {'kit_creation_id_assign_to_kit_line': obj.kit_creation_id_stock_move.id,
                              'kit_id_assign_to_kit_line': kit.id,
                              'assigned_qty_assign_to_kit_line': assigned_qty,
                              }
                    result.append(values)
            # kit list
            if 'kit_ids_assign_to_kit' in fields:
                res.update({'kit_ids_assign_to_kit': result})
            # product
            if 'product_id_assign_to_kit' in fields:
                res.update({'product_id_assign_to_kit': obj.product_id.id})
            # total qty
            if 'qty_assign_to_kit' in fields:
                res.update({'qty_assign_to_kit': obj.product_qty})
            # uom
            if 'uom_id_assign_to_kit' in fields:
                res.update({'uom_id_assign_to_kit': obj.product_uom.id})
            # lot
            if 'prodlot_id_assign_to_kit' in fields:
                res.update({'prodlot_id_assign_to_kit': obj.prodlot_id.id})
            # expiry date
            if 'expiry_date_assign_to_kit' in fields:
                res.update({'expiry_date_assign_to_kit': obj.expired_date})
            if 'kit_creation_id_assign_to_kit' in fields:
                res.update({'kit_creation_id_assign_to_kit': obj.kit_creation_id_stock_move.id})
            
        return res
        
    _columns = {'kit_creation_id_assign_to_kit': fields.many2one('kit.creation', string="Kitting Order", readonly=True, required=True),
                'product_id_assign_to_kit': fields.many2one('product.product', string='Product', readonly=True),
                'qty_assign_to_kit': fields.float(string='Total Qty', digits_compute=dp.get_precision('Product UoM'), readonly=True),
                'uom_id_assign_to_kit': fields.many2one('product.uom', string='UoM', readonly=True),
                'prodlot_id_assign_to_kit': fields.many2one('stock.production.lot', string='Batch Number', readonly=True),
                'expiry_date_assign_to_kit': fields.date(string='Expiry Date', readonly=True),
                'kit_ids_assign_to_kit': fields.one2many('assign.to.kit.line', 'wizard_id_assign_to_kit_line', string='Components to Consume'),
                }

assign_to_kit()


class assign_to_kit_line(osv.osv_memory):
    '''
    substitute items
    '''
    _name = 'assign.to.kit.line'
    
    _columns = {'kit_creation_id_assign_to_kit_line': fields.many2one('kit.creation', string="Kitting Order", readonly=True, required=True),
                'kit_id_assign_to_kit_line': fields.many2one('composition.kit', string="Kit Composition List", readonly=True, required=True),
                'wizard_id_assign_to_kit_line': fields.many2one('assign.to.kit', string='Assign wizard'),
                # data
                'assigned_qty_assign_to_kit_line': fields.float(string='Assigned Qty', digits_compute=dp.get_precision('Product UoM'), required=True),
                }
    
assign_to_kit_line()

