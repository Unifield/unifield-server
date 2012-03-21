# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting
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
from tools.translate import _
import netsvc
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import decimal_precision as dp
import netsvc
import logging
import tools
import time
from os import path

KIT_CREATION_STATE = [('draft', 'Draft'),
                      ('in_production', 'In Production'),
                      ('done', 'Closed'),
                      ('cancel', 'Cancelled'),
                      ]

KIT_TO_CONSUME_AVAILABILITY = [('empty', ''),
                               ('not_available', 'Not Available'),
                               ('partially_available', 'Partially Available'),
                               ('available', 'Available')]

class kit_creation(osv.osv):
    '''
    kit composition class, representing both theoretical composition and actual ones
    '''
    _name = 'kit.creation'
    
    def create_sequence(self, cr, uid, vals, context=None):
        """
        create a new sequence
        """
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')

        name = 'Kit Creation'
        code = 'kit.creation'

        types = {'name': name,
                 'code': code,
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
        create a new sequence for to consume lines
        '''
        vals.update({'to_consume_sequence_id': self.create_sequence(cr, uid, vals, context=context)})
        return super(kit_creation, self).create(cr, uid, vals, context=context)
    
    def reset_to_version(self, cr, uid, ids, context=None):
        '''
        open confirmation wizard
        '''
        # data
        name = _("Reset Components to Consume to Version Reference. Are you sure?")
        model = 'confirm'
        step = 'default'
        question = 'The list of items to consume will be reset to reference list from the selected Version. Are you sure ?'
        clazz = 'kit.creation'
        func = 'do_reset_to_version'
        args = [ids]
        kwargs = {}
        # to reset to version
        for obj in self.browse(cr, uid, ids, context=context):
            # must be a real kit
            if obj.state == 'draft':
                raise osv.except_osv(_('Warning !'), _('Cannot modify draft Kitting Order.'))
            # a version must have been selected
            if not obj.version_id_kit_creation:
                raise osv.except_osv(_('Warning !'), _('The Kitting order is not linked to any version.'))
        
        wiz_obj = self.pool.get('wizard')
        # open the selected wizard
        res = wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=dict(context, question=question,
                                                                                                callback={'clazz': clazz,
                                                                                                          'func': func,
                                                                                                          'args': args,
                                                                                                          'kwargs': kwargs}))
        return res
    
    def do_reset_to_version(self, cr, uid, ids, context=None):
        '''
        remove all items and create one item for each item from the referenced version
        '''
        # objects
        item_obj = self.pool.get('kit.creation.to.consume')
        # unlink all to consume items corresponding to selected kits
        item_ids = item_obj.search(cr, uid, [('kit_creation_id_to_consume', 'in', ids)], context=context)
        item_obj.unlink(cr, uid, item_ids, context=context)
        for obj in self.browse(cr, uid, ids, context=context):
            # copy all items from the version
            for item_v in obj.version_id_kit_creation.composition_item_ids:
                values = {'kit_creation_id_to_consume': obj.id,
                          'product_id_to_consume': item_v.item_product_id.id,
                          'qty_to_consume': item_v.item_qty,
                          'uom_id_to_consume': item_v.item_uom_id.id,
                          'location_src_id_to_consume': obj.default_location_src_id_kit_creation.id,
                          }
                item_obj.create(cr, uid, values, context=context)
        return True
    
    def dummy_function(self, cr, uid, ids, context=None):
        '''
        dummy function to refresh the screen
        '''
        return True
    
    def _confirm_internal_picking(self, cr, uid, ids, pick_id, context=None):
        '''
        confirm the internal picking
        '''
        # objects
        pick_obj = self.pool.get('stock.picking')
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(uid, 'stock.picking', pick_id, 'button_confirm', cr)
        return True
    
    def _validate_internal_picking(self, cr, uid, ids, pick_id, context=None):
        '''
        confirm and validate the internal picking
        '''
        # objects
        pick_obj = self.pool.get('stock.picking')
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(uid, 'stock.picking', pick_id, 'button_confirm', cr)
        # simulate check assign button, as stock move must be available
        pick_obj.force_assign(cr, uid, [pick_id])
        # trigger standard workflow
        pick_obj.action_move(cr, uid, [pick_id])
        wf_service.trg_validate(uid, 'stock.picking', pick_id, 'button_done', cr)
        return True
    
    def _create_picking(self, cr, uid, ids, context=None):
        '''
        create internal picking object
        '''
        # objects
        kit_obj = self.pool.get('composition.kit')
        pick_obj = self.pool.get('stock.picking')
        # we create the internal picking object
        data = self.read(cr, uid, ids, ['name'], context=context)[0]
        kitting_order_name = data['name']
        name = self.pool.get('ir.sequence').get(cr, uid, 'stock.picking.internal')
        pick_values = {'name': name,
                       'origin': kitting_order_name,
                       'type': 'internal',
                       'state': 'draft',
                       'sale_id': False,
                       'address_id': False,
                       'note': 'Internal Picking corresponding to Kitting Order %s.'%kitting_order_name,
                       'date': context['common']['date'],
                       'company_id': context['common']['company_id'],
                       'reason_type_id': context['common']['reason_type_id'],
                       }
        pick_id = pick_obj.create(cr, uid, pick_values, context=context)
        # log picking creation
        pick_obj.log(cr, uid, pick_id, _('The new internal Picking %s has been created.'%name))
        return pick_id
    
    def _create_kit(self, cr, uid, ids, obj, context=None):
        '''
        create a kit
        - if the product is batch management, we create a new lot
        '''
        # objects
        lot_obj = self.pool.get('stock.production.lot')
        kit_obj = self.pool.get('composition.kit')
        
        batch_management = obj.product_id_kit_creation.batch_management
        lot_ref_name = self.pool.get('ir.sequence').get(cr, uid, 'kit.lot')
        default_date = kit_obj.get_default_expiry_date(cr, uid, ids, context=context)
        if batch_management:
            # we create a new lot
            vals = {'product_id': obj.product_id_kit_creation.id,
                    'name': lot_ref_name,
                    'life_date': default_date, # default value, the kit does not exist yet
                    }
            new_lot_id = lot_obj.create(cr, uid, vals, context=context)
            lot_obj.log(cr, uid, new_lot_id, _('Batch Number %s has been created.'%lot_ref_name))
        
        values = {'composition_type': 'real',
                  'composition_product_id': obj.product_id_kit_creation.id,
                  'composition_version_id': obj.version_id_kit_creation and obj.version_id_kit_creation.id or False,
                  #'composition_creation_date': lambda *a: time.strftime('%Y-%m-%d'),
                  'composition_reference': not batch_management and lot_ref_name or False,
                  'composition_lot_id': batch_management and new_lot_id or False,
                  'composition_ref_exp': not batch_management and default_date or False,
                  'composition_kit_creation_id': obj.id,
                  }
        new_kit_id = kit_obj.create(cr, uid, values, context=context)
        # log kit creation
        kit_obj.log(cr, uid, new_kit_id, _('The new empty Kit Composition List %s has been created.'%lot_ref_name))
        return new_kit_id
    
    def start_production(self, cr, uid, ids, context=None):
        '''
        start production - change the state and create internal picking and corresponding kits
        '''
        # objects
        pick_obj = self.pool.get('stock.picking')
        kit_obj = self.pool.get('composition.kit')
        data_tools_obj = self.pool.get('data.tools')
        # load data into the context
        data_tools_obj.load_common_data(cr, uid, ids, context=context)
        for obj in self.browse(cr, uid, ids, context=context):
            # create the internal picking - confirmation of internal picking cannot be performed as long as no stock move exist
            pick_id = self._create_picking(cr, uid, ids, context=context)
            # update the link to picking object and the state
            # change the state
            self.write(cr, uid, ids, {'state': 'in_production',
                                      'internal_picking_id_kit_creation': pick_id}, context=context)
            # create kit in production
            for i in range(obj.qty_kit_creation):
                kit_id = self._create_kit(cr, uid, ids, obj, context=context)
        
        return True
    
    def force_assign(self, cr, uid, ids, context=None):
        '''
        force assign moves in 'confirmed' (Not Available) state
        '''
        for obj in self.browse(cr, uid, ids, context=context):
            return obj.internal_picking_id_kit_creation.force_assign(cr, uid, ids, context)
    
    def cancel_all_lines(self, cr, uid, ids, context=None):
        '''
        cancel corresponding stock move which are in state 'confirmed' and 'assigned'
        '''
        # objects
        move_obj = self.pool.get('stock.move')
        # states to take into account
        states = ['confirmed', 'assigned']
        move_ids = move_obj.search(cr, uid, [('state', 'in', states),('kit_creation_id_stock_move', 'in', ids)], context=context)
        move_obj.write(cr, uid, move_ids, {'state': 'cancel'}, context=context)
        return True
    
    def check_availability(self, cr, uid, ids, context=None):
        '''
        auto selection of location and lots for stock moves
        
        we treat ('confirmed', 'Not Available') moves
        '''
        # objects
        move_obj = self.pool.get('stock.move')
        loc_obj = self.pool.get('stock.location')
        data_tools_obj = self.pool.get('data.tools')
        # load data into the context
        data_tools_obj.load_common_data(cr, uid, ids, context=context)
        
        for obj in self.browse(cr, uid, ids, context=context):
            # data
            data = {}
            # moves consolidated
            move_list = []
            # default location
            default_location_id = obj.default_location_src_id_kit_creation.id
            for move in obj.consumed_ids_kit_creation:
                if move.state == 'confirmed':
                    move_list.append(move.id)
                    # consolidate the moves qty
                    qty = data.setdefault(move.product_id.id, {}).setdefault('uoms', {}).setdefault(move.product_uom.id, 0.0)
                    qty += move.product_qty
                    data.setdefault(move.product_id.id, {}).setdefault('uoms', {})[move.product_uom.id] = qty
                    # save object for efficiency
                    data.setdefault(move.product_id.id, {}).setdefault('object', move.product_id)
            # delete stock moves
            move_obj.unlink(cr, uid, move_list, context=dict(context, call_unlink=True))
            # create consolidated stock moves
            for product_id in data.keys():
                for uom_id in data[product_id]['uoms'].keys():
                    # we check the availability - we use default location from kitting order object
                    res = loc_obj.compute_availability(cr, uid, [default_location_id], obj.consider_child_locations_kit_creation, product_id, uom_id, context=context)
                    # total qty needed for this product/uom
                    needed_qty = data[product_id]['uoms'][uom_id]
                    if res['total'] < needed_qty:
                            diff_qty = needed_qty - res['total']
                            needed_qty -= diff_qty
                            # we dont have enough availability, a first move 'confirmed' is created with missing qty
                            # true for both batch management and not batch management products
                            values = {'kit_creation_id_stock_move': obj.id,
                                      'name': data[product_id]['object'].name,
                                      'picking_id': obj.internal_picking_id_kit_creation.id,
                                      'product_uom': uom_id,
                                      'product_id': product_id,
                                      'date_expected': context['common']['date'],
                                      'date': context['common']['date'],
                                      'product_qty': diff_qty,
                                      'prodlot_id': False, # the qty is not available
                                      'location_id': default_location_id,
                                      'location_dest_id': context['common']['kitting_id'],
                                      'state': 'confirmed', # not available
                                      'reason_type_id': context['common']['reason_type_id']}
                            move_obj.create(cr, uid, values, context=context)
                    if data[product_id]['object'].perishable: # perishable for perishable or batch management
                        # the product is batch management we use the FEFO list
                        for loc in res['fefo']:
                            # as long all needed are not fulfilled
                            if needed_qty > 0.0:
                                # we treat the available qty from FEFO list corresponding to needed quantity
                                if loc['qty'] > needed_qty:
                                    # we have everything !
                                    selected_qty = needed_qty
                                    needed_qty = 0.0
                                else:
                                    # we take all available
                                    selected_qty = loc['qty']
                                    needed_qty -= selected_qty
                                # stock move values
                                values = {'kit_creation_id_stock_move': obj.id,
                                          'name': data[product_id]['object'].name,
                                          'picking_id': obj.internal_picking_id_kit_creation.id,
                                          'product_uom': uom_id,
                                          'product_id': product_id,
                                          'date_expected': context['common']['date'],
                                          'date': context['common']['date'],
                                          'product_qty': selected_qty,
                                          'prodlot_id': loc['prodlot_id'],
                                          'location_id': loc['location_id'],
                                          'location_dest_id': context['common']['kitting_id'],
                                          'state': 'assigned', # available
                                          'reason_type_id': context['common']['reason_type_id']}
                                move_obj.create(cr, uid, values, context=context)
                    else:
                        # the product is not batch management, we use locations in id order
                        for loc in sorted(res.keys()):
                            if isinstance(loc, int) and res[loc]['total'] > 0.0:
                                # as long all needed are not fulfilled
                                if needed_qty > 0.0:
                                    # we treat the available qty from locations corresponding to needed quantity
                                    if res[loc]['total'] > needed_qty:
                                        # we have everything !
                                        selected_qty = needed_qty
                                        needed_qty = 0.0
                                    else:
                                        # we take all available
                                        selected_qty = res[loc]['total']
                                        needed_qty -= selected_qty
                                    # stock move values
                                    values = {'kit_creation_id_stock_move': obj.id,
                                              'name': data[product_id]['object'].name,
                                              'picking_id': obj.internal_picking_id_kit_creation.id,
                                              'product_uom': uom_id,
                                              'product_id': product_id,
                                              'date_expected': context['common']['date'],
                                              'date': context['common']['date'],
                                              'product_qty': selected_qty,
                                              'prodlot_id': False, # not batch management
                                              'location_id': loc,
                                              'location_dest_id': context['common']['kitting_id'],
                                              'state': 'assigned',
                                              'reason_type_id': context['common']['reason_type_id']}
                                    move_obj.create(cr, uid, values, context=context)
        #raise osv.except_osv(_('Warning !'), _('DEBUG.'))
        return True
        
    def process_to_consume(self, cr, uid, ids, context=None):
        '''
        open wizard for to consume processing
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        # data
        name = _("Process Components to Consume")
        model = 'process.to.consume'
        step = 'default'
        wiz_obj = self.pool.get('wizard')
        # this purchase order line replacement function can only be used when the po is in state ('confirmed', 'Validated'),
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.state == 'draft':
                raise osv.except_osv(_('Warning !'), _('Draft Kitting Order cannot process Components to Consume.'))
            if not len(obj.to_consume_ids_kit_creation):
                raise osv.except_osv(_('Warning !'), _('Components to Consume list is empty.'))
        # open the selected wizard
        res = wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=dict(context))
        return res
    
    def mark_as_active(self, cr, uid, ids, context=None):
        '''
        button function
        set the active flag to False
        
        to consumed state function test
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        self.write(cr, uid, ids, {'state': 'in_production'}, context=context)
        return True
    
    def on_change_product_id(self, cr, uid, ids, product_id, context=None):
        '''
        on change function
        
        version - qty - uom are set to False
        '''
        result = {'value': {'batch_check_kit_creation': False,
                            'expiry_check_kit_creation': False,
                            'version_id_kit_creation': False,
                            'qty_kit_creation': 1,
                            'uom_id_kit_creation': False}}
        if not product_id:
            # no product, reset values
            result['value'].update({})
        else:
            # we have a product
            product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            # set the default uom
            uom_id = product.uom_id.id
            # product, fill default UoM
            result['value'].update({'uom_id_kit_creation': uom_id,
                                    'batch_check_kit_creation': product.batch_management,
                                    'expiry_check_kit_creation': product.perishable})
        
        return result
    
    _columns = {'name': fields.char(string='Reference', size=1024, required=True),
                'to_consume_sequence_id': fields.many2one('ir.sequence', 'To Consume Sequence', required=True, ondelete='cascade'),
                'creation_date_kit_creation': fields.date(string='Creation Date', required=True),
                'product_id_kit_creation': fields.many2one('product.product', string='Product', required=True, domain=[('type', '=', 'product'), ('subtype', '=', 'kit')]),
                'version_id_kit_creation': fields.many2one('composition.kit', string='Version', domain=[('composition_type', '=', 'theoretical'), ('state', '=', 'completed')]),
                'qty_kit_creation': fields.integer(string='Qty', digits_compute=dp.get_precision('Product UoM'), required=True),
                'uom_id_kit_creation': fields.many2one('product.uom', string='UoM', required=True),
                'notes_kit_creation': fields.text(string='Notes'),
                'default_location_src_id_kit_creation': fields.many2one('stock.location', string='Default Source Location', required=True, domain=[('usage', '=', 'internal')], help='The Kitting Order needs to be saved in order this option to be taken into account.'),
                'consider_child_locations_kit_creation': fields.boolean(string='Consider Child Locations', help='Consider or not child locations for availability check. The Kitting Order needs to be saved in order this option to be taken into account.'),
                'internal_picking_id_kit_creation': fields.many2one('stock.picking', string='Internal Picking', readonly=True),
                'state': fields.selection(KIT_CREATION_STATE, string='State', readonly=True, required=True),
                'to_consume_ids_kit_creation': fields.one2many('kit.creation.to.consume', 'kit_creation_id_to_consume', string='To Consume'),
                'consumed_ids_kit_creation': fields.one2many('stock.move', 'kit_creation_id_stock_move', string='Stock Moves'),
                'kit_ids_kit_creation': fields.one2many('composition.kit', 'composition_kit_creation_id', string='Stock Moves'),
                # related
                'batch_check_kit_creation': fields.related('product_id_kit_creation', 'batch_management', type='boolean', string='Batch Number Mandatory', readonly=True, store=False),
                # expiry is always true if batch_check is true. we therefore use expry_check for now in the code
                'expiry_check_kit_creation': fields.related('product_id_kit_creation', 'perishable', type='boolean', string='Expiry Date Mandatory', readonly=True, store=False),
                }
    
    _defaults = {'state': 'draft',
                 'name': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'kit.creation'),
                 'creation_date_kit_creation': lambda *a: time.strftime('%Y-%m-%d'),
                 'default_location_src_id_kit_creation': lambda obj, cr, uid, c: obj.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_stock') and obj.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1] or False,
                 'consider_child_locations_kit_creation': True,
                 'qty_kit_creation': 1,
                 }
    
    _order = 'name desc'
    
    def _kit_creation_constraint(self, cr, uid, ids, context=None):
        '''
        constraint on item composition 
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.qty_kit_creation <= 0.0:
                # qty to consume cannot be empty
                raise osv.except_osv(_('Warning !'), _('Number of Kit to produce must be greater than 0.'))
                
        return True
    
    _constraints = [(_kit_creation_constraint, 'Constraint error on Kit Creation.', []),]

kit_creation()


class kit_creation_to_consume(osv.osv):
    '''
    common ancestor
    '''
    _name = 'kit.creation.to.consume'
    _rec_name = 'product_id_to_consume'
    
    def create(self, cr, uid, vals, context=None):
        '''
        add the corresponding line number
        '''
        # gather the line number from the sequence
        kit_creation = self.pool.get('kit.creation').browse(cr, uid, vals['kit_creation_id_to_consume'], context)
        sequence = kit_creation.to_consume_sequence_id
        line = sequence.get_id(test='id', context=context)
        vals.update({'line_number_to_consume': line})
        result = super(kit_creation_to_consume, self).create(cr, uid, vals, context=context)
        return result
    
    def process_to_consume(self, cr, uid, ids, context=None):
        '''
        open wizard for to consume processing
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # objects
        kit_creation_obj = self.pool.get('kit.creation')
        
        for obj in self.browse(cr, uid, ids, context=context):
            # inform the wizard we only want one line in it
            context.update({'to_consume_line_id': obj.id})
            # call the kit order method
            return kit_creation_obj.process_to_consume(cr, uid, [obj.kit_creation_id_to_consume.id], context=context)
    
    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        multi fields function method
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # objects
        loc_obj = self.pool.get('stock.location')
            
        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            # batch management
            result.setdefault(obj.id, {}).update({'batch_check_kit_creation_to_consume': obj.product_id_to_consume.batch_management})
            # perishable
            result.setdefault(obj.id, {}).update({'expiry_check_kit_creation_to_consume': obj.product_id_to_consume.perishable})
            # total_qty
            total_qty = obj.kit_creation_id_to_consume.qty_kit_creation * obj.qty_to_consume
            result.setdefault(obj.id, {}).update({'total_qty_to_consume': total_qty})
            # state
            result.setdefault(obj.id, {}).update({'state': obj.kit_creation_id_to_consume.state})
            # qty_available_to_consume
            # corresponding product object
            product = obj.product_id_to_consume
            # uom from product is taken by default if needed
            uom_id = obj.uom_id_to_consume.id
            # compute child
            compute_child = obj.kit_creation_id_to_consume.consider_child_locations_kit_creation
            # we check for the available qty (in:done, out: assigned, done)
            res = loc_obj.compute_availability(cr, uid, [obj.location_src_id_to_consume.id], compute_child, product.id, uom_id, context=context)
            result.setdefault(obj.id, {}).update({'qty_available_to_consume': res['total']})
        return result
    
    def on_change_product_id(self, cr, uid, ids, product_id, default_location_src_id, consider_child_locations, context=None):
        '''
        on change function
        
        version - qty - uom are set to False
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # objects
        loc_obj = self.pool.get('stock.location')
        prod_obj = self.pool.get('product.product')
        
        result = {'value': {'batch_check_kit_creation_to_consume': False,
                            'expiry_check_kit_creation_to_consume': False,
                            'qty_to_consume': 0.0,
                            'total_qty_to_consume': 0.0,
                            'uom_id_to_consume': False,
                            'location_src_id_to_consume': default_location_src_id,
                            }}
        
        if product_id:
            # we have a product
            product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            # set the default uom
            uom_id = product.uom_id.id
            # product, fill default UoM
            result['value'].update({'uom_id_to_consume': uom_id,
                                    'batch_check_kit_creation': product.batch_management,
                                    'expiry_check_kit_creation': product.perishable})
        
            if default_location_src_id:
                # we check for the available qty (in:done, out: assigned, done)
                res = loc_obj.compute_availability(cr, uid, [default_location_src_id], consider_child_locations, product_id, uom_id, context=context)
                result.setdefault('value', {}).update({'qty_available_to_consume': res['total']})
        
        return result
    
    def on_change_qty(self, cr, uid, ids, qty, creation_qty, context=None):
        '''
        on change function
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        result = {}
        result.setdefault('value', {}).update({'total_qty_to_consume': qty * creation_qty})
        
        return result
    
    def on_change_uom_id(self, cr, uid, ids, product_id, default_location_src_id, consider_child_locations, uom_id, location_src_id, context=None):
        '''
        on change function
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # objects
        loc_obj = self.pool.get('stock.location')
        prod_obj = self.pool.get('product.product')
        
        result = {}
        # priority to line location
        location_id = location_src_id or default_location_src_id
        if product_id and location_id:
            # availability flag
            # corresponding product object
            product = prod_obj.browse(cr, uid, product_id, context=context)
            # uom from product is taken by default if needed - priority to selected uom
            uom_id = uom_id or product.uom_id.id
            # we check for the available qty (in:done, out: assigned, done)
            res = loc_obj.compute_availability(cr, uid, [location_id], consider_child_locations, product_id, uom_id, context=context)
            result.setdefault('value', {}).update({'qty_available_to_consume': res['total']})
        
        return result
    
    def _get_to_consume_ids(self, cr, uid, ids, context=None):
        '''
        ids represents the ids of composition.kit objects for which values have changed
        
        return the list of ids of composition.item objects which need to get their fields updated
        
        self is an composition.kit object
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        to_consume_obj = self.pool.get('kit.creation.to.consume')
        result = to_consume_obj.search(cr, uid, [('kit_creation_id_to_consume', 'in', ids)], context=context)
        return result
    
    _columns = {'kit_creation_id_to_consume': fields.many2one('kit.creation', string="Kitting Order", readonly=True, required=True),
                'product_id_to_consume': fields.many2one('product.product', string='Product', required=True),
                'qty_to_consume': fields.float(string='Qty', digits_compute=dp.get_precision('Product UoM'), required=True),
                'uom_id_to_consume': fields.many2one('product.uom', string='UoM', required=True),
                'location_src_id_to_consume': fields.many2one('stock.location', string='Source Location', required=True, domain=[('usage', '=', 'internal')]),
                'line_number_to_consume': fields.integer(string='Line', required=True, readonly=True),
                'availability_to_consume': fields.selection(KIT_TO_CONSUME_AVAILABILITY, string='Availability', readonly=True, required=True),
                # functions
                # state is defined in children classes as the dynamic store does not seem to work properly with _name + _inherit
                'total_qty_to_consume': fields.function(_vals_get, method=True, type='float', string='Total Qty', multi='get_vals', store=False),
                'qty_available_to_consume': fields.function(_vals_get, method=True, type='float', string='Available Qty', multi='get_vals', store=False),
                'state': fields.function(_vals_get, method=True, type='selection', selection=KIT_CREATION_STATE, string='State', readonly=True, multi='get_vals',
                                         store= {'kit.creation.to.consume': (lambda self, cr, uid, ids, c=None: ids, ['kit_creation_id_to_consume'], 10),
                                                 'kit.creation': (_get_to_consume_ids, ['state'], 10)}),
                'batch_check_kit_creation_to_consume': fields.function(_vals_get, method=True, type='boolean', string='B.Num', multi='get_vals', store=False, readonly=True),
                'expiry_check_kit_creation_to_consume': fields.function(_vals_get, method=True, type='boolean', string='Exp', multi='get_vals', store=False, readonly=True),
                }
    
    _defaults = {'location_src_id_to_consume': lambda obj, cr, uid, c: c.get('location_src_id_to_consume', False),
                 'availability_to_consume': 'empty',
                 }
    _order = 'line_number_to_consume'
    
    def _kit_creation_to_consume_constraint(self, cr, uid, ids, context=None):
        '''
        constraint on item composition 
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.qty_to_consume <= 0.0:
                # qty to consume cannot be empty
                raise osv.except_osv(_('Warning !'), _('Quantity to consume must be greater than 0.0.'))
                
        return True
    
    _constraints = [(_kit_creation_to_consume_constraint, 'Constraint error on Kit Creation to Consume.', []),]
    
kit_creation_to_consume()


#class kit_creation_consumed(osv.osv):
#    '''
#    products to be consumed
#    '''
#    _name = 'kit.creation.consumed'
#    _inherit = 'kit.creation.consume.common'
#    
#    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
#        '''
#        multi fields function method
#        '''
#        # Some verifications
#        if context is None:
#            context = {}
#        if isinstance(ids, (int, long)):
#            ids = [ids]
#            
#        result = {}
#        for obj in self.browse(cr, uid, ids, context=context):
#            result[obj.id] = {}
#            # state
#            result[obj.id].update({'state': obj.kit_creation_id_to_consume.state})
#        return result
#    
#    def _get_consumed_ids(self, cr, uid, ids, context=None):
#        '''
#        ids represents the ids of composition.kit objects for which values have changed
#        
#        return the list of ids of composition.item objects which need to get their fields updated
#        
#        self is an composition.kit object
#        '''
#        # Some verifications
#        if context is None:
#            context = {}
#        if isinstance(ids, (int, long)):
#            ids = [ids]
#            
#        consumed_obj = self.pool.get('kit.creation.consumed')
#        result = consumed_obj.search(cr, uid, [('kit_creation_id_to_consume', 'in', ids)], context=context)
#        return result
#    
#    _columns = {'lot_id_consumed': fields.char(string='Batch Nb', size=1024),
#                'expiry_date_consumed': fields.date(string='Expiry Date'),
#                'kit_id_consumed': fields.many2one('kit.creation', string='Kit Ref', readonly=True),
#                # functions
#                'state': fields.function(_vals_get, method=True, type='selection', selection=KIT_CREATION_STATE, string='State', readonly=True, multi='get_vals',
#                                         store= {'kit.creation.consumed': (lambda self, cr, uid, ids, c=None: ids, ['kit_creation_id_to_consume'], 10),
#                                                 'kit.creation': (_get_consumed_ids, ['state'], 10)}),
#                }
#    
#kit_creation_consumed()


class stock_move(osv.osv):
    '''
    add link to kit creation
    '''
    _inherit = 'stock.move'
    
    _columns = {'kit_creation_id_stock_move': fields.many2one('kit.creation', string='Kit Creation', readonly=True)}
    
    def check_assign_lot(self, cr, uid, ids, context=None):
        """
        check the assignation of stock move taking into account lot and FEFO rule
        """
        # treated move ids
        done = []
        count = 0
        pickings = {}
        if context is None:
            context = {}
        for move in self.browse(cr, uid, ids, context=context):
            if move.product_id.type == 'consu' or move.location_id.usage == 'supplier':
                if move.state in ('confirmed', 'waiting'):
                    done.append(move.id)
                pickings[move.picking_id.id] = 1
                continue
            if move.state in ('confirmed', 'waiting'):
                # Important: we must pass lock=True to _product_reserve() to avoid race conditions and double reservations
                res = self.pool.get('stock.location')._product_reserve(cr, uid, [move.location_id.id], move.product_id.id, move.product_qty, {'uom': move.product_uom.id}, lock=True)
                if res:
                    #_product_available_test depends on the next status for correct functioning
                    #the test does not work correctly if the same product occurs multiple times
                    #in the same order. This is e.g. the case when using the button 'split in two' of
                    #the stock outgoing form
                    self.write(cr, uid, [move.id], {'state':'assigned'})
                    done.append(move.id)
                    pickings[move.picking_id.id] = 1
                    r = res.pop(0)
                    cr.execute('update stock_move set location_id=%s, product_qty=%s, product_uos_qty=%s where id=%s', (r[1], r[0], r[0] * move.product_id.uos_coeff, move.id))

                    while res:
                        r = res.pop(0)
                        move_id = self.copy(cr, uid, move.id, {'product_qty': r[0],'product_uos_qty': r[0] * move.product_id.uos_coeff,'location_id': r[1]})
                        done.append(move_id)
        if done:
            count += len(done)
            self.write(cr, uid, done, {'state': 'assigned'})

        if count:
            for pick_id in pickings:
                wf_service = netsvc.LocalService("workflow")
                wf_service.trg_write(uid, 'stock.picking', pick_id, cr)
        return count
    
stock_move()

