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

from osv import osv, fields
import netsvc

import logging

from sync_common import xmlid_to_sdref
from sync_client import get_sale_purchase_logger
import picking_rw

class stock_move(osv.osv):

    _inherit = "stock.move"
    _description = "Stock move at RW"

    def _create_chained_picking_internal_request(self, cr, uid, context=None, *args, **kwargs):
        '''
        Overrided in delivery_mechanism to write the flag for replicating the new Internal picking if the instance is a RW one, not the CP 
        '''
        pickid = kwargs['picking']
        picking_obj = self.pool.get('stock.picking')
        if pickid and picking_obj._get_usb_entity_type(cr, uid) == picking_obj.REMOTE_WAREHOUSE and not context.get('sync_message_execution', False):
            picking_obj.write(cr, uid, pickid, {'already_replicated': False}, context=context)                
                
        return super(stock_move, self)._create_chained_picking_internal_request(cr, uid, context, *args, **kwargs)

stock_move()

class stock_picking(osv.osv):
    '''
    Stock.picking override for Remote Warehouse tasks: This class is for the INcoming Shipment and Internal moves
    
    '''
    _inherit = "stock.picking"
    _logger = logging.getLogger('------sync.stock.picking')


    # Retrieve the value of sdref and rw_sdref_counterpart from the given backorder_idS
    def rw_get_backorders_values(self, cr, uid, pick_dict, context=None):
        if 'backorder_ids' in pick_dict and pick_dict['backorder_ids']:
            if pick_dict.get('backorder_ids', False):
                for line in pick_dict['backorder_ids']:
                    sdref = line['id'][3:]
                    rw_sdref_counterpart = line['rw_sdref_counterpart']
                    return sdref, rw_sdref_counterpart
        return False, False

    def usb_update_in_shipped_available(self, cr, uid, source, in_info, context=None):
        # UF-2422: Update new data for the IN before available, now shipped
        if context is None:
            context = {}


        rw_type = self._get_usb_entity_type(cr, uid)
        if rw_type == self.CENTRAL_PLATFORM:
            message = "Sorry, the given operation is only available for Remote Warehouse instance!"
            self._logger.info(message)
            raise Exception, message

        pick_dict = in_info.to_dict()
        pick_name = pick_dict['name']
        move_obj = self.pool.get('stock.move')
        
        existing_pick = self.search(cr, uid, [('name', '=', pick_name)], context=context)
        if not existing_pick: # If not exist, just create the new IN
            message = "The IN " + pick_name + " will be created in " + cr.dbname
            self._logger.info(message)
            return self.usb_replicate_in(cr, uid, source, in_info, context)

        # if existed already, just update the new values into the existing IN
        self._logger.info("+++ RW: Update the existing IN with new data and status shipped available: %s from %s to %s" % (pick_name, source, cr.dbname))
        existing_pick = self.browse(cr, uid, existing_pick[0], context=context)
        if existing_pick.state != 'assigned':
            message = "Sorry, the existing IN " + pick_name + " may have already been processed. Cannot update any more!"
            self._logger.info(message)
            return message 
        
        # UF-2422: Remove all current IN lines, then recreate new lines
        for move in existing_pick.move_lines:
            move_obj.write(cr, uid, move.id, {'state': 'draft'}, context=context)
            move_obj.unlink(cr, uid, move.id)
            
        picking_lines = self.get_picking_lines(cr, uid, source, pick_dict, context)
        for line in picking_lines:
            vals = line[2]
            vals['picking_id'] = existing_pick.id
            move_obj.create(cr, uid, vals, context=context)
                
        self.write(cr, uid, existing_pick.id, {'state': 'shipped'}, context=context)
        message = "The IN " + pick_name + " has been now updated and sent to shipped available."
        self._logger.info(message)
        return message
    
    def usb_cancel_in(self, cr, uid, source, in_info, context=None):
        if context is None:
            context = {}

        pick_dict = in_info.to_dict()
        pick_name = pick_dict['name']
        origin = pick_dict['origin']
            
        self._logger.info("+++ RW: Cancel the Incoming Shipment: %s from %s to %s" % (pick_name, source, cr.dbname))

        rw_type = self._get_usb_entity_type(cr, uid)
        if rw_type == self.REMOTE_WAREHOUSE:
            if origin:
                existing_pick = self.search(cr, uid, [('origin', '=', origin), ('name', '=', pick_name), ('type', '=', 'in'), ('state', '!=', 'done')], context=context)
                if not existing_pick:
                    message = "Sorry, the IN: " + pick_name + " does not exist in " + cr.dbname
                    self._logger.info(message)
                    raise Exception, message
                
                self.action_cancel(cr, uid,existing_pick, context=context)
                message = "Cancelled successfully the Incoming Shipment: " + pick_name
            else:
                message = "Sorry, the case without the origin PO is not yet available!"
                self._logger.info(message)
                raise Exception, message
        else:
            message = "Sorry, the given operation is only available for Remote Warehouse instance!"
        
        self._logger.info(message)
        return message
    
    def usb_replicate_in(self, cr, uid, source, in_info, context=None):
        if context is None:
            context = {}

        pick_dict = in_info.to_dict()
        pick_name = pick_dict['name']
        origin = pick_dict['origin']
            
        self._logger.info("+++ RW: Replicate the Incoming Shipment: %s from %s to %s" % (pick_name, source, cr.dbname))
        move_obj = self.pool.get('stock.move')

        rw_type = self._get_usb_entity_type(cr, uid)
        if rw_type == self.REMOTE_WAREHOUSE:
            if origin:
                header_result = {}
                self.retrieve_picking_header_data(cr, uid, source, header_result, pick_dict, context)
                picking_lines = self.get_picking_lines(cr, uid, source, pick_dict, context)
                header_result['move_lines'] = picking_lines
                header_result['already_replicated'] = True
                
                # Check if the PICK is already there, then do not create it, just inform the existing of it, and update the possible new name
                existing_pick = self.search(cr, uid, [('origin', '=', origin), ('subtype', '=', 'picking'), ('type', '=', 'in'), ('state', '=', 'draft')], context=context)
                if existing_pick:
                    message = "Sorry, the IN: " + pick_name + " existed already in " + cr.dbname
                    self._logger.info(message)
                    return message
                del header_result['state']
                pick_id = self.create(cr, uid, header_result , context=context)
                # update this object as backorder of previous object
                
                if pick_id: # If successfully created, then get the sdref of the CP IN and store into this replicated IN in RW
                    sdref, temp = self.rw_get_backorders_values(cr, uid, pick_dict, context=context)
                    if sdref:
                        bo_of_other = self.search(cr, uid, [('rw_sdref_counterpart', '=', sdref)], context=context)
                        if bo_of_other:# The original IN of this backorder IN exists, update that original IN
                            self.write(cr, uid, bo_of_other, {'backorder_id': pick_id}, context=context)

                todo_moves = []
                for move in self.browse(cr, uid, pick_id, context=context).move_lines:
                    todo_moves.append(move.id)
                move_obj.action_confirm(cr, uid, todo_moves)
                move_obj.force_assign(cr, uid, todo_moves)
                wf_service = netsvc.LocalService("workflow")
                wf_service.trg_validate(uid, 'stock.picking', pick_id, 'button_confirm', cr)
                if pick_dict['state'] == 'shipped':
                    self.write(cr, uid, pick_id, {'state': 'shipped'}, context=context)
                message = "The IN: " + pick_name + " has been well replicated in " + cr.dbname
            else:
                message = "Sorry, the case without the origin PO is not yet available!"
                self._logger.info(message)
                raise Exception, message
        else:
            message = "Sorry, the given operation is only available for Remote Warehouse instance!"
        
        self._logger.info(message)
        return message


    def usb_create_partial_in(self, cr, uid, source, out_info, context=None):
        '''
        This is the PICK with format PICK00x-y, meaning the PICK00x-y got closed making the backorder PICK got updated (return products
        into this backorder PICK)
        '''
        
        pick_dict = out_info.to_dict()
        pick_name = pick_dict['name']
            
        self._logger.info("+++ RW: Create partial INcoming Shipment: %s from %s to %s" % (pick_name, source, cr.dbname))
        if context is None:
            context = {}

        message = "Unknown error, please check the log file."
        
        # Look for the original PICK based on the origin of OUT and check if this PICK still exists and not closed or converted
        origin = pick_dict['origin']
        rw_type = self._get_usb_entity_type(cr, uid)
        if rw_type == self.CENTRAL_PLATFORM:
            if origin:
                header_result = {}
                self.retrieve_picking_header_data(cr, uid, source, header_result, pick_dict, context)
                pick_ids = self.search(cr, uid, [('origin', '=', origin), ('type', '=', 'in'), ('subtype', '=', 'standard'), ('state', 'in', ['assigned', 'shipped'])], context=context)
                if pick_ids and len(pick_ids) > 1:
                    '''
                    Search for the right IN to do partial reception, using the backorder_idS to look for that right original IN
                    The value is stored in the rw_sdref_counterpart of the RW, from this value, the real IN Id from the CP will be retrieved
                    '''
                    # Check if it is a full reception
                    exact_ids = self.search(cr, uid, [('name', '=', pick_name), ('state', 'in', ['assigned', 'shipped'])], context=context)
                    if exact_ids:
                        pick_ids = exact_ids
                    else:
                        temp, rw_sdref_counterpart = self.rw_get_backorders_values(cr, uid, pick_dict, context=context)
                        if rw_sdref_counterpart:
                            real_in_id = self.find_sd_ref(cr, uid, xmlid_to_sdref(rw_sdref_counterpart), context=context)
                            if real_in_id: # found the real IN id of the original IN for performing the partial incoming reception
                                pick_ids = [real_in_id]
                
                if pick_ids:
                    state = pick_dict['state']
                    if state in ('done', 'assigned'):
                        picking_lines = self.get_picking_lines(cr, uid, source, pick_dict, context)
                        header_result['move_lines'] = picking_lines
                        #self.force_assign(cr, uid, pick_ids)
                        context['rw_backorder_name'] = pick_name
                        self.rw_do_create_partial_in(cr, uid, pick_ids[0], header_result, picking_lines, context)
                        
                        message = "The IN: " + pick_name + " has been successfully created in " + cr.dbname
                        self.write(cr, uid, pick_ids[0], {'already_replicated': True}, context=context)
        
                else:
                    message = "The IN: " + pick_name + " not found in " + cr.dbname
                    self._logger.info(message)
                    raise Exception, message
            else:
                message = "Sorry, the case without the origin PO is not yet available!"
                self._logger.info(message)
                raise Exception, message
                
        elif rw_type == self.REMOTE_WAREHOUSE: 
            message = "Sorry, the given operation is not available for Remote Warehouse instance!"
                
        self._logger.info(message)
        return message


    #UF-2531: Allow also the INT to be synced between CP and RW
    # If INT from sratch from RW ---> tolerate no partner when replicating the INT in the other instance
    def usb_replicate_int(self, cr, uid, source, out_info, context=None):
        '''
        '''
        if context is None:
            context = {}

        pick_dict = out_info.to_dict()
        pick_name = pick_dict['name']
        origin = pick_dict['origin']
        self._logger.info("+++ RW: Replicate the INT from an IR: %s from %s to %s" % (pick_name, source, cr.dbname))
        search_condition = [('type', '=', 'internal'), ('subtype', '=', 'standard'), ('name', '=', pick_name)]
        if origin:
            search_condition.append(('origin', '=', origin))
            
        header_result = {}
        self.retrieve_picking_header_data(cr, uid, source, header_result, pick_dict, context, pick_dict['partner_id'])
        picking_lines = self.get_picking_lines(cr, uid, source, pick_dict, context)
        header_result['move_lines'] = picking_lines
        header_result['already_replicated'] = True
        state = pick_dict['state']
        
        # Check if the PICK is already there, then do not create it, just inform the existing of it, and update the possible new name
        existing_pick = self.search(cr, uid, search_condition, context=context)
        if existing_pick:
            message = "Sorry, the INT: " + pick_name + " existed already in " + cr.dbname
            self._logger.info(message)
            return message
        pick_id = self.create(cr, uid, header_result , context=context)
        if state != 'draft': # if draft, do nothing
            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_validate(uid, 'stock.picking', pick_id, 'button_confirm', cr)
            if header_result.get('date_done', False):
                context['rw_date'] = header_result.get('date_done')
            self.action_assign(cr, uid, [pick_id], context=context)
            if header_result.get('date_done', False):
                context['rw_date'] = False
        
        message = "The INT: " + pick_name + " has been well replicated in " + cr.dbname
            
        self._logger.info(message)
        return message

    def action_shipped_wkf(self, cr, uid, ids, context=None):
        """ set the sync flag to true for re-syncing
        """
        res = super(stock_picking, self).action_shipped_wkf(cr, uid, ids, context=context)
        rw_type = self._get_usb_entity_type(cr, uid)
        if rw_type == self.CENTRAL_PLATFORM:        
            self.write(cr, uid, ids, {'already_replicated': False})
        return res

    def rw_do_create_partial_in(self, cr, uid, pick_id, header_result, pack_data, context=None):
        # Objects
        processor_obj = self.pool.get('stock.incoming.processor')
        in_processor = processor_obj.create(cr, uid, {'picking_id': pick_id}, context=context)
        processor_obj.write(cr, uid, in_processor, {'direct_incoming': False}, context=context)
        
        self.pool.get('stock.incoming.processor').create_lines(cr, uid, in_processor, context=context)
        partial_datas = {}
        partial_datas[pick_id] = {}
        context['InShipOut'] = "IN"  # asking the IN object to be logged
        context['rw_sync'] = True
        
        move_obj = self.pool.get('stock.move')
        move_proc = self.pool.get('stock.move.in.processor')
        
        # UF-2531: Get the associate name for the case of creating PICK or INT
        associate_pick_name = False
        if 'associate_pick_name' in header_result:
            associate_pick_name = header_result.get('associate_pick_name', False)
        
        for l in pack_data:
            data = l[2]

            # get the corresponding picking data ids
            ln = data['line_number']
            # UF-2148: if the line contains 0 qty, just ignore it!
            qty = data['product_qty']
            data['quantity'] = data['product_qty']
            if qty == 0:
                message = "Line number " + str(ln) + " with quantity 0 is ignored!"
                self._logger.info(message)
                continue

            # If the line is canceled, then just ignore it!
            state = data['state']
            if state == 'cancel':
                message = "Line number " + str(ln) + " with state cancel is ignored!"
                self._logger.info(message)
                continue

            search_move = [('picking_id', '=', pick_id), ('line_number', '=', data['line_number'])]

            original_qty_partial = data['original_qty_partial']
            orig_qty = data['product_qty']
            if original_qty_partial != -1:
                search_move.append(('product_qty', '=', original_qty_partial))
                orig_qty = original_qty_partial

            move_ids = move_obj.search(cr, uid, search_move, context=context)
            if not move_ids and original_qty_partial != -1:
                search_move = [('picking_id', '=', pick_id), ('line_number', '=', data['line_number']), ('original_qty_partial', '=', original_qty_partial)]
                move_ids = move_obj.search(cr, uid, search_move, context=context)

            if not move_ids:
                search_move = [('picking_id', '=', pick_id), ('line_number', '=', data['line_number'])]
                move_ids = move_obj.search(cr, uid, search_move, context=context)
                if not move_ids:
                    message = "Line number " + str(ln) + " is not found in the original IN or PO"
                    self._logger.info(message)
                    raise Exception(message)

            move_id = False # REF-99: declare the variable before using it, otherwise if it go to else, then line 268 "if not move_id" -> problem!
            if move_ids and len(move_ids) == 1:  # if there is only one move, take it for process
                move_id = move_ids[0]
            else:  # if there are more than 1 moves, then pick the next one not existing in the partial_datas[pick_id]
                # Search the best matching move
                best_diff = False
                for move in move_obj.read(cr, uid, move_ids, ['product_qty'], context=context):
                    line_proc_ids = move_proc.search(cr, uid, [
                        ('wizard_id', '=', in_processor),
                        ('move_id', '=', move['id']),
                    ], context=context)
                    if not line_proc_ids:
                        diff = move['product_qty'] - orig_qty
                        if diff >= 0 and (not best_diff or diff < best_diff):
                            best_diff = diff
                            move_id = move['id']
                            if best_diff == 0.00:
                                break
                if not move_id:
                    move_id = move_ids[0]

            # If we have a shipment with 10 packs and return from shipment
            # the pack 2 and 3, the IN shouldn't be splitted in three moves (pack 1 available,
            # pack 2 and 3 not available and pack 4 to 10 available) but splitted into
            # two moves (one move for all products available and one move for all
            # products not available in IN)
            line_proc_ids = move_proc.search(cr, uid, [
                ('wizard_id', '=', in_processor),
                ('move_id', '=', move_id),
                ('quantity', '=', 0.00),
            ], context=context)
            data['move_id'] = move_id
            data['cost'] = data['price_unit'] # Add the cost price if changed during the processing of INT
            data['wizard_id'] = in_processor
            if not line_proc_ids:
                data['ordered_quantity'] = data['product_qty']
                self.pool.get('stock.move.in.processor').create(cr, uid, data, context=context)
            else:
                for line in move_proc.browse(cr, uid, line_proc_ids, context=context):
                    if line.product_id.id == data['product_id'] and \
                       line.uom_id.id == data['uom_id'] and \
                       (line.prodlot_id and line.prodlot_id.id == data['prodlot_id']) or (not line.prodlot_id and not data['prodlot_id']) and \
                       (line.asset_id and line.asset_id.id == data['asset_id']) or (not line.asset_id and not data['asset_id']):
                        move_proc.write(cr, uid, [line.id], data, context=context)
                        break
                else:
                    data['ordered_quantity'] = data['product_qty']
                    move_proc.create(cr, uid, data, context=context)

        # UF-2531: if creating PICK, check if the associated name is well a PICK 
        if associate_pick_name and 'PICK' in associate_pick_name:
            context['associate_pick_name'] = associate_pick_name

        # for the last Shipment of an FO, no new INcoming shipment will be created --> same value as pick_id
        new_picking = self.do_incoming_shipment(cr, uid, in_processor, context)
        # we should also get the newly created INT object for this new picking, the force the name of it as what received from the RW
        if associate_pick_name and 'INT' in associate_pick_name:
            associate_pick_name = header_result.get('associate_pick_name')
            origin = header_result.get('origin')
            old_ref_name = self.browse(cr, uid, new_picking, context=context)['associate_pick_name']
            int_ids = self.search(cr, uid, [('origin', '=', origin),('name', '=', old_ref_name), ('type', '=', 'internal'), ('subtype', '=', 'standard')], context=context)
            if int_ids:
                self.write(cr, uid, int_ids[0], {'name': associate_pick_name}, context)
                self.write(cr, uid, new_picking, {'associate_pick_name': associate_pick_name}, context)
        
        # Set the backorder reference to the IN !!!! THIS NEEDS TO BE CHECKED WITH SUPPLY PM!
        in_name = self.browse(cr, uid, new_picking, context=context)['name']
        if new_picking != pick_id:
            self.write(cr, uid, pick_id, {'backorder_id': new_picking}, context)
            self.write(cr, uid, new_picking, {'already_replicated': True}, context=context)
        else: # update the IN name which has been wrongly named when creating BO
            pick_name = header_result['name']
            if in_name != pick_name:
                self.write(cr, uid, new_picking, {'name': pick_name}, context=context)

        message = "The INcoming " + in_name + " is partially processed!"
        self._logger.info(message)
        return message

    def usb_create_partial_int_moves(self, cr, uid, source, out_info, context=None):
        '''
        Create the partial Internal Moves in the CP instance
        '''
        pick_dict = out_info.to_dict()
        pick_name = pick_dict['name']
            
        self._logger.info("+++ RW: Create Partial Internal Moves: %s from %s to %s" % (pick_name, source, cr.dbname))
        if context is None:
            context = {}

        message = "Unknown error, please check the log file."
        # Look for the original PICK based on the origin of OUT and check if this PICK still exists and not closed or converted
        origin = pick_dict['origin']
        rw_type = self._get_usb_entity_type(cr, uid)
        if rw_type == self.CENTRAL_PLATFORM:
            header_result = {}
            self.retrieve_picking_header_data(cr, uid, source, header_result, pick_dict, context)
            search_condition = [('type', '=', 'internal'), ('subtype', '=', 'standard'), ('state', 'in', ['assigned', 'confirmed'])]
            if header_result.get('associate_pick_name', False):
                search_condition.append(('name', '=', header_result.get('associate_pick_name')))
            else: # if this is not a partial reception of INT, then just take the given INT itself
                search_condition.append(('name', '=', pick_name))
                
            #US-24: Now allow also the INT without origin nor partner
            if origin:
                search_condition.append(('origin', '=', origin))
            
            pick_ids = self.search(cr, uid, search_condition, context=context)
            if pick_ids:
                pick_id = pick_ids[0]
                state = pick_dict['state']
                if state in ('done', 'assigned'):
                    picking_lines = self.get_picking_lines(cr, uid, source, pick_dict, context)
                    header_result['move_lines'] = picking_lines

                    self.cancel_moves_before_process(cr, uid, [pick_id], context=context)
                    #UF-2426: Inform the do_partial that this is a full process if there is no back order
                    if 'backorder_ids' in pick_dict and pick_dict['backorder_ids']:
                        context['rw_backorder_name'] = pick_name
                    else:
                        context['rw_full_process'] = True

                    if header_result.get('date_done', False):
                        context['rw_date'] = header_result.get('date_done')

                    # try to perform a check available after cancel all moves? not really sure!
                    self.action_assign(cr, uid, [pick_id], context=context)

                    if header_result.get('date_done', False):
                        context['rw_date'] = False

                    self.rw_do_create_partial_int_moves(cr, uid, pick_id, picking_lines, context)
                    
                    message = "The Internal Moves: " + pick_name + " has been successfully received in " + cr.dbname
                    self.write(cr, uid, pick_id, {'already_replicated': True}, context=context)
    
            else:
                message = "The IN: " + pick_name + " not found in " + cr.dbname
                self._logger.info(message)
                raise Exception, message
                
        elif rw_type == self.REMOTE_WAREHOUSE: 
            message = "Sorry, the given operation is not available for Remote Warehouse instance!"
                
        self._logger.info(message)
        return message

    def rw_do_create_partial_int_moves(self, cr, uid, pick_id, picking_lines, context=None):
        # Objects
        wizard_obj = self.pool.get('internal.picking.processor')
        in_processor = wizard_obj.create(cr, uid, {'picking_id': pick_id})
        wizard_line_obj = self.pool.get('internal.move.processor')
        move_obj = self.pool.get('stock.move')
        wizard = wizard_obj.browse(cr, uid, in_processor, context=context)
        
        # Copy values from the OUT message move lines into the the wizard lines before making the partial OUT
        # If the line got split, based on line number and create new wizard line
        move_already_checked = []
        for sline in picking_lines:
            sline = sline[2]            
            line_number = sline['line_number']
            if not sline['product_qty'] or sline['product_qty'] == 0.00:
                continue
            upd1 = {
                'picking_id': wizard.picking_id.id,
                'line_number': line_number,
                'product_qty': sline['product_qty'],
            }
            query = '''
                SELECT id
                FROM stock_move
                WHERE
                    picking_id = %(picking_id)s
                    AND line_number = %(line_number)s
                ORDER BY abs(product_qty-%(product_qty)s)'''
            cr.execute(query, upd1)

            move_ids = [x[0] for x in cr.fetchall()]
            #move_diff = set(move_ids) - set(move_already_checked)
            move_diff = [x for x in move_ids if x not in move_already_checked]
            if move_ids and move_diff:
                move_id = list(move_diff)[0]
            elif move_ids:
                move_id = move_ids[0]
            else:
                move_id = False

            if move_id:
                move = move_obj.browse(cr, uid, move_id, context=context)
                line_data = wizard_line_obj._get_line_data(cr, uid, wizard, move, context=context)
                if line_data:
                    if move.id not in move_already_checked:
                        move_already_checked.append(move.id)
                        # the location_dest_id needs to be updated into the move directly if it has been changed
                        if move.location_dest_id and move.location_dest_id.id != sline['location_dest_id']:
                            move_obj.write(cr, uid, move.id, {'location_dest_id': sline['location_dest_id']}, context=context)

                    vals = {'line_number': line_number,'product_id': sline['product_id'],
                            'location_id': sline['location_id'],'location_dest_id': sline['location_dest_id'],
                            'ordered_quantity': sline['product_qty'],'quantity': sline['product_qty'],
                            'uom_id': sline['product_uom'], 'prodlot_id': sline['prodlot_id'],
                            'move_id': move_id, 'wizard_id': wizard.id, 'composition_list_id':line_data['composition_list_id'],
                            'cost':line_data['cost'],'currency':line_data['currency'],
                            }
                    wizard_line_obj.create(cr, uid, vals, context=context)

        wizard_obj.do_partial(cr, uid, [in_processor], context=context)
        
        in_name = self.browse(cr, uid, pick_id, context=context)['name']
        message = "The Internal Moves " + in_name + " is now closed!"
        self._logger.info(message)
        return message

stock_picking()

