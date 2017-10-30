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
from order_types import ORDER_CATEGORY

class product_template(osv.osv):
    '''
    add the new service with reception type
    '''
    _inherit = "product.template"

    PRODUCT_TYPE = [
        ('product', 'Stockable Product'),
        ('consu', 'Non-Stockable'),
        ('service_recep', 'Service with Reception'),
    ]

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

        if type in ('consu', 'service', 'service_recep'):
            return {'value': {'procure_method': 'make_to_order', 'supply_method': 'buy', }}
        return {}

    def _check_procurement_for_service_with_recep(self, cr, uid, ids, context=None):
        """
        You cannot select Service Location as Source Location.
        """
        if context is None:
            context = {}
        for obj in self.read(cr, uid, ids, ['type', 'procure_method'], context=context):
            if obj['type'] in ('consu', 'service', 'service_recep') and obj['procure_method'] != 'make_to_order':
                raise osv.except_osv(_('Error'), _('You must select on order procurement method for %s products.') % (obj['type'] == 'consu' and 'Non-stockable' or 'Service'))
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

    def onchange_product_id(self, cr, uid, ids, prod_id=False, loc_id=False, loc_dest_id=False, address_id=False, parent_type=False, purchase_line_id=False, out=False):
        '''
        if the product is "service with reception" or "service", the destination location is Service
        '''
        prod_obj = self.pool.get('product.product')
        location_obj = self.pool.get('stock.location')

        result = super(stock_move, self).onchange_product_id(cr, uid, ids, prod_id, loc_id, loc_dest_id, address_id, parent_type, purchase_line_id, out)

        product_type = False
        location_id = loc_id and location_obj.browse(cr, uid, loc_id) or False
        location_dest_id = loc_dest_id and location_obj.browse(cr, uid, loc_dest_id) or False
        service_loc = location_obj.get_service_location(cr, uid)
        non_stockable_loc = location_obj.search(cr, uid, [('non_stockable_ok', '=', True)])
        id_cross = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        input_id = location_obj.search(cr, uid, [('input_ok', '=', True)])
        po = purchase_line_id and self.pool.get('purchase.order.line').browse(cr, uid, purchase_line_id) or False
        cd = po and po.order_id.cross_docking_ok or False
        packing_ids = []
        stock_ids = []

        wh_ids = self.pool.get('stock.warehouse').search(cr, uid, [])
        for wh in self.pool.get('stock.warehouse').browse(cr, uid, wh_ids):
            packing_ids.append(wh.lot_packing_id.id)
            stock_ids.append(wh.lot_stock_id.id)

        vals = {}

        if prod_id:
            product_type = prod_obj.browse(cr, uid, prod_id).type
            vals.update({'product_type': product_type})
        else:
            vals.update({'product_type': False})

        if non_stockable_loc:
            non_stockable_loc = non_stockable_loc[0]

        if input_id:
            input_id = input_id[0]

        if not prod_id:
            if parent_type == 'in':
                vals.update(location_dest_id=False)
            elif parent_type == 'out':
                vals.update(location_id=False)
            else:
                vals.update(location_id=False, location_dest_id=False)

        # Case when incoming shipment
        if product_type and parent_type == 'in':
            # Set service location as destination for service products
            if product_type in ('service_recep', 'service'):
                if service_loc:
                    vals.update(location_dest_id=service_loc, product_type=product_type)
            # Set cross-docking as destination for non-stockable with cross-docking context
            elif product_type == 'consu' and cd and loc_dest_id not in (id_cross, service_loc):
                vals.update(location_dest_id=id_cross)
            # Set non-stockable as destination for non-stockable without cross-docking context
            elif product_type == 'consu' and not cd and loc_dest_id not in (id_cross, service_loc):
                vals.update(location_dest_id=non_stockable_loc)
            # Set input for standard products
            elif product_type == 'product' and not (loc_dest_id and (not location_dest_id.non_stockable_ok and (location_dest_id.usage == 'internal' or location_dest_id.virtual_ok))):
                vals.update(location_dest_id=input_id)
        # Case when internal picking
        elif product_type and parent_type == 'internal':
            # Source location
            # Only cross-docking is available for Internal move for non-stockable products
            if product_type == 'consu' and not (loc_id and (location_id.cross_docking_location_ok or location_id.quarantine_location)):
                vals.update(location_id=id_cross)
            elif product_type == 'product' and not (loc_id and (location_id.usage == 'internal' or location_dest_id.virtual_ok)):
                vals.update(location_id=stock_ids and stock_ids[0] or False)
            elif product_type == 'service_recep':
                vals.update(location_id=id_cross)
            # Destination location
            if product_type == 'consu' and not (loc_dest_id and (location_dest_id.usage == 'inventory' or location_dest_id.destruction_location or location_dest_id.quarantine_location)):
                vals.update(location_dest_id=non_stockable_loc)
            elif product_type == 'product' and not (loc_dest_id and (not location_dest_id.non_stockable_ok and (location_dest_id.usage == 'internal' or location_dest_id.virtual_ok))):
                vals.update(location_dest_id=False)
            elif product_type == 'service_recep':
                vals.update(location_dest_id=service_loc)
        # Case when outgoing delivery or picking ticket
        elif product_type and parent_type == 'out':
            # Source location
            # Only cross-docking is available for Outgoing moves for non-stockable products
            if product_type == 'consu' and not (loc_id and location_id.cross_docking_location_ok):
                vals.update(location_id=id_cross)
            elif product_type == 'product' and not (loc_id and (location_id.usage == 'internal' or not location_id.quarantine_location or not location_id.output_ok or not location_id.input_ok)):
                vals.update(location_id=stock_ids and stock_ids[0] or False)
            elif product_type == 'service_recep':
                vals.update(location_id=id_cross)
            # Destinatio location
            if product_type == 'consu' and not (loc_dest_id and (location_dest_id.output_ok or location_dest_id.usage == 'customer')):
                # If we are not in Picking ticket and the dest. loc. is not output or customer, unset the dest.
                if loc_id and loc_id not in packing_ids:
                    vals.update(location_dest_id=False)

        if not result.get('value'):
            result['value'] = vals
        else:
            result['value'].update(vals)

        return result

    def _check_constaints_service(self, cr, uid, ids, context=None):
        """
        You cannot select Service Location as Source Location.
        """
        if context is None:
            context = {}
        if ids:
            cr.execute("""select
                count(pick.type = 'in' and t.type in ('service_recep', 'service') and not dest.service_location and not dest.cross_docking_location_ok or NULL),
                count(pick.type = 'internal' and not src.cross_docking_location_ok and t.type in ('service_recep', 'service') or NULL),
                count(pick.type = 'internal' and not dest.service_location and t.type in ('service_recep', 'service') or NULL),
                count(t.type in ('service_recep', 'service') and pick.type = 'out' and pick.subtype in ('standard', 'picking') and not src.cross_docking_location_ok or NULL),
                count(t.type not in ('service_recep', 'service') and (dest.service_location or src.service_location ) or NULL)
                from stock_move m
                left join stock_picking pick on m.picking_id = pick.id
                left join product_product p on m.product_id = p.id
                left join product_template t on p.product_tmpl_id = t.id
                left join stock_location src on m.location_id = src.id
                left join stock_location dest on m.location_dest_id = dest.id
            where m.id in %s""", (tuple(ids),))
            for res in cr.fetchall():
                if res[0]:
                    raise osv.except_osv(_('Error'), _('Service Products must have Service or Cross Docking Location as Destination Location.'))
                if res[1]:
                    raise osv.except_osv(_('Error'), _('Service Products must have Cross Docking Location as Source Location.'))
                if res[2]:
                    raise osv.except_osv(_('Error'), _('Service Products must have Service Location as Destination Location.'))
                if res[3]:
                    raise osv.except_osv(_('Error'), _('Service Products must have Cross Docking Location as Source Location.'))
                if res[4]:
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


class purchase_order(osv.osv):
    '''
    add constraint
    the function is modified to take into account the new service with reception as stockable product
    '''
    _inherit = 'purchase.order'

#    def _check_purchase_category(self, cr, uid, ids, context=None):
#        """
#        Purchase Order of type Category Service should contain only Service Products.
#        """
#        if context is None:
#            context = {}
#        for obj in self.browse(cr, uid, ids, context=context):
#            if obj.categ == 'service':
#                for line in obj.order_line:
#                    if not line.product_id or line.product_id.type not in ('service_recep', 'service',):
#                        return False
#        return True

    def has_stockable_product(self, cr, uid, ids, *args):
        '''
        service with reception is considered as stockable product and produce therefore an incoming shipment and corresponding stock moves
        '''
        result = super(purchase_order, self).has_stockable_product(cr, uid, ids, *args)
        for order in self.browse(cr, uid, ids):
            for order_line in order.order_line:
                if order_line.product_id and order_line.product_id.product_tmpl_id.type in ('service_recep',) and order.order_type != 'direct':
                    return True

        return result

#    by QT : Remove the constraint because if you change the Order category from 'Service' to 'Medical' and try to add a non-service product,
#            the constraint returns False
    _constraints = [
        #        (_check_purchase_category, 'Purchase Order of type Category Service should contain only Service Products.', ['categ']),
    ]

purchase_order()


#    by QT : Remove the constraint because if you change the Order category from 'Service' to 'Medical' and try to add a non-service product,
#            the constraint returns False
# class purchase_order_line(osv.osv):
#    '''
#    add constraint
#    '''
#    _inherit = 'purchase.order.line'
#
#    def _check_purchase_order_category(self, cr, uid, ids, context=None):
#        """
#        Purchase Order of type Category Service should contain only Service Products.
#        """
#        if context is None:
#            context = {}
#        for obj in self.browse(cr, uid, ids, context=context):
#            if obj.product_id.type not in ('service_recep', 'service',) and obj.order_id.categ == 'service':
#                return False
#        return True
#
#    _constraints = [
#        (_check_purchase_order_category, 'Purchase Order of type Category Service should contain only Service Products.', ['product_id']),
#    ]
#
# purchase_order_line()


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
                result[obj.id].update({f:False, })
            # a sale order is linked, we gather the categ
            if obj.sale_id:
                result[obj.id]['order_category'] = obj.sale_id.categ
            # a purchase order is linked, we gather the categ
            elif obj.purchase_id:
                result[obj.id]['order_category'] = obj.purchase_id.categ
            elif obj.rac_id:
                result[obj.id]['order_category'] = obj.rac_id.categ

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

    def _get_rac_ids(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        return self.pool.get('stock.picking').search(cr, uid, [('rac_id', 'in', ids)], context=context)

    _columns = {
        'order_category': fields.function(_vals_get23, method=True, type='selection', selection=ORDER_CATEGORY, string='Order Category', multi='vals_get23', readonly=True,
                                          store={
                                              'stock.picking': (lambda obj, cr, uid, ids, context: ids, ['purchase_id', 'sale_id'], 10),
                                              'purchase.order': (_get_purchase_ids, ['categ', ], 10),
                                              'sale.order': (_get_sale_ids, ['categ', ], 10),
                                              'real.average.consumption': (_get_rac_ids, ['categ'], 10),
                                          },
                                          ),
    }

stock_picking()
