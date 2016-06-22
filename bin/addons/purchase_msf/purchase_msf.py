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

class purchase_order_line(osv.osv):
    '''
    information from product are repacked
    '''
    _inherit = 'purchase.order.line'

    def _get_manufacturers(self, cr, uid, ids, field_name, arg, context=None):
        '''
        get manufacturers info
        '''
        result = {}
        for record in self.browse(cr, uid, ids, context=context):
            result[record.id] = {
                                 'manufacturer_id': False,
                                 'second_manufacturer_id': False,
                                 'third_manufacturer_id': False,
                                }
            po_supplier = record.order_id.partner_id
            if record.product_id:
                for seller_id in record.product_id.seller_ids:
                    if seller_id.name == po_supplier:
                        result[record.id] = {
                                             'manufacturer_id': seller_id.manufacturer_id.id,
                                             'second_manufacturer_id': seller_id.second_manufacturer_id.id,
                                             'third_manufacturer_id': seller_id.third_manufacturer_id.id,
                                             }
                        break

        return result
    
    def _getProductInfo(self, cr, uid, ids, field_name, arg, context=None):
        '''
        compute function fields related to product identity
        '''
        prod_obj = self.pool.get('product.product')
        # the name of the field is used to select the data to display
        result = {}
        for i in ids:
            result[i] = {}
            for f in field_name:
                result[i].update({f:False,})
                
        for obj in self.browse(cr, uid, ids, context=context):
            # default values
            internal_code = False
            internal_name = False
            supplier_code = False
            supplier_name = False
            if obj.product_id:
                prod = obj.product_id
                # new fields
                internal_code = prod.default_code
                internal_name = prod.name
                # filter the seller list - only select the seller which corresponds
                # to the supplier selected during PO creation
                # if no supplier selected in product, there is no specific supplier info
                if prod.seller_ids:
                    partner_id = obj.order_id.partner_id.id
                    sellers = filter(lambda x: x.name.id == partner_id, prod.seller_ids)
                    if sellers:
                        seller = sellers[0]
                        supplier_code = seller.product_code
                        supplier_name = seller.product_name
            # update dic
            result[obj.id].update(internal_code=internal_code,
                                  internal_name=internal_name,
                                  supplier_code=supplier_code,
                                  supplier_name=supplier_name,
                                  )
        
        return result

    _columns = {'internal_code': fields.function(_getProductInfo, method=True, type='char', size=1024, string='Internal code', multi='get_vals',),
                'internal_name': fields.function(_getProductInfo, method=True, type='char', size=1024, string='Internal name', multi='get_vals',),
                'supplier_code': fields.function(_getProductInfo, method=True, type='char', size=1024, string='Supplier code', multi='get_vals',),
                'supplier_name': fields.function(_getProductInfo, method=True, type='char', size=1024, string='Supplier name', multi='get_vals',),
                # new colums to display product manufacturers linked to the purchase order supplier
                'manufacturer_id': fields.function(_get_manufacturers, method=True, type='many2one', relation="res.partner", string="Manufacturer", store=False, multi="all"),
                'second_manufacturer_id': fields.function(_get_manufacturers, method=True, type='many2one', relation="res.partner", string="Second Manufacturer", store=False, multi="all"),
                'third_manufacturer_id': fields.function(_get_manufacturers, method=True, type='many2one', relation="res.partner", string="Third Manufacturer", store=False, multi="all"),
                }

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
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
