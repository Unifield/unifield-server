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

from tools.translate import _

import logging

from sync_common import xmlid_to_sdref


class shipment(osv.osv):
    '''
    Shipment override for Remove Warehouse Tasks
    '''
    _inherit = 'shipment'
    _logger = logging.getLogger('------sync.shipment')

    _columns = {
        'already_rw_delivered': fields.boolean(
            string='Already delivered through the RW - for rw sync. only',
        ),
        'already_rw_validated': fields.boolean(
            string='Already validated through the RW - for rw sync. only',
        ),
        'already_replicated': fields.boolean(string='Already replicated - for sync only'),
    }

    _defaults = {
        'already_rw_delivered': False,
        'already_rw_validated': False,
        'already_replicated': True,
    }

    def usb_set_state_shipment(self, cr, uid, source, out_info, state, context=None):
        '''
        Set the shipment at CP according to the state when it is flagged on RW
        '''
        pick_obj = self.pool.get('stock.picking')

        if context is None:
            context = {}

        ship_dict = out_info.to_dict()
        ship_name = ship_dict['name']
        message = ''

        if state == 'done':
            self._logger.info("+++ RW: Set Delivered the SHIP: %s from %s to %s" % (ship_name, source, cr.dbname))
        elif state == 'shipped':
            self._logger.info("+++ RW: Validated the SHIP: %s from %s to %s" % (ship_name, source, cr.dbname))

        rw_type = pick_obj._get_usb_entity_type(cr, uid)
        if rw_type == pick_obj.CENTRAL_PLATFORM:
            ship_ids = self.search(cr, uid, [('name', '=', ship_name), ('state', '=', state)], context=context)
            if not ship_ids:
                message = _("Sorry, no Shipment with the name %s in state %s found !") % (ship_name, state)
                raise Exception, message # keep this message to not run, because other previous messages in the flow are also not run
            else:
                if state == 'done':
                    self.set_delivered(cr, uid, ship_ids, context=context)
                    self.write(cr, uid, ship_ids, {'already_rw_delivered': True}, context=context)
                elif state == 'shipped':
                    self.validate(cr, uid, ship_ids, context=context)
                    self.write(cr, uid, ship_ids, {'already_rw_validated': True}, context=context)
        else:
            message = ("Sorry, the given operation is only available for Central Platform instance!")
            
        self._logger.info(message)
        return message

    def usb_set_delivered_shipment(self, cr, uid, source, out_info, context=None):
        '''
        Set the shipment as delivered at CP when it is flagged as delivered on RW
        '''
        return self.usb_set_state_shipment(cr, uid, source, out_info, state='done', context=context)

    def usb_set_validated_shipment(self, cr, uid, source, out_info, context=None):
        '''
        Validate the shipment at CP when it is flagged as validated on RW
        '''
        return self.usb_set_state_shipment(cr, uid, source, out_info, state='shipped', context=context)

    def retrieve_shipment_header_data(self, cr, uid, source, header_result, pick_dict, context):
        so_po_common = self.pool.get('so.po.common')
        
        '''
        Need to get all header values for the Ship!
        '''
        
        '''
        if 'name' in pick_dict:
            header_result['name'] = pick_dict.get('name')
        if 'state' in pick_dict:
            header_result['state'] = pick_dict.get('state')
            
'shipper_address/id',
 'address_id/id',
 'date_of_departure',
 'shipment_expected_date',
 'invoice_id/id',
 'consignee_date',
 'shipper_name',
 'carrier_address',
 'registration',
 'planned_date_of_arrival',
 'partner_id',
 'carrier_name',
 'carrier_other',
 'consignee_email',
 'shipment_actual_date',
 'shipper_date',
 'parent_id/id',
 'state'        ,
 'driver_name'   ,
 'cargo_manifest_reference',
 'carrier_signature',
 'shipper_phone'     ,
 'carrier_phone'      ,
 'consignee_signature' ,
 'sequence_id'          ,
 'carrier_email'         ,
 'date',
 'shipper_signature',
 'carrier_date',
 'name'         ,
 'consignee_other',
 'consignee_phone' ,
 'consignee_address',
 'in_ref',
 'transit_via',
 'transport_type',
 'shipper_email',
 'partner_id2/id'   ,
 'shipper_other'  ,
 'consignee_name'  ,
 'transport_order_id/id'
['shipper_address/id','address_id/id','date_of_departure','shipment_expected_date','invoice_id/id', 'consignee_date', 'shipper_name', 'carrier_address', 'registration', 'planned_date_of_arrival', 'partner_id', 'carrier_name', 'carrier_other', 'consignee_email', 'shipment_actual_date', 'shipper_date', 'parent_id/id', 'state', 'driver_name'   , 'cargo_manifest_reference', 'carrier_signature', 'shipper_phone'     , 'carrier_phone'      , 'consignee_signature' , 'sequence_id'          , 'carrier_email'         , 'date', 'shipper_signature', 'carrier_date', 'name'         , 'consignee_other', 'consignee_phone' , 'consignee_address', 'in_ref', 'transit_via', 'transport_type', 'shipper_email', 'partner_id2/id'   , 'shipper_other'  , 'consignee_name'  , 'transport_order_id/id','picking_ids/id']
            
        '''
        if 'name' in pick_dict:
            header_result['name'] = pick_dict.get('name')
        if 'state' in pick_dict:
            header_result['state'] = pick_dict.get('state')
        
        return header_result


    def usb_create_shipment(self, cr, uid, source, ship_info, context=None):
        ship_dict = ship_info.to_dict()
        shipment_name = ship_dict['name']
            
        self._logger.info("+++ RW: Create Shipment: %s from %s to %s" % (shipment_name, source, cr.dbname))
        if context is None:
            context = {}

        search_name = shipment_name
        if 'parent_id' in ship_dict:
            search_name = ship_dict['parent_id']['name']

        message = "Unknown error, please check the log file."
        header_result = {}
        
        # Look for the original PICK based on the origin of OUT and check if this PICK still exists and not closed or converted
        pick_obj = self.pool.get('stock.picking')
        rw_type = pick_obj._get_usb_entity_type(cr, uid)
        if rw_type == pick_obj.CENTRAL_PLATFORM:
            self.retrieve_shipment_header_data(cr, uid, source, header_result, ship_dict, context)
            ship_ids = self.search(cr, uid, [('name', '=', search_name), ('state', 'in', ['draft'])], order='id asc', context=context)
            if ship_ids:
                context['rw_shipment_name'] = shipment_name
                self.rw_do_create_shipment(cr, uid, ship_ids[0], ship_dict, context)
                message = "The shipment: " + shipment_name + " has been successfully created."
            else:
                message = "Cannot generate the Shipment: " + shipment_name + " because no relevant document found at " + cr.dbname
                self._logger.info(message)
                raise Exception, message
                
        elif rw_type == self.REMOTE_WAREHOUSE: 
            message = "Sorry, the given operation is not available for Remote Warehouse instance!"
                
        self._logger.info(message)
        return message

    def rw_do_create_shipment(self, cr, uid, ship_id, ship_dict, context=None): 
        '''
        Create the shipment from an existing draft shipment, then perform the ship
        '''
        # from the picking Id, search for the shipment
        ship = self.browse(cr, uid, ship_id, context=context)
        
        # Objects
        order_line_obj = self.pool.get('sale.order.line')
        ship_proc_obj = self.pool.get('shipment.processor')
        ship_proc_vals = {
            'shipment_id': ship.id,
            'address_id': ship.address_id.id,
        }
        wizard_line_obj = self.pool.get('shipment.family.processor')
        proc_id = ship_proc_obj.create(cr, uid, ship_proc_vals, context=context)
        ship_proc_obj.create_lines(cr, uid, proc_id, context=context)
        wizard = ship_proc_obj.browse(cr, uid, proc_id, context=context)

        pack_families = ship_dict.get('pack_family_memory_ids', False)
        if not pack_families:
            raise Exception, "This Ship " + ship.name + " is empty!"
        
        # Reset the selected packs for shipment, because by a wizard, it sets total pack!
        for family in wizard.family_ids:
            ppl_name = family.ppl_id and family.ppl_id.name or False
            for line in pack_families:
                if ppl_name == line['ppl_id']['name']:
                    selected_number = line['to_pack'] - line['from_pack'] + 1
                    wizard_line_obj.write(cr, uid, [family.id], {'selected_number': selected_number}, context=context)
                    break        

        self.pool.get('shipment').do_create_shipment(cr, uid, [proc_id], context=context)
        return True

 
shipment()

class stock_move(osv.osv):
    # This is to treat the location requestor on Remote warehouse instance if IN comes from an IR
    _inherit = 'stock.move'
    _columns = {'location_requestor_rw': fields.many2one('stock.location', 'Location Requestor For RW-IR', required=False, ondelete="cascade"),
                }

    def create(self, cr, uid, vals, context=None):
        if not context:
            context = {}
        if not vals:
            vals = {}

        # Save the location requestor from IR into the field location_requestor_rw if exists
        res = super(stock_move, self).create(cr, uid, vals, context=context)
        move = self.browse(cr, uid, [res], context=context)[0]
        if move.purchase_line_id:
            proc = move.purchase_line_id.procurement_id
            if proc and proc.sale_order_line_ids and proc.sale_order_line_ids[0].order_id and proc.sale_order_line_ids[0].order_id.procurement_request:
                location_dest_id = proc.sale_order_line_ids[0].order_id.location_requestor_id.id
                if location_dest_id:
                    cr.execute('update stock_move set location_requestor_rw=%s where id=%s', (location_dest_id, move.id))
        
        return res

    def _get_location_for_internal_request(self, cr, uid, context=None, **kwargs):
        '''
            If it is a remote warehouse instance, then take the location requestor from IR
        '''
        location_dest_id = super(stock_move, self)._get_location_for_internal_request(cr, uid, context=context, **kwargs)
        rw_type = self.pool.get('stock.picking')._get_usb_entity_type(cr, uid)
        if rw_type == 'remote_warehouse':
            move = kwargs['move']
            if move.location_requestor_rw:
                return move.location_requestor_rw.id
        # for any case, just return False and let the caller to pick the normal loc requestor
        return location_dest_id

stock_move()

class stock_picking(osv.osv):
    '''
    Stock.picking override for Remote Warehouse tasks
    '''
    _inherit = "stock.picking"
    _logger = logging.getLogger('------sync.stock.picking')

    _columns = {'already_replicated': fields.boolean(string='Already replicated - for sync only'),
                'for_shipment_replicate': fields.boolean(string='To be synced for RW for Shipment - for sync only'),
                'associate_int_name': fields.char('Name of INT associated with the IN', size=256),
                'rw_sdref_counterpart': fields.char('SDRef of the stock picking at the other instance', size=256),
                'rw_force_seq': fields.integer('Force sequence on stock picking in Remote warehouse'),
                }
    _defaults = {'already_replicated': True,
                 'for_shipment_replicate': False,
                 'rw_force_seq': -1,
                 }

    def cancel_moves_before_process(self, cr, uid, pick_ids, context=None):
        if context is None:
            context = {}

        tmp_sme = context.get('sync_message_execution')
        context['sync_message_execution'] = False

        move_obj = self.pool.get('stock.move')
        move_ids = move_obj.search(cr, uid, [('picking_id', 'in', pick_ids), ('state', 'in', ['assigned'])], context=context)
        for move_id in move_ids:
            move_obj.cancel_assign(cr, uid, [move_id], context=context)

        context['sync_message_execution'] = tmp_sme

    def search(self, cr, uid, args, offset=None, limit=None, order=None, context=None, count=False):
        '''
        Change the order if we are on RW synchronisation
        '''
        if context is None:
            context = {}
          
        if context.get('rw_sync_in_progress', False) and not order:
            order = 'id'
    
        return super(stock_picking, self).search(cr, uid, args, offset=offset, limit=limit, order=order, context=context, count=count)

    def retrieve_picking_header_data(self, cr, uid, source, header_result, pick_dict, context):
        so_po_common = self.pool.get('so.po.common')
        
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

        if 'backorder_id' in pick_dict and pick_dict['backorder_id'] and pick_dict['backorder_id']['id']:
            backorder_id = self.find_sd_ref(cr, uid, xmlid_to_sdref(pick_dict['backorder_id']['id']), context=context)
            if backorder_id:
                header_result['backorder_id'] = backorder_id
                
        # get the sdref of the given IN and store it into the new field rw_sdref_counterpart for later retrieval
        header_result['rw_sdref_counterpart'] = so_po_common.get_xml_id_counterpart(cr, uid, self, context=context)        

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
        if 'cross_docking_ok' in pick_dict:
            header_result['cross_docking_ok'] = pick_dict.get('cross_docking_ok')
            
        if 'type' in pick_dict:
            header_result['type'] = pick_dict.get('type')
        if 'subtype' in pick_dict:
            header_result['subtype'] = pick_dict.get('subtype')

        if 'from_wkf' in pick_dict:
            header_result['from_wkf'] = pick_dict.get('from_wkf')
            
        if 'transport_order_id' in pick_dict:
            header_result['transport_order_id'] = pick_dict.get('transport_order_id')

        if 'associate_int_name' in pick_dict:
            header_result['associate_int_name'] = pick_dict.get('associate_int_name')

        if 'date_done' in pick_dict:
            header_result['date_done'] = pick_dict.get('date_done')

        partner_id = so_po_common.get_partner_id(cr, uid, source, context)
        if 'partner_id' in pick_dict:
            partner_id = so_po_common.get_partner_id(cr, uid, pick_dict['partner_id'], context)
        
        location_id = so_po_common.get_location(cr, uid, partner_id, context)
        address_id = so_po_common.get_partner_address_id(cr, uid, partner_id, context)
        header_result['partner_ref'] = source + "." + pick_dict.get('name')
        header_result['partner_id'] = partner_id
        header_result['partner_id2'] = partner_id
        header_result['address_id'] = address_id
        header_result['location_id'] = location_id
        
        # For RW instances, order line ids need to be retrieved and store in the IN and OUT to keep references (via procurement) when making the INcoming via cross docking
        if pick_dict['sale_id'] and pick_dict['sale_id']['id']:
            order_id = pick_dict['sale_id']['id']
            order_id = self.pool.get('sale.order').find_sd_ref(cr, uid, xmlid_to_sdref(order_id), context=context)
            header_result['sale_id'] = order_id

        if pick_dict['purchase_id'] and pick_dict['purchase_id']['id']:
            order_id = pick_dict['purchase_id']['id']
            order_id = self.pool.get('purchase.order').find_sd_ref(cr, uid, xmlid_to_sdref(order_id), context=context)
            header_result['purchase_id'] = order_id
        
        return header_result

    def get_picking_line(self, cr, uid, data, context=None):
        '''
        we format the data, gathering ids corresponding to objects
        '''
        # objects
        uom_obj = self.pool.get('product.uom')
        location_obj = self.pool.get('stock.location')

        # Get the product from ID
        product_id = False
        if data['product_id'] and data['product_id']['id']:
            prod_obj = self.pool.get('product.product')
            product_id = prod_obj.find_sd_ref(cr, uid, xmlid_to_sdref(data['product_id']['id']), context=context)
            
        if not product_id:
            raise Exception, "Product id not found for the given line %s " % data['product_id']

        asset_id = False
        if data['asset_id'] and data['asset_id']['id']:
            asset_id = self.pool.get('product.asset').find_sd_ref(cr, uid, xmlid_to_sdref(data['asset_id']['id']), context=context)
        
        # Get the location requestor
        location_requestor_rw = False
        if 'location_requestor_rw' in data and data.get('location_requestor_rw', False):
            location_requestor_rw = data['location_requestor_rw']['id']
            location_requestor_rw = location_obj.find_sd_ref(cr, uid, xmlid_to_sdref(location_requestor_rw), context=context)
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
                  'product_uos_qty': data['product_uos_qty']  or 0.0, 

                  'prodlot_id': batch_id,
                  'expired_date': expired_date,

                  'location_dest_id': location_dest_id,
                  'location_id': location_id,
                  'location_requestor_rw': location_requestor_rw,
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
                  'picking_id': data.get('picking_id', {}).get('name', False),
                  }
        
        # For RW instances, order line ids need to be retrieved and store in the IN and OUT to keep references (via procurement) when making the INcoming via cross docking
        if data['sale_line_id'] and data['sale_line_id']['id']:
            sale_line_id = data['sale_line_id']['id']
            sale_line_id = self.pool.get('sale.order.line').find_sd_ref(cr, uid, xmlid_to_sdref(sale_line_id), context=context)
            result.update({'sale_line_id': sale_line_id,})

        if data['purchase_line_id'] and data['purchase_line_id']['id']:
            purchase_line_id = data['purchase_line_id']['id']
            purchase_line_id = self.pool.get('purchase.order.line').find_sd_ref(cr, uid, xmlid_to_sdref(purchase_line_id), context=context)
            result.update({'purchase_line_id': purchase_line_id,})
        return result

    def get_picking_lines(self, cr, uid, source, out_info, context=None):
        '''
        package the data to get info concerning already processed or not
        '''
        line_result = []
        if out_info.get('move_lines', False):
            for line in out_info['move_lines']:
                line_data = self.get_picking_line(cr, uid, line, context=context)
                line_result.append((0, 0, line_data))

        return line_result

    def _get_usb_entity_type(self, cr, uid, context=None):
        '''
        Verify if the given instance is Remote Warehouse instance, if no, just return False, if yes, return the type (RW or CP) 
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
        rw_type = self._get_usb_entity_type(cr, uid)
        if rw_type == self.CENTRAL_PLATFORM:
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

    def usb_replicate_picking(self, cr, uid, source, out_info, context=None):
        '''
        '''
        if context is None:
            context = {}

        pick_dict = out_info.to_dict()
        pick_name = pick_dict['name']
        origin = pick_dict['origin']
            
        self._logger.info("+++ RW: Replicate the PICK: %s from %s to %s" % (pick_name, source, cr.dbname))
        rw_type = self._get_usb_entity_type(cr, uid)
        if rw_type == self.REMOTE_WAREHOUSE or 'OUT-CONSO' in pick_name: # if it's a OUT-CONSO, just executing it
            if origin:
                header_result = {}
                self.retrieve_picking_header_data(cr, uid, source, header_result, pick_dict, context)
                picking_lines = self.get_picking_lines(cr, uid, source, pick_dict, context)
                header_result['move_lines'] = picking_lines
                state = header_result['state']
                del header_result['state']
                if 'OUT-CONSO' in pick_name:
                    header_result['state'] = 'assigned' # for CONSO OUT, do not take "done state" -> can't execute workflow later
                
                # Check if the PICK is already there, then do not create it, just inform the existing of it, and update the possible new name
                existing_pick = self.search(cr, uid, [('name', '=', pick_name), ('origin', '=', origin), ('subtype', '=', 'picking'), ('type', '=', 'out'), ('state', '=', 'draft')], context=context)
                if existing_pick:
                    message = "Sorry, the PICK: " + pick_name + " existed already in " + cr.dbname
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
    
#                    if state == 'assigned' and self.browse(cr, uid, pick_id, context=context).state == 'confirmed':
#                        self.force_assign(cr, uid, [pick_id])
                
                # Check if this PICK/OUT comes from a procurement, if yes, then update the move id to the procurement if exists
                if pick_id:
                    proc_obj = self.pool.get('procurement.order')
                    pick = self.browse(cr, uid, pick_id, context=context)
                    for move in pick.move_lines:
                        if move.sale_line_id and move.sale_line_id.procurement_id and move.sale_line_id.procurement_id.id:
                            # check this procurement has already move_id, if not then update
                            proc = proc_obj.read(cr, uid, move.sale_line_id.procurement_id.id, ['move_id'])['move_id']
                            if not proc:
                                proc_obj.write(cr, uid, move.sale_line_id.procurement_id.id, {'move_id': move.id}, context=context)
                
                message = "The PICK: " + pick_name + " has been well replicated in " + cr.dbname
            else:
                message = "Sorry, the case without the origin FO or IR is not yet available!"
                self._logger.info(message)
                raise Exception, message
        else:
            message = "Sorry, the given operation is only available for Remote Warehouse instance!"
            
        self._logger.info(message)
        return message

    # Create a RW message when a Pick is converted to OUT for syncing back to its partner
    def _hook_create_rw_out_sync_messages(self, cr, uid, ids, context=None, out=True):
        if self._get_usb_entity_type(cr, uid) != self.REMOTE_WAREHOUSE:
            return
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        rule_obj = self.pool.get("sync.client.message_rule")
        # Default it's an OUT message
        remote_call = "stock.picking.usb_convert_pick_to_out"
        already_replicated = False
        if not out: # convert to PICK --> do not resend this object again
            already_replicated = True
            remote_call = "stock.picking.usb_convert_out_to_pick"
        rule = rule_obj.get_rule_by_remote_call(cr, uid, remote_call, context)
        
        so_po_common = self.pool.get('so.po.common')
        super(stock_picking, self)._hook_create_rw_out_sync_messages(cr, uid, ids, context=context)
        for pick in self.browse(cr, uid, ids, context=context):
            partner = pick.partner_id
            so_po_common.create_message_with_object_and_partner(cr, uid, rule.sequence_number, pick.id, partner.name, context, True)
        
        # If the PICK got successfully converted to OUT, then reupdate the value already_replicated, for sync purpose
        self.write(cr, uid, ids, {'already_replicated': already_replicated}, context=context)
        

    # WORK IN PROGRESS
    def _hook_delete_rw_out_sync_messages(self, cr, uid, ids, context=None, out=True):
        return

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

            
    def usb_convert_pick_to_out(self, cr, uid, source, out_info, context=None):
        ''' Convert PICK to OUT, normally from RW to CP 
        '''
        pick_dict = out_info.to_dict()
        pick_name = pick_dict['name']
            
        self._logger.info("+++ RW: PICK converted to OUT %s syncs from %s to %s" % (pick_name, source, cr.dbname))
        if context is None:
            context = {}

        # Look for the original PICK based on the origin of OUT and check if this PICK still exists and not closed or converted
        message = "Unknown error, please check the log file"
        origin = pick_dict['origin']
        
        rw_type = self._get_usb_entity_type(cr, uid)
        if rw_type == self.CENTRAL_PLATFORM:
            if origin:
                # look for FO if it is a CP instance
                pick_ids = self.search(cr, uid, [('origin', '=', origin), ('subtype', '=', 'picking'), ('type', '=', 'out'), ('state', '=', 'draft')], context=context)  
                if pick_ids: # This is a real pick in draft, then convert it to OUT
                    old_name = self.read(cr, uid, pick_ids, ['name'], context=context)[0]['name']
                    context['rw_backorder_name'] = pick_name
                    # Before converting to OUT, the PICK needs to be updated as what sent from the RW
                    self.convert_to_standard(cr, uid, pick_ids, context)
                    self.write(cr, uid, pick_ids[0], {'name': pick_name, 'already_replicated': True, 'state': 'assigned'}, context=context)
                    message = "The PICK " + old_name + " has been converted to OUT " + pick_name
                else:
                    pick_ids = self.search(cr, uid, [('origin', '=', origin), ('subtype', '=', 'standard'), ('state', '=', 'assigned')], context=context)
                    if pick_ids:
                        old_name = self.read(cr, uid, pick_ids, ['name'], context=context)[0]['name']
                        message = "The PICK has already been converted to OUT: " + old_name
                
                if pick_ids:
                    picking_lines = self.get_picking_lines(cr, uid, source, pick_dict, context)
                    self.update_original_pick(cr, uid, pick_ids[0], picking_lines, context)
            else:
                message = "Sorry, the case without the origin FO or IR is not yet available!"
                self._logger.info(message)
                raise Exception, message
        elif rw_type == self.REMOTE_WAREHOUSE: 
            message = "Sorry, the given operation is not available for Remote Warehouse instance!"
                
        self._logger.info(message)
        return message

    def usb_convert_out_to_pick(self, cr, uid, source, out_info, context=None):
        ''' Convert OUT to PICK, normally from RW to CP 
        '''
        pick_dict = out_info.to_dict()
        pick_name = pick_dict['name']
            
        self._logger.info("+++ RW: Convert OUT back to PICK (%s), from %s to %s" % (pick_name, source, cr.dbname))
        if context is None:
            context = {}

        # Look for the original PICK based on the origin of OUT and check if this PICK still exists and not closed or converted
        message = "Unknown error, please check the log file."
        origin = pick_dict['origin']
       
        rw_type = self._get_usb_entity_type(cr, uid)
        if rw_type == self.CENTRAL_PLATFORM:
            if origin:
                # look for the OUT if it has already been converted before, using the origin from FO
                pick_ids = self.search(cr, uid, [('origin', '=', origin), ('subtype', '=', 'standard'), ('type', '=', 'out'),('state', 'in', ['draft', 'assigned'])], context=context)  
                if pick_ids: # This is a real pick in draft, then convert it to OUT
                    old_name = self.read(cr, uid, pick_ids, ['name'], context=context)[0]['name']
                    context['rw_backorder_name'] = pick_name
                    # Before converting to OUT, the PICK needs to be updated as what sent from the RW
                    self.convert_to_pick(cr, uid, pick_ids, context)
                    self.write(cr, uid, pick_ids[0], {'name': pick_name, 'already_replicated': True, 'state': 'assigned'}, context=context)
                    message = "The OUT: " + old_name + " has been converted back to PICK: " + pick_name
                else:
                    # If the OUT has already been converted back to PICK before, then just inform this fact
                    pick_ids = self.search(cr, uid, [('origin', '=', origin), ('subtype', '=', 'picking'), ('state', '=', 'assigned')], context=context)
                    if pick_ids:
                        old_name = self.read(cr, uid, pick_ids, ['name'], context=context)[0]['name']
                        message = "The OUT has already been converted to PICK: " + old_name
                    else:
                        message = "The relevant PICK/OUT for the FO: " + origin + " not found for converting."
                        self._logger.info(message)
                        raise Exception, message
            else:
                message = "Sorry, the case without the origin FO or IR is not yet available!"
                self._logger.info(message)
                raise Exception, message
                
            if pick_ids:
                # Should update the lines again? will there be new updates from the OUT converted to PICK? --- TO CHECK, if not do not call the stmt below
                picking_lines = self.get_picking_lines(cr, uid, source, pick_dict, context)
                self.update_original_pick(cr, uid, pick_ids[0], picking_lines, context)
                
        elif rw_type == self.REMOTE_WAREHOUSE: 
            message = "Sorry, the given operation is not available for Remote Warehouse instance!"
                
        self._logger.info(message)
        return message
    
    def usb_closed_out_closes_out(self, cr, uid, source, out_info, context=None):
        ''' There are 2 cases: 
        + If the PICK exists in the current instance, then just convert that pick to OUT, same xmlid
        + If the PICK not present, the a PICK needs to be created first, then convert it to OUT
        + Another case: OUT with Back order, meaning that the original PICK is not directly linked to this OUT, but an existing OUT at local
        '''
        pick_dict = out_info.to_dict()
        pick_name = pick_dict['name']
            
        self._logger.info("+++ RW: OUT closed %s at %s closes the relevant OUT at %s" % (pick_name, source, cr.dbname))
        if context is None:
            context = {}

        # Look for the original PICK based on the origin of OUT and check if this PICK still exists and not closed or converted
        message = "Unknown error, please check the log file."
        origin = pick_dict['origin']
        rw_type = self._get_usb_entity_type(cr, uid)
        if rw_type == self.CENTRAL_PLATFORM:
            if origin:
                header_result = {}
                self.retrieve_picking_header_data(cr, uid, source, header_result, pick_dict, context)
                pick_ids = self.search(cr, uid, [('origin', '=', origin), ('subtype', '=', 'standard'), ('state', 'in', ['confirmed', 'assigned'])], context=context)
                if pick_ids:
                    state = pick_dict['state']
                    if state == 'done':   
                        picking_lines = self.get_picking_lines(cr, uid, source, pick_dict, context)
                        header_result['move_lines'] = picking_lines
                        
                        # do not set if it is a full out closed!
                        if 'backorder_ids' in pick_dict and pick_dict['backorder_ids']:
                            context['rw_backorder_name'] = pick_name
                        else:
                            context['rw_full_process'] = True

                        # UF-2426: Cancel all the Check Availability before performing the partial
                        self.cancel_moves_before_process(cr, uid, pick_ids, context)

                        if header_result.get('date_done', False):
                            context['rw_date'] = header_result.get('date_done')
                        self.action_assign(cr, uid, pick_ids, context=context)
                        if header_result.get('date_done', False):
                            context['rw_date'] = False

                        self.rw_do_out_partial(cr, uid, pick_ids[0], picking_lines, context)
                        
                        message = "The OUT " + pick_name + " has been successfully closed in " + cr.dbname
                        self.write(cr, uid, pick_ids[0], {'already_replicated': True}, context=context)
        
                else:
                    message = "The OUT: " + pick_name + " not found in " + cr.dbname
                    self._logger.info(message)
                    raise Exception, message
            else:
                message = "Sorry, the case without the origin FO or IR is not yet available!"
                self._logger.info(message)
                raise Exception, message
                
        elif rw_type == self.REMOTE_WAREHOUSE: 
            message = "Sorry, the given operation is not available for Remote Warehouse instance!"
                
        self._logger.info(message)
        return message
    
    def rw_do_out_partial(self, cr, uid, out_id, picking_lines, context=None):
        wizard_obj = self.pool.get('outgoing.delivery.processor')
        wizard_line_obj = self.pool.get('outgoing.delivery.move.processor')
        move_obj = self.pool.get('stock.move')
        proc_id = wizard_obj.create(cr, uid, {'picking_id': out_id})
        wizard = wizard_obj.browse(cr, uid, proc_id, context=context)
        
        move_already_checked = []
        move_id = False
        line_data = False
        if wizard.picking_id.move_lines:
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
                move_diff = [x for x in move_ids if x not in move_already_checked]
                if move_ids and move_diff:
                    move_id = list(move_diff)[0]
                elif move_ids:
                    move_id = move_ids[0]
                else:
                    move_id = False
                
                if move_id:
                    move = move_obj.browse(cr, uid, move_id, context=context)
                    if move.id not in move_already_checked:
                        move_already_checked.append(move.id)
                    line_data = wizard_line_obj._get_line_data(cr, uid, wizard, move, context=context)
                    if line_data:
                        vals = {'line_number': line_number,'product_id': sline['product_id'], 'quantity': sline['product_qty'],
                                'location_id': sline['location_id'],'location_dest_id': sline['location_dest_id'],
                                'ordered_quantity': sline['product_qty'],
                                'uom_id': sline['product_uom'], 'asset_id': sline['asset_id'], 'prodlot_id': sline['prodlot_id'],
                                'move_id': move_id, 'wizard_id': wizard.id, 'composition_list_id':line_data['composition_list_id'],
                                'cost':line_data['cost'],'currency':line_data['currency'],
                                }
                        wizard_line_obj.create(cr, uid, vals, context=context)

        self.do_partial(cr, uid, [proc_id], 'outgoing.delivery.processor', context=context)
        return True

    def usb_create_picking(self, cr, uid, source, out_info, context=None):
        '''
        This is the PICK with format PICK00x-y, meaning the PICK00x-y got closed making the backorder PICK got updated (return products
        into this backorder PICK)
        '''
        pick_dict = out_info.to_dict()
        pick_name = pick_dict['name']
            
        self._logger.info("+++ RW: Replicate Picking: %s from %s to %s" % (pick_name, source, cr.dbname))
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
                same_ids = self.search(cr, uid, [
                    ('name', '=', pick_name),
                    ('origin', '=', origin),
                    ('subtype', '=', 'picking'),
                    ('state', 'in', ['assigned', 'draft']),
                ], context=context)
                if same_ids:
                    message = "The Picking: " + pick_name + " is already replicated in " + cr.dbname
                    self._logger.info(message)
                    return message

                pick_ids = self.search(cr, uid, [('origin', '=', origin), ('subtype', '=', 'picking'), ('state', 'in', ['draft'])], context=context)
                if not pick_ids:
                    pick_ids = self.search(cr, uid, [('origin', '=', origin), ('subtype', '=', 'picking'), ('state', 'in', ['draft','confirmed', 'assigned'])], context=context)
                if pick_ids:
                    state = pick_dict['state']
                    if state in ('done', 'assigned'):   
                        picking_lines = self.get_picking_lines(cr, uid, source, pick_dict, context)
                        header_result['move_lines'] = picking_lines
#                        self.force_assign(cr, uid, pick_ids)
                        context['rw_backorder_name'] = pick_name
                        if header_result.get('date_done', False):
                            context['rw_date'] = header_result.get('date_done')
                            
                        self.cancel_moves_before_process(cr, uid, [pick_ids[0]], context=context)
#                        self.action_assign(cr, uid, [pick_ids[0]], context=context)
                            
                        self.rw_do_create_picking_partial(cr, uid, pick_ids[0], picking_lines, context)
                        if header_result.get('date_done', False):
                            context['rw_date'] = False
                        
                        message = "The Picking " + pick_name + " has been successfully replicated in " + cr.dbname
                        self.write(cr, uid, pick_ids[0], {'already_replicated': True}, context=context)
        
                else:
                    message = "The Picking: " + pick_name + " not found in " + cr.dbname
                    self._logger.info(message)
                    raise Exception, message
            else:
                message = "Sorry, the case without the origin FO or IR is not yet available!"
                self._logger.info(message)
                raise Exception, message
                
        elif rw_type == self.REMOTE_WAREHOUSE: 
            message = "Sorry, the given operation is not available for Remote Warehouse instance!"
                
        self._logger.info(message)
        return message

    def rw_do_create_picking_partial(self, cr, uid, pick_id, picking_lines, context=None):
        """

        :rtype : object
        """
        wizard_obj = self.pool.get('create.picking.processor')
        wizard_line_obj = self.pool.get('create.picking.move.processor')
        proc_id = wizard_obj.create(cr, uid, {'picking_id': pick_id}, context=context)

        wizard = wizard_obj.browse(cr, uid, proc_id, context=context)

        # Check how many lines the wizard has, to make it mirror with the lines received from the sync        
        # Check if the number of moves of the wizard is different with the number of received PPL --> recreate a new lines
        move_already_checked = []
        move_id = False
        line_data = False

        if wizard.picking_id.move_lines:
            for sline in picking_lines:
                sline = sline[2]            
                line_number = sline['line_number']
                if not sline['product_qty'] or sline['product_qty'] == 0.00:
                    continue
                
                for move in wizard.picking_id.move_lines:
                    if move.line_number == line_number:
                        if move.id not in move_already_checked:
                            move_id = move.id
                            move_already_checked.append(move.id) # this move id will not be picked in the next search when creating lines
                            line_data = wizard_line_obj._get_line_data(cr, uid, wizard, move, context=context)
                            break

                if move_id and line_data:
                    vals = {'line_number': line_number,'product_id': sline['product_id'], 'quantity': sline['product_qty'],
                            'location_id': sline['location_id'],'location_dest_id': sline['location_dest_id'],
                            'ordered_quantity': sline['product_qty'],
                            'uom_id': sline['product_uom'], 'asset_id': sline['asset_id'], 'prodlot_id': sline['prodlot_id'],
                            'move_id': move_id, 'wizard_id': wizard.id, 'composition_list_id':line_data['composition_list_id'],
                            'cost':line_data['cost'],'currency':line_data['currency'],
                            }

                    wizard_line_obj.create(cr, uid, vals, context=context)

        line_to_del = wizard_line_obj.search(cr, uid, [('wizard_id', '=', proc_id), ('quantity', '=', 0.00)], context=context)
        if line_to_del:
            wizard_line_obj.unlink(cr, uid, line_to_del, context=context)

        self.do_create_picking(cr, uid, [proc_id], context=context)
        return True

    def usb_replicate_ppl(self, cr, uid, source, out_info, context=None):
        pick_dict = out_info.to_dict()
        pick_name = pick_dict['name']
            
        self._logger.info("+++ RW: Replicate the PPL: %s from %s to %s" % (pick_name, source, cr.dbname))
        if context is None:
            context = {}
        message = "Unknown error, please check the log file."
        
        # Look for the original PICK based on the origin of OUT and check if this PICK still exists and not closed or converted
        origin = pick_dict['origin']
        rw_type = self._get_usb_entity_type(cr, uid)
        pack_name = pick_dict['previous_step_id'] and pick_dict['previous_step_id']['name'] or None
        if rw_type == self.CENTRAL_PLATFORM:
            if origin:
                header_result = {}
                self.retrieve_picking_header_data(cr, uid, source, header_result, pick_dict, context)
                search_name = [('origin', '=', origin), ('subtype', '=', 'picking'), ('state', 'in', ['confirmed', 'assigned'])]
                if pack_name:
                    search_name.append(('name', '=', pack_name))
                pick_ids = self.search(cr, uid, search_name, context=context)
                if pick_ids:
                    state = pick_dict['state']
                    if state in ('done', 'assigned'):   
                        picking_lines = self.get_picking_lines(cr, uid, source, pick_dict, context)
                        header_result['move_lines'] = picking_lines
#                        self.force_assign(cr, uid, pick_ids)
                        context['rw_backorder_name'] = pick_name
                        self.rw_do_validate_picking(cr, uid, pick_ids[0], picking_lines, context)
                        
                        old_pick = self.browse(cr, uid, pick_ids[0], context)
                        if old_pick.backorder_id:
                            self.write(cr, uid, old_pick.backorder_id.id, {'already_replicated': True}, context=context) #'name': pick_name,
                        message = "The PICK: " + old_pick.name + " has been successfully validated and has generated the PPL: " + pick_name
                        self.write(cr, uid, pick_ids[0], {'already_replicated': True}, context=context)
                        
                    # perform right a way the validate Picking to set pack and size of pack
                    pick_ids = self.search(cr, uid, [('origin', '=', origin), ('subtype', '=', 'ppl'), ('state', 'in', ['confirmed', 'assigned'])], context=context)
                    pick_id = False
                    for pick in pick_ids:
                        if not self.pool.get('ppl.processor').search(cr, uid, [('picking_id', '=', pick)]):
                            pick_id = pick
                            break
                    if pick_id:
                        state = pick_dict['state']
                        if state in ('done','draft','assigned'):   
                            self.rw_create_ppl_step_1_only(cr, uid, pick_id, picking_lines, context)
                            
                            message = "The pre-packing list: " + pick_name + " has been replicated in " + cr.dbname
                            self.write(cr, uid, pick_id, {'already_replicated': True}, context=context)
            
                    else:
                        message = "Cannot replicate the packing " + pick_name + " because no relevant document found at " + cr.dbname
                        self._logger.info(message)
                        raise Exception, message
        
                else:
                    message = "Cannot replicate the PPL " + pick_name + " because no relevant document found at " + cr.dbname
                    self._logger.info(message)
                    raise Exception, message
            else:
                message = "Sorry, the case without the origin FO or IR is not yet available!"
                self._logger.info(message)
                raise Exception, message

        elif rw_type == self.REMOTE_WAREHOUSE: 
            message = "Sorry, the given operation is not available for Remote Warehouse instance!"
                
        self._logger.info(message)
        return message

    def rw_do_validate_picking(self, cr, uid, pick_id, picking_lines, context=None):
        # Objects
        wizard_obj = self.pool.get('validate.picking.processor')
        proc_id = wizard_obj.create(cr, uid, {'picking_id': pick_id}, context=context)
        wizard = wizard_obj.browse(cr, uid, proc_id, context=context)
        line_obj = self.pool.get(wizard._columns['move_ids']._obj)
        
        # Make the full quantity process for this PICK to PPL
        for move in wizard.picking_id.move_lines:
            if move.state in ('draft', 'done', 'cancel', 'confirmed') or  move.product_qty == 0.00 :
                continue

            line_data = line_obj._get_line_data(cr, uid, wizard, move, context=context)
            line_data['product_qty'] = move.product_qty
            line_data['quantity'] = move.product_qty
            ret = line_obj.create(cr, uid, line_data, context=context)

        self.do_validate_picking(cr, uid, [proc_id], context=context)
        return True

    def usb_create_packing(self, cr, uid, source, out_info, context=None):
        pick_dict = out_info.to_dict()
        pick_name = pick_dict['name']
            
        self._logger.info("+++ RW: Replicate the Packing list: %s from %s to %s" % (pick_name, source, cr.dbname))
        if context is None:
            context = {}
        message = "Unknown error, please check the log file."
        header_result = {}
        
        # Look for the original PICK based on the origin of OUT and check if this PICK still exists and not closed or converted
        origin = pick_dict['origin']
        shipment_name = pick_dict['shipment_id'] and pick_dict['shipment_id']['name'] or None
        ppl_name = pick_dict['previous_step_id'] and pick_dict['previous_step_id']['name'] or None
        
        rw_type = self._get_usb_entity_type(cr, uid)
        if rw_type == self.CENTRAL_PLATFORM:
            if origin:
                self.retrieve_picking_header_data(cr, uid, source, header_result, pick_dict, context)
                search_name = [('origin', '=', origin), ('subtype', '=', 'ppl'), ('state', 'in', ['confirmed', 'assigned'])]
                if ppl_name:
                    search_name.append(('name', '=', ppl_name))
                pick_ids = self.search(cr, uid, search_name, context=context)
                if pick_ids:
                    state = pick_dict['state']
                    if state in ('done','draft','assigned'):   
                        picking_lines = self.get_picking_lines(cr, uid, source, pick_dict, context)
                        header_result['move_lines'] = picking_lines
                        context['rw_shipment_name'] = shipment_name
                        self.rw_ppl_step_2_only(cr, uid, pick_ids[0], picking_lines, context)
                        
                        message = "The pre-packing list: " + pick_name + " has been replicated in " + cr.dbname
                        self.write(cr, uid, pick_ids[0], {'already_replicated': True}, context=context)
        
                else:
                    message = "Cannot replicate the packing " + pick_name + " because no relevant document found at " + cr.dbname
                    self._logger.info(message)
                    raise Exception, message
            else:
                message = "Sorry, the case without the origin FO or IR is not yet available!"
                self._logger.info(message)
                raise Exception, message
                
        elif rw_type == self.REMOTE_WAREHOUSE: 
            message = "Sorry, the given operation is not available for Remote Warehouse instance!"
                
        self._logger.info(message)
        return message

    def rw_create_ppl_step_1_only(self, cr, uid, pick_id, picking_lines, context=None):
        '''
        Prepare the wizard for 2 steps of creating packing: pack family and size/weight of the pack
        '''
        wizard_obj = self.pool.get('ppl.processor')
        wizard_line_obj = self.pool.get('ppl.move.processor')
        family_obj = self.pool.get('ppl.family.processor')
        
        proc_id = wizard_obj.create(cr, uid, {'picking_id': pick_id}, context=context)
        wizard = wizard_obj.browse(cr, uid, proc_id, context=context)
        
        # Check how many lines the wizard has, to make it mirror with the lines received from the sync        
        # Check if the number of moves of the wizard is different with the number of received PPL --> recreate a new lines
        move_already_checked = []
        move_id = False
        line_data = False
        if wizard.picking_id.move_lines:
            for sline in picking_lines:
                sline = sline[2]            
                line_number = sline['line_number']
                if not sline['from_pack'] or not sline['to_pack']:
                    continue
                for move in wizard.picking_id.move_lines:
                    if move.line_number == line_number:
                        if move.id not in move_already_checked:
                            move_id = move.id
                            move_already_checked.append(move.id) # this move id will not be picked in the next search when creating lines
                            line_data = wizard_line_obj._get_line_data(cr, uid, wizard, move, context=context)
                            break
                
                if move_id and line_data:
                    vals = {'line_number': line_number,'product_id': sline['product_id'], 'quantity': sline['product_qty'],
                            'location_id': sline['location_id'],'location_dest_id': sline['location_dest_id'],
                            'ordered_quantity': sline['product_qty'],
                            'uom_id': sline['product_uom'], 'asset_id': sline['asset_id'], 'prodlot_id': sline['prodlot_id'],
                            'from_pack': sline['from_pack'], 'to_pack': sline['to_pack'],'pack_type': sline['pack_type'],
                            'move_id': move_id, 'wizard_id': wizard.id, 'composition_list_id':line_data['composition_list_id'],
                            'cost':line_data['cost'],'currency':line_data['currency'],
                            }
                    wizard_line_obj.create(cr, uid, vals, context=context)

        self.do_ppl_step1(cr, uid, [proc_id], context=context)
        
        # Simulate the setting of size of pack before executing step 2
        for sline in picking_lines:
            sline = sline[2]            
            from_pack = sline['from_pack']
            to_pack = sline['to_pack']
        
            for family in wizard.family_ids:
                # Only pack "from" and "to" can allow to identify the family! 
                if family.from_pack == from_pack and family.to_pack == to_pack:  
                    values = {
                        'length': sline['length'],
                        'width': sline['width'],
                        'height': sline['height'],
                        'weight': sline['weight'],
                    }        
                    family_obj.write(cr, uid, [family.id], values, context=context)
        
        return True

    def rw_ppl_step_2_only(self, cr, uid, pick_id, picking_lines, context=None):
        '''
        Prepare the wizard for 2 steps of creating packing: pack family and size/weight of the pack
        '''
        wizard_obj = self.pool.get('ppl.processor')
        proc_id = wizard_obj.search(cr, uid, [('picking_id','=', pick_id)], context=context)
        if proc_id:
            proc_id = proc_id[0]
        else:
            proc_id = wizard_obj.create(cr, uid, {'picking_id': pick_id}, context=context)
            wizard_obj.create_lines(cr, uid, proc_id, context=context)        

        self.do_ppl_step2(cr, uid, [proc_id], context=context)
        return True
    
stock_picking()
