# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

from osv import osv
from osv import fields
from osv import orm
from tools.translate import _
from datetime import datetime
import tools
import time
import pprint
pp = pprint.PrettyPrinter(indent=4)

"""
    This class is just for test purpose
    A proof of concept for message passing
"""

class sale_order_sync(osv.osv):
    _inherit = "sale.order"
    
    _columns = {
                'received': fields.boolean('Received by Client', readonly=True),
    }
    
    def get_partner_id(self, cr, uid, partner_name, context=None):
        ids = self.pool.get('res.partner').search(cr, uid, [('name', '=', partner_name)], context=context)
        if ids:
            return ids[0]
        return self.pool.get('res.partner').create(cr, uid, {'name' : partner_name}, context=context)
    def get_partner_address_id(self, cr, uid, partner_id, context=None):
        partner = self.pool.get('res.partner').browse(cr, uid, partner_id, context=context)
        if partner.address:
            return partner.address[0].id
        else:
            return self.pool.get('res.partner.address').create(cr, uid, {'name' : partner.name, 'partner_id' : partner.id} ,context=context)
    def get_price_list_id(self, cr, uid, partner_id, context=None):
        part = self.pool.get('res.partner').browse(cr, uid, partner_id, context=context)
        return part.property_product_pricelist and part.property_product_pricelist.id or False
    
    def get_lines(self, cr, uid, po_info, context=None):
        line_result = []
        for line in po_info.order_line:
            line_result.append((0, 0, {'name' : line.product_id.name ,
                                       'product_id' : self.get_product_id(cr, uid, line.product_id), 
                                       'product_uom' : self.get_uom_id(cr, uid, line.product_uom, context=context), 
                                       'product_uom_qty' : line.product_qty, 
                                      'price_unit' : line.price_unit}))
        return line_result 
    
    def get_product_id(self, cr, uid, product_id):
        ids = self.pool.get('product.product').search(cr, uid, [('name', '=', product_id.name)])
        if ids:
            return ids[0]
        return self.pool.get('product.product').create(cr, uid, {'name' : product_id.name})
    
    def get_uom_id(self, cr, uid, uom_name, context=None):
        ids = self.pool.get('product.uom').search(cr, uid, [('name', '=', uom_name)], context=context)
        if ids:
            return ids[0]
        return self.pool.get('product.uom').create(cr, uid, {'name' : uom_name}, context=context)
        
    def create_so(self, cr, uid, source, po_info, context=None):
        if not context:
            context = {}
        partner_id = self.get_partner_id(cr, uid, source, context)
        address_id = self.get_partner_address_id(cr, uid, partner_id, context)
        lines = self.get_lines(cr, uid, po_info, context)
        default = self.default_get(cr, uid, ['name'], context=context)
        data = {                        'client_order_ref' : source + "." + po_info.name,
                                        'partner_id' : partner_id,
                                        'partner_order_id' : address_id,
                                        'partner_shipping_id': address_id,
                                        'partner_invoice_id' : address_id,
                                        'pricelist_id' : self.get_price_list_id(cr, uid, partner_id, context),
                                        'order_line' : lines}
        default.update(data)
        res_id = self.create(cr, uid, default , context=context)
        return True
    
    def picking_received(self, cr, uid, source, picking_info, context=None):
        if not context:
            context = {}
        name = picking_info.purchase_id.name
        ids = self.search(cr, uid, [('client_order_ref', '=', source + "." + name)])
        self.write(cr, uid, ids, {'received' : True}, context=context)
        return True
sale_order_sync()



class account_period_sync(osv.osv):
    
    _inherit = "account.period"
    
    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        print "generate xml name for period"
        period = self.browse(cr, uid, res_id)
        return period.fiscalyear_id.code + "/" + period.name + "_" + period.date_start
    
account_period_sync()