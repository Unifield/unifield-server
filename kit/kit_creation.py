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
        item_ids = item_obj.search(cr, uid, [('kit_creation_id_consume_common', 'in', ids)], context=context)
        item_obj.unlink(cr, uid, item_ids, context=context)
        for obj in self.browse(cr, uid, ids, context=context):
            # copy all items from the version
            for item_v in obj.version_id_kit_creation.composition_item_ids:
                values = {'kit_creation_id_consume_common': obj.id,
                          'product_id_consume_common': item_v.item_product_id.id,
                          'qty_consume_common': item_v.item_qty,
                          'uom_id_consume_common': item_v.item_uom_id.id,
                          'location_src_id_consume_common': obj.default_location_src_id_kit_creation.id,
                          }
                item_obj.create(cr, uid, values, context=context)
        return True
    
    def dummy_function(self, cr, uid, ids, context=None):
        '''
        dummy function to refresh the screen
        '''
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
        result = {'value': {'batch_check_kit_creation': False, 'expiry_check_kit_creation': False}}
        if not product_id:
            # no product, reset values
            result['value'].update({'version_id_kit_creation': False, 'qty_kit_creation': 0.0, 'uom_id_kit_creation': False})
        else:
            # we have a product
            product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            # set the default uom
            uom_id = product.uom_id.id
            # product, fill default UoM
            result['value'].update({'version_id_kit_creation': False,
                                    'qty_kit_creation': 0.0,
                                    'uom_id_kit_creation': uom_id,
                                    'batch_check_kit_creation': product.batch_management,
                                    'expiry_check_kit_creation': product.perishable})
        
        return result
    
    _columns = {'name': fields.char(string='Reference', size=1024, required=True),
                'creation_date_kit_creation': fields.date(string='Creation Date', required=True),
                'product_id_kit_creation': fields.many2one('product.product', string='Product', required=True, domain=[('type', '=', 'product'), ('subtype', '=', 'kit')]),
                'version_id_kit_creation': fields.many2one('composition.kit', string='Version', domain=[('composition_type', '=', 'theoretical'), ('state', '=', 'completed')]),
                'qty_kit_creation': fields.integer(string='Qty', digits_compute=dp.get_precision('Product UoM'), required=True),
                'uom_id_kit_creation': fields.many2one('product.uom', string='UoM', required=True),
                'notes_kit_creation': fields.text(string='Notes'),
                'default_location_src_id_kit_creation': fields.many2one('stock.location', string='Default Source Location', required=True, domain=[('usage', '=', 'internal')], help='The Kitting Order needs to be saved in order this option to be taken into account.'),
                'state': fields.selection(KIT_CREATION_STATE, string='State', readonly=True, required=True),
                'to_consume_ids_kit_creation': fields.one2many('kit.creation.to.consume', 'kit_creation_id_consume_common', string='To Consume'),
                'consumed_ids_kit_creation': fields.one2many('kit.creation.consumed', 'kit_creation_id_consume_common', string='Consumed', readonly=True),
                'consider_child_locations_kit_creation': fields.boolean(string='Consider Child Locations', help='Consider or not child locations for availability check. The Kitting Order needs to be saved in order this option to be taken into account.'),
                'to_consume_sequence_id': fields.many2one('ir.sequence', 'To Consume Sequence', required=True, ondelete='cascade'),
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
    _rec_name = 'product_id_consume_common'
    
    def create(self, cr, uid, vals, context=None):
        '''
        _inherit = 'sale.order.line'
        
        add the corresponding line number
        '''
        # gather the line number from the sale order sequence
        order = self.pool.get('sale.order').browse(cr, uid, vals['order_id'], context)
        sequence = order.sequence_id
        line = sequence.get_id(test='id', context=context)
        vals.update({'line_number': line})
        
        # create the new sale order line
        result = super(sale_order_line, self).create(cr, uid, vals, context=context)
        
        return result
    
    def on_change_product_id(self, cr, uid, ids, product_id, default_location_id, context=None):
        '''
        on change function
        
        version - qty - uom are set to False
        '''
        result = {'value': {'batch_check_kit_creation_consume_common': False,
                            'expiry_check_kit_creation_consume_common': False,
                            'qty_consume_common': 0.0,
                            'uom_id_consume_common': False,
                            'location_src_id_consume_common': default_location_id,
                            }}
        if product_id:
            # we have a product
            product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            # set the default uom
            uom_id = product.uom_id.id
            # product, fill default UoM
            result['value'].update({'uom_id_consume_common': uom_id,
                                    'batch_check_kit_creation': product.batch_management,
                                    'expiry_check_kit_creation': product.perishable})
        
        return result
    
    def _vals_get1(self, cr, uid, ids, fields, arg, context=None):
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
            # batch management
            result.setdefault(obj.id, {}).update({'batch_check_kit_creation_consume_common': obj.product_id_consume_common.batch_management})
            # perishable
            result.setdefault(obj.id, {}).update({'expiry_check_kit_creation_consume_common': obj.product_id_consume_common.perishable})
        return result
    
    _columns = {'kit_creation_id_consume_common': fields.many2one('kit.creation', string="Kitting Order", readonly=True, required=True),
                'product_id_consume_common': fields.many2one('product.product', string='Product', required=True),
                'qty_consume_common': fields.float(string='Qty', digits_compute=dp.get_precision('Product UoM'), required=True),
                'uom_id_consume_common': fields.many2one('product.uom', string='UoM', required=True),
                'location_src_id_consume_common': fields.many2one('stock.location', string='Source Location', required=True, domain=[('usage', '=', 'internal')]),
                'line_number_consume_common': fields.integer(string='Line', required=True),
                # functions
                # state is defined in children classes as the dynamic store does not seem to work properly with _name + _inherit
                'batch_check_kit_creation_consume_common': fields.function(_vals_get1, method=True, type='boolean', string='B.Num', multi='get_vals1', store=False, readonly=True),
                'expiry_check_kit_creation_consume_common': fields.function(_vals_get1, method=True, type='boolean', string='Exp', multi='get_vals1', store=False, readonly=True),
                }
    
    _defaults = {'location_src_id_consume_common': lambda obj, cr, uid, c: c.get('location_src_id_consume_common', False)}
    _order = 'line_number_consume_common'
    
kit_creation_to_consume()


class kit_creation_to_consume(osv.osv):
    '''
    products to be consumed
    '''
    _name = 'kit.creation.to.consume'
    _inherit = 'kit.creation.consume.common'
    
    def _compute_availability(self, cr, uid, ids, consider_child_locations, product_id, uom_id, context=None):
        '''
        call stock computation function
        
        ids represent location ids !!!
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # objects
        loc_obj = self.pool.get('stock.location')
        # do we want the child location
        stock_context = dict(context, compute_child=consider_child_locations)
        # we check for the available qty (in:done, out: assigned, done)
        res = loc_obj._product_reserve_lot(cr, uid, ids, product_id, uom_id, context=stock_context, lock=True)
        return res
    
    def _vals_get2(self, cr, uid, ids, fields, arg, context=None):
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
        prod_obj = self.pool.get('product.product')
        
        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            # total_qty
            total_qty = obj.kit_creation_id_consume_common.qty_kit_creation * obj.qty_consume_common
            result.setdefault(obj.id, {}).update({'total_qty_to_consume': total_qty})
            # state
            result.setdefault(obj.id, {}).update({'state': obj.kit_creation_id_consume_common.state})
            # qty_available_to_consume
            # corresponding product object
            product = obj.product_id_consume_common
            # uom from product is taken by default if needed
            uom_id = obj.uom_id_consume_common.id
            # compute child
            compute_child = obj.kit_creation_id_consume_common.consider_child_locations_kit_creation
            # we check for the available qty (in:done, out: assigned, done)
            res = self._compute_availability(cr, uid, [obj.location_src_id_consume_common.id], compute_child, product.id, uom_id, context=context)
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
        
        result = super(kit_creation_to_consume, self).on_change_product_id(cr, uid, ids, product_id, default_location_src_id, context=context)
        result.setdefault('value', {}).update({'total_qty_to_consume': 0.0})
        
        if product_id and default_location_src_id:
            # availability flag
            # corresponding product object
            product = prod_obj.browse(cr, uid, product_id, context=context)
            # uom from product is taken by default if needed
            uom_id = product.uom_id.id
            # we check for the available qty (in:done, out: assigned, done)
            res = self._compute_availability(cr, uid, [default_location_src_id], consider_child_locations, product_id, uom_id, context=context)
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
            res = self._compute_availability(cr, uid, [location_id], consider_child_locations, product_id, uom_id, context=context)
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
        result = to_consume_obj.search(cr, uid, [('kit_creation_id_consume_common', 'in', ids)], context=context)
        return result
    
    _columns = {'availability_to_consume': fields.selection(KIT_TO_CONSUME_AVAILABILITY, string='Availability', readonly=True, required=True),
                'qty_available_to_consume': fields.function(_vals_get2, method=True, type='float', string='Available Qty', multi='get_vals2', store=False),
                # functions
                'total_qty_to_consume': fields.function(_vals_get2, method=True, type='float', string='Total Qty', multi='get_vals2', store=False),
                'state': fields.function(_vals_get2, method=True, type='selection', selection=KIT_CREATION_STATE, string='State', readonly=True, multi='get_vals2',
                                         store= {'kit.creation.to.consume': (lambda self, cr, uid, ids, c=None: ids, ['kit_creation_id_consume_common'], 10),
                                                 'kit.creation': (_get_to_consume_ids, ['state'], 10)}),
                }
    
    _defaults = {'availability_to_consume': 'empty',
                 }
    
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
            if obj.qty_consume_common <= 0.0:
                # qty to consume cannot be empty
                raise osv.except_osv(_('Warning !'), _('Quantity to consume must be greater than 0.0.'))
                
        return True
    
    _constraints = [(_kit_creation_to_consume_constraint, 'Constraint error on Kit Creation to Consume.', []),]
    
kit_creation_to_consume()


class kit_creation_consumed(osv.osv):
    '''
    products to be consumed
    '''
    _name = 'kit.creation.consumed'
    _inherit = 'kit.creation.consume.common'
    
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
            result[obj.id] = {}
            # state
            result[obj.id].update({'state': obj.kit_creation_id_consume_common.state})
        return result
    
    def _get_consumed_ids(self, cr, uid, ids, context=None):
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
            
        consumed_obj = self.pool.get('kit.creation.consumed')
        result = consumed_obj.search(cr, uid, [('kit_creation_id_consume_common', 'in', ids)], context=context)
        return result
    
    _columns = {'lot_id_consumed': fields.char(string='Batch Nb', size=1024),
                'expiry_date_consumed': fields.date(string='Expiry Date'),
                'kit_id_consumed': fields.many2one('kit.creation', string='Kit Ref', readonly=True),
                # functions
                'state': fields.function(_vals_get, method=True, type='selection', selection=KIT_CREATION_STATE, string='State', readonly=True, multi='get_vals',
                                         store= {'kit.creation.consumed': (lambda self, cr, uid, ids, c=None: ids, ['kit_creation_id_consume_common'], 10),
                                                 'kit.creation': (_get_consumed_ids, ['state'], 10)}),
                }
    
kit_creation_consumed()


