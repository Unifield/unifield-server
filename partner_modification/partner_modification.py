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

class res_partner(osv.osv):
    _description='Partner'
    _inherit = "res.partner"
    
    def _calc_dellay(self, cr, uid, ids, fields, arg, context=None):
        result = {}
        for partner in self.browse(cr, uid, ids, context=context):
            for field in fields:
                result[partner.id] = {field:0}
                
            # get the default transport, the smallest sequence
            value_list = self.read(cr, uid, [partner.id], ['air_sequence', 'sea_sequence', 'road_sequence'], context=context)
            if not value_list:
                continue
            
            value = value_list[0]
            
            air_seq = value['air_sequence']
            sea_seq = value['sea_sequence']
            road_seq = value['road_sequence']
            # the default transport lead time
            default_lt = 0
            # select the smallest lead time
            if air_seq < sea_seq:
                if air_seq < road_seq:
                    default_lt = partner.transport_by_air_lt
                else:
                    default_lt = partner.transport_by_road_lt
            elif sea_seq < road_seq:
                default_lt = partner.transport_by_sea_lt
            else:
                default_lt = partner.transport_by_road_lt
                
            result[partner.id]['default_delay'] = default_lt + partner.procurement_lt
            
        return result
    
    _columns = {
                'zone': fields.selection([('national','National'),('international','International'),], 'Zone',),
                'customer_lt': fields.integer('Customer Lead Time'),
                'procurement_lt': fields.integer('Procurement Treatment Lead Time'),
                'transport_by_air_lt': fields.integer('Transport Lead Time by Air'),
                'air_sequence': fields.integer('Air priority'),
                'transport_by_sea_lt': fields.integer('Transport Lead Time by Sea'),
                'sea_sequence': fields.integer('Sea priority'),
                'transport_by_road_lt': fields.integer('Transport Lead Time by Road'),
                'road_sequence': fields.integer('Road priority'),
                'default_delay': fields.function(_calc_dellay, method=True, type='integer', string='Supplier Lead Time', multi="seller_delay"),
                }
    
res_partner()


class purchase_order_line(osv.osv):
    '''
    this modify the onchange function for product, set the date_planned value
    '''
    _inherit = 'purchase.order.line'
    
    def product_id_change(self, cr, uid, ids, pricelist, product, qty, uom,
            partner_id, date_order=False, fiscal_position=False, date_planned=False,
            name=False, price_unit=False, notes=False):
        
        res = super(purchase_order_line, self).product_id_change(cr, uid, ids, pricelist, product, qty, uom,
                                                           partner_id, date_order, fiscal_position, date_planned,
                                                           name, price_unit, notes)
        
        if product:
            # product obj
            product_obj = self.pool.get('product.product')
            # product
            product = product_obj.browse(cr, uid, product)
            
            lt_date = (datetime.now() + relativedelta(days=int(product.seller_delay))).strftime('%Y-%m-%d')
            res.update(date_planned=lt_date)
        
        return res
    
    
purchase_order_line()


class product_supplierinfo(osv.osv):
    _name = 'product.supplierinfo'
    _inherit = 'product.supplierinfo'

    def onchange_supplier_id(self, cr, uid, ids, name):
        '''
        set the default delay value
        '''
        # supplier object
        partner_obj = self.pool.get('res.partner')
        # partner
        partner = partner_obj.browse(cr, uid, name)
        
        return {'value': {'delay': partner.default_delay}}
        
product_supplierinfo()
