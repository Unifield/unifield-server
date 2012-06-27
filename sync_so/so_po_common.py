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

class so_po_common(osv.osv_memory):
    _name = "so.po.common"
    _description = "Common methods for SO - PO"
    
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

    def get_record_id(self, cr, uid, context, entry):
        if not entry:
            return False
        ir_data = self.pool.get('ir.model.data').get_ir_record(cr, uid, entry.id, context=context)
        if ir_data:
            return ir_data.res_id
        return False

    def get_lines(self, cr, uid, line_values, context=None):
        line_result = []
        for line in line_values.order_line:
                
            values = {'name' : line.product_id and line.product_id.name or False,
                      'product_uom' : self.get_uom_id(cr, uid, line.product_uom, context=context), # PLEASE Use the get_record_id!!!!!
                      #'analytic_distribution_id' : self.ppol.dsdasas.copy(analytic_distrib.id),
                      'comment' : line.comment,
                      'have_analytic_distribution_from_header' : line.have_analytic_distribution_from_header,
                      'line_number' : line.line_number,
                      'notes' : line.notes,
                                       
                      'price_unit' : line.price_unit}

            line_dict = line.to_dict()
            if 'product_uom_qty' in line_dict:
                values['product_uom_qty'] = line.product_uom_qty,

            if 'product_qty' in line_dict:
                values['product_qty'] = line.product_qty,
            
            if 'date_planned' in line_dict:
                values['date_planned'] = line.date_planned 
            
            if 'confirmed_delivery_date' in line_dict:
                values['confirmed_delivery_date'] = line.confirmed_delivery_date 

            rec_id = self.get_record_id(cr, uid, context, line.product_id)
            if rec_id:
                values['product_id'] = rec_id 

            rec_id = self.get_record_id(cr, uid, context, line.nomen_manda_0)
            if rec_id:
                values['nomen_manda_0'] = rec_id 
                
            rec_id = self.get_record_id(cr, uid, context, line.nomen_manda_1)
            if rec_id:
                values['nomen_manda_1'] = rec_id 

            rec_id = self.get_record_id(cr, uid, context, line.nomen_manda_2)
            if rec_id:
                values['nomen_manda_2'] = rec_id 

            rec_id = self.get_record_id(cr, uid, context, line.nomen_manda_3)
            if rec_id:
                values['nomen_manda_3'] = rec_id
                
            rec_id = self.get_record_id(cr, uid, context, line.analytic_distribution_id)
            if rec_id:
                values['analytic_distribution_id'] = rec_id 
                
            line_result.append((0, 0, values))

        return line_result 
    
    def get_uom_id(self, cr, uid, uom_name, context=None):
        ids = self.pool.get('product.uom').search(cr, uid, [('name', '=', uom_name)], context=context)
        if ids:
            return ids[0]
        return self.pool.get('product.uom').create(cr, uid, {'name' : uom_name}, context=context)

    def get_location(self, cr, uid, partner_id, context=None):
        return self.pool.get('res.partner').browse(cr, uid, partner_id, context=context).property_stock_customer.id

so_po_common()

