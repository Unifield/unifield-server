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
            raise Exception, "PO reference format/value is invalid! (correct format: instance_name.po_name) " + po_ref

        if not context:
            context = {}
        context.update({'active_test': False})
        po_ids = self.pool.get('purchase.order').search(cr, uid, [('name', '=', po_split[1])], context=context)
        if not po_ids:
            raise Exception, "The original PO does not exist! " + po_ref
        return po_ids[0]

    # Update the next line number for the FO, PO that have been created by the synchro
    def update_next_line_number_fo_po(self, cr, uid, order_id, fo_po_obj, order_line_object, context):
        sequence_id = fo_po_obj.read(cr, uid, [order_id], ['sequence_id'], context=context)[0]['sequence_id'][0]
        
        cr.execute("select max(line_number) from " + order_line_object + " where order_id = " + str(order_id))
        for x in cr.fetchall():
            seq_tools = self.pool.get('sequence.tools')
            seq_tools.reset_next_number(cr, uid, sequence_id, int(x[0]) + 1, context=context)
        
        return True

    def get_original_so_id(self, cr, uid, so_ref, context):
        # Get the Id of the original PO to update these info back 
        if not so_ref:
            return False
        so_split = so_ref.split('.')
        if len(so_split) != 2:
            raise Exception, "The original sub-FO reference format/value is invalid! (correct format: instance_name.so_name) " + so_ref

        if not context:
            context = {}                
        context.update({'active_test': False})
        so_ids = self.pool.get('sale.order').search(cr, uid, [('name', '=', so_split[1])], context=context)
        if not so_ids:
            raise Exception, "The original sub-FO does not exist! " + so_split[1]
        return so_ids[0]

    def retrieve_po_header_data(self, cr, uid, source, header_result, header_info, context):
        if 'notes' in header_info:
            header_result['notes'] = header_info.get('notes')
            header_result['note'] = header_info.get('notes')
        elif 'note' in header_info:
            header_result['notes'] = header_info.get('note')
            header_result['note'] = header_info.get('note')
            
        if 'order_type' in header_info:
            header_result['order_type'] = header_info.get('order_type')
        if 'priority' in header_info:
            header_result['priority'] = header_info.get('priority')
        if 'categ' in header_info:
            header_result['categ'] = header_info.get('categ')
        if 'loan_duration' in header_info:
            header_result['loan_duration'] = header_info.get('loan_duration')
            
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
        if 'notes' in header_info:
            header_result['notes'] = header_info.get('notes')
            header_result['note'] = header_info.get('notes')
        elif 'note' in header_info:
            header_result['notes'] = header_info.get('note')
            header_result['note'] = header_info.get('note')

        if 'order_type' in header_info:
            header_result['order_type'] = header_info.get('order_type')
        if 'priority' in header_info:
            header_result['priority'] = header_info.get('priority')
        if 'categ' in header_info:
            header_result['categ'] = header_info.get('categ')
        if 'loan_duration' in header_info:
            header_result['loan_duration'] = header_info.get('loan_duration')
            
        if 'details' in header_info:
            header_result['details'] = header_info.get('details')
        if 'delivery_requested_date' in header_info:
            header_result['delivery_requested_date'] = header_info.get('delivery_requested_date')

        analytic_id = header_info.get('analytic_distribution_id', False)
        if analytic_id:
            header_result['analytic_distribution_id'] = self.get_analytic_distribution_id(cr, uid, header_info, context)
        
        partner_id = self.get_partner_id(cr, uid, source, context)
        address_id = self.get_partner_address_id(cr, uid, partner_id, context)
        price_list = self.get_price_list_id(cr, uid, partner_id, context)

        header_result['client_order_ref'] = source + "." + header_info.get('name')
        header_result['partner_id'] = partner_id
        header_result['partner_order_id'] = address_id
        header_result['partner_shipping_id'] = address_id
        header_result['partner_invoice_id'] = address_id
        header_result['pricelist_id'] = price_list
        
        return header_result
    
    def get_lines(self, cr, uid, line_values, po_id, so_id, for_update, context):
        line_result = []
        update_lines = []
        
        line_vals_dict = line_values.to_dict()
        if 'order_line' not in line_vals_dict:
            return []
        
        for line in line_values.order_line:
            values = {}
            line_dict = line.to_dict()

            if 'product_uom' in line_dict:
                values['product_uom'] = self.get_uom_id(cr, uid, line.product_uom, context=context)

            if 'have_analytic_distribution_from_header' in line_dict: 
                values['have_analytic_distribution_from_header'] = line.have_analytic_distribution_from_header
                
            if 'line_number' in line_dict:
                values['line_number'] = line.line_number
                
            if 'price_unit' in line_dict:
                values['price_unit'] = line.price_unit
                
            if 'notes' in line_dict:
                values['notes'] = line.notes

            if 'comment' in line_dict:
                values['comment'] = line.comment

            if 'product_uom_qty' in line_dict: # come from the SO
                values['product_qty'] = line.product_uom_qty

            if 'product_qty' in line_dict: # come from the PO
                values['product_uom_qty'] = line.product_qty
            
            if 'date_planned' in line_dict:
                values['date_planned'] = line.date_planned 

            if 'confirmed_delivery_date' in line_dict:
                values['confirmed_delivery_date'] = line.confirmed_delivery_date
                 
            if 'nomenclature_description' in line_dict:
                values['nomenclature_description'] = line.nomenclature_description 

            if 'product_id' in line_dict:
                rec_id = self.get_record_id(cr, uid, context, line.product_id)
                if rec_id:
                    values['product_id'] = rec_id
                    values['name'] = line.product_id.name
                    product_obj = self.pool.get('product.product')
                    procure_method = product_obj.browse(cr, uid, [rec_id], context=context)[0].procure_method
                    values['type'] = procure_method
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
                    
            line_ids = False
            sync_order_line_db_id = False
            if 'sync_order_line_db_id' in line_dict:
                sync_order_line_db_id = line.sync_order_line_db_id
                values['sync_order_line_db_id'] = sync_order_line_db_id 
            
            if (po_id or so_id) and not sync_order_line_db_id: # this updates the PO or SO -> the sync_order_line_db_id must exist
                raise Exception, "The field sync_order_line_db_id is missing - please check the relevant message rule!"
                
            if po_id: # this case is for update the PO
                # look for the correct PO line for updating the value - corresponding to the SO line
                line_ids = self.pool.get('purchase.order.line').search(cr, uid, [('sync_order_line_db_id', '=', sync_order_line_db_id), ('order_id', '=', po_id)], context=context)
            elif so_id:
                # look for the correct PO line for updating the value - corresponding to the SO line
                line_ids = self.pool.get('sale.order.line').search(cr, uid, [('sync_order_line_db_id', '=', sync_order_line_db_id), ('order_id', '=', so_id)], context=context)

            if line_ids and line_ids[0]:
                if for_update: # add this value to the list of update, then remove
                    update_lines.append(line_ids[0])
                    
                line_result.append((1, line_ids[0], values))
            else:     
                line_result.append((0, 0, values))
            
        # for update case, then check all updated lines, the other lines that are not presented in the sync message must be deleted at this destination instance!    
        if for_update:
            existing_line_ids = False
            if po_id: # this case is for update the PO
                # look for the correct PO line for updating the value - corresponding to the SO line
                existing_line_ids = self.pool.get('purchase.order.line').search(cr, uid, [('order_id', '=', po_id),], context=context)
            elif so_id:
                # look for the correct PO line for updating the value - corresponding to the SO line
                existing_line_ids = self.pool.get('sale.order.line').search(cr, uid, [('order_id', '=', so_id)], context=context)
                
            if existing_line_ids and update_lines:
                for existing_line in existing_line_ids:
                    if existing_line not in update_lines:
                        line_result.append((2, existing_line))
                
        return line_result 

    def get_uom_id(self, cr, uid, uom_name, context=None):
        ids = self.pool.get('product.uom').search(cr, uid, [('name', '=', uom_name)], context=context)
        if ids:
            return ids[0]
        return self.pool.get('product.uom').create(cr, uid, {'name' : uom_name}, context=context)

    def get_location(self, cr, uid, partner_id, context=None):
        '''
        For instance, the location ID for the PO created will be by default the Input Location of the default warehouse
        Proper location should be taken when creating the PO from an SO 
        
        The location is mandatory in PO, so, if there is no location, an exception will be raised to stop creating the PO
        '''
        warehouse_obj = self.pool.get('stock.warehouse')
        warehouse_ids = warehouse_obj.search(cr, uid, [], limit=1)
        if not warehouse_ids:
            raise Exception, "No valid warehouse location found for the PO! The PO cannot be created."
        return warehouse_obj.read(cr, uid, warehouse_ids, ['lot_input_id'])[0]['lot_input_id'][0]

so_po_common()

