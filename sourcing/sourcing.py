# -*- coding: utf-8 -*-
##############################################################################
#
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

from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta, relativedelta
from osv import osv, fields
from osv.orm import browse_record, browse_null
from tools.translate import _

import decimal_precision as dp
import netsvc
import pooler
import time

from order_types import ORDER_PRIORITY, ORDER_CATEGORY

_SELECTION_PO_CFT = [
                     ('po', 'Purchase Order'),
                     ('cft', 'Call for Tender'),
                     ]

class sourcing_line(osv.osv):
    '''
    Class for sourcing_line
    
    sourcing lines are generated when a Sale Order is created
    (overriding of create method of sale_order)
    '''
    _SELECTION_TYPE = [
                       ('make_to_stock', 'from stock'),
                       ('make_to_order', 'on order'),
                       ]
    
    _SELECTION_SALE_ORDER_STATE = [
                                   ('draft', 'Quotation'),
                                   ('waiting_date', 'Waiting Schedule'),
                                   ('manual', 'Manual In Progress'),
                                   ('progress', 'In Progress'),
                                   ('shipping_except', 'Shipping Exception'),
                                   ('invoice_except', 'Invoice Exception'),
                                   ('done', 'Done'),
                                   ('cancel', 'Cancelled'),
                                   ]
    
    _SELECTION_SALE_ORDER_LINE_STATE = [
                                        ('draft', 'Draft'),
                                        ('confirmed', 'Confirmed'),
                                        ('done', 'Done'),
                                        ('cancel', 'Cancelled'),
                                        ('exception', 'Exception'),
                                        ]
    
    def _saveRelatedFields(self, cr, uid, ids, name, value, arg, context=None):
        '''
        function saving related data
        
        **NOTE** not used, saving done in write method
        '''
        for sourcingLine in self.browse(cr, uid, ids, context=context):
            # corresponding sale order line
            solId = sourcingLine.sale_order_line_id.id
            self.pool.get('sale.order.line').write(cr, uid, solId, {name: value}, context=context)
        
        return True
    
    def _getCorrespondingSourcingLines(self, cr, uid, ids, context=None):
        '''
        Where ids will be the ids of records in the other object’s table
        that have changed values in the watched fields. The function should
        return a list of ids of records in its own table that should have the
        field recalculated. That list will be sent as a parameter for the main
        function of the field.
        '''
        result = []
        for sol in self.pool.get('sale.order.line').browse(cr, uid, ids, context=context):
            result.extend(map(lambda x: x.id, sol.sourcing_line_ids))
            
        return result
    
    _name = 'sourcing.line'
    _description = 'Sourcing Line'
    _columns = {
        # sequence number
        'name': fields.char('Name', size=128),
        'sale_order_id': fields.many2one('sale.order', 'Sale Order', on_delete='cascade', readonly=True),
        'sale_order_line_id': fields.many2one('sale.order.line', 'Sale Order Line', on_delete='cascade', readonly=True),
        'reference': fields.related('sale_order_id', 'name', type='char', size=128, string='Reference', readonly=True),
        'state': fields.related('sale_order_line_id', 'state', type="selection", selection=_SELECTION_SALE_ORDER_LINE_STATE, readonly=True, string="State", store=False), 
        #'priority': fields.related('sale_order_id', 'priority', type="selection", selection=ORDER_PRIORITY, readonly=True, string='Priority', store=False),
        'priority': fields.selection(ORDER_PRIORITY, string='Priority', readonly=True),
        #'categ': fields.related('sale_order_id', 'categ', type="selection", selection=ORDER_CATEGORY, readonly=True, string='Category', store=False),
        'categ': fields.selection(ORDER_CATEGORY, string='Category', readonly=True),
        #'sale_order_state': fields.related('sale_order_id', 'state', string="Order State", type="selection", selection=_SELECTION_SALE_ORDER_STATE, readonly=True, store=False),
        'sale_order_state': fields.selection(_SELECTION_SALE_ORDER_STATE, string="Order State", readonly=True),
        'line_number': fields.integer(string='Line', readonly=True),
        #'product_id': fields.related('sale_order_line_id', 'product_id', relation='product.product', type='many2one', string='Product', readonly=True),
        'product_id': fields.many2one('product.product', string='Product', readonly=True),
        'qty': fields.related('sale_order_line_id', 'product_uom_qty', type='float', string='Quantity', readonly=True),
        'uom_id': fields.related('sale_order_line_id', 'product_uom', relation='product.uom', type='many2one', string='UoM', readonly=True),
        'rts': fields.date(string='RTS', readonly=True),
        'sale_order_line_state': fields.related('sale_order_line_id', 'state', type="selection", selection=_SELECTION_SALE_ORDER_LINE_STATE, readonly=True, store=False),
        'type': fields.selection(_SELECTION_TYPE, string='Procurement Method', readonly=True, states={'draft': [('readonly', False)]}),
        'po_cft': fields.selection(_SELECTION_PO_CFT, string='PO/CFT', readonly=True, states={'draft': [('readonly', False)]}),
        'real_stock': fields.related('product_id', 'qty_available', type='float', string='Real Stock', readonly=True),
        'available_stock': fields.float('Available Stock', readonly=True),
        'virtual_stock': fields.related('product_id', 'virtual_available', type='float', string='Virtual Stock', readonly=True),
        'supplier': fields.many2one('product.supplierinfo', 'Supplier', readonly=True, states={'draft': [('readonly', False)]}),
        'estimated_delivery_date': fields.date(string='Estimated DD', readonly=True),
    }
    _order = 'sale_order_id desc, line_number'
    _defaults = {
             'name': lambda self, cr, uid, context=None: self.pool.get('ir.sequence').get(cr, uid, 'sourcing.line'),
    }
    
    def write(self, cr, uid, ids, values, context=None):
        '''
        _name = 'sourcing.line'
        
        override write method to write back
         - po_cft
         - supplier
         - type
        
        to sale order line
        '''
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if 'fromOrderLine' not in context:
            context['fromSourcingLine'] = True
            for sourcingLine in self.browse(cr, uid, ids, context=context):
                solId = sourcingLine.sale_order_line_id.id
                # type
                type = 'type' in values and values['type'] or sourcingLine.type
                # pocft: if type == make_to_stock, pocft = False, otherwise modified value or saved value
                pocft = False
                if type == 'make_to_order':
                    pocft = 'po_cft' in values and values['po_cft'] or sourcingLine.po_cft
                # supplier
                supplier = 'supplier' in values and values['supplier'] or sourcingLine.supplier.id
                self.pool.get('sale.order.line').write(cr, uid, solId, {'po_cft': pocft, 'supplier': supplier, 'type': type}, context=context)
        
        return super(sourcing_line, self).write(cr, uid, ids, values, context=context)
    
    def onChangeType(self, cr, uid, id, type, context=None):
        '''
        if type == make to stock, change pocft to False
        '''
        value = {}
        if type == 'make_to_stock':
            value.update({'po_cft': False})
    
        return {'value': value}
    
    def copy(self, cr, uid, id, default=None, context=None):
        '''
        copy method from sourcing_line
        '''
        result = super(sourcing_line, self).copy(cr, uid, id, default, context)
        return result
    
    def create(self, cr, uid, vals, context=None):
        '''
        create method from sourcing_line
        '''
        result = super(sourcing_line, self).create(cr, uid, vals, context)
        return result
    
    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        copy_data method for soucring_line
        '''
        if not default:
            default = {}
            
        if not context:
            context = {}
        # updated sequence number
        default.update({'name': self.pool.get('ir.sequence').get(cr, uid, 'sourcing.line'),})
        # get sale_order_id
#        if '__copy_data_seen' in context and 'sale.order' in context['__copy_data_seen'] and len(context['__copy_data_seen']['sale.order']) == 1:
#            soId = context['__copy_data_seen']['sale.order'][0]
#            default.update({'sale_order_id': soId,})
            
        return super(sourcing_line, self).copy_data(cr, uid, id, default, context=context)
    
    def confirmLine(self, cr, uid, ids, context=None):
        '''
        set the corresponding line's state to 'confirmed'
        if all lines are 'confirmed', the sale order is confirmed
        '''
        wf_service = netsvc.LocalService("workflow")
        result = []
        for sl in self.browse(cr, uid, ids, context):
            # set the corresponding sale order line to 'confirmed'
            result.append((sl.id, sl.sale_order_line_id.write({'state':'confirmed'}, context)))
            # check if all order lines have been confirmed
            linesConfirmed = True
            for ol in sl.sale_order_id.order_line:
                if ol.state != 'confirmed':
                    linesConfirmed = False
            # if all lines have been confirmed, we confirm the sale order
            if linesConfirmed:
                wf_service.trg_validate(uid, 'sale.order', sl.sale_order_id.id, 'order_confirm', cr)
                
        return result
    
    def unconfirmLine(self, cr, uid, ids, context=None):
        '''
        set the sale order line state to 'draft'
        '''
        wf_service = netsvc.LocalService("workflow")
        result = []
        for sl in self.browse(cr, uid, ids, context):
            result.append((sl.id, sl.sale_order_line_id.write(cr, uid, sl.sale_order_line_id.id, {'state':'draft'}, context)))
                
        return result
        
sourcing_line()

class sale_order(osv.osv):
    
    _inherit = 'sale.order'
    _description = 'Sales Order'
    _columns = {'sourcing_line_ids': fields.one2many('sourcing.line', 'sale_order_id', 'Sourcing Lines'),
                }
    
    def create(self, cr, uid, vals, context=None):
        '''
        create from sale_order
        '''
        return super(sale_order, self).create(cr, uid, vals, context)
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        _inherit = 'sale.order'
        
        override to update sourcing_line :
         - priority
         - category
         - order state
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
   
        values = {}
        if 'priority' in vals:
            values.update({'priority': vals['priority']})
        if 'categ' in vals:
            values.update({'categ': vals['categ']})
        if 'state' in vals:
            values.update({'sale_order_state': vals['state']})
        
        # for each sale order
        for so in self.browse(cr, uid, ids, context):
            # for each sale order line
            for sol in so.order_line:
                # update the sourcing line
                for sl in sol.sourcing_line_ids:
                    self.pool.get('sourcing.line').write(cr, uid, sl.id, values, context)
        
        return super(sale_order, self).write(cr, uid, ids, vals, context)
        
    
    def copy(self, cr, uid, id, default=None, context=None):
        '''
        copy from sale_order
        
        dont copy sourcing lines, they are generated at sale order lines creation
        '''
        if not default:
            default={}
            
        default['sourcing_line_ids']=[]
        
        return super(sale_order, self).copy(cr, uid, id, default, context)
    
    def unlink(self, cr, uid, ids, context=None):
        '''
        _inherit = 'sale.order'
        
        
        override because of Bug #604347
        
        on_delete constraints are not generated
        
        remove manually all linked sourcing_line
        '''
        idsToDelete = []
        for order in self.browse(cr, uid, ids, context):
            for orderLine in order.order_line:
                for sourcingLine in orderLine.sourcing_line_ids:
                    idsToDelete.append(sourcingLine.id)
        
        self.pool.get('sourcing.line').unlink(cr, uid, idsToDelete, context)
        
        return super(sale_order, self).unlink(cr, uid, ids, context)
    
    def _hook_ship_create_procurement_order(self, cr, uid, ids, procurement_data, order_line, *args, **kwargs):
        # new field representing selected supplierinfo from sourcing tool
        procurement_data['supplier'] = order_line.supplier and order_line.supplier.id or False
        return super(sale_order, self)._hook_ship_create_procurement_order(cr, uid, ids, procurement_data, order_line, *args, **kwargs)

sale_order()

class sale_order_line(osv.osv):
    '''
    override of sale_order_line class
    creation/update/copy of sourcing_line 
    '''
    _inherit = 'sale.order.line'
    _description = 'Sales Order Line'
    _columns = {
                'po_cft': fields.selection(_SELECTION_PO_CFT, string="PO/CFT"),
                'supplier': fields.many2one('product.supplierinfo', 'Supplier'),
                'sourcing_line_ids': fields.one2many('sourcing.line', 'sale_order_line_id', 'Sourcing Lines'),
                }
    
    def create(self, cr, uid, vals, context=None):
        '''
        _inherit = 'sale.order.line'
        
        override create method, create corresponding sourcing.line objects
        
        vals > dict: {
        'property_ids': [(6, 0, [])], 
        'product_uos_qty': 1.0, 
        'name': '[PC1] Basic PC', 
        'product_uom': 1, 
        'order_id': 14, 
        'notes': False, 
        'product_uom_qty': 1.0, 
        'delay': 2.0, 
        'discount': 0.0, 
        'product_id': 3, 
        'th_weight': 0.0, 
        'product_uos': False, 
        'product_packaging': False, 
        'tax_id': [(6, 0, [])], 
        'type': 'make_to_stock', 
        'price_unit': 450.0, 
        'address_allotment_id': False
        }
        '''
        # if a product has been selected, get supplier default value
        sellerId = False
        deliveryDate = False
        if 'product_id' in vals and vals['product_id']:
            product = self.pool.get('product.product').browse(cr, uid, vals['product_id'], context)
            template = product.product_tmpl_id
            seller = template.seller_info_id
            sellerId = (seller and seller.id) or False
            deliveryDate = int(template.seller_delay)
        
        # type
        if not vals.get('type'):
            vals['type'] = 'make_to_stock'
        
        # fill po/cft : by default, if mto -> po, if mts -> False
        pocft = False
        if vals['type'] == 'make_to_order':
            pocft = 'po'
        
        # fill the default pocft and supplier
        vals.update({'po_cft': pocft})
        vals.update({'supplier': sellerId})
        
        # create the new sale order line
        result = super(sale_order_line, self).create(cr, uid, vals, context=context)

        # delivery date : supplier lead-time and 2 days for administrative treatment
        daysToAdd = deliveryDate and deliveryDate + 2 or 2
        estDeliveryDate = date.today()
        estDeliveryDate = estDeliveryDate + relativedelta(days=daysToAdd)
        
        # order state
        order = self.pool.get('sale.order').browse(cr, uid, vals['order_id'], context)
        orderState = order.state
        orderPriority = order.priority
        orderCategory = order.categ
        
        values = {
                  'sale_order_id': vals['order_id'],
                  'sale_order_line_id': result,
                  'supplier': sellerId,
                  'po_cft': pocft,
                  'estimated_delivery_date': estDeliveryDate.strftime('%Y-%m-%d'),
                  'rts': time.strftime('%Y-%m-%d'),
                  'type': vals['type'],
                  'line_number': vals['line_number'],
                  'product_id': vals['product_id'],
                  'priority': orderPriority,
                  'categ': orderCategory,
                  'sale_order_state': orderState,
                  }
        
        self.pool.get('sourcing.line').create(cr, uid, values, context=context)
            
        return result
    
    def copy(self, cr, uid, id, default=None, context=None):
        '''
        copy from sale order line
        '''
        if not context:
            context = {}
        
        result = super(sale_order_line, self).copy(cr, uid, id, default, context)
        return result
    
    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        copy_data from sale order line
        
        dont copy sourcing lines, they are generated at sale order lines creation
        '''
        if not default:
            default = {}
        default.update({'sourcing_line_ids': []})
        
        return super(sale_order_line, self).copy_data(cr, uid, id, default, context=context)
        
    def write(self, cr, uid, ids, vals, context=None):
        '''
        _inherit = 'sale.order.line'
        
        override to update sourcing_line :
         - supplier
         - type
         - po_cft
         - product_id
        ''' 
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # update the corresponding sourcing line if not called from a sourcing line updated
        if 'fromSourcingLine' not in context:
            context['fromOrderLine'] = True
            values = {}
            if 'supplier' in vals:
                values.update({'supplier': vals['supplier']})
            if 'po_cft' in vals:
                values.update({'po_cft': vals['po_cft']})
            if 'type' in vals:
                values.update({'type': vals['type']})
                if vals['type'] == 'make_to_stock':
                    values.update({'po_cft': False})
            if 'product_id' in vals:
                values.update({'product_id': vals['product_id']})
                
            # for each sale order line
            for sol in self.browse(cr, uid, ids, context):
                # for each sourcing line
                for sourcingLine in sol.sourcing_line_ids:
                    self.pool.get('sourcing.line').write(cr, uid, sourcingLine.id, values, context)
        
        result = super(sale_order_line, self).write(cr, uid, ids, vals, context)
        return result
    
    def unlink(self, cr, uid, ids, context=None):
        '''
        _inherit = 'sale.order.line'
        
        
        override because of Bug #604347
        
        on_delete constraints are not generated
        
        remove manually all linked sourcing_line
        '''
        idsToDelete = []
        for orderLine in self.browse(cr, uid, ids, context):
            for sourcingLine in orderLine.sourcing_line_ids:
                    idsToDelete.append(sourcingLine.id)
            
        self.pool.get('sourcing.line').unlink(cr, uid, idsToDelete, context)
        
        return super(sale_order_line, self).unlink(cr, uid, ids, context)
        
    def product_id_change(self, cr, uid, ids, pricelist, product, qty=0,
        uom=False, qty_uos=0, uos=False, name='', partner_id=False,
        lang=False, update_tax=True, date_order=False, packaging=False, fiscal_position=False, flag=False):
        '''
        override to update hidden values :
         - supplier
         - type
         - po_cft
        '''
        result = super(sale_order_line, self).product_id_change(cr, uid, ids, pricelist, product, qty,
                                                                uom, qty_uos, uos, name, partner_id,
                                                                lang, update_tax, date_order, packaging, fiscal_position, flag)
        
        # add supplier
        sellerId = False
        po_cft = False
        type = 'type' in result['value'] and result['value']['type']
        if product and type:
            productObj = self.pool.get('product.product').browse(cr, uid, product)
            template = productObj.product_tmpl_id
            seller = template.seller_info_id
            sellerId = (seller and seller.id) or False
            
            if type == 'make_to_order':
                po_cft = 'po'
                
            result['value'].update({'supplier': sellerId, 'po_cft': po_cft})
        
        return result
            
sale_order_line()

class procurement_order(osv.osv):
    """
    Procurement Orders
    
    modififed workflow to take into account
    the supplier specified during sourcing step
    """
    _inherit = "procurement.order"
    _description = "Procurement"
    _columns = {
        'supplier': fields.many2one('product.supplierinfo', 'Supplier'),
    }
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        override for workflow modification
        '''
        return super(procurement_order, self).write(cr, uid, ids, vals, context)

    # @@@override procurement.py > procurement.order > check_buy
    def check_buy(self, cr, uid, ids):
        """ Checks product type.
        @return: True or Product Id.
        """
        user = self.pool.get('res.users').browse(cr, uid, uid)
        partner_obj = self.pool.get('res.partner')
        for procurement in self.browse(cr, uid, ids):
            if procurement.product_id.product_tmpl_id.supply_method <> 'buy':
                return False
            # use new selection field instead
            # the new selection field does not exist when the procurement has been produced by
            # an order_point (minimum stock rules). in this case we take the default supplier from product
            #if not procurement.product_id.seller_ids:
            if not procurement.supplier and not procurement.product_id.seller_ids:
                cr.execute('update procurement_order set message=%s where id=%s',
                        (_('No supplier defined for this product !'), procurement.id))
                return False
            # use new selection field instead, **FIRST** the new one, and if not exist, from product
            # the new selection field does not exist when the procurement has been produced by
            # an order_point (minimum stock rules). in this case we take the default supplier from product
            #partner = procurement.product_id.seller_id #Taken Main Supplier of Product of Procurement.
            partner = procurement.supplier.name or procurement.product_id.seller_id

            if user.company_id and user.company_id.partner_id:
                if partner.id == user.company_id.partner_id.id:
                    return False
            address_id = partner_obj.address_get(cr, uid, [partner.id], ['delivery'])['delivery']
            if not address_id:
                cr.execute('update procurement_order set message=%s where id=%s',
                        (_('No address defined for the supplier'), procurement.id))
                return False
        return True
    # @@@override end

    # @@@override purchase>purchase.py>procurement_order
    def make_po(self, cr, uid, ids, context=None):
        """ Make purchase order from procurement
        @return: New created Purchase Orders procurement wise
        """
        res = {}
        if context is None:
            context = {}
        company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
        partner_obj = self.pool.get('res.partner')
        uom_obj = self.pool.get('product.uom')
        pricelist_obj = self.pool.get('product.pricelist')
        prod_obj = self.pool.get('product.product')
        acc_pos_obj = self.pool.get('account.fiscal.position')
        po_obj = self.pool.get('purchase.order')
        for procurement in self.browse(cr, uid, ids, context=context):
            res_id = procurement.move_id.id
            # use new selection field instead, **FIRST** the new one, and if not exist, from product
            # the new selection field does not exist when the procurement has been produced by
            # an order_point (minimum stock rules). in this case we take the default supplier from product
            if procurement.supplier:
                partner = procurement.supplier.name
                seller_qty = procurement.supplier.qty
                seller_delay = int(procurement.supplier.delay)
                
            else:
                partner = procurement.product_id.seller_id # Taken Main Supplier of Product of Procurement.
                seller_qty = procurement.product_id.seller_qty
                seller_delay = int(procurement.product_id.seller_delay)
            
            partner_id = partner.id
            address_id = partner_obj.address_get(cr, uid, [partner_id], ['delivery'])['delivery']
            pricelist_id = partner.property_product_pricelist_purchase.id

            uom_id = procurement.product_id.uom_po_id.id

            qty = uom_obj._compute_qty(cr, uid, procurement.product_uom.id, procurement.product_qty, uom_id)
            if seller_qty:
                qty = max(qty,seller_qty)

            price = pricelist_obj.price_get(cr, uid, [pricelist_id], procurement.product_id.id, qty, partner_id, {'uom': uom_id})[pricelist_id]

            newdate = datetime.strptime(procurement.date_planned, '%Y-%m-%d %H:%M:%S')
            newdate = (newdate - relativedelta(days=company.po_lead)) - relativedelta(days=seller_delay)

            #Passing partner_id to context for purchase order line integrity of Line name
            context.update({'lang': partner.lang, 'partner_id': partner_id})

            product = prod_obj.browse(cr, uid, procurement.product_id.id, context=context)

            line = {
                'name': product.partner_ref,
                'product_qty': qty,
                'product_id': procurement.product_id.id,
                'product_uom': uom_id,
                'price_unit': price,
                'date_planned': newdate.strftime('%Y-%m-%d %H:%M:%S'),
                'move_dest_id': res_id,
                'notes': product.description_purchase,
            }

            taxes_ids = procurement.product_id.product_tmpl_id.supplier_taxes_id
            taxes = acc_pos_obj.map_tax(cr, uid, partner.property_account_position, taxes_ids)
            line.update({
                'taxes_id': [(6,0,taxes)]
            })
            purchase_id = po_obj.create(cr, uid, {
                'origin': procurement.origin,
                'partner_id': partner_id,
                'partner_address_id': address_id,
                'location_id': procurement.location_id.id,
                'pricelist_id': pricelist_id,
                'order_line': [(0,0,line)],
                'company_id': procurement.company_id.id,
                'fiscal_position': partner.property_account_position and partner.property_account_position.id or False
            })
            res[procurement.id] = purchase_id
            self.write(cr, uid, [procurement.id], {'state': 'running', 'purchase_id': purchase_id})
        return res
    # @@@override end

procurement_order()

class purchase_order(osv.osv):
    '''
    override for workflow modification
    '''
    _inherit = "purchase.order"
    _description = "Purchase Order"
    
    def create(self, cr, uid, vals, context=None):
        '''
        override for debugging purpose
        '''
        return super(purchase_order, self).create(cr, uid, vals, context)
        
purchase_order()

class product_template(osv.osv):
    '''
    override to add new seller_info_id : default seller but supplierinfo object
    '''
    def _calc_seller(self, cr, uid, ids, fields, arg, context=None):
        result = super(product_template, self)._calc_seller(cr, uid, ids, fields, arg, context)
        
        for product in self.browse(cr, uid, ids, context=context):
            if product.seller_ids:
                partner_list = sorted([(partner_id.sequence, partner_id) for partner_id in  product.seller_ids if partner_id and partner_id.sequence])
                main_supplier = partner_list and partner_list[0] and partner_list[0][1] or False
                result[product.id]['seller_info_id'] = main_supplier and main_supplier.id or False
        return result
    
    _inherit = "product.template"
    _description = "Product Template"
    _columns = {
                'seller_info_id': fields.function(_calc_seller, method=True, type='many2one', relation='product.supplierinfo', string='Main Supplier Info', help="Main Supplier who has highest priority in Supplier List - Info object.", multi="seller_id"),
                }
    
product_template()

class product_supplierinfo(osv.osv):
    '''
    override name_get to display name of the related supplier
    
    override create to be able to create a new supplierinfo from sourcing view
    '''
    _inherit = "product.supplierinfo"
    _description = "Information about a product supplier"

    def name_get(self, cr, uid, ids, context=None):
        '''
        product_supplierinfo
        display the name of the product instead of the id of supplierinfo
        '''
        if not ids:
            return []
        
        result = []
        for supinfo in self.browse(cr, uid, ids, context=context):
            supplier = supinfo.name
            result.append((supinfo.id, supplier.name_get(context=context)[0][1]))
        
        return result
    
    def create(self, cr, uid, values, context=None):
        '''
        product_supplierinfo
        inject product_id in newly created supplierinfo
        '''
        if not values:
            values = {}
        if context and 'sourcing-product_id' in context:
            values.update({'product_id': context['sourcing-product_id']})
        
        return super(product_supplierinfo, self).create(cr, uid, values, context)
        
product_supplierinfo()
