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
import netsvc
pp = pprint.PrettyPrinter(indent=4)

class purchase_order_sync(osv.osv):
    
    _inherit = "purchase.order"
    
    _columns = {
        'sended_by_supplier': fields.boolean('Sended by supplier', readonly=True),
    }
    
    def get_partner_id(self, cr, uid, partner_name, context=None):
        print "get Partner"
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
            line_result.append((0, 0, {'name' : line.name , 
                                       'product_id' : self.get_product_id(cr, uid, line.product_id), 
                                       'product_uom' : self.get_uom_id(cr, uid, line.product_uom, context=context), 
                                       'product_qty' : line.product_uom_qty, 
                                      'price_unit' : line.price_unit,
                                      'date_planned' : '2011-12-09'})) #TODO change for real case
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
        
    def get_location(self, cr, uid, partner_id, context=None):
        return self.pool.get('res.partner').browse(cr, uid, partner_id, context=context).property_stock_customer.id

    def create_po(self, cr, uid, source, so_info, context=None):
        if not context:
            context = {}
        print "call purchase order", source
        partner_id = self.get_partner_id(cr, uid, source, context)
        address_id = self.get_partner_address_id(cr, uid, partner_id, context)
        lines = self.get_lines(cr, uid, so_info, context)
        default = self.default_get(cr, uid, ['name'], context=context)
        data = {                        'partner_ref' : source + "." + so_info.name,
                                        'partner_id' : partner_id,
                                        'partner_address_id' :  address_id,
                                        'pricelist_id' : self.get_price_list_id(cr, uid, partner_id, context),
                                        'location_id' : self.get_location(cr, uid, partner_id, context),
                                        'order_line' : lines}
        default.update(data)
        res_id = self.create(cr, uid, default , context=context)
        return res_id
        
        
    def confirm_po(self, cr, uid, source, so_info, context=None):
        if not context:
            context = {}
        name = so_info.client_order_ref.split('.')[1]
        ids = self.search(cr, uid, [('name', '=', name)])
        wf_service = netsvc.LocalService("workflow")
        return wf_service.trg_validate(uid, 'purchase.order', ids[0], 'purchase_confirm', cr)
    
    
    def picking_send(self, cr, uid, source, picking_info, context=None):
        if not context:
            context = {}
        name = picking_info.sale_id.client_order_ref.split('.')[1]
        ids = self.search(cr, uid, [('name', '=', name)])
        self.write(cr, uid, ids, {'sended_by_supplier' : True}, context=context)
        return True
purchase_order_sync()