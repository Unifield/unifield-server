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
import netsvc
import so_po_common
from sync_common import xmlid_to_sdref
import logging

class stock_picking(osv.osv):
    '''
    synchronization methods related to stock picking objects
    '''
    _inherit = "stock.picking"
    _logger = logging.getLogger('stock.picking')
    
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
        
        #UF-1617: asset form
        asset_id = False
        if data['asset_id'] and data['asset_id']['id']: 
            asset_id = self.pool.get('product.asset').find_sd_ref(cr, uid, xmlid_to_sdref(data['asset_id']['id']), context=context)

        # uom
        uom_name = data['product_uom']['name']
        uom_ids = uom_obj.search(cr, uid, [('name', '=', uom_name)], context=context)
        if not uom_ids:
            raise Exception, "The corresponding uom does not exist here. Uom name: %s"%uom_name
        uom_id = uom_ids[0]
        
        #UF-1617: Handle batch and asset object
        batch_id = False
        if data['prodlot_id']:
            batch_id = self.pool.get('stock.production.lot').find_sd_ref(cr, uid, xmlid_to_sdref(data['prodlot_id']['id']), context=context)
            if not batch_id:
                raise Exception, "Batch Number %s not found for this sync data record" %data['prodlot_id']
        
        expired_date = data['expired_date']

        # build a dic which can be used directly to update the stock move
        result = {'line_number': data['line_number'],
                  'product_id': product_id,
                  'product_uom': uom_id,
                  'product_uos': uom_id,
                  'date': data['date'],
                  'date_expected': data['date_expected'],

                  'prodlot_id': batch_id,
                  'expired_date': expired_date,

                  'asset_id': asset_id,
                  'change_reason': data['change_reason'] or None,
                  'name': data['name'],
                  'product_qty': data['product_qty'] or 0.0,
                  'product_uos_qty': data['product_qty'] or 0.0,
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
                # Don't get the returned pack lines
                if line.get('location_dest_id', {}).get('usage', 'customer') == 'customer':
                    # aggregate according to line number
                    line_dic = result.setdefault(line.get('line_number'), {})
                    # set the data
                    line_dic.setdefault('data', []).append(self.format_data(cr, uid, line, context=context))
                    # set the flag to know if the data has already been processed (partially or completely) in Out side
                    line_dic.update({'out_processed':  line_dic.setdefault('out_processed', False) or line['processed_stock_move']})
            
        return result
        

    def out_fo_updates_in_po(self, cr, uid, source, out_info, context=None):
        #####        
        ##### THIS METHOD IS CURRENTLY NOT USED! AS THE METHOD partial_shipped_fo_updates_in_po is doing the task
        #####
        
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
        self._logger.info("+++ Call update INcoming shipment at %s from Out in FO at %s"%(cr.dbname, source))
        
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
        in_id = so_po_common.get_in_id(cr, uid, po_id, po_name, context)
        
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
            
            state_done = False
            if pick_dict['state'] == 'done':
                state_done = True
            all_done_flag = True # set False if existed a line not done
            
            # update lines
            for line in pack_data:
                line_data = pack_data[line]
                # get the corresponding picking line ids
                move_ids = move_obj.search(cr, uid, [('picking_id', '=', in_id), ('line_number', '=', line)], context=context)
                if not move_ids:
                    # no stock moves with the corresponding line_number in the picking, could have already been processed
                    continue
                
                # if state of the OUT is done, then check if a line of the IN is 0, close the line, and keep the flag all_done
                # if some line is still not 0, meaning there is still products waiting to receive, then set the flag all_done to False
                # then with this flag, we don't close the whole IN
                
                # we check that all stock moves for a given line number have not been processed yet at IN side
                moves_data = move_obj.read(cr, uid, move_ids, ['processed_stock_move', 'product_qty'], context=context)
                
                for move_data in moves_data:
                    if move_data['product_qty'] != 0.0:
                        all_done_flag = False

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
            
            # If the state of OUT/PICK is done, then close also this IN
            
            if all_done_flag:
                netsvc.LocalService("workflow").trg_validate(uid, 'stock.picking', in_id, 'button_shipped', cr)
                
        return res_id

    def partial_shipped_fo_updates_in_po(self, cr, uid, source, out_info, context=None):
        '''
        ' This sync method is used for updating the IN of Project side when the OUT/PICK at Coordo side became done.
        ' In partial shipment/OUT, when the last shipment/OUT is made, the original IN will become Available Shipped, no new IN will
        ' be created, as the whole quantiy of the IN is delivered (but not yet received at Project side)
        '''
        
        if context is None:
            context = {}
        self._logger.info("+++ Call to update partial shipment/OUT from supplier %s to INcoming Shipment of PO at %s"%(source, cr.dbname))
        
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
        in_id = so_po_common.get_in_id(cr, uid, po_id, po_name, context)
        
        if in_id:
            partial_datas = {}
            partial_datas[in_id] = {}
            line_numbers = {}
            for line in pack_data:
                line_data = pack_data[line]
                # get the corresponding picking line ids
                for data in line_data['data']:
                    ln = data.get('line_number', False)
                    
                    if ln not in line_numbers.keys():
                        move_ids = move_obj.search(cr, uid, [('picking_id', '=', in_id), ('line_number', '=', data.get('line_number'))], context=context)
                        if move_ids and move_ids[0]:
                            line_numbers[ln] = move_ids[0]
                        else:
                            message = "Line number is not found in the original IN or PO: " + str(ln)
                            self._logger.info(message)
                            raise Exception(message)
                    move_id = line_numbers[ln]
                       
                    # If we have a shipment with 10 packs and return from shipment
                    # the pack 2 and 3, the IN shouldn't be splitted in three moves (pack 1 available,
                    # pack 2 and 3 not available and pack 4 to 10 available) but splitted into 
                    # two moves (one move for all products available and one move for all
                    # products not available in IN)
                    if not partial_datas[in_id].get(move_id):
                        partial_datas[in_id].setdefault(move_id, []).append(data)
                    else:
                        for x in partial_datas[in_id][move_id]:
                            if x.get('product_id') == data.get('product_id') and x.get('product_uom') == data.get('product_uom') and x.get('prodlot_id') == data.get('prodlot_id') and x.get('asset_id') == data.get('asset_id'):
                                x['product_qty'] += data.get('product_qty')
                                x['product_uos_qty'] += data.get('product_uos_qty')
                                break
                        else:
                            partial_datas[in_id][move_id].append(data)
                    
            # for the last Shipment of an FO, no new INcoming shipment will be created --> same value as in_id
            new_picking = self.do_incoming_shipment_sync(cr, uid, in_id, partial_datas, context)            

            # set the Shipment ID/OUT from the Coordo side to this IN 
            shipment = pick_dict.get('shipment_id', False)
            if shipment:
                shipment_ref = source + "." + shipment['name'] # shipment made
            else:
                shipment_ref = source + "." +  pick_dict.get('name', False) # the case of OUT
            self.write(cr, uid, new_picking, {'already_shipped': True, 'shipment_ref': shipment_ref}, context)
            
            # Set the backorder reference to the IN !!!! THIS NEEDS TO BE CHECKED WITH SUPPLY PM!
            if new_picking != in_id:
                self.write(cr, uid, in_id, {'backorder_id': new_picking}, context)
            
        return True

    def do_incoming_shipment_sync(self, cr, uid, in_id, partial_datas, context=None):
        '''
        ' Modify the original method do_incoming_shipment in delivery_mechanism/wizard/stock_partial_picking.py to perform similarly as a
        ' partial incoming shipment for the sync case, as partial shipment/OUT has been made. 
        '
        ' The main idea here is to "rebuild" the value of "partial_datas" then call the method do_incoming_shipment of stock.picking
        '''
        # picking ids
        move_obj = self.pool.get('stock.move')
        prodlot_obj = self.pool.get('stock.production.lot')
        
        pick = self.browse(cr, uid, in_id, context=context)

        # treated moves
        move_ids = partial_datas[in_id].keys()
        # all moves
        all_move_ids = [move.id for move in pick.move_lines]
        # these moves will be set to 0 - not present in the wizard - create partial objects with qty 0
        missing_move_ids = [x for x in all_move_ids if x not in move_ids]
        # missing moves (deleted memory moves) are replaced by a corresponding partial with qty 0
        for missing_move in move_obj.browse(cr, uid, missing_move_ids, context=context):
            values = {'name': move.product_id.partner_ref,
                      'product_id': missing_move.product_id.id,
                      'product_qty': 0,
                      'product_uom': missing_move.product_uom.id,
                      'prodlot_id': False,
                      'asset_id': False,
                      'force_complete': False,
                      'change_reason': None,
                      }
            # average computation from original openerp
            if (missing_move.product_id.cost_method == 'average') and not missing_move.location_dest_id.cross_docking_location_ok:
                values.update({'product_price' : missing_move.product_id.standard_price,
                               'product_currency': missing_move.product_id.company_id and missing_move.product_id.company_id.currency_id and missing_move.product_id.company_id.currency_id.id or False,
                               })
            partial_datas[in_id].setdefault(missing_move.id, []).append(values)
        return self.do_incoming_shipment(cr, uid, [in_id], context=dict(context, partial_datas=partial_datas))


    def cancel_out_pick_cancel_in(self, cr, uid, source, out_info, context=None):
        if not context:
            context = {}
        self._logger.info("+++ Cancel the relevant IN at %s due to the cancel of OUT at supplier %s"%(cr.dbname, source))
        
        wf_service = netsvc.LocalService("workflow")
        so_po_common = self.pool.get('so.po.common')
        po_obj = self.pool.get('purchase.order')
        pick_dict = out_info.to_dict()

        # Look for the PO name, which has the reference to the FO on Coordo as source.out_info.origin
        so_ref = source + "." + pick_dict['origin']
        po_id = so_po_common.get_po_id_by_so_ref(cr, uid, so_ref, context)
        if po_id:
            # Then from this PO, get the IN with the reference to that PO, and update the data received from the OUT of FO to this IN
            in_id = so_po_common.get_in_id_from_po_id(cr, uid, po_id, context)
            if in_id:
                # Cancel the IN object
                wf_service.trg_validate(uid, 'stock.picking', in_id, 'button_cancel', cr)
                return True
        
        raise Exception("There is a problem when cancel of the IN at project")

    def closed_in_validates_delivery_out_ship(self, cr, uid, source, out_info, context=None):
        if not context:
            context = {}
        self._logger.info("+++ Closed INcoming at %s confirms the delivery of the relevant OUT/SHIP at %s"%(source, cr.dbname))
        
        wf_service = netsvc.LocalService("workflow")
        so_po_common = self.pool.get('so.po.common')
        pick_dict = out_info.to_dict()
        
        shipment_ref = pick_dict.get('shipment_ref', False)
        if not shipment_ref:
            raise Exception("The shipment reference is empty. The action cannot be executed.")
        
        ship_split = shipment_ref.split('.')
        if len(ship_split) != 2:
            message = "Invalid shipment reference format"
            self._logger.info(message)
            raise Exception(message)
        
        # Check if it an SHIP --_> call Shipment object to proceed the validation of delivery, otherwise, call OUT to validate the delivery!
        message = False
        if 'SHIP' in ship_split[1]:
            shipment_obj = self.pool.get('shipment')
            ship_ids = shipment_obj.search(cr, uid, [('name', '=', ship_split[1]), ('state', '=', 'done')], context=context)
            if ship_ids:
                # set the Shipment to become delivered
                shipment_obj.set_delivered(cr, uid, ship_ids, context=context)
                message = "The shipment " + ship_split[1] + " has been well delivered to its partner." 
        elif 'OUT' in ship_split[1]:
            ship_ids = self.search(cr, uid, [('name', '=', ship_split[1]), ('state', '=', 'done')], context=context)
            if ship_ids:
                # set the Shipment to become delivered
                self.set_delivered(cr, uid, ship_ids, context=context)
                message = "The OUTcoming " + ship_split[1] + " has been well delivered to its partner."
                 
        if message:
            self._logger.info(message)
            return message
        
        message = "Something goes wrong with this message and no confirmation of delivery"
        self._logger.info(message)
        raise Exception(message)

    def create_batch_number(self, cr, uid, source, out_info, context=None):
        if not context:
            context = {}
        self._logger.info("+++ Create batch number that comes with the SHIP/OUT from %s"%source)
        so_po_common = self.pool.get('so.po.common')
        batch_obj = self.pool.get('stock.production.lot')
        
        batch_dict = out_info.to_dict()
        error_message = "Create Batch Number: Something go wrong with this message, invalid instance reference"
        
        if batch_dict['instance_id'] and batch_dict['instance_id']['id']: 
            rec_id = self.pool.get('msf.instance').find_sd_ref(cr, uid, xmlid_to_sdref(batch_dict['instance_id']['id']), context=context)
            if rec_id:
                batch_dict['instance_id'] = rec_id

                existing_bn = batch_obj.search(cr, uid, [('name', '=', batch_dict['name']), ('instance_id', '=', rec_id)], context=context)
                if existing_bn: # existed already, then don't need to create a new one
                    message = "Create Batch Number: the given BN exists already local instance, no new BN will be created"
                    self._logger.info(message)
                    error_message = False
                    return message

                error_message = "Create Batch Number: Invalid reference to the product or product does not exist"
                if batch_dict.get('product_id'):
                    rec_id = self.pool.get('product.product').find_sd_ref(cr, uid, xmlid_to_sdref(out_info.product_id.id), context=context)
                    if rec_id:
                        batch_dict['product_id'] = rec_id
                        error_message = False

        # If error message exists --> cannot create the BN        
        if error_message:    
            self._logger.info(error_message)
            raise Exception, error_message

        batch_obj.create(cr, uid, batch_dict, context=context)
        message = "The new BN " + batch_dict['name'] + ", " + source +  ") has been created"
        self._logger.info(message)
        return message    
    

    def create_asset(self, cr, uid, source, out_info, context=None):
        if not context:
            context = {}
        self._logger.info("+++ Create asset form that comes with the SHIP/OUT from %s"%source)
        so_po_common = self.pool.get('so.po.common')
        asset_obj = self.pool.get('product.asset')
        
        asset_dict = out_info.to_dict()
        error_message = False
        
        if asset_dict['instance_id'] and asset_dict['instance_id']['id']: 
            rec_id = self.pool.get('msf.instance').find_sd_ref(cr, uid, xmlid_to_sdref(asset_dict['instance_id']['id']), context=context)
            if rec_id:
                asset_dict['instance_id'] = rec_id
            
                existing_asset = asset_obj.search(cr, uid, [('name', '=', asset_dict['name']), ('instance_id', '=', rec_id)], context=context)
                if existing_asset: # existed already, then don't need to create a new one
                    message = "Create Asset: the given asset form exists already local instance, no new asset will be created"
                    self._logger.info(message)
                    return message
        
                if asset_dict.get('product_id'):
                    rec_id = self.pool.get('product.product').find_sd_ref(cr, uid, xmlid_to_sdref(out_info.product_id.id), context=context)
                    if rec_id:
                        asset_dict['product_id'] = rec_id
                    else:
                        error_message = "Invalid product reference for the asset. The asset cannot be created"
        
                    rec_id = self.pool.get('product.asset.type').find_sd_ref(cr, uid, xmlid_to_sdref(out_info.asset_type_id.id), context=context)
                    if rec_id:
                        asset_dict['asset_type_id'] = rec_id
                    else:
                        error_message = "Invalid asset type reference for the asset. The asset cannot be created"
        
                    rec_id = self.pool.get('res.currency').find_sd_ref(cr, uid, xmlid_to_sdref(out_info.invo_currency.id), context=context)
                    if rec_id:
                        asset_dict['invo_currency'] = rec_id
                    else:
                        error_message = "Invalid currency reference for the asset. The asset cannot be created"
                else:
                    error_message = "Invalid reference to product for the asset. The asset cannot be created"
            else:
                error_message = "Create Asset: Something go wrong with this message, invalid instance reference"

        # If error message exists --> raise exception and no esset will be created        
        if error_message:    
            self._logger.info(error_message)
            raise Exception, error_message
        
        asset_obj.create(cr, uid, asset_dict, context=context)
        message = "The new asset (" + asset_dict['name'] + ", " + source +  ") has been created"
        self._logger.info(message)
        return message
    
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

#    def write(self, cr, uid, ids, vals, context=None):
#        if isinstance(ids, (int, long)):
#            ids = [ids]
#        if context is None:
#            context = {}
#                    
#        ret = super(stock_picking, self).write(cr, uid, ids, vals, context=context)
#        ##############################################################################
#        # SP-135: call the method to create manually a message for the relevant object, if needed
#        #
#        ##############################################################################
##        self.create_manual_message(cr, uid, ids, context)
#        return  ret


    def create_message_with_object_and_partner(self, cr, uid, rule_sequence, object_id, partner_name, context):
        
        ##############################################################################
        # This method creates a message and put into the sendbox, but the message is created for a given object, AND for a given partner
        # Meaning that for the same object, but for different internal partners, the object could be sent many times to these partner  
        #
        ##############################################################################
        rule_obj = self.pool.get("sync.client.message_rule")
        rule = rule_obj.get_rule_by_sequence(cr, uid, rule_sequence, context)
        
        if not rule or not object_id:
            return

        model_obj = self.pool.get(rule.model.model)
        msg_to_send_obj = self.pool.get("sync.client.message_to_send")
        
        arguments = model_obj.get_message_arguments(cr, uid, object_id, rule, context=context)
        
        identifiers = msg_to_send_obj._generate_message_uuid(cr, uid, rule.model.model, [object_id], rule.server_id, context=context)
        if not identifiers:
            return
        
        xml_id = identifiers[object_id]
        existing_message_id = msg_to_send_obj.search(cr, uid, [('identifier', '=', xml_id), ('destination_name', '=', partner_name)], context=context)
        if existing_message_id: # if similar message does not exist in the system, then do nothing
            return
        
        # if not then create a new one --- FOR THE GIVEN Batch number AND Destination
        data = {
                'identifier' : xml_id,
                'remote_call': rule.remote_call,
                'arguments': arguments,
                'destination_name': partner_name,
                'sent' : False,
                'generate_message' : True,
        }
        return msg_to_send_obj.create(cr, uid, data, context=context)


    # UF-1617: Override the hook method to create sync messages manually for some extra objects once the OUT/Partial is done
    def _hook_create_sync_messages(self, cr, uid, ids, context = None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        res = super(stock_picking, self)._hook_create_sync_messages(cr, uid, ids, context=context)
        for pick in self.browse(cr, uid, ids, context=context):
            partner = pick.partner_id
            if not partner or partner.partner_type != 'internal':
                return True
            
            list_batch = []
            list_asset = []
            # only treat for the internal partner
            for move in pick.move_lines:
                if move.state not in ('done'):
                    continue
                # Get batch number object
                if move.prodlot_id:
                    # put the new batch number into the list, and create messages for them below
                    list_batch.append(move.prodlot_id.id)
                    
                # Get asset object
                if move.asset_id:
                    # put the new batch number into the list, and create messages for them below
                    list_asset.append(move.asset_id.id)
            
            # for each new batch number object and for each partner, create messages and put into the queue for sending on next sync round
            for item in list_batch:
                self.create_message_with_object_and_partner(cr, uid, 1001, item, partner.name, context)

            # for each new batch number object and for each partner, create messages and put into the queue for sending on next sync round
            for item in list_asset:
                self.create_message_with_object_and_partner(cr, uid, 1002, item, partner.name, context)

        return res  
    
stock_picking()
