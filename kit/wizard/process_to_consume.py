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

class process_to_consume(osv.osv_memory):
    '''
    substitute wizard
    '''
    _name = "process.to.consume"
    
    def do_process_to_consume(self, cr, uid, ids, context=None):
        '''
        - update components to consume
        - create a stock move for each line
        '''
        # objects
        to_consume_obj = self.pool.get('kit.creation.to.consume')
        move_obj = self.pool.get('stock.move')
        obj_data = self.pool.get('ir.model.data')
        loc_obj = self.pool.get('stock.location')
        
        for obj in self.browse(cr, uid, ids, context=context):
            # empty to consume lines will be deleted
            to_consume_ids = []
            for mem in obj.components_to_consume_ids:
                if mem.selected_qty_process_to_consume >= mem.to_consume_id_process_to_consume.qty_to_consume:
                    # everything has been selected
                    to_consume_ids.append(mem.to_consume_id_process_to_consume.id)
                else:
                    # decrement the qty
                    qty = mem.to_consume_id_process_to_consume.qty_to_consume - mem.selected_qty_process_to_consume
                    mem.to_consume_id_process_to_consume.write({'qty_to_consume': qty}, context=context)
                
                # find the FEFO logic if the product is BATCH MANAGEMENT or EXPIRY DATE
                stock_context = dict(context, compute_child=mem.consider_child_locations_process_to_consume)
                # we check for the available qty (in:done, out: assigned, done)
                # location
                location_ids = [mem.location_src_id_process_to_consume.id]
                # product
                product_id = mem.product_id_process_to_consume.id
                # uom
                uom_id = mem.uom_id_process_to_consume.id
                res = loc_obj._product_reserve_lot(cr, uid, location_ids, product_id, uom_id, context=stock_context, lock=True)
                # kitting location
                kitting_id = obj_data.get_object_reference(cr, uid, 'stock', 'location_production')[1]
                # reason type
                reason_type_id = obj_data.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_kit')[1]
                # create a corresponding stock move
                values = {'kit_creation_id_stock_move': mem.kit_creation_id_process_to_consume.id,
                          'name': mem.product_id_process_to_consume.name,
                          'picking_id': False, # todo create internal picking with kit.creation
                          'product_uom': mem.uom_id_process_to_consume.id,
                          'product_id': mem.product_id_process_to_consume.id,
                          'date_expected': time.strftime('%Y-%m-%d'),
                          'date': time.strftime('%Y-%m-%d'),
                          'product_qty': mem.selected_qty_process_to_consume,
                          'prodlot_id': False,
                          'location_id': mem.location_src_id_process_to_consume.id,
                          'location_dest_id': kitting_id,
                          'state': 'confirmed',
                          'reason_type_id': reason_type_id}
                move_obj.create(cr, uid, values, context=context)
                
        # delete empty lines
        to_consume_obj.unlink(cr, uid, to_consume_ids, context=context)
        return {'type': 'ir.actions.close_window'}
    
    def default_get(self, cr, uid, fields, context=None):
        '''
        fill the lines with default values:
        - context contains to_consume_id, only the selected line
        - context does not contain to_consume_id, all existing to_consume lines from the kit_creation object
        '''
        # Some verifications
        if context is None:
            context = {}
            
        kit_creation_obj = self.pool.get('kit.creation')
        res = super(process_to_consume, self).default_get(cr, uid, fields, context=context)
        kit_creation_ids = context.get('active_ids', False)
        if not kit_creation_ids:
            return res

        result = []
        for obj in kit_creation_obj.browse(cr, uid, kit_creation_ids, context=context):
            for to_consume in obj.to_consume_ids_kit_creation:
                values = {'kit_creation_id_process_to_consume': obj.id,
                          'to_consume_id_process_to_consume': to_consume.id,
                          # data
                          'product_id_process_to_consume': to_consume.product_id_to_consume.id,
                          'qty_process_to_consume': to_consume.qty_to_consume,
                          'selected_qty_process_to_consume': to_consume.qty_to_consume,
                          'uom_id_process_to_consume': to_consume.uom_id_to_consume.id,
                          'location_src_id_process_to_consume': to_consume.location_src_id_to_consume.id,
                          }
                result.append(values)

        if 'components_to_consume_ids' in fields:
            res.update({'components_to_consume_ids': result})
        return res
        
    _columns = {'components_to_consume_ids': fields.one2many('process.to.consume.line', 'wizard_id_process_to_consume', string='Components to Consume'),
                }

process_to_consume()


class process_to_consume_line(osv.osv_memory):
    '''
    substitute items
    '''
    _name = 'process.to.consume.line'
    
    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        multi fields function method
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            # qty_available_to_consume
            # corresponding product object
            product_id = obj.product_id_process_to_consume.id
            # uom from product is taken by default if needed
            uom_id = obj.uom_id_process_to_consume.id
            # compute child
            compute_child = obj.consider_child_locations_process_to_consume
            # we check for the available qty (in:done, out: assigned, done)
            res = self._compute_availability(cr, uid, [obj.location_src_id_process_to_consume.id], compute_child, product_id, uom_id, context=context)
            result.setdefault(obj.id, {}).update({'qty_available_process_to_consume': res['total']})
        return result
    
    _columns = {'kit_creation_id_process_to_consume': fields.many2one('kit.creation', string="Kitting Order", readonly=True, required=True),
                'to_consume_id_process_to_consume': fields.many2one('kit.creation.to.consume', string="To Consume Line", readonly=True, required=True),
                'wizard_id_process_to_consume': fields.many2one('substitute', string='Substitute wizard'),
                # data
                'product_id_process_to_consume': fields.many2one('product.product', string='Product', readonly=True, required=True),
                'qty_process_to_consume': fields.float(string='Qty', digits_compute=dp.get_precision('Product UoM'), readonly=True, required=True),
                'selected_qty_process_to_consume': fields.float(string='Selected Qty', digits_compute=dp.get_precision('Product UoM'), required=True),
                'uom_id_process_to_consume': fields.many2one('product.uom', string='UoM', readonly=True, required=True),
                'location_src_id_process_to_consume': fields.many2one('stock.location', string='Source Location', required=True, readonly=True, domain=[('usage', '=', 'internal')]),
                # function
                'qty_available_process_to_consume': fields.function(_vals_get, method=True, type='float', string='Available Qty', multi='get_vals', store=False),
                # related
                'line_number_process_to_consume': fields.related('to_consume_id_process_to_consume', 'line_number_to_consume', type='integer', string='Line'),
                'consider_child_locations_process_to_consume': fields.related('kit_creation_id_process_to_consume', 'consider_child_locations_kit_creation', type='boolean', string='Consider Child Location'),
                }
    
process_to_consume_line()

