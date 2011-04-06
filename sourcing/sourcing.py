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

class sourcing_line(osv.osv):
    '''
    Class for sourcing_line
    
    sourcing lines are generated when a Sale Order is created
    (overriding of create method of sale_order)
    '''
    _name = 'sourcing.line'
    _description = 'Sourcing Line'
    
    _SELECTION_PROCUREMENT_METHOD = [
                                     ('make_to_stock', 'Make to Stock'),
                                     ('make_to_order', 'Make to Order'),
                                     ]
    
    _SELECTION_PO_CFT = [
                                     ('po', 'Purchase Order'),
                                     ('cft', 'Call for Tender'),
                                     ]
    
    
    _columns = {
        # sequence number
        'name': fields.char('Name', size=128),
        # sale order id
        'sale_order_id': fields.many2one('sale.order', 'Sale Order'),
        # sale order line id
        'sale_order_line_id': fields.many2one('sale.order.line', 'Sale Order Line', on_delete='cascade'),
        # reference
        'reference': fields.related('sale_order_id', 'name', type='char', size=128, string='Reference'),
        # state
        'state': fields.selection([('created', 'Created')], string='State'),
        # priority -> will be changed to related wm order type
        'priority': fields.char(string='Priority', size=128),
        # category -> will be changed to related wm order type
        'category': fields.char(string='Category', size=128),
        # sale order state
        'sale_order_state': fields.related('sale_order_id', 'state', type='char', size=128, string='Order State'),
        # line number -> will be changed to related
        'sale_order_line_number': fields.char(string='Line', size=128),
        # product (name & reference) from sale order line
        'product_id': fields.related('sale_order_line_id', 'product_id', relation='product.product', type='many2one', string='Product'),
        # qty
        'qty': fields.related('sale_order_line_id', 'product_uom_qty', type='float', string='Quantity'),
        # uom
        'uom_id': fields.related('sale_order_line_id', 'product_uom', relation='product.uom', type='many2one', string='UoM'),
        # rts
        'rts': fields.date(string='RTS'),
        # order line state
        'sale_order_line_state': fields.related('sale_order_line_id', 'state', type='char', size=128, string='Line State'),
        # procurement method
        'procurement_method': fields.selection(_SELECTION_PROCUREMENT_METHOD, string='Procurement Method'),
        # po/cft
        'po_cft': fields.selection(_SELECTION_PO_CFT, string='PO/CFT'),
        # real stock
        'real_stock': fields.related('product_id', 'qty_available', type='float', string='Real Stock'),
        # available stock -> will be changed to function
        'available_stock': fields.float('Available Stock'),
        # virtual stock
        'virtual_stock': fields.related('product_id', 'virtual_available', type='float', string='Virtual Stock'),
        # supplier - many2one with default value from supplier from product
        'supplier': fields.many2one('res.partner', 'Supplier'),
        # estimated delivery date
        'estimated_delivery_date': fields.date(string='Estimated DD'),
    }
    
    
    #_order = 'reference desc'
    
    
    def _getSequenceName(self, cr, uid, c):
        '''
        
        '''
        return self.pool.get('ir.sequence').get(cr, uid, 'sourcing.line')
        
        
    def _getRTS(self, cr, uid, c):
        '''
        
        '''
        return time.strftime('%Y-%m-%d')
        
        
    def _getEstimatedDeliveryDate(self, cr, uid, c):
        '''
        
        '''
        return time.strftime('%Y-%m-%d')
    
    
    def _getSupplier(self, cr, uid, c):
        '''
        "product_tmpl_id" > "seller_id"
        
        next_date = (datetime.strptime(date_ref, "%Y-%m-%d") + relativedelta(days=line.days))
        '''
        #supplierId = self.pool.get('').
        return 1
    
    def _getProcurementMethod(self, cr, uid, c):
        '''
        
        '''
        return 'mts'

        
    
    _defaults = {
                 'rts': _getRTS,
                 'estimated_delivery_date': _getEstimatedDeliveryDate,
                 'procurement_method': _getProcurementMethod,
                 'state': 'created',
    }
    
    def createProcurementOrder(self):
        '''
        
        '''
        
        
        
        
        
    
sourcing_line()



class sale_order_line(osv.osv):


    _inherit = 'sale.order.line'
    _description = 'Sales Order Line'
    
    
    def create(self, cr, uid, vals, context=None):
        '''
        override create method, create corresponding sourcing.line objects
        
        # create a sourcing.line object
                "product_tmpl_id" > "seller_id"
        '''
        
        result = super(sale_order_line, self).create(cr, uid, vals, context=context)
        
        
        # if a product has been selected, get supplier default value
        seller_id = False
        deliveryDate = False
        if 'product_id' in vals and vals['product_id']:
            product = self.pool.get('product.product').browse(cr, uid, vals['product_id'], context)
            template = product.product_tmpl_id
            seller = template.seller_id
            seller_id = (seller and seller.id) or False
            deliveryDate = int(template.seller_delay)

#        vals > dict: {
#        'property_ids': [(6, 0, [])], 
#        'product_uos_qty': 1.0, 
#        'name': '[PC1] Basic PC', 
#        'product_uom': 1, 
#        'order_id': 14, 
#        'notes': False, 
#        'product_uom_qty': 1.0, 
#        'delay': 2.0, 
#        'discount': 0.0, 
#        'product_id': 3, 
#        'th_weight': 0.0, 
#        'product_uos': False, 
#        'product_packaging': False, 
#        'tax_id': [(6, 0, [])], 
#        'type': 'make_to_stock', 
#        'price_unit': 450.0, 
#        'address_allotment_id': False
#        }
        
        # delivery date : supplier lead-time and 2 days for administrative treatment
        daysToAdd = deliveryDate and deliveryDate + 2 or 2
        estDeliveryDate = datetime.date.today()
        estDeliveryDate = estDeliveryDate + relativedelta(days=daysToAdd)
        
        
        values = {
                  'name': self.pool.get('ir.sequence').get(cr, uid, 'sourcing.line'),
                  'sale_order_id': vals['order_id'],
                  'sale_order_line_id': result,
                  'supplier': seller_id,
                  'procurement_method': vals['type'],
                  'estimated_delivery_date': estDeliveryDate.strftime('%Y-%m-%d'),
                  }
        self.pool.get('sourcing.line').create(cr, uid, values, context=context)
        
        
        return result

    
    
sale_order_line()

