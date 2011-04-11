# -*- coding: utf-8 -*-
##############################################################################
#
#    MSF 2011
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

import time
import datetime
from dateutil.relativedelta import relativedelta

from osv import osv, fields
import netsvc
import pooler
from tools.translate import _
import decimal_precision as dp
from osv.orm import browse_record, browse_null



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
    
    
    def _getRelatedFields(self, cr, uid, ids, name, arg, context=None):
        '''
        function returning related data
        '''
        result = {}
        
        for sourcingLine in self.browse(cr, uid, ids, context=context):
            
            id = sourcingLine.id
            so = sourcingLine.sale_order_id
            sol = sourcingLine.sale_order_line_id
            
            result[id] = {'sale_order_state': so.state,
                          'sale_order_line_state': sol.state,
                          'type': sol.type,
                          }
            
        return result
    
    
    
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
        # sale order id
        'sale_order_id': fields.many2one('sale.order', 'Sale Order', on_delete='cascade', readonly=True),
        # sale order line id
        'sale_order_line_id': fields.many2one('sale.order.line', 'Sale Order Line', on_delete='cascade', readonly=True),
        # reference
        'reference': fields.related('sale_order_id', 'name', type='char', size=128, string='Reference', readonly=True),
        # state
        'state': fields.selection([('created', 'Created')], string='State', readonly=True),
        # priority -> will be changed to related wm order type
        'priority': fields.char(string='Priority', size=128, readonly=True),
        # category -> will be changed to related wm order type
        'category': fields.char(string='Category', size=128, readonly=True),
        # sale order state
        'sale_order_state': fields.function(_getRelatedFields, string="Order State", multi="states", method=True, type="selection", selection=_SELECTION_SALE_ORDER_STATE),
        # line number -> will be changed to related
        'sale_order_line_number': fields.char(string='Line', size=128, readonly=True),
        # product (name & reference) from sale order line
        'product_id': fields.related('sale_order_line_id', 'product_id', relation='product.product', type='many2one', string='Product', readonly=True),
        # qty
        'qty': fields.related('sale_order_line_id', 'product_uom_qty', type='float', string='Quantity', readonly=True),
        # uom
        'uom_id': fields.related('sale_order_line_id', 'product_uom', relation='product.uom', type='many2one', string='UoM', readonly=True),
        # rts
        'rts': fields.date(string='RTS', readonly=True),
        # order line state
        'sale_order_line_state': fields.function(_getRelatedFields, string="Line State", multi="states", method=True, type="selection", selection=_SELECTION_SALE_ORDER_LINE_STATE),
        # procurement method
        # if type changes in sale.order.line, we gather the corresponding sourcing.line ids to be updated which is passed to _getRelatedFields
#        'type': fields.function(_getRelatedFields,
#                                string="Procurement Method", multi="states",
#                                method=True, type="selection", selection=_SELECTION_TYPE,
#                                store = {
#                                    'sale.order.line': (_getCorrespondingSourcingLines, ['type'], 20)
#                                }, readonly=False),
        'type': fields.selection(_SELECTION_TYPE, string='Procurement Method'),
        # po/cft
        'po_cft': fields.selection(_SELECTION_PO_CFT, string='PO/CFT'),
        # real stock
        'real_stock': fields.related('product_id', 'qty_available', type='float', string='Real Stock', readonly=True),
        # available stock -> will be changed to function
        'available_stock': fields.float('Available Stock', readonly=True),
        # virtual stock
        'virtual_stock': fields.related('product_id', 'virtual_available', type='float', string='Virtual Stock', readonly=True),
        # supplier - many2one with default value from supplier from product
        'supplier': fields.many2one('res.partner', 'Supplier'),
        # estimated delivery date
        'estimated_delivery_date': fields.date(string='Estimated DD', readonly=True),
    }
    _order = 'sale_order_id desc'
    
    
    def write(self, cr, uid, ids, values, context=None):
        '''
        _name = 'sourcing.line'
        
        
        override write method to write back
         - po_cft
         - supplier
         - type
        
        to sale order line
        '''
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

    
    _defaults = {
                 'state': 'created',
    }
    
sourcing_line()



class sale_order(osv.osv):
    
    _inherit = 'sale.order'
    _description = 'Sales Order'
    _columns = {}
    
    
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


sale_order()


class sale_order_line(osv.osv):


    _inherit = 'sale.order.line'
    _description = 'Sales Order Line'
    _columns = {
                'po_cft': fields.selection(_SELECTION_PO_CFT, string="PO/CFT"),
                'supplier': fields.many2one('res.partner', 'Supplier'),
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
            seller = template.seller_id
            sellerId = (seller and seller.id) or False
            deliveryDate = int(template.seller_delay)
        
        # type
        type = vals['type']
        
        # fill po/cft : by default, if mto -> po, if mts -> False
        pocft = False
        if type == 'make_to_order':
            pocft = 'po'
        
        # fill the default pocft and supplier
        vals.update({'po_cft': pocft})
        vals.update({'supplier': sellerId})
        # create the new sale order line
        result = super(sale_order_line, self).create(cr, uid, vals, context=context)

        # delivery date : supplier lead-time and 2 days for administrative treatment
        daysToAdd = deliveryDate and deliveryDate + 2 or 2
        estDeliveryDate = datetime.date.today()
        estDeliveryDate = estDeliveryDate + relativedelta(days=daysToAdd)
        
        values = {
                  'name': self.pool.get('ir.sequence').get(cr, uid, 'sourcing.line'),
                  'sale_order_id': vals['order_id'],
                  'sale_order_line_id': result,
                  'supplier': sellerId,
                  'po_cft': pocft,
                  'estimated_delivery_date': estDeliveryDate.strftime('%Y-%m-%d'),
                  'rts': time.strftime('%Y-%m-%d'),
                  'type': vals['type']
                  }
        self.pool.get('sourcing.line').create(cr, uid, values, context=context)
        
        
        return result
        
        
        
        
    def write(self, cr, uid, ids, vals, context=None):
        '''
        _inherit = 'sale.order.line'
        
        
        override to update sourcing_linne :
         - supplier
         - type
         - po_cft
         
        ''' 
        # update the corresponding sourcing line if not called from sourcing line updated
        if 'fromSourcingLine' not in context:
            context['fromOrderLine'] = True
            values = {}
            if 'supplier' in vals:
                values.update({'supplier': vals['supplier']})
            if 'po_cft' in vals:
                values.update({'po_cft': vals['po_cft']})
            if 'type' in vals:
                values.update({'type': vals['type']})
                
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
        if product:
            productObj = self.pool.get('product.product').browse(cr, uid, product)
            template = productObj.product_tmpl_id
            seller = template.seller_id
            sellerId = (seller and seller.id) or False
            type = result['value']['type']
            if type == 'make_to_order':
                po_cft = 'po'
        
        result['value'].update({'supplier': sellerId, 'po_cft': po_cft})
        
        return result
            

sale_order_line()

