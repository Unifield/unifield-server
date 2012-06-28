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
import logging
import tools
from os import path
from order_types import ORDER_PRIORITY, ORDER_CATEGORY

class product_template(osv.osv):
    '''
    add the new service with reception type
    '''
    _inherit = "product.template"
    
    PRODUCT_TYPE = [('product','Stockable Product'),
                    ('consu', 'Non-Stockable'),
                    ('service','Service'), 
                    ('service_recep', 'Service with Reception'),]
    
    _columns = {
        'type': fields.selection(PRODUCT_TYPE, 'Product Type', required=True, help="Will change the way procurements are processed. Consumables are stockable products with infinite stock, or for use when you have no inventory management in the system."),
    }
    
product_template()


class product_product(osv.osv):
    '''
    add on change on type
    '''
    _inherit = 'product.product'
    
    def on_change_type(self, cr, uid, ids, type, context=None):
        '''
        if type is service_with_reception, procure_method is set to make_to_order
        '''
        if context is None:
            context = {}
        
        if type == 'service_recep':
            return {'value': {'procure_method': 'make_to_order', 'supply_method': 'buy',}}
        return {}
    
    def _check_procurement_for_service_with_recep(self, cr, uid, ids, context=None):
        """
        You cannot select Service Location as Source Location.
        """
        if context is None:
            context = {}
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.type == 'service_recep' and obj.procure_method != 'make_to_order':
                raise osv.except_osv(_('Error'), _('You must select on order procurement method for Service with Reception products.'))
        return True
    
    _constraints = [
        (_check_procurement_for_service_with_recep, 'You must select on order procurement method for Service with Reception products.', []),
    ]
    
product_product()


class stock_location(osv.osv):
    '''
    override stock location to add:
    - service location (checkbox - boolean)
    '''
    _inherit = 'stock.location'
    
    _columns = {
        'service_location': fields.boolean(string='Service Location', readonly=True,),
    }
    
    def get_service_location(self, cr, uid, context=None):
        ids = self.search(cr, uid, [('service_location', '=', True)])
        if not ids:
            raise osv.except_osv(_('Error'), _('You must have a location with "Service Location".'))
        return ids[0]

stock_location()


class stock_move(osv.osv):
    '''
    add constraints:
        - source location cannot be a Service location
        - if picking_id is not type 'in', cannot select a product service
        - if product is service, the destination location must be Service location
        - if destination location is Service, the product must be service
    
    on_change on product id
    '''
    _inherit = 'stock.move'
    
    def onchange_product_id(self, cr, uid, ids, prod_id=False, loc_id=False, loc_dest_id=False, address_id=False, parent_type=False):
        '''
        if the product is "service with reception" or "service", the destination location is Service
        '''
        prod_obj = self.pool.get('product.product')
        location_obj = self.pool.get('stock.location')
        result = super(stock_move, self).onchange_product_id(cr, uid, ids, prod_id, loc_id, loc_dest_id, address_id)
        service_loc = location_obj.search(cr, uid, [('service_location', '=', True)])
        if service_loc:
            service_loc = service_loc[0]
        
        if prod_id and prod_obj.browse(cr, uid, prod_id).type in ('service_recep', 'service') and parent_type == 'in':
            if service_loc:
                prod_type = prod_obj.browse(cr, uid, prod_id).type
                result.setdefault('value', {}).update(location_dest_id=service_loc, product_type=prod_type)
                result.update({'domain': {'location_dest_id': [('id', '=', service_loc)]}})
        else:
            if loc_dest_id == service_loc: 
                result.setdefault('value', {}).update(location_dest_id=False, product_type=prod_id and prod_id.type or 'product')
            if parent_type == 'out':
                result.update({'domain': {'location_dest_id': [('standard_out_ok', '=', 'dest')]}})
            else:
                result.update({'domain': {'location_dest_id': [('usage','=','internal')]}})
            
        
        return result
    
    def _check_constaints_service(self, cr, uid, ids, context=None):
        """
        You cannot select Service Location as Source Location.
        """
        if context is None:
            context = {}
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.location_id.service_location:
                raise osv.except_osv(_('Error'), _('You cannot select Service Location as Source Location.'))
            if obj.product_id.type in ('service_recep', 'service'):
                if not obj.picking_id or obj.picking_id.type != 'in':
                    raise osv.except_osv(_('Error'), _('Only Incoming Shipment can manipulate Service Products.'))
                if not obj.location_dest_id.service_location:
                    raise osv.except_osv(_('Error'), _('Service Products must have Service Location as Destination Location.'))
            elif obj.location_dest_id.service_location:
                raise osv.except_osv(_('Error'), _('Service Location cannot be used for non Service Products.'))
        return True
    
    _constraints = [
        (_check_constaints_service, 'You cannot select Service Location as Source Location.', []),
    ]

stock_move()


class sale_order_line(osv.osv):
    '''
    add a constraint as service with reception products are only available with on order procurement method
    '''
    _inherit = 'sale.order.line'
    
    def _check_procurement_for_service_with_recep(self, cr, uid, ids, context=None):
        """
        You cannot select Service Location as Source Location.
        """
        if context is None:
            context = {}
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.product_id.type == 'service_recep' and obj.type != 'make_to_order':
                raise osv.except_osv(_('Error'), _('You must select on order procurement method for Service with Reception products.'))
        return True
    
    _constraints = [
        (_check_procurement_for_service_with_recep, 'You must select on order procurement method for Service with Reception products.', []),
    ]
    
sale_order_line()


class sourcing_line(osv.osv):
    '''
    add a constraint as service with reception products are only available with on order procurement method
    '''
    _inherit = 'sourcing.line'
    
    def _check_procurement_for_service_with_recep(self, cr, uid, ids, context=None):
        """
        You cannot select Service Location as Source Location.
        """
        if context is None:
            context = {}
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.product_id.type == 'service_recep' and obj.type != 'make_to_order':
                raise osv.except_osv(_('Error'), _('You must select on order procurement method for Service with Reception products.'))
        return True
    
    _constraints = [
        (_check_procurement_for_service_with_recep, 'You must select on order procurement method for Service with Reception products.', []),
    ]
    
sourcing_line()


class purchase_order(osv.osv):
    '''
    add constraint
    the function is modified to take into account the new service with reception as stockable product
    '''
    _inherit = 'purchase.order'
    
    def _check_purchase_category(self, cr, uid, ids, context=None):
        """
        Purchase Order of type Category Service should contain only Service Products.
        """
        if context is None:
            context = {}
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.categ == 'service':
                for line in obj.order_line:
                    if not line.product_id or line.product_id.type not in ('service_recep', 'service',):
                        return False
        return True
    
    def has_stockable_product(self,cr, uid, ids, *args):
        '''
        service with reception is considered as stockable product and produce therefore an incoming shipment and corresponding stock moves
        '''
        result = super(purchase_order, self).has_stockable_product(cr, uid, ids, *args)
        for order in self.browse(cr, uid, ids):
            for order_line in order.order_line:
                if order_line.product_id and order_line.product_id.product_tmpl_id.type in ('service_recep',) and order.order_type != 'direct':
                    return True
                
        return result
    
    _constraints = [
        (_check_purchase_category, 'Purchase Order of type Category Service should contain only Service Products.', ['categ']),
    ]
    
purchase_order()


class purchase_order_line(osv.osv):
    '''
    add constraint
    '''
    _inherit = 'purchase.order.line'
    
    def _check_purchase_order_category(self, cr, uid, ids, context=None):
        """
        Purchase Order of type Category Service should contain only Service Products.
        """
        if context is None:
            context = {}
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.product_id.type not in ('service_recep', 'service',) and obj.order_id.categ == 'service':
                return False
        return True
    
    _constraints = [
        (_check_purchase_order_category, 'Purchase Order of type Category Service should contain only Service Products.', ['product_id']),
    ]
    
purchase_order_line()


class stock_picking(osv.osv):
    '''
    add a new field order_category, which reflects the order_category of corresponding sale order/purchase order
    '''
    _inherit = 'stock.picking'
    
    def _vals_get23(self, cr, uid, ids, fields, arg, context=None):
        '''
        get the order category if sale_id or purchase_id exists
        '''
        if context is None:
            context = {}
        
        result = {}
            
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {}
            # initialize the dic
            for f in fields:
                result[obj.id].update({f:False,})
            # a sale order is linked, we gather the categ
            if obj.sale_id:
                result[obj.id]['order_category'] = obj.sale_id.categ
            # a purchase order is linked, we gather the categ    
            elif obj.purchase_id:
                result[obj.id]['order_category'] = obj.purchase_id.categ
                
        return result
    
    def _get_purchase_ids(self, cr, uid, ids, context=None):
        '''
        ids represents the ids of purchase order objects for which categ has changed
        
        return the list of ids of stock picking object which need to get their category field updated
        '''
        if context is None:
            context = {}
        picking_obj = self.pool.get('stock.picking')
        # all stock picking which are linked to the changing purchase order
        result = picking_obj.search(cr, uid, [('purchase_id', 'in', ids)], context=context)
        return result
    
    def _get_sale_ids(self, cr, uid, ids, context=None):
        '''
        ids represents the ids of sale order objects for which categ has changed
        
        return the list of ids of stock picking object which need to get their category field updated
        '''
        if context is None:
            context = {}
        picking_obj = self.pool.get('stock.picking')
        # all stock picking which are linked to the changing sale order
        result = picking_obj.search(cr, uid, [('sale_id', 'in', ids)], context=context)
        return result
    
    _columns = {
            'order_category': fields.function(_vals_get23, method=True, type='selection', selection=ORDER_CATEGORY, string='Order Category', multi='vals_get23', readonly=True,
                store= {
                    'stock.picking': (lambda obj, cr, uid, ids, context: ids, ['purchase_id', 'sale_id'], 10),
                    'purchase.order': (_get_purchase_ids, ['categ',], 10),
                    'sale.order': (_get_sale_ids, ['categ',], 10),
                },
            ),
    }

stock_picking()
