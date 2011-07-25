# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF
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

from datetime import datetime
from dateutil.relativedelta import relativedelta
from osv import osv, fields
from osv.orm import browse_record, browse_null
from tools.translate import _
import decimal_precision as dp
import netsvc
import pooler
import time


#
# Model definition
#

class purchase_order_line(osv.osv):

    _inherit = 'purchase.order.line'
    #_name = 'purchase.order.line'
    _description = 'Purchase Order Line modified for MSF'
    
    def _get_manufacturers(self, cr, uid, ids, field_name, arg, context=None):
        result = {}
        for record in self.browse(cr, uid, ids, context=context):
            result[record.id] = {
                                 'manufacturer_id': False,
                                 'second_manufacturer_id': False,
                                 'third_manufacturer_id': False,
                                }
            po_supplier = record.order_id.partner_id
            for seller_id in record.product_id.seller_ids:
                if seller_id.name == po_supplier:
                    result[record.id] = {
                                         'manufacturer_id': seller_id.manufacturer_id.id,
                                         'second_manufacturer_id': seller_id.second_manufacturer_id.id,
                                         'third_manufacturer_id': seller_id.third_manufacturer_id.id,
                                        }
                    break

        return result
    
    def _getProductInfo(self, cr, uid, ids, field_name, arg, context):
        
        # ACCESS to product_id ??
        
        # the name of the field is used to select the data to display
        result = {}
        for i in ids:
            result[i] = i
            
        return result

    _columns = {
        #function test column
        #'temp': fields.function(_getProductInfo,
        #                        type='char',
        #                        obj=None,
        #                        method=True,
        #                        string='Test function'),
        #new column internal_code
        'internal_code': fields.char('Internal code', size=256),
        #new column internal_name
        'internal_name': fields.char('Internal name', size=256),
        #new column supplier_code
        'supplier_code': fields.char('Supplier code', size=256),
        #new column supplier_name
        'supplier_name': fields.char('Supplier name', size=256),
        # new colums to display product manufacturers linked to the purchase order supplier
        'manufacturer_id': fields.function(_get_manufacturers, method=True, type='many2one', relation="res.partner", string="Manufacturer", store=False, multi="all"),
        'second_manufacturer_id': fields.function(_get_manufacturers, method=True, type='many2one', relation="res.partner", string="Second Manufacturer", store=False, multi="all"),
        'third_manufacturer_id': fields.function(_get_manufacturers, method=True, type='many2one', relation="res.partner", string="Third Manufacturer", store=False, multi="all"),
    }
    
    _defaults = {
    }
    
    
    def product_id_change(self, cr, uid, ids, pricelist, product, qty, uom,
            partner_id, date_order=False, fiscal_position=False, date_planned=False,
            name=False, price_unit=False, notes=False):
        
        # 1. call the original method
        result = super(purchase_order_line, self).product_id_change(
                                                                      cr, uid, ids, pricelist, product, qty, uom,
                                                                      partner_id, date_order=False, fiscal_position=False,
                                                                      date_planned=False, name=False, price_unit=False,
                                                                      notes=False)
        
        # when we erase the field, it is empty, so no product information but modified
        if not product:
            # reset values
            result['value'].update({'name': False,
                          'internal_code': False,
                          'internal_name': False,
                          'supplier_code': False,
                          'supplier_name': False})
            return result
        
        # 2. complete the new fields
        # - internal code
        # - internal name
        # - supplier code
        # - supplier name
        
        #@@@override@purchase>purchase.py>purchase_order_line.product_id_change : copied from original method, is everything needed ?
        if partner_id:
            lang=self.pool.get('res.partner').read(cr, uid, partner_id, ['lang'])['lang']
        context={'lang':lang}
        context['partner_id'] = partner_id
        
        prod = self.pool.get('product.product').browse(cr, uid, product, context=context)
        #@@@end
        
        # new fields
        internal_code = prod.default_code
        internal_name = prod.name
        supplier_code = False
        supplier_name = False
        
        # filter the seller list - only select the seller which corresponds
        # to the supplier selected during PO creation
        # if no supplier selected in product, there is no specific supplier info
        if prod.seller_ids:
            sellers = filter(lambda x: x.name.id == partner_id, prod.seller_ids)
            if sellers:
                seller = sellers[0]
                supplier_code = seller.product_code
                supplier_name = seller.product_name
            
        # 3 .modify the description ('name' attribute)
        result['value'].update({'name': internal_name,
                      'internal_code': internal_code,
                      'internal_name': internal_name,
                      'supplier_code': supplier_code,
                      'supplier_name': supplier_name})
        
        # return the dictionary to update the view
        return result
        

purchase_order_line()


class product_product(osv.osv):

    _inherit = 'product.product'
    _description = 'Product'
    
    def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        if not len(ids):
            return []
        def _name_get(d):
            name = d.get('name','')
            code = d.get('default_code',False)
            if code:
                name = '[%s] %s' % (code,name)
            if d.get('variants'):
                name = name + ' - %s' % (d['variants'],)
            return (d['id'], name)

        partner_id = context.get('partner_id', False)

        result = []
        for product in self.browse(cr, user, ids, context=context):
            mydict = {
                      'id': product.id,
                      'name': product.name,
                      'default_code': product.default_code,
                      'variants': product.variants
                      }
            result.append(_name_get(mydict))
        return result
    
product_product()
    
    
    
