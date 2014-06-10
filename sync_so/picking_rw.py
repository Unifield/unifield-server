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

class stock_picking(osv.osv):
    '''
    Stock.picking override for Remote Warehouse tasks
    
    WORK IN PROGRESS
    
    '''
    _inherit = "stock.picking"
    _logger = logging.getLogger('------sync.stock.picking')

    _columns = {'already_replicated': fields.boolean(string='Already replicated - for sync only'),
                }
    _defaults = {'already_replicated': False,
                 }

    def copy_data(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({
            'already_replicated': False,
        })
        return super(stock_picking, self).copy_data(cr, uid, id, default, context=context)

    def retrieve_picking_header_data(self, cr, uid, source, header_result, pick_dict, context):
        if 'name' in pick_dict:
            header_result['name'] = pick_dict.get('name')
        if 'state' in pick_dict:
            header_result['state'] = pick_dict.get('state')
        if 'stock_journal_id' in pick_dict:
            header_result['stock_journal_id'] = pick_dict.get('stock_journal_id')
        if 'origin' in pick_dict:
            header_result['origin'] = pick_dict.get('origin')
        if 'order_category' in pick_dict:
            header_result['order_category'] = pick_dict.get('order_category')

        if pick_dict['reason_type_id'] and pick_dict['reason_type_id']['id']:
            header_result['reason_type_id'] = self.pool.get('stock.reason.type').find_sd_ref(cr, uid, xmlid_to_sdref(pick_dict['reason_type_id']['id']), context=context)
        else:
            raise Exception, "Reason Type at picking header cannot be empty"
              
        if 'overall_qty' in pick_dict:
            header_result['overall_qty'] = pick_dict.get('overall_qty')
        if 'change_reason' in pick_dict:
            header_result['change_reason'] = pick_dict.get('change_reason')
            
        if 'move_type' in pick_dict:
            header_result['move_type'] = pick_dict.get('move_type')
        if 'type' in pick_dict:
            header_result['type'] = pick_dict.get('type')
        if 'subtype' in pick_dict:
            header_result['subtype'] = pick_dict.get('subtype')
            
        if 'transport_order_id' in pick_dict:
            header_result['transport_order_id'] = pick_dict.get('transport_order_id')

        so_po_common = self.pool.get('so.po.common')

        partner_id = so_po_common.get_partner_id(cr, uid, source, context)
        address_id = so_po_common.get_partner_address_id(cr, uid, partner_id, context)
        price_list = so_po_common.get_price_list_id(cr, uid, partner_id, context)
        location_id = so_po_common.get_location(cr, uid, partner_id, context)
        address_id = so_po_common.get_partner_address_id(cr, uid, partner_id, context)
        header_result['partner_ref'] = source + "." + pick_dict.get('name')
        header_result['partner_id'] = partner_id
        header_result['partner_id2'] = partner_id
        header_result['address_id'] = address_id
        header_result['location_id'] = location_id
        return header_result

    def get_picking_line(self, cr, uid, data, context=None):
        '''
        we format the data, gathering ids corresponding to objects
        '''
        # objects
        prod_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        location_obj = self.pool.get('stock.location')

        # product
        product_name = data['product_id']['name']
        product_ids = prod_obj.search(cr, uid, [('name', '=', product_name)], context=context)
        if not product_ids:
            raise Exception, "The corresponding product does not exist here. Product name: %s" % product_name
        product_id = product_ids[0]

        asset_id = False
        if data['asset_id'] and data['asset_id']['id']:
            asset_id = self.pool.get('product.asset').find_sd_ref(cr, uid, xmlid_to_sdref(data['asset_id']['id']), context=context)

        if data['location_dest_id'] and data['location_dest_id']['id']:
            location = data['location_dest_id']['id']
            location_dest_id = location_obj.find_sd_ref(cr, uid, xmlid_to_sdref(location), context=context)
        else:
            raise Exception, "Destination Location cannot be empty"
        
        if data['location_id'] and data['location_id']['id']:
            location = data['location_id']['id']
            location_id = location_obj.find_sd_ref(cr, uid, xmlid_to_sdref(location), context=context)
        else:
            raise Exception, "Location cannot be empty"

        if data['reason_type_id'] and data['reason_type_id']['id']:
            reason_type_id = self.pool.get('stock.reason.type').find_sd_ref(cr, uid, xmlid_to_sdref(data['reason_type_id']['id']), context=context)
        else:
            raise Exception, "Reason Type at line cannot be empty"

        uom_name = data['product_uom']['name']
        uom_ids = uom_obj.search(cr, uid, [('name', '=', uom_name)], context=context)
        if not uom_ids:
            raise Exception, "The corresponding uom does not exist here. Uom name: %s" % uom_name
        uom_id = uom_ids[0]
        

        batch_id = False
        if data['prodlot_id']:
            batch_id = self.pool.get('stock.production.lot').find_sd_ref(cr, uid, xmlid_to_sdref(data['prodlot_id']['id']), context=context)
            if not batch_id:
                raise Exception, "Batch Number %s not found for this sync data record" % data['prodlot_id']

        expired_date = data['expired_date']
        state = data['state']
        if state == 'done':
            state = 'assigned'
        result = {'line_number': data['line_number'],
                  'product_id': product_id,
                  'product_uom': uom_id,
                  'product_uos': uom_id,
                  'uom_id': uom_id,
                  'date': data['date'],
                  'date_expected': data['date_expected'],
                  'state': state,

                  'original_qty_partial': data['original_qty_partial'], 

                  'prodlot_id': batch_id,
                  'expired_date': expired_date,

                  'location_dest_id': location_dest_id,
                  'location_id': location_id,
                  'reason_type_id': reason_type_id,
                  
                  'from_pack': data['from_pack'] or 0,
                  'to_pack': data['to_pack'] or 0,
                  'height': data['height'] or 0,
                  'weight': data['weight'] or 0,
                  'length': data['length'] or 0,
                  'width': data['width'] or 0,
                  'pack_type': data['pack_type'] or None,
                  
                  'asset_id': asset_id,
                  'change_reason': data['change_reason'] or None,
                  'name': data['name'],
                  'product_qty': data['product_qty'] or 0.0,
                  'note': data['note'],
                  }
        return result

    def get_picking_lines(self, cr, uid, source, out_info, context=None):
        '''
        package the data to get info concerning already processed or not
        '''
        result = {}
        line_result = []
        if out_info.get('move_lines', False):
            for line in out_info['move_lines']:
                line_data = self.get_picking_line(cr, uid, line, context=context)
                line_result.append((0, 0, line_data))

        return line_result

    def _usb_entity_type(self, cr, uid, context=None):
        '''
        '''
        entity = self.pool.get('sync.client.entity').get_entity(cr, uid)
        if not hasattr(entity, 'usb_instance_type'):
            return False
        
        return entity.usb_instance_type


    def _hook_check_cp_instance(self, cr, uid, ids, context=None):
        '''
        If this is a CP instance (of a RW), then all the process of IN/OUT/PICK should be warned, because it should be done at the RW instance!
        '''
        res = super(stock_picking, self)._hook_check_cp_instance(cr, uid, ids, context=context)
        rw_type = self._usb_entity_type(cr, uid)
        if rw_type and rw_type == 'central_platform':
            name = "This action should only be performed at the Remote Warehouse instance! Are you sure to proceed it at this main instance?"
            model = 'confirm'
            step = 'default'
            question = name
            clazz = 'stock.picking'
            func = 'original_action_process'
            args = [ids]
            kwargs = {}            
            wiz_obj = self.pool.get('wizard')
            # open the selected wizard
            res = wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=dict(context, question=question,
                                                                                                    callback={'clazz': clazz,
                                                                                                              'func': func,
                                                                                                              'args': args,
                                                                                                              'kwargs': kwargs}))
            return res
        return False            

    def replicate_picking(self, cr, uid, source, out_info, context=None):
        '''
        '''
        if context is None:
            context = {}

        pick_dict = out_info.to_dict()
        pick_name = pick_dict['name']
        origin = pick_dict['origin']
            
        self._logger.info("+++ RW: Replicate the PICK object: %s from %s to %s" % (pick_name, source, cr.dbname))
        so_po_common = self.pool.get('so.po.common')
        move_obj = self.pool.get('stock.move')
        pick_tools = self.pool.get('picking.tools')

        header_result = {}
        self.retrieve_picking_header_data(cr, uid, source, header_result, pick_dict, context)
        picking_lines = self.get_picking_lines(cr, uid, source, pick_dict, context)
        header_result['move_lines'] = picking_lines
        header_result['already_replicated'] = True
        
        # Check if the PICK is already there, then do not create it, just inform the existing of it, and update the possible new name
        existing_pick = self.search(cr, uid, [('origin', '=', origin), ('subtype', '=', 'picking'), ('type', '=', 'out'), ('state', '=', 'draft')], context=context)
        if existing_pick:
            message = "Sorry, the PICK: " + pick_name + " existed already in " + cr.dbname
        else:
            pick_id = self.create(cr, uid, header_result , context=context)
            message = "The PICK: " + pick_name + " has been well replicated in " + cr.dbname
            
        self._logger.info(message)
        return message

    # Create a RW message when a Pick is converted to OUT for syncing back to its partner
    def _hook_create_rw_out_sync_messages(self, cr, uid, ids, context=None, out=True):
        if self._usb_entity_type(cr, uid) != 'remote_warehouse':
            return
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        message_id = 2001 # Default it's an OUT message
        already_replicated = False
        if not out: # convert to PICK --> do not resend this object again
            message_id = 2002
            already_replicated = True

        so_po_common = self.pool.get('so.po.common')
        res = super(stock_picking, self)._hook_create_rw_out_sync_messages(cr, uid, ids, context=context)
        for pick in self.browse(cr, uid, ids, context=context):
            partner = pick.partner_id
            so_po_common.create_message_with_object_and_partner(cr, uid, message_id, pick.id, partner.name, context, True)
        
        # If the PICK got successfully converted to OUT, then reupdate the value already_replicated, for sync purpose
        self.write(cr, uid, ids, {'already_replicated': already_replicated}, context=context)
        

    # WORK IN PROGRESS
    def _hook_delete_rw_out_sync_messages(self, cr, uid, ids, context=None, out=True):
        if self._usb_entity_type(cr, uid) != 'remote_warehouse':
            return
        if isinstance(ids, (int, long)):
            ids = [ids]
        so_po_common = self.pool.get('so.po.common')

        res = super(stock_picking, self)._hook_delete_rw_out_sync_messages(cr, uid, ids, context=context)
        for pick in self.browse(cr, uid, ids, context=context):
            partner = pick.partner_id
            return True

    def update_original_pick(self, cr, uid, pick_id, picking_lines, context=None):
        move_obj = self.pool.get('stock.move')

        # Copy values from the OUT message move lines into the the wizard lines before making the partial OUT
        # If the line got split, based on line number and create new wizard line
        for sline in picking_lines:
            sline = sline[2]
            line_number = sline['line_number']
            
            pick = self.browse(cr, uid, pick_id, context=context)
            for mline in pick.move_lines:
                if mline.line_number == line_number:
                    # match the line, copy the content of picking line into the wizard line
                    vals = {'product_id': sline['product_id'], 'quantity': sline['product_qty'],'location_dest_id': sline['location_dest_id'],
                            'location_id': sline['location_id'], 'product_uom': sline['product_uom'], 'asset_id': sline['asset_id'], 'prodlot_id': sline['prodlot_id']}
                    move_obj.write(cr, uid, mline.id, vals, context)
                    break
        return True
            
    def convert_pick_to_out(self, cr, uid, source, out_info, context=None):
        ''' Convert PICK to OUT, normally from RW to CP 
        '''
        pick_dict = out_info.to_dict()
        pick_name = pick_dict['name']
            
        self._logger.info("+++ RW: PICK converted to OUT %s syncs from %s to %s" % (pick_name, source, cr.dbname))
        if context is None:
            context = {}

        so_po_common = self.pool.get('so.po.common')
        move_obj = self.pool.get('stock.move')
        pick_tools = self.pool.get('picking.tools')

        # Look for the original PICK based on the origin of OUT and check if this PICK still exists and not closed or converted
        message = "Unknown error, please check the log file"
        origin = pick_dict['origin']
        
        rw_type = self._usb_entity_type(cr, uid)
        if rw_type == 'central_platform' and origin:
            # look for FO if it is a CP instance
            pick_ids = self.search(cr, uid, [('origin', '=', origin), ('subtype', '=', 'picking'), ('type', '=', 'out'), ('state', '=', 'draft')], context=context)  
            if pick_ids: # This is a real pick in draft, then convert it to OUT
                old_name = self.read(cr, uid, pick_ids, ['name'], context=context)[0]['name']
                context['rw_backorder_name'] = pick_name
                # Before converting to OUT, the PICK needs to be updated as what sent from the RW
                self.convert_to_standard(cr, uid, pick_ids, context)
                self.write(cr, uid, pick_ids, {'name': pick_name, 'already_replicated': True, 'state': 'assigned'}, context=context)
                message = "The PICK " + old_name + " has been converted to OUT " + pick_name
            else:
                pick_ids = self.search(cr, uid, [('origin', '=', origin), ('subtype', '=', 'standard'), ('state', '=', 'assigned')], context=context)
                if pick_ids:
                    old_name = self.read(cr, uid, pick_ids, ['name'], context=context)[0]['name']
                    message = "The PICK has already been converted to OUT: " + old_name
                
            if pick_ids:
                picking_lines = self.get_picking_lines(cr, uid, source, pick_dict, context)
                self.update_original_pick(cr, uid, pick_ids[0], picking_lines, context)
                
        elif rw_type == 'remote_warehouse': 
            message = "Sorry, the given operation is not available for Remote Warehouse instance!"
                
        self._logger.info(message)
        return message

    def convert_out_to_pick(self, cr, uid, source, out_info, context=None):
        ''' Convert OUT to PICK, normally from RW to CP 
        '''
        pick_dict = out_info.to_dict()
        pick_name = pick_dict['name']
            
        self._logger.info("+++ RW: Convert %s to PICK, from %s to %s" % (pick_name, source, cr.dbname))
        if context is None:
            context = {}

        so_po_common = self.pool.get('so.po.common')
        move_obj = self.pool.get('stock.move')
        pick_tools = self.pool.get('picking.tools')

        # Look for the original PICK based on the origin of OUT and check if this PICK still exists and not closed or converted
        message = "Unknown error, please check the log file."
        origin = pick_dict['origin']
       
        rw_type = self._usb_entity_type(cr, uid)
        if rw_type == 'central_platform' and origin:
            # look for the OUT if it has already been converted before, using the origin from FO
            pick_ids = self.search(cr, uid, [('origin', '=', origin), ('subtype', '=', 'standard'), ('type', '=', 'out'),('state', 'in', ['draft', 'assigned'])], context=context)  
            if pick_ids: # This is a real pick in draft, then convert it to OUT
                old_name = self.read(cr, uid, pick_ids, ['name'], context=context)[0]['name']
                context['rw_backorder_name'] = pick_name
                # Before converting to OUT, the PICK needs to be updated as what sent from the RW
                self.convert_to_pick(cr, uid, pick_ids, context)
                self.write(cr, uid, pick_ids, {'name': pick_name, 'already_replicated': True, 'state': 'assigned'}, context=context)
                message = "The OUT: " + old_name + " has been converted to PICK: " + pick_name
            else:
                # If the OUT has already been converted back to PICK before, then just inform this fact
                pick_ids = self.search(cr, uid, [('origin', '=', origin), ('subtype', '=', 'picking'), ('state', '=', 'assigned')], context=context)
                if pick_ids:
                    old_name = self.read(cr, uid, pick_ids, ['name'], context=context)[0]['name']
                    message = "The PICK has already been converted to OUT: " + old_name
                else:
                    message = "The OUT for the FO: " + origin + " found for converting to PICK."
                    self._logger.info(message)
                    raise Exception, message
                
            if pick_ids:
                # Should update the lines again? will there be new updates from the OUT converted to PICK? --- TO CHECK, if not do not call the stmt below
                picking_lines = self.get_picking_lines(cr, uid, source, pick_dict, context)
                self.update_original_pick(cr, uid, pick_ids[0], picking_lines, context)
                
        elif rw_type == 'remote_warehouse': 
            message = "Sorry, the given operation is not available for Remote Warehouse instance!"
                
        self._logger.info(message)
        return message
    
    def closed_out_closes_out(self, cr, uid, source, out_info, context=None):
        ''' There are 2 cases: 
        + If the PICK exists in the current instance, then just convert that pick to OUT, same xmlid
        + If the PICK not present, the a PICK needs to be created first, then convert it to OUT
        + Another case: OUT with Back order, meaning that the original PICK is not directly linked to this OUT, but an existing OUT at local
        '''
        pick_dict = out_info.to_dict()
        pick_name = pick_dict['name']
            
        self._logger.info("+++ RW: OUT closed %s closes original PICK object from %s to %s" % (pick_name, source, cr.dbname))
        if context is None:
            context = {}

        so_po_common = self.pool.get('so.po.common')
        move_obj = self.pool.get('stock.move')
        pick_tools = self.pool.get('picking.tools')

        header_result = {}
        self.retrieve_picking_header_data(cr, uid, source, header_result, pick_dict, context)
        
        # Look for the original PICK based on the origin of OUT and check if this PICK still exists and not closed or converted
        message = "Unknown error, please check the log file."
        origin = pick_dict['origin']
        rw_type = self._usb_entity_type(cr, uid)
        if rw_type == 'central_platform' and origin:
            pick_ids = self.search(cr, uid, [('origin', '=', origin), ('subtype', '=', 'standard'), ('state', 'in', ['confirmed', 'assigned'])], context=context)
            if pick_ids:
                state = pick_dict['state']
                if state == 'done':   
                    picking_lines = self.get_picking_lines(cr, uid, source, pick_dict, context)
                    header_result['move_lines'] = picking_lines
                    self.force_assign(cr, uid, pick_ids)
                    context['rw_backorder_name'] = pick_name
                    self.rw_do_out_partial(cr, uid, pick_ids[0], picking_lines, context)
                    
                    old_pick = self.browse(cr, uid, pick_ids[0], context)
                    if old_pick.backorder_id:
                        self.write(cr, uid, old_pick.backorder_id.id, {'already_replicated': True}, context=context) #'name': pick_name,
                    message = "The OUT " + pick_name + " has been closed in " + cr.dbname
                    self.write(cr, uid, pick_ids[0], {'already_replicated': True}, context=context)
    
            else:
                message = "The OUT " + pick_name + " not found in " + cr.dbname
                self._logger.info(message)
                raise Exception, message
                
        elif rw_type == 'remote_warehouse': 
            message = "Sorry, the given operation is not available for Remote Warehouse instance!"
                
        self._logger.info(message)
        return message
    
    def rw_do_out_partial(self, cr, uid, out_id, picking_lines, context=None):
        # Objects
        picking_obj = self.pool.get('stock.picking')
        sequence_obj = self.pool.get('ir.sequence')
        uom_obj = self.pool.get('product.uom')
        move_obj = self.pool.get('stock.move')
        wf_service = netsvc.LocalService("workflow")

        wizard_obj = self.pool.get('outgoing.delivery.processor')
        wizard_line_obj = self.pool.get('outgoing.delivery.move.processor')
        proc_id = wizard_obj.create(cr, uid, {'picking_id': out_id})
        wizard_obj.create_lines(cr, uid, proc_id, context=context)

        # Copy values from the OUT message move lines into the the wizard lines before making the partial OUT
        # If the line got split, based on line number and create new wizard line
        for sline in picking_lines:
            sline = sline[2]
            line_number = sline['line_number']
            
            #### CHECK HOW TO COPY THE LINE IN WIZARD IF THE OUT HAS BEEN SPLIT!
            #### WORK IN PROGRESS
            
            wizard = wizard_obj.browse(cr, uid, proc_id, context=context)
            for mline in wizard.move_ids:
                if mline.line_number == line_number:
                    # match the line, copy the content of picking line into the wizard line
                    vals = {'product_id': sline['product_id'], 'quantity': sline['product_qty'],'location_id': sline['location_id'],
                            'product_uom': sline['product_uom'], 'asset_id': sline['asset_id'], 'prodlot_id': sline['prodlot_id']}
                    wizard_line_obj.write(cr, uid, mline.id, vals, context)
                    break

        self.do_partial(cr, uid, [proc_id], 'outgoing.delivery.processor', context=context)
        return True

    def rw_create_picking(self, cr, uid, source, out_info, context=None):
        '''
        This is the PICK with format PICK00x-y, meaning the PICK00x-y got closed making the backorder PICK got updated (return products
        into this backorder PICK), and the PICK00x becomes  
        '''
        
        pick_dict = out_info.to_dict()
        pick_name = pick_dict['name']
            
        self._logger.info("+++ RW: %s closed at %s is now closed at %s" % (pick_name, source, cr.dbname))
        if context is None:
            context = {}

        so_po_common = self.pool.get('so.po.common')
        move_obj = self.pool.get('stock.move')
        pick_tools = self.pool.get('picking.tools')

        message = "Unknown error, please check the log file."
        header_result = {}
        self.retrieve_picking_header_data(cr, uid, source, header_result, pick_dict, context)
        
        # Look for the original PICK based on the origin of OUT and check if this PICK still exists and not closed or converted
        origin = pick_dict['origin']
        rw_type = self._usb_entity_type(cr, uid)
        if rw_type == 'central_platform' and origin:
            pick_ids = self.search(cr, uid, [('origin', '=', origin), ('subtype', '=', 'picking'), ('state', 'in', ['confirmed', 'assigned'])], context=context)
            if pick_ids:
                state = pick_dict['state']
                if state in ('done', 'assigned'):   
                    picking_lines = self.get_picking_lines(cr, uid, source, pick_dict, context)
                    header_result['move_lines'] = picking_lines
                    self.force_assign(cr, uid, pick_ids)
                    context['rw_backorder_name'] = pick_name
                    self.rw_do_create_picking_partial(cr, uid, pick_ids[0], picking_lines, context)
                    
                    old_pick = self.browse(cr, uid, pick_ids[0], context)
                    if old_pick.backorder_id:
                        self.write(cr, uid, old_pick.backorder_id.id, {'already_replicated': True}, context=context) #'name': pick_name,
                    message = "The OUT " + pick_name + " has been closed in " + cr.dbname
                    self.write(cr, uid, pick_ids[0], {'already_replicated': True}, context=context)
    
            else:
                message = "The OUT " + pick_name + " not found in " + cr.dbname
                self._logger.info(message)
                raise Exception, message
                
        elif rw_type == 'remote_warehouse': 
            message = "Sorry, the given operation is not available for Remote Warehouse instance!"
                
        self._logger.info(message)
        return message

    def rw_do_create_picking_partial(self, cr, uid, pick_id, picking_lines, context=None):
        # Objects
        picking_obj = self.pool.get('stock.picking')
        sequence_obj = self.pool.get('ir.sequence')

        wizard_obj = self.pool.get('create.picking.processor')
        wizard_line_obj = self.pool.get('create.picking.move.processor')
        proc_id = wizard_obj.create(cr, uid, {'picking_id': pick_id}, context=context)
        wizard_obj.create_lines(cr, uid, proc_id, context=context)        
        

        # Copy values from the OUT message move lines into the the wizard lines before making the partial OUT
        # If the line got split, based on line number and create new wizard line
        for sline in picking_lines:
            sline = sline[2]
            line_number = sline['line_number']
            
            #### CHECK HOW TO COPY THE LINE IN WIZARD IF THE OUT HAS BEEN SPLIT!
            #### WORK IN PROGRESS
            
            wizard = wizard_obj.browse(cr, uid, proc_id, context=context)
            for mline in wizard.move_ids:
                if mline.line_number == line_number:
                    # match the line, copy the content of picking line into the wizard line
                    vals = {'product_id': sline['product_id'], 'quantity': sline['product_qty'],'location_id': sline['location_id'],
                            'product_uom': sline['product_uom'], 'asset_id': sline['asset_id'], 'prodlot_id': sline['prodlot_id']}
                    wizard_line_obj.write(cr, uid, mline.id, vals, context)
                    break

        self.do_create_picking(cr, uid, [proc_id], context=context)
        return True

    def replicate_ppl(self, cr, uid, source, out_info, context=None):
        pick_dict = out_info.to_dict()
        pick_name = pick_dict['name']
            
        self._logger.info("+++ RW: Replicate the PPL: %s from %s to %s" % (pick_name, source, cr.dbname))
        if context is None:
            context = {}

        so_po_common = self.pool.get('so.po.common')
        move_obj = self.pool.get('stock.move')
        pick_tools = self.pool.get('picking.tools')

        message = "Unknown error, please check the log file."
        header_result = {}
        self.retrieve_picking_header_data(cr, uid, source, header_result, pick_dict, context)
        
        # Look for the original PICK based on the origin of OUT and check if this PICK still exists and not closed or converted
        origin = pick_dict['origin']
        rw_type = self._usb_entity_type(cr, uid)
        if rw_type == 'central_platform' and origin:
            pick_ids = self.search(cr, uid, [('origin', '=', origin), ('subtype', '=', 'picking'), ('state', 'in', ['confirmed', 'assigned'])], context=context)
            if pick_ids:
                state = pick_dict['state']
                if state in ('done', 'assigned'):   
                    picking_lines = self.get_picking_lines(cr, uid, source, pick_dict, context)
                    header_result['move_lines'] = picking_lines
                    self.force_assign(cr, uid, pick_ids)
                    context['rw_backorder_name'] = pick_name
                    self.rw_do_validate_picking(cr, uid, pick_ids[0], picking_lines, context)
                    
                    old_pick = self.browse(cr, uid, pick_ids[0], context)
                    if old_pick.backorder_id:
                        self.write(cr, uid, old_pick.backorder_id.id, {'already_replicated': True}, context=context) #'name': pick_name,
                    message = "The PICK: " + old_pick.name + " has been validated and generated a PPL: " + pick_name
                    self.write(cr, uid, pick_ids[0], {'already_replicated': True}, context=context)
    
            else:
                message = "The OUT " + pick_name + " not found in " + cr.dbname
                self._logger.info(message)
                raise Exception, message
                
        elif rw_type == 'remote_warehouse': 
            message = "Sorry, the given operation is not available for Remote Warehouse instance!"
                
        self._logger.info(message)
        return message

    def rw_do_validate_picking(self, cr, uid, pick_id, picking_lines, context=None):
        # Objects
        picking_obj = self.pool.get('stock.picking')
        sequence_obj = self.pool.get('ir.sequence')

        wizard_obj = self.pool.get('validate.picking.processor')
        wizard_line_obj = self.pool.get('validate.move.processor')
        proc_id = wizard_obj.create(cr, uid, {'picking_id': pick_id}, context=context)
        wizard_obj.create_lines(cr, uid, proc_id, context=context)        

        # Copy values from the OUT message move lines into the the wizard lines before making the partial OUT
        # If the line got split, based on line number and create new wizard line
        for sline in picking_lines:
            sline = sline[2]
            line_number = sline['line_number']
            
            #### CHECK HOW TO COPY THE LINE IN WIZARD IF THE OUT HAS BEEN SPLIT!
            #### WORK IN PROGRESS
            
            wizard = wizard_obj.browse(cr, uid, proc_id, context=context)
            for mline in wizard.move_ids:
                if mline.line_number == line_number:
                    # match the line, copy the content of picking line into the wizard line
                    vals = {'product_id': sline['product_id'], 'quantity': sline['product_qty'],'location_id': sline['location_id'],
                            'product_uom': sline['product_uom'], 'asset_id': sline['asset_id'], 'prodlot_id': sline['prodlot_id']}
                    wizard_line_obj.write(cr, uid, mline.id, vals, context)
                    break

        self.do_validate_picking(cr, uid, [proc_id], context=context)
        return True


    def sync_create_packing(self, cr, uid, source, out_info, context=None):
        pick_dict = out_info.to_dict()
        pick_name = pick_dict['name']
            
        self._logger.info("+++ RW: Replicate the Packing list: %s from %s to %s" % (pick_name, source, cr.dbname))
        if context is None:
            context = {}

        so_po_common = self.pool.get('so.po.common')
        move_obj = self.pool.get('stock.move')
        pick_tools = self.pool.get('picking.tools')

        message = "Unknown error, please check the log file."
        header_result = {}
        self.retrieve_picking_header_data(cr, uid, source, header_result, pick_dict, context)
        
        # Look for the original PICK based on the origin of OUT and check if this PICK still exists and not closed or converted
        origin = pick_dict['origin']
        shipment_name = pick_dict['shipment_id'] and pick_dict['shipment_id']['name'] or None
        
        rw_type = self._usb_entity_type(cr, uid)
        if rw_type == 'central_platform' and origin:
            pick_ids = self.search(cr, uid, [('origin', '=', origin), ('subtype', '=', 'ppl'), ('state', 'in', ['confirmed', 'assigned'])], context=context)
            if pick_ids:
                state = pick_dict['state']
                if state in ('done','draft','assigned'):   
                    picking_lines = self.get_picking_lines(cr, uid, source, pick_dict, context)
                    header_result['move_lines'] = picking_lines
                    context['shipment_name'] = shipment_name
                    self.rw_create_ppl_all_steps(cr, uid, pick_ids[0], picking_lines, context)
                    
                    old_pick = self.browse(cr, uid, pick_ids[0], context)
                    if old_pick.backorder_id:
                        self.write(cr, uid, old_pick.backorder_id.id, {'already_replicated': True}, context=context) #'name': pick_name,
                    message = "The PICK: " + old_pick.name + " has been validated and generated a PPL: " + pick_name
                    self.write(cr, uid, pick_ids[0], {'already_replicated': True}, context=context)
    
            else:
                message = "The OUT " + pick_name + " not found in " + cr.dbname
                self._logger.info(message)
                raise Exception, message
                
        elif rw_type == 'remote_warehouse': 
            message = "Sorry, the given operation is not available for Remote Warehouse instance!"
                
        self._logger.info(message)
        return message

    def rw_create_ppl_all_steps(self, cr, uid, pick_id, picking_lines, context=None):
        '''
        Create the Pack family for the packing list
        '''
        
        # Objects
        picking_obj = self.pool.get('stock.picking')
        sequence_obj = self.pool.get('ir.sequence')

        wizard_obj = self.pool.get('ppl.processor')
        wizard_line_obj = self.pool.get('ppl.move.processor')
        proc_id = wizard_obj.create(cr, uid, {'picking_id': pick_id}, context=context)
        wizard_obj.create_lines(cr, uid, proc_id, context=context)        

        for sline in picking_lines:
            sline = sline[2]
            line_number = sline['line_number']
            
            #### CHECK HOW TO COPY THE LINE IN WIZARD IF THE OUT HAS BEEN SPLIT!
            #### WORK IN PROGRESS
            
            wizard = wizard_obj.browse(cr, uid, proc_id, context=context)
            for mline in wizard.move_ids:
                if mline.line_number == line_number:
                    # match the line, copy the content of picking line into the wizard line
                    vals = {'product_id': sline['product_id'], 'quantity': sline['product_qty'],'location_id': sline['location_id'],
                            'product_uom': sline['product_uom'], 'asset_id': sline['asset_id'], 'prodlot_id': sline['prodlot_id'],
                            'from_pack': sline['from_pack'], 'to_pack': sline['to_pack'],'pack_type': sline['pack_type'],
                            'height': sline['height'], 'weight': sline['weight'],'length': sline['length'], 'width': sline['width'],
                            }
                    
                    wizard_line_obj.write(cr, uid, mline.id, vals, context)
                    break

        self.do_ppl_step1(cr, uid, [proc_id], context=context)
        self.do_ppl_step2(cr, uid, [proc_id], context=context)
        return True

    def sync_create_shipment(self, cr, uid, source, out_info, context=None):
        pick_dict = out_info.to_dict()
        
        if not pick_dict['shipment_id']:
            message = "Sorry the Shipment is invalid in the sync message! The message cannot be processed"
            self._logger.info(message)
            raise Exception, message
        
        shipment_name = pick_dict['shipment_id']['name']
            
        self._logger.info("+++ RW: Create Shipment: %s from %s to %s" % (shipment_name, source, cr.dbname))
        if context is None:
            context = {}

        so_po_common = self.pool.get('so.po.common')
        move_obj = self.pool.get('stock.move')
        pick_tools = self.pool.get('picking.tools')

        message = "Unknown error, please check the log file."
        header_result = {}
        self.retrieve_picking_header_data(cr, uid, source, header_result, pick_dict, context)
        
        # Look for the original PICK based on the origin of OUT and check if this PICK still exists and not closed or converted
        origin = pick_dict['origin']
        rw_type = self._usb_entity_type(cr, uid)
        if rw_type == 'central_platform' and origin:
            pick_ids = self.search(cr, uid, [('origin', '=', origin), ('subtype', '=', 'packing'),('shipment_id', '!=', False), ('state', 'in', ['draft', 'assigned'])], context=context)
            if pick_ids:
                state = pick_dict['state']
                if state in ('done','draft','assigned'):   
                    header_result['move_lines'] = picking_lines
                    context['shipment_name'] = shipment_name
                    num_of_packs = pick_dict['shipment_id']['num_of_packs']
                    self.rw_do_create_shipment(cr, uid, pick_ids[0], num_of_packs, context)
                    
                    old_pick = self.browse(cr, uid, pick_ids[0], context)
                    if old_pick.backorder_id:
                        self.write(cr, uid, old_pick.backorder_id.id, {'already_replicated': True}, context=context) #'name': shipment_name,
                    message = "The PICK: " + old_pick.name + " has been validated and generated a PPL: " + shipment_name
                    self.write(cr, uid, pick_ids[0], {'already_replicated': True}, context=context)
    
            else:
                message = "No valid Packing List found for the Shipment " + shipment_name + " in " + cr.dbname
                self._logger.info(message)
                raise Exception, message
                
        elif rw_type == 'remote_warehouse': 
            message = "Sorry, the given operation is not available for Remote Warehouse instance!"
                
        self._logger.info(message)
        return message

    def rw_do_create_shipment(self, cr, uid, pick_id, num_of_packs, context=None):
        '''
        Create the shipment from an existing draft shipment, then perform the ship
        '''
        
        # from the picking Id, search for the shipment
        
        pick = self.browse(cr, uid, pick_id, context=context)
        
        # Objects
        ship_proc_obj = self.pool.get('shipment.processor')
        ship_proc_vals = {
            'shipment_id': pick.shipment_id.id,
            'address_id': pick.shipment_id.address_id.id,
        }        

        wizard_line_obj = self.pool.get('shipment.family.processor')
        proc_id = ship_proc_obj.create(cr, uid, ship_proc_vals, context=context)
        ship_proc_obj.create_lines(cr, uid, proc_id, context=context)        

        #### CHECK THE CASE WHERE ONE SHIPMENT WIZARD HAS MORE THAN ONE FAMILIES
        #### WORK IN PROGRESS
        
        wizard = ship_proc_obj.browse(cr, uid, proc_id, context=context)
        for family in wizard.family_ids:
            # match the line, copy the content of picking line into the wizard line
            vals = {'selected_number': num_of_packs}
            wizard_line_obj.write(cr, uid, family.id, vals, context)
            break

        self.pool.get('shipment').do_create_shipment(cr, uid, [proc_id], context=context)
        return True

stock_picking()

