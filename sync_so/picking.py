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
import so_po_common
pp = pprint.PrettyPrinter(indent=4)

class stock_picking(osv.osv):
    '''
    synchronization methods related to stock picking objects
    '''
    _inherit = "stock.picking"
    
    def format_data(self, cr, uid, data, context=None):
        '''
        we format the data, gathering ids corresponding to objects
        '''
        # objects
        prod_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        
        # product
        product_name = data['product_id']['name']
        product_ids = prod_obj.search(cr, uid, [('name', '=', product_name)], context=context)
        if not product_ids:
            raise Exception, "The corresponding product does not exist here. Product name: %s"%product_name
        product_id = product_ids[0]
        # uom
        uom_name = data['product_uom']['name']
        uom_ids = uom_obj.search(cr, uid, [('name', '=', uom_name)], context=context)
        if not uom_ids:
            raise Exception, "The corresponding uom does not exist here. Uom name: %s"%uom_name
        uom_id = uom_ids[0]
        
        batch_ids = False
        so_po_common = self.pool.get('so.po.common')
        if data['prodlot_id']:
            batch_ids = self.pool.get('stock.production.lot').search(cr, uid, [('name', '=', data['prodlot_id'])], context=context)
            if not batch_ids:
                raise Exception, "Batch Number %s not found for this sync data record" %data['prodlot_id']
            batch_ids = batch_ids[0]
        
        expired_date = data['expired_date']

        # build a dic which can be used directly to update the stock move
        result = {'line_number': data['line_number'],
                  'product_id': product_id,
                  'product_uom': uom_id,
                  'product_uos': uom_id,
                  'date': data['date'],
                  'date_expected': data['date_expected'],

                  'prodlot_id': batch_ids,
                  'expired_date': expired_date,

                  'name': data['name'],
                  'product_qty': data['product_qty'],
                  'product_uos_qty': data['product_qty'],
                  'note': data['note'],
                  }
        return result
    
    def package_data_update_in(self, cr, uid, source, out_info, context=None):
        '''
        package the data to get info concerning already processed or not
        '''
        result = {}
        if out_info.get('move_lines', False):
            for line in out_info['move_lines']:
                # aggregate according to line number
                line_dic = result.setdefault(line.get('line_number'), {})
                # set the data
                line_dic.setdefault('data', []).append(self.format_data(cr, uid, line, context=context))
                # set the flag to know if the data has already been processed (partially or completely) in Out side
                line_dic.update({'out_processed':  line_dic.setdefault('out_processed', False) or line['processed_stock_move']})
            
        return result
        

    def out_fo_updates_in_po(self, cr, uid, source, out_info, context=None):
        '''
        method called when the OUT at coordo level updates the corresponding IN at project level
        
        
        fields used for info and consistency check only:
        'update_version_from_in_stock_picking': 
        'partner_type_stock_picking'
        
        fields used for update:
        'move_lines/product_qty' -> used for update product_qty AND product_uos_qty
        
        dates:
        - we update both date and date_expected at line level. date_expected is sychronized because is the expected date
          and date is also synchronized for consistency. Date is updated with actual date when the picking is processed to done (action_done@stock_move) 
        
        rules:
        - we do not updated objects with state 'done'
        - 
        '''
        if context is None:
            context = {}
        print "call update In in PO from Out in FO", source
        
        pick_dict = out_info.to_dict()
        
        # objects
        so_po_common = self.pool.get('so.po.common')
        po_obj = self.pool.get('purchase.order')
        move_obj = self.pool.get('stock.move')
        pick_tools = self.pool.get('picking.tools')
        
        # package data
        pack_data = self.package_data_update_in(cr, uid, source, pick_dict, context=context)
        # Look for the PO name, which has the reference to the FO on Coordo as source.out_info.origin
        so_ref = source + "." + pick_dict['origin']
        po_id = so_po_common.get_po_id_by_so_ref(cr, uid, so_ref, context)
        po_name = po_obj.browse(cr, uid, po_id, context=context)['name']
        # Then from this PO, get the IN with the reference to that PO, and update the data received from the OUT of FO to this IN
        in_id = so_po_common.get_in_id(cr, uid, po_name, context)
        
        if in_id:
            # update header
            header_result = {}
            # get the original note
            orig_note = self.read(cr, uid, in_id, ['note'], context=context)['note']
            if orig_note and pick_dict['note']:
                header_result['note'] = orig_note + '\n' + str(source) + ':' + pick_dict['note']
            elif orig_note:
                header_result['note'] = orig_note
            elif pick_dict['note']:
                header_result['note'] = str(source) + ':' + pick_dict['note']
            else:
                header_result['note'] = False
            
            header_result['min_date'] = pick_dict['min_date']
            res_id = self.write(cr, uid, [in_id], header_result, context=context)
            
            # update lines
            for line in pack_data:
                line_data = pack_data[line]
                # get the corresponding picking line ids
                move_ids = move_obj.search(cr, uid, [('picking_id', '=', in_id), ('line_number', '=', line)], context=context)
                if not move_ids:
                    # no stock moves with the corresponding line_number in the picking, could have already been processed
                    continue
                # we check that all stock moves for a given line number have not been processed yet at IN side
                moves_data = move_obj.read(cr, uid, move_ids, ['processed_stock_move'], context=context)
                if not all([not move_data['processed_stock_move'] for move_data in moves_data]):
                    # some lines have already been processed
                    continue
                # we check that all stock moves for a given line number have not been processed yet at OUT side
                
                ################################################################3
                # SP-135/UF-1617: TO BE CHECKed why it stops the update of the IN lines
                # So just remove it and perform tests to see the result
                ################################################################3
#                if line_data['out_processed']:
#                    continue
                
                completed_ids = []
                # we loop through the lines from OUT, updating if lines exists, or creating copies
                for data in line_data['data']:
                    # store the move id which will be modified
                    move_id = False
                    if move_ids:
                        # search orders by default by id, we therefore take the smallest id first
                        move_id = move_ids.pop(0)
                        # update existing line and drop from list
                        move_obj.write(cr, uid, [move_id], data, context=context)
                    else:
                        # copy the first one used
                        move_id = move_obj.copy(cr, uid, completed_ids[0], dict(data, state='confirmed'), context=context)
                    # save the used id
                    completed_ids.append(move_id)
                    
                # all lines have been created from OUT, if some lines stays in the IN, we remove them
                if move_ids:
                    move_obj.unlink(cr, uid, move_ids, context=context)
                    
            # we process a check availability on the incoming shipment so the lines copied will be available
            pick_tools.check_assign(cr, uid, [in_id], context=context)
            
        return res_id

    def ship_fo_updates_in_po(self, cr, uid, source, out_info, context=None):
        if context is None:
            context = {}
        print "call update In in PO from Out in FO", source
        
        pick_dict = out_info.to_dict()
        
        # objects
        so_po_common = self.pool.get('so.po.common')
        po_obj = self.pool.get('purchase.order')
        move_obj = self.pool.get('stock.move')
        pick_tools = self.pool.get('picking.tools')
        
        # package data
        pack_data = self.package_data_update_in(cr, uid, source, pick_dict, context=context)
        # Look for the PO name, which has the reference to the FO on Coordo as source.out_info.origin
        so_ref = source + "." + pick_dict['origin']
        po_id = so_po_common.get_po_id_by_so_ref(cr, uid, so_ref, context)
        po_name = po_obj.browse(cr, uid, po_id, context=context)['name']
        # Then from this PO, get the IN with the reference to that PO, and update the data received from the OUT of FO to this IN
        in_id = so_po_common.get_in_id(cr, uid, po_name, context)
        
        if in_id:
            # update header
            header_result = {}
            # get the original note
            orig_note = self.read(cr, uid, in_id, ['note'], context=context)['note']
            if orig_note and pick_dict['note']:
                header_result['note'] = orig_note + '\n' + str(source) + ':' + pick_dict['note']
            elif orig_note:
                header_result['note'] = orig_note
            elif pick_dict['note']:
                header_result['note'] = str(source) + ':' + pick_dict['note']
            else:
                header_result['note'] = False
            
            header_result['min_date'] = pick_dict['min_date']
            res_id = self.write(cr, uid, [in_id], header_result, context=context)
            
            # update lines
            for line in pack_data:
                line_data = pack_data[line]
                # get the corresponding picking line ids
                move_ids = move_obj.search(cr, uid, [('picking_id', '=', in_id), ('line_number', '=', line)], context=context)
                if not move_ids:
                    # no stock moves with the corresponding line_number in the picking, could have already been processed
                    continue
                # we check that all stock moves for a given line number have not been processed yet at IN side
                moves_data = move_obj.read(cr, uid, move_ids, ['processed_stock_move'], context=context)
                if not all([not move_data['processed_stock_move'] for move_data in moves_data]):
                    # some lines have already been processed
                    continue
                # we check that all stock moves for a given line number have not been processed yet at OUT side
                
                ################################################################3
                # SP-135/UF-1617: TO BE CHECKed why it stops the update of the IN lines
                # So just remove it and perform tests to see the result
                ################################################################3
#                if line_data['out_processed']:
#                    continue
                
                completed_ids = []
                # we loop through the lines from OUT, updating if lines exists, or creating copies
                for data in line_data['data']:
                    # store the move id which will be modified
                    move_id = False
                    if move_ids:
                        # search orders by default by id, we therefore take the smallest id first
                        move_id = move_ids.pop(0)
                        # update existing line and drop from list
                        move_obj.write(cr, uid, [move_id], data, context=context)
                    else:
                        # copy the first one used
                        move_id = move_obj.copy(cr, uid, completed_ids[0], dict(data, state='confirmed'), context=context)
                    # save the used id
                    completed_ids.append(move_id)
                    
        return res_id



    def cancel_out_pick_cancel_in(self, cr, uid, source, out_info, context=None):
        if not context:
            context = {}
        print "Cancel the relevant IN due to the cancel of OUT at Coordo"
        wf_service = netsvc.LocalService("workflow")
        so_po_common = self.pool.get('so.po.common')
        po_obj = self.pool.get('purchase.order')
        pick_dict = out_info.to_dict()

        # Look for the PO name, which has the reference to the FO on Coordo as source.out_info.origin
        so_ref = source + "." + pick_dict['origin']
        po_id = so_po_common.get_po_id_by_so_ref(cr, uid, so_ref, context)
        if po_id:
            po_name = po_obj.browse(cr, uid, po_id, context=context)['name']
            # Then from this PO, get the IN with the reference to that PO, and update the data received from the OUT of FO to this IN
            in_id = so_po_common.get_in_id(cr, uid, po_name, context)
            if in_id:
                # Cancel the IN object
                wf_service.trg_validate(uid, 'stock.picking', in_id, 'button_cancel', cr)
                return True
        
        raise Exception("There is a problem when cancel of the IN at project")

    def check_valid_to_generate_message(self, cr, uid, ids, rule, context):
        # Check if the given object is valid for the rule
        model_obj = self.pool.get(rule.model.model)
        domain = rule.domain and eval(rule.domain) or []
        domain.insert(0, '&')
        domain.append(('id', '=', ids[0])) # add also this id to short-list only the given object 
        return model_obj.search(cr, uid, domain, context=context)

    def create_manual_message(self, cr, uid, ids, context):
        rule_obj = self.pool.get("sync.client.message_rule")
        
        ##############################################################################
        # Define the message rule to be fixed, or by given a name for it
        #
        ##############################################################################
        rule = rule_obj.get_rule_by_sequence(cr, uid, 1000, context)
        
        if not rule or not ids or not ids[0]:
            return

        valid_ids = self.check_valid_to_generate_message(cr, uid, ids, rule, context)
        if not valid_ids:
            return # the current object is not valid for creating message
        valid_id = valid_ids[0] 
        
        model_obj = self.pool.get(rule.model.model)
        msg_to_send_obj = self.pool.get("sync.client.message_to_send")
        
        arg = model_obj.get_message_arguments(cr, uid, ids[0], rule, context=context)
        call = rule.remote_call
        update_destinations = model_obj.get_destination_name(cr, uid, ids, rule.destination_name, context=context)
        
        identifiers = msg_to_send_obj._generate_message_uuid(cr, uid, rule.model.model, ids, rule.server_id, context=context)
        if not identifiers or not update_destinations:
            return
        
        xml_id = identifiers[valid_id]
        existing_message_id = msg_to_send_obj.search(cr, uid, [('identifier', '=', xml_id)], context=context)
        if not existing_message_id: # if similar message does not exist in the system, then do nothing
            return
        
        # make a change on the message only now
        msg_to_send_obj.modify_manual_message(cr, uid, existing_message_id, xml_id, call, arg, update_destinations.values()[0], context)

    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
                    
        ret = super(stock_picking, self).write(cr, uid, ids, vals, context=context)
        ##############################################################################
        # SP-135: call the method to create manually a message for the relevant object, if needed
        #
        ##############################################################################
        self.create_manual_message(cr, uid, ids, context)
        return  ret
    
stock_picking()
