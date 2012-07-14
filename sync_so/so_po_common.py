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

    def get_original_po_id(self, cr, uid, po_ref, context):
        # Get the Id of the original PO to update these info back 
        if not po_ref:
            return False
        po_split = po_ref.split('.')
        if len(po_split) != 2:
            return False

        po_ids = self.pool.get('purchase.order').search(cr, uid, [('name', '=', po_split[1])], context=context)
        if not po_ids:
            raise Exception, "The original PO does not exist! " + po_ref
        return po_ids[0]

    def retrieve_po_header_data(self, cr, uid, source, header_result, header_info, context):
        if 'note' in header_info:
            header_result['note'] = header_info.get('note')
        if 'details' in header_info:
            header_result['details'] = header_info.get('details')
        if 'delivery_confirmed_date' in header_info:
            header_result['delivery_confirmed_date'] = header_info.get('delivery_confirmed_date')
        if 'est_transport_lead_time' in header_info:
            header_result['est_transport_lead_time'] = header_info.get('est_transport_lead_time')
        if 'transport_type' in header_info:
            header_result['transport_type'] = header_info.get('transport_type')
        if 'ready_to_ship_date' in header_info:
            header_result['ready_to_ship_date'] = header_info.get('ready_to_ship_date')
            
            
        if 'analytic_distribution_id' in header_info: 
            header_result['analytic_distribution_id'] = self.get_analytic_distribution_id(cr, uid, header_info, context)
        
        partner_id = self.get_partner_id(cr, uid, source, context)
        address_id = self.get_partner_address_id(cr, uid, partner_id, context)
        price_list = self.get_price_list_id(cr, uid, partner_id, context)
        location_id = self.get_location(cr, uid, partner_id, context)

        header_result['partner_ref'] = source + "." + header_info.get('name')
        header_result['partner_id'] = partner_id
        header_result['partner_address_id'] = address_id
        header_result['pricelist_id'] = price_list
        header_result['location_id'] = location_id
        header_result['split_po'] = True
        
        return header_result

    def get_analytic_distribution_id(self, cr, uid, data_dict, context):
        # if it has been given in the sync message, then take into account if the value is False by intention, 
        # --> be careful when modifying the statement below
        analytic_id = data_dict.get('analytic_distribution_id', False)
        if analytic_id:
            ir_data = self.pool.get('ir.model.data').get_ir_record(cr, uid, analytic_id['id'], context=context)
            if ir_data:
                return ir_data.res_id
        return False 

    def retrieve_so_header_data(self, cr, uid, source, header_result, header_info, context):
        if 'note' in header_info:
            header_result['note'] = header_info.get('note')
        if 'details' in header_info:
            header_result['details'] = header_info.get('details')
        if 'delivery_requested_date' in header_info:
            header_result['delivery_requested_date'] = header_info.get('delivery_requested_date')
        if 'priority' in header_info:
            header_result['priority'] = header_info.get('priority')
        if 'categ' in header_info:
            header_result['categ'] = header_info.get('categ')

        analytic_id = header_info.get('analytic_distribution_id', False)
        if analytic_id:
            header_result['analytic_distribution_id'] = self.get_analytic_distribution_id(cr, uid, header_info, context)
        
        partner_id = self.get_partner_id(cr, uid, source, context)
        address_id = self.get_partner_address_id(cr, uid, partner_id, context)
        price_list = self.get_price_list_id(cr, uid, partner_id, context)
        location_id = self.get_location(cr, uid, partner_id, context)

        header_result['client_order_ref'] = source + "." + header_info.get('name')
        header_result['partner_id'] = partner_id
        header_result['partner_order_id'] = address_id
        header_result['partner_shipping_id'] = address_id
        header_result['partner_invoice_id'] = address_id
        header_result['pricelist_id'] = price_list
        header_result['location_id'] = location_id
        
        return header_result
    
    def get_lines(self, cr, uid, line_values, po_id, context):
        line_result = []
        
        line_vals_dict = line_values.to_dict()
        if 'order_line' not in line_vals_dict:
            return line_result
        
        for line in line_values.order_line:
            values = {}
            line_dict = line.to_dict()

            if 'product_uom' in line_dict:
                values['product_uom'] = self.get_uom_id(cr, uid, line.product_uom, context=context)

            if 'have_analytic_distribution_from_header' in line_dict: 
                values['product_qty'] = line.have_analytic_distribution_from_header
                
            if 'line_number' in line_dict:
                values['product_qty'] = line.line_number
                
            if 'price_unit' in line_dict:
                values['price_unit'] = line.price_unit
                
            if 'notes' in line_dict:
                values['product_qty'] = line.notes

            if 'comment' in line_dict:
                values['comment'] = line.comment

            if 'product_qty' in line_dict:
                values['product_uom_qty'] = line.product_qty
            
            if 'product_uom_qty' in line_dict: # come from the SO
                values['product_qty'] = line.product_uom_qty

            if 'product_qty' in line_dict: # come from the PO
                values['product_uom_qty'] = line.product_qty
            
            if 'date_planned' in line_dict:
                values['date_planned'] = line.date_planned 

            if 'sync_pol_db_id' in line_dict:
                values['sync_pol_db_id'] = line.sync_pol_db_id 

            if 'sync_sol_db_id' in line_dict:
                values['sync_sol_db_id'] = line.sync_sol_db_id 
            
            if 'confirmed_delivery_date' in line_dict:
                values['confirmed_delivery_date'] = line.confirmed_delivery_date
                 
            if 'nomenclature_description' in line_dict:
                values['nomenclature_description'] = line.nomenclature_description 

            if 'product_id' in line_dict:
                rec_id = self.get_record_id(cr, uid, context, line.product_id)
                if rec_id:
                    values['product_id'] = rec_id
                    values['name'] = line.product_id.name
                else:
                    values['name'] = line.comment
            else:
                values['name'] = line.comment

            if 'nomen_manda_0' in line_dict:
                rec_id = self.get_record_id(cr, uid, context, line.nomen_manda_0)
                if rec_id:
                    values['nomen_manda_0'] = rec_id 
                
            if 'nomen_manda_1' in line_dict:
                rec_id = self.get_record_id(cr, uid, context, line.nomen_manda_1)
                if rec_id:
                    values['nomen_manda_1'] = rec_id 

            if 'nomen_manda_2' in line_dict:
                rec_id = self.get_record_id(cr, uid, context, line.nomen_manda_2)
                if rec_id:
                    values['nomen_manda_2'] = rec_id 

            if 'nomen_manda_3' in line_dict:
                rec_id = self.get_record_id(cr, uid, context, line.nomen_manda_3)
                if rec_id:
                    values['nomen_manda_3'] = rec_id
                
            if 'analytic_distribution_id' in line_dict:
                values['analytic_distribution_id'] = self.get_analytic_distribution_id(cr, uid, line_dict, context)
                    
            if po_id: # this case is for update the PO
                if 'sync_sol_db_id' not in line_dict:
                    raise Exception, "The field sync_sol_db_id is missing - please check at the message rule!"
                else:
                    sync_sol_db_id = line.sync_sol_db_id
                
                # look for the correct PO line for updating the value - corresponding to the SO line
                line_ids = self.pool.get('purchase.order.line').search(cr, uid, [('sync_sol_db_id', '=', sync_sol_db_id), ('order_id', '=', po_id)], context=context)
                if line_ids:
                    line_result.append((1, line_ids[0], values))
                else:     
                    line_result.append((0, 0, values))
            else:
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

