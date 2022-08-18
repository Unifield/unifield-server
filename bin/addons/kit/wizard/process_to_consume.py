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
import decimal_precision as dp


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
        data_tools_obj = self.pool.get('data.tools')
        # load data into the context
        data_tools_obj.load_common_data(cr, uid, ids, context=context)

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

                # create a corresponding stock move
                values = {'kit_creation_id_stock_move': mem.kit_creation_id_process_to_consume.id,
                          'to_consume_id_stock_move': mem.to_consume_id_process_to_consume.id,
                          'name': mem.product_id_process_to_consume.name,
                          'picking_id': mem.kit_creation_id_process_to_consume.internal_picking_id_kit_creation.id,
                          'product_uom': mem.uom_id_process_to_consume.id,
                          'product_id': mem.product_id_process_to_consume.id,
                          'date_expected': context['common']['date'],
                          'date': context['common']['date'],
                          'product_qty': mem.total_selected_qty_process_to_consume,
                          'prodlot_id': False,
                          'location_id': mem.location_src_id_process_to_consume.id,
                          'location_dest_id': context['common']['kitting_id'],
                          'state': 'confirmed',
                          'reason_type_id': context['common']['reason_type_id']}
                move_obj.create(cr, uid, values, context=context)

        # delete empty lines
        to_consume_obj.unlink(cr, uid, to_consume_ids, context=context)
        return {'type': 'ir.actions.act_window_close'}

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        '''
        fill the lines with default values:
        - context contains to_consume_id, only the selected line
        - context does not contain to_consume_id, all existing to_consume lines from the kit_creation object
        '''
        # Some verifications
        if context is None:
            context = {}
        # objects
        kit_creation_obj = self.pool.get('kit.creation')
        to_consume_obj = self.pool.get('kit.creation.to.consume')

        res = super(process_to_consume, self).default_get(cr, uid, fields, context=context, from_web=from_web)
        kit_creation_ids = context.get('active_ids', False)
        if not kit_creation_ids:
            return res

        result = []
        for obj in kit_creation_obj.browse(cr, uid, kit_creation_ids, context=context):
            if context.get('to_consume_line_id', False):
                # one line is selected, we load only this one
                to_consume = to_consume_obj.browse(cr, uid, context.get('to_consume_line_id'), context=context)
                values = {'kit_creation_id_process_to_consume': obj.id,
                          'to_consume_id_process_to_consume': to_consume.id,
                          # data
                          'product_id_process_to_consume': to_consume.product_id_to_consume.id,
                          'qty_process_to_consume': to_consume.qty_to_consume,
                          'selected_qty_process_to_consume': to_consume.qty_to_consume,
                          'uom_id_process_to_consume': to_consume.uom_id_to_consume.id,
                          'location_src_id_process_to_consume': to_consume.location_src_id_to_consume.id,
                          'consider_child_locations_process_to_consume': obj.consider_child_locations_kit_creation,
                          }
                result.append(values)
            else:
                # no line selected, we load all lines
                for to_consume in obj.to_consume_ids_kit_creation:
                    values = {'kit_creation_id_process_to_consume': obj.id,
                              'to_consume_id_process_to_consume': to_consume.id,
                              # data
                              'product_id_process_to_consume': to_consume.product_id_to_consume.id,
                              'qty_process_to_consume': to_consume.qty_to_consume,
                              'selected_qty_process_to_consume': to_consume.qty_to_consume,
                              'uom_id_process_to_consume': to_consume.uom_id_to_consume.id,
                              'location_src_id_process_to_consume': to_consume.location_src_id_to_consume.id,
                              'consider_child_locations_process_to_consume': obj.consider_child_locations_kit_creation,
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

    def on_change_location_src_id(self, cr, uid, ids, product_id, uom_id, location_src_id, consider_child_locations, context=None):
        '''
        on change
        '''
        # objects
        loc_obj = self.pool.get('stock.location')
        # default value
        result = {'value': {'qty_available_process_to_consume': 0.0}}
        if product_id and uom_id and location_src_id:
            # we check for the available qty (in:done, out: assigned, done)
            res = loc_obj.compute_availability(cr, uid, [location_src_id], consider_child_locations, product_id, uom_id, context=context)
            result.setdefault('value', {}).update({'qty_available_process_to_consume': res['total']})
        return result

    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        multi fields function method
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # objects
        loc_obj = self.pool.get('stock.location')

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
            res = loc_obj.compute_availability(cr, uid, [obj.location_src_id_process_to_consume.id], compute_child, product_id, uom_id, context=context)
            result.setdefault(obj.id, {}).update({'qty_available_process_to_consume': res['total']})
            # total selected qty
            total_qty = obj.selected_qty_process_to_consume * obj.kit_creation_id_process_to_consume.qty_kit_creation
            result.setdefault(obj.id, {}).update({'total_selected_qty_process_to_consume': total_qty})
        return result

    _columns = {'kit_creation_id_process_to_consume': fields.many2one('kit.creation', string="Kitting Order", readonly=True, required=True),
                'to_consume_id_process_to_consume': fields.many2one('kit.creation.to.consume', string="To Consume Line", readonly=True, required=True),
                'wizard_id_process_to_consume': fields.many2one('substitute', string='Substitute wizard'),
                # data
                'product_id_process_to_consume': fields.many2one('product.product', string='Product', readonly=True, required=True),
                'qty_process_to_consume': fields.float(string='Qty per Kit', digits_compute=dp.get_precision('Product UoM'), readonly=True, required=True, related_uom='uom_id_process_to_consume'),
                'selected_qty_process_to_consume': fields.float(string='Selected Qty per Kit', digits_compute=dp.get_precision('Product UoM'), required=True, related_uom='uom_id_process_to_consume'),
                'uom_id_process_to_consume': fields.many2one('product.uom', string='UoM', readonly=True, required=True),
                'location_src_id_process_to_consume': fields.many2one('stock.location', string='Source Location', required=True, domain=[('usage', '=', 'internal')]),
                #'consider_child_locations_process_to_consume': fields.boolean(string='Consider Child Locations', help='Consider or not child locations for availability check.'),
                # function
                'total_selected_qty_process_to_consume': fields.function(_vals_get, method=True, type='float', string='Total Selected Qty', multi='get_vals', store=False, readonly=True),
                'qty_available_process_to_consume': fields.function(_vals_get, method=True, type='float', string='Available Qty', multi='get_vals', store=False),
                # related
                'line_number_process_to_consume': fields.related('to_consume_id_process_to_consume', 'line_number_to_consume', type='integer', string='Line', write_relate=False),
                'consider_child_locations_process_to_consume': fields.related('kit_creation_id_process_to_consume', 'consider_child_locations_kit_creation', type='boolean', string='Consider Child Location', write_relate=False),
                }

process_to_consume_line()

