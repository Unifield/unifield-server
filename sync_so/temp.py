from osv import osv
from osv import fields
from osv import orm
from tools.translate import _
from datetime import datetime
import tools
import time
import pprint
import netsvc
import so_po_common
pp = pprint.PrettyPrinter(indent=4)

# Method copied from purchase.py
class purchase_order_sync_TEMP(osv.osv):

    def po_update_fo_NO_USE(self, cr, uid, source, so_info, context=None):
        if not context:
            context = {}
        print "PO updates FO on the state", source

        po_ids = so_po_common.get_original_po_id(cr, uid, so_info.client_order_ref, context)
        if not po_ids:
            raise Exception, "The original PO does not exist! " + so_info.client_order_ref
        
        wf_service = netsvc.LocalService("workflow")
        return wf_service.trg_validate(uid, 'purchase.order', po_ids[0], 'purchase_confirm', cr)


    # THIS METHOD NEEDS TO BE RE-WORKED BEFORE PUT IT IN USE!
    def validated_fo_to_po(self, cr, uid, source, so_info, context=None):
        if not context:
            context = {}
        print "The FO got validated, some info will be syncing to the original PO", source
        
        so_po_common = self.pool.get('so.po.common')
        partner_id = so_po_common.get_partner_id(cr, uid, source, context)
        address_id = so_po_common.get_partner_address_id(cr, uid, partner_id, context)

        # get the PO id        
        po_ids = so_po_common.get_original_po_id(cr, uid, so_info.client_order_ref, context)
        if not po_ids:
            raise Exception, "The original PO does not exist! " + so_info.client_order_ref
        
        lines = so_po_common.get_lines(cr, uid, so_info, True, context)
        
        data = {                        #'partner_ref' : source + "." + so_info.name,
                                        'partner_id' : partner_id,
                                        'partner_address_id' :  address_id,
                                        'pricelist_id' : so_po_common.get_price_list_id(cr, uid, partner_id, context),
                                        'location_id' : so_po_common.get_location(cr, uid, partner_id, context),
                                        'note' : so_info.notes,
                                        'details' : so_info.details,
                                        'delivery_confirmed_date' : so_info.delivery_confirmed_date,
                                        'est_transport_lead_time' : so_info.est_transport_lead_time,
                                        'transport_type' : so_info.transport_type,
                                        'ready_to_ship_date' : so_info.ready_to_ship_date,
                                        'order_line' : lines}

        rec_id = so_po_common.get_record_id(cr, uid, context, so_info.analytic_distribution_id)
        if rec_id:
            data['analytic_distribution_id'] = rec_id 
        
        default = {}
        default.update(data)
        
        res_id = self.write(cr, uid, po_ids, default , context=context)
        return res_id
        
    def confirm_po(self, cr, uid, source, so_info, context=None):
        if not context:
            context = {}
        name = so_info.client_order_ref.split('.')[1]
        po_ids = self.search(cr, uid, [('name', '=', name)])
        values = {}
        values['delivery_confirmed_date'] = so_info.delivery_confirmed_date
        
        res_id = self.write(cr, uid, po_ids, values , context=context)
        if not res_id:
            raise Exception, "Delivery Confirmed Date missing! " + name
        
        wf_service = netsvc.LocalService("workflow")
        return wf_service.trg_validate(uid, 'purchase.order', po_ids[0], 'purchase_approve', cr)

    def update_split_po_BACKUP(self, cr, uid, source, so_info, context=None):
        if not context:
            context = {}
        print "Update the split PO when the sourced FO got confirmed", source
        
        name = source + '.' + so_info.name
        po_ids = self.search(cr, uid, [('partner_ref', '=', name), ('state', '!=', 'cancelled')])
        if not po_ids:
            raise Exception, "Original split PO not found " + name
        
        if not so_info.delivery_confirmed_date:
            raise Exception, "Delivery Confirmed Date missing! " + name
 
        values = {}
        values['delivery_confirmed_date'] = so_info.delivery_confirmed_date
        
        res_id = self.write(cr, uid, po_ids, values , context=context)
        if not res_id:
            raise Exception, "Delivery Confirmed Date missing! " + name
        
        wf_service = netsvc.LocalService("workflow")
        if so_info.state == 'validated':
            ret = wf_service.trg_validate(uid, 'purchase.order', po_ids[0], 'purchase_confirm', cr)
        else:
            ret = wf_service.trg_validate(uid, 'purchase.order', po_ids[0], 'purchase_confirm', cr)
            ret = wf_service.trg_validate(uid, 'purchase.order', po_ids[0], 'purchase_approve', cr)
        return ret
        
    
    def picking_send(self, cr, uid, source, picking_info, context=None):
        if not context:
            context = {}
        name = picking_info.sale_id.client_order_ref.split('.')[1]
        ids = self.search(cr, uid, [('name', '=', name)])
        self.write(cr, uid, ids, {'sended_by_supplier' : True}, context=context)
        return True

purchase_order_sync_TEMP()



class sale_order_sync_TEMP(osv.osv):

    def split_fo_creates_split_po(self, cr, uid, source, so_info, context=None):
        if not context:
            context = {}
        print "Split FO updates back the lines in the original PO", source

        so_po_common = self.pool.get('so.po.common')
        print so_po_common
        po_ids = so_po_common.get_original_po_id(cr, uid, so_info.client_order_ref, context)
        
        partner_id = so_po_common.get_partner_id(cr, uid, source, context)
        address_id = so_po_common.get_partner_address_id(cr, uid, partner_id, context)
        
        if not po_ids:
            raise Exception, "The original PO does not exist! " + so_info.client_order_ref

        # now process to the PO line, to update it when the FO line has been already confirmed
        lines = so_po_common.confirm_po_lines(cr, uid, so_info, po_ids, context)
        
        po_obj = self.pool.get('purchase.order')
        
        default = {}
        data = {                        #'partner_ref' : source + "." + so_info.name,
                                        'partner_id' : partner_id,
                                        'partner_address_id' :  address_id,
                                        'note' : so_info.notes,
                                        'details' : so_info.details,
                                        'delivery_confirmed_date' : so_info.delivery_confirmed_date,
                                        'est_transport_lead_time' : so_info.est_transport_lead_time,
                                        'details' : so_info.details,
                                        'order_line' : lines}
        
        default.update(data)
        
        res_id = po_obj.write(cr, uid, po_ids, default , context=context)
        return res_id         

    def split_fo_updates_po(self, cr, uid, source, so_info, context=None):
        if not context:
            context = {}
        print "Split FO updates back the lines in the original PO", source

        so_po_common = self.pool.get('so.po.common')
        print so_po_common
        po_ids = so_po_common.get_original_po_id(cr, uid, so_info.client_order_ref, context)
        
        partner_id = so_po_common.get_partner_id(cr, uid, source, context)
        address_id = so_po_common.get_partner_address_id(cr, uid, partner_id, context)
        
        if not po_ids:
            raise Exception, "The original PO does not exist!" + so_info.client_order_ref

        # now process to the PO line, to update it when the FO line has been already confirmed
        lines = so_po_common.confirm_po_lines(cr, uid, so_info, po_ids, context)
        
        po_obj = self.pool.get('purchase.order')
        
        default = {}
        data = {                        #'partner_ref' : source + "." + so_info.name,
                                        'partner_id' : partner_id,
                                        'partner_address_id' :  address_id,
                                        'note' : so_info.notes,
                                        'details' : so_info.details,
                                        'delivery_confirmed_date' : so_info.delivery_confirmed_date,
                                        'est_transport_lead_time' : so_info.est_transport_lead_time,
                                        'details' : so_info.details,
                                        'order_line' : lines}
        
        default.update(data)
        
        res_id = po_obj.write(cr, uid, po_ids, default , context=context)
        return res_id         

    def picking_received(self, cr, uid, source, picking_info, context=None):
        if not context:
            context = {}
        name = picking_info.purchase_id.name
        ids = self.search(cr, uid, [('client_order_ref', '=', source + "." + name)])
        self.write(cr, uid, ids, {'received' : True}, context=context)
        return True

sale_order_sync_TEMP()


class so_po_common_TEMP(osv.osv_memory):
    
    def confirm_po_line(self, cr, uid, po_id, line_values, context=None):
        line_result = []
        
        if not po_id:
            print "Error: The original PO not provided"
            return False 
        
        po_line_obj = self.pool.get('purchase.order.line')
        
        for line in line_values.order_line:
            line_dict = line.to_dict()
            sync_pol_db_id = False
            if 'sync_pol_db_id' in line_dict:
                sync_pol_db_id = line.sync_pol_db_id
            if not sync_pol_db_id:
                print "This line not found in the original PO"
                return False 
                
            line_ids = po_line_obj.search(cr, uid, [('sync_pol_db_id', '=', sync_pol_db_id), ('order_id', '=', po_id)], context=context)
            if not line_ids:
                print "This line not found in the original PO"
                return False 
                    
            po_line = po_line_obj.browse(cr, uid, line_ids[0], context=context)
            if not po_line:
                print "This line not found in the original PO"
                return False
            
            values = {'state' : 'confirmed',}
            line_result.append((1, line_ids[0], values))
                        
        return line_result


    def confirm_po_lines(self, cr, uid, line_values, po_ids, context=None):
        line_result = []
        
        if not po_ids:
            print "Error: The original PO not provided"
            return False 
        
        po_line_obj = self.pool.get('purchase.order.line')
        
        for line in line_values.order_line:

            line_dict = line.to_dict()

            # Get the line Id             
            sync_pol_db_id = False
            if 'sync_pol_db_id' in line_dict:
                sync_pol_db_id = line.sync_pol_db_id
            
            if not sync_pol_db_id:
                print "This line not found in the original PO"
                return False 
            
            line_ids = po_line_obj.search(cr, uid, [('sync_pol_db_id', '=', sync_pol_db_id), ('order_id', '=', po_ids[0])], context=context)
            if not line_ids:
                print "This line not found in the original PO"
                return False 
                
            po_line = po_line_obj.browse(cr, uid, line_ids[0], context=context)
            if not po_line:
                print "This line not found in the original PO"
                return False
            
            values = {'product_uom' : self.get_uom_id(cr, uid, line.product_uom, context=context), # PLEASE Use the get_record_id!!!!!
                      'comment' : line.comment,
                      'have_analytic_distribution_from_header' : line.have_analytic_distribution_from_header,
                      'line_number' : line.line_number,
                      'notes' : line.notes,
                                       
                      'price_unit' : line.price_unit}

            line_dict = line.to_dict()
            
            rec_id = self.get_record_id(cr, uid, context, line.product_id)
            if rec_id:
                values['product_id'] = rec_id
                values['name'] = line.product_id.name
            else:
                values['name'] = line.comment
                
            if 'product_uom_qty' in line_dict: # come from the SO
                values['product_qty'] = line.product_uom_qty

            if 'product_qty' in line_dict: # come from the PO
                values['product_uom_qty'] = line.product_qty
            
            if 'date_planned' in line_dict:
                values['date_planned'] = line.date_planned 

            if 'confirmed_delivery_date' in line_dict:
                values['confirmed_delivery_date'] = line.confirmed_delivery_date 

            rec_id = self.get_record_id(cr, uid, context, line.analytic_distribution_id)
            if rec_id:
                values['analytic_distribution_id'] = rec_id 

            # finally if everything is Ok for this line, set the state of the original line to confirmed
            values['state'] = 'done'
                        
            line_result.append((1, po_line, values))

        return line_result 
    
so_po_common_TEMP()    