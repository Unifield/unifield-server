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
        if context is None:
            context = {}

        ship_dict = out_info.to_dict()
        ship_name = ship_dict['name']
        message = ''

        if state == 'done':
            self._logger.info("+++ RW: Set Delivered the SHIP: %s from %s to %s" % (ship_name, source, cr.dbname))
        elif state == 'shipped':
            self._logger.info("+++ RW: Validated the SHIP: %s from %s to %s" % (ship_name, source, cr.dbname))

        ship_ids = self.search(cr, uid, [('name', '=', ship_name), ('state', '=', state)], context=context)
        if not ship_ids:
            ship_ids = self.search(cr, uid, [('name', '=', ship_name), ('state', '=', "delivered")], context=context)
            if ship_ids:
                message = _("The Shipment %s is already in delivered state!") % (ship_name)
            else:
                # UF-2531: Check if this Ship is already in closed state --> just inform and ignore
                ship_ids = self.search(cr, uid, [('name', '=', ship_name), ('state', '=', "done")], context=context)
                if ship_ids:
                    message = _("The Shipment %s is already in closed state!") % (ship_name)
                else:
                    message = _("Sorry, no Shipment with the name %s in state %s found !") % (ship_name, state)
                    raise Exception, message # keep this message to not run, because other previous messages in the flow are also not run
        else:
            if state == 'done':
                self.set_delivered(cr, uid, ship_ids, context=context)
                self.write(cr, uid, ship_ids, {'already_rw_delivered': True}, context=context)
                message = _("The Shipment %s is set to delivered!") % (ship_name)
            elif state == 'shipped':
                self.validate(cr, uid, ship_ids, context=context)
                self.write(cr, uid, ship_ids, {'already_rw_validated': True}, context=context)
                message = _("The Shipment %s is set to closed!") % (ship_name)

        self._logger.info(message)
        return message

    def _manual_create_rw_shipment_message(self, cr, uid, res_id, return_info, rule_method, context=None):
        rule_obj = self.pool.get("sync.client.message_rule")
        rule_obj._manual_create_rw_message(cr, uid, self._name, res_id, return_info, rule_method, self._logger, context=context)

    #UF-2531: Create packs return for the shipment
    def usb_shipment_return_packs(self, cr, uid, source, out_info, context=None):
        '''
        Method to return packs from a shipped Shipment from RW
        '''
        if context is None:
            context = {}

        pick_obj = self.pool.get('stock.picking')
        rw_type = pick_obj._get_usb_entity_type(cr, uid)
        if rw_type != pick_obj.CENTRAL_PLATFORM:
            message = "Sorry, the given operation is not available for Remote Warehouse instance!"
            self._logger.info(message)
            return message

        state='shipped'
        ship_dict = out_info.to_dict()
        ship_name = ship_dict['name']
        ppl = ship_dict['picking']

        self._logger.info("+++ RW: The Ship %s has packs returned" % (ship_name))
        ship_ids = self.search(cr, uid, [('name', '=', ship_name), ('state', '=', state)], context=context)
        if not ship_ids or not ppl:
            message = "Sorry, no Ship %s in state shipped available or invalid packing list for making the return packs!" % (ship_name)
            self._logger.info(message)
            return message

        message = 'The Ship %s has the following packs returned: ' % (ship_name)
        # UF-2531: Create processor for return packs in Shipment
        proc_obj = self.pool.get('return.pack.shipment.processor')
        processor_id = proc_obj.create(cr, uid, {'shipment_id': ship_ids[0]}, context=context)
        proc_obj.create_lines(cr, uid, processor_id, context=context)
        family_obj = self.pool.get('return.pack.shipment.family.processor')

        for wizard in proc_obj.browse(cr, uid, [processor_id], context=context):
            for family in wizard.family_ids:
                # check the family with ppl_id, pack_from and pack_to to find the correct line
                for pack in ppl:
                    pack_fam_sync = ppl[pack]
                    ppl_name = pack_fam_sync['name']
                    if ppl_name == family.ppl_id.name and family.from_pack == pack_fam_sync['from_pack'] and family.to_pack == pack_fam_sync['to_pack']:
                        message += "%s (return: %s --> %s), " % (ppl_name, pack_fam_sync['return_from'], pack_fam_sync['return_to'])
                        # This is the correct pack family --> update the return from and to packs
                        family_obj.write(cr, uid, [family.id], {
                            'return_from': pack_fam_sync['return_from'],
                            'return_to': pack_fam_sync['return_to'],
                        }, context=context)
                        break

        # Now process this return by call the method
        proc_obj.do_return_pack_from_shipment(cr, uid, processor_id, context=context)

        message += ". The operation has successfully executed"
        self._logger.info(message)
        return message

    #UF-2531: Create packs return for the shipment in draft state --> packs will be put back into the PICK object
    def usb_shipment_return_packs_shipment_draft(self, cr, uid, source, out_info, context=None):
        '''
        Method to return packs from a shipped Shipment from RW
        '''
        if context is None:
            context = {}

        pick_obj = self.pool.get('stock.picking')
        rw_type = pick_obj._get_usb_entity_type(cr, uid)
        if rw_type != pick_obj.CENTRAL_PLATFORM:
            message = "Sorry, the given operation is not available for Remote Warehouse instance!"
            self._logger.info(message)
            return message

        state='draft'
        ship_dict = out_info.to_dict()
        ship_name = ship_dict['name']
        draft_pack = ship_dict['picking']

        self._logger.info("+++ RW: The Ship %s has packs returned to picking objects" % (ship_name))
        ship_ids = self.search(cr, uid, [('name', '=', ship_name), ('state', '=', state)], context=context)
        if not ship_ids or not draft_pack:
            message = "Sorry, no Ship %s in state draft available or invalid pick document for making the return packs!" % (ship_name)
            self._logger.info(message)
            return message

        message = 'The Ship %s has the following packs returned: ' % (ship_name)
        # UF-2531: Create processor for return packs in Shipment
        proc_obj = self.pool.get('return.shipment.processor')
        processor_id = proc_obj.create(cr, uid, {'shipment_id': ship_ids[0]}, context=context)
        proc_obj.create_lines(cr, uid, processor_id, context=context)
        family_obj = self.pool.get('return.shipment.family.processor')
        #return.shipment.family.processor
        #pack.family.memory

        for wizard in proc_obj.browse(cr, uid, [processor_id], context=context):
            for family in wizard.family_ids:
                draft_picking = family.ppl_id and family.ppl_id.previous_step_id and family.ppl_id.previous_step_id.backorder_id or False

                # check the family with ppl_id, pack_from and pack_to to find the correct line
                for pack in draft_pack:
                    pack_fam_sync = draft_pack[pack]
                    ppl_name = pack_fam_sync['name']

                    if ppl_name == draft_picking.name and family.from_pack == pack_fam_sync['from_pack'] and family.to_pack == pack_fam_sync['to_pack']:
                        message += "%s (number of packs returned: %s), " % (ppl_name, pack_fam_sync['selected_number'])
                        # This is the correct pack family --> update the return from and to packs
                        family_obj.write(cr, uid, [family.id], {
                            'selected_number': pack_fam_sync['selected_number'],
                        }, context=context)
                        break

        # Now process this return by call the method
        proc_obj.do_return_packs(cr, uid, processor_id, context=context)

        message += ". The operation has successfully executed"
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
        '''
        Need to get all header values for the Ship!
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
        if context is None:
            context = {}
        # from the picking Id, search for the shipment
        ship = self.browse(cr, uid, ship_id, context=context)

        # Objects
        ship_proc_obj = self.pool.get('shipment.processor')
        ship_proc_vals = {
            'shipment_id': ship.id,
            'address_id': ship.address_id.id,
        }
        pack_families = ship_dict.get('pack_family_memory_ids', False)
        if not pack_families:
            raise Exception, "This Ship " + ship.name + " is empty!"

        # US-803: point 9: If the ship contains description, add it to the context and will be added while creating the ship
        # description is "cloned" to all ship lines, so just only get once
        for line in pack_families:
            if line['description_ppl']:
                context['description_ppl'] = line['description_ppl']
                break

        wizard_line_obj = self.pool.get('shipment.family.processor')
        proc_id = ship_proc_obj.create(cr, uid, ship_proc_vals, context=context)
        ship_proc_obj.create_lines(cr, uid, proc_id, context=context)
        wizard = ship_proc_obj.browse(cr, uid, proc_id, context=context)

        for family in wizard.family_ids:
            wizard_line_obj.write(cr, uid, [family.id], {'selected_number': 0,}, context=context)

        # Reset the selected packs for shipment, because by a wizard, it sets total pack!
        for family in wizard.family_ids:
            ppl_name = family.ppl_id and family.ppl_id.name or False
            for line in pack_families:
                #UF-2531, point 4): Added more check from the pack info to make sure to pick the right line
                if ppl_name == line['ppl_id']['name'] and line['from_pack'] >= family.from_pack and line['to_pack'] <= family.to_pack:
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
                'associate_pick_name': fields.char('Name of INT associated with the IN', size=256),
                'rw_sdref_counterpart': fields.char('SDRef of the stock picking at the other instance', size=256),
                'rw_force_seq': fields.integer('Force sequence on stock picking in Remote warehouse'),
                }
    _defaults = {'already_replicated': True,
                 'for_shipment_replicate': False,
                 'rw_force_seq': -1,
                 }

    #US-803: Tricky case: when saving the ship description, if the ship message has not been sent, this description must be completed into the message!
    def change_description_save(self, cr, uid, ids, context=None):
        # Check if there is any ship message UNSENT related to this picking
        picks = self.browse(cr, uid, ids, context=context)
        if picks and picks[0]:
            # get the current pick which has been changed in description
            pick = picks[0]
            usb_entity = self._get_usb_entity_type(cr, uid)
            if pick and pick.shipment_id and usb_entity == self.REMOTE_WAREHOUSE:  # only special handle when it's in RW
                # Now, check if there is any sync message UNSENT for this shipment
                msg_to_send_obj = self.pool.get("sync_remote_warehouse.message_to_send")
                remote_call = "shipment.usb_create_shipment"
                # Get only the unsent ships, normal there should be a minimum numbers of msg unsent
                shipmsgs = msg_to_send_obj.search(cr, uid, [('remote_call', '=', remote_call), ('sent', '=', False)], context=context)
                for s in shipmsgs:
                    identifier = msg_to_send_obj.read(cr, uid, s, ['identifier'])['identifier']
                    # build the identifier for the given pick
                    shipment_name = "shipment/" + str(pick.shipment_id.id) + "/RW_"
                    if shipment_name in identifier:
                        # if it's related to the current pick, then start to update the message
                        arguments = msg_to_send_obj.read(cr, uid, s, ['arguments'])['arguments']
                        st = arguments.find('\'description_ppl\': False')
                        if st >= 0:  # if the original description is empty, normally on creation of the message, then search for text with False
                            old_desc = '\'description_ppl\': False'
                        else:
                            # otherwise, search for the old desc
                            st = arguments.find('\'description_ppl\': ')
                            ende = arguments.find('\',',st)
                            old_desc = arguments[st:ende + 1]

                        # build the new desc, if it's empty -> False
                        new_desc = '\'description_ppl\': False'
                        if pick.details:
                            new_desc = '\'description_ppl\': \'' + pick.details + '\''

                        # replace the desc in argument and save it into the message
                        arguments = arguments.replace(old_desc, new_desc)
                        msg_to_send_obj.write(cr, uid, s, {'arguments': arguments}, context=context)
                        break  # One pick is only valid for one ship, no need to go further

        return super(stock_picking, self).change_description_save(cr, uid, ids, context=context)

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

        return super(stock_picking, self).search(cr, uid, args, offset=offset,
                                                 limit=limit, order=order, context=context, count=count)

    #UF-2531: The last param for the case no need to check for partner, such as the case of INT from scratch created at RW
    def retrieve_picking_header_data(self, cr, uid, source, header_result, pick_dict, context, need_partner_check=True):
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

        if 'associate_pick_name' in pick_dict:
            header_result['associate_pick_name'] = pick_dict.get('associate_pick_name')

        if 'date_done' in pick_dict:
            header_result['date_done'] = pick_dict.get('date_done')

        partner_id = False
        # UF-2531: If no partner is needed for checking, then do not perform the following check -- INT from scratch from RW to CP
        if need_partner_check and pick_dict.get('partner_id', False):
            partner_id = so_po_common.get_partner_id(cr, uid, source, context)
            if 'partner_id' in pick_dict:
                partner_id = so_po_common.get_partner_id(cr, uid, pick_dict['partner_id'], context)
            header_result['partner_id'] = partner_id
            header_result['partner_id2'] = partner_id
            address_id = so_po_common.get_partner_address_id(cr, uid, partner_id, context)
            header_result['address_id'] = address_id

        location_id = so_po_common.get_location(cr, uid, partner_id, context)
        header_result['partner_ref'] = source + "." + pick_dict.get('name')
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

        # US-803: point 20. Added the price currency for IN line
        if data['price_currency_id'] and data['price_currency_id']['id']:
            self.pool.get('res.currency').find_sd_ref(cr, uid, xmlid_to_sdref(data['price_currency_id']['id']), context=context)

        if data['reason_type_id'] and data['reason_type_id']['id']:
            reason_type_id = self.pool.get('stock.reason.type').find_sd_ref(cr, uid, xmlid_to_sdref(data['reason_type_id']['id']), context=context)
        else:
            raise Exception, "Reason Type at line cannot be empty"

        uom_name = data['product_uom']['name']
        uom_ids = uom_obj.search(cr, uid, [('name', '=', uom_name)], context=context)
        if not uom_ids:
            raise Exception, "The corresponding uom does not exist here. Uom name: %s" % uom_name
        uom_id = uom_ids[0]

        # US-838: RW, need to check the new mechanism of the BN and ED object!!!!!!!
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

        if data['price_unit']: # if the cost price got changed from RW
            result.update({'price_unit': data['price_unit'],})

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
        if not entity.__hasattr__('usb_instance_type'):
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
                existing_pick = self.search(cr, uid, [('name', '=', pick_name),
                                                      ('origin', '=', origin), ('subtype', '=', 'picking'),
                                                      ('type', '=', 'out'), ('state', '=', 'draft')],
                                            limit=1, order='NO_ORDER', context=context)
                if existing_pick:
                    message = "Sorry, the document: " + pick_name + " existed already in " + cr.dbname
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

                message = "The document: " + pick_name + " has been well replicated in " + cr.dbname
            else:
                message = "Sorry, the case without the origin FO or IR is not yet available!"
                self._logger.info(message)
                raise Exception, message
        elif rw_type == self.CENTRAL_PLATFORM  and not origin and 'OUT' in pick_name and 'RW' in pick_name: #US-702: sync also the OUT from scratch, no link to IR/FO
            existing_pick = self.search(cr, uid, [('name', '=', pick_name),
                                                  ('subtype', '=', 'picking'), ('type', '=', 'out'),
                                                  ('state', '=', 'draft')], limit=1, order='NO_ORDER', context=context)
            if existing_pick:
                message = "Sorry, the OUT: " + pick_name + " existed already in " + cr.dbname
                self._logger.info(message)
                return message

            header_result = {}
            self.retrieve_picking_header_data(cr, uid, source, header_result, pick_dict, context)
            picking_lines = self.get_picking_lines(cr, uid, source, pick_dict, context)
            header_result['move_lines'] = picking_lines
            state = header_result['state']
            del header_result['state']

            pick_id = self.create(cr, uid, header_result , context=context)
            if state != 'draft': # if draft, do nothing
                wf_service = netsvc.LocalService("workflow")
                wf_service.trg_validate(uid, 'stock.picking', pick_id, 'button_confirm', cr)
                if header_result.get('date_done', False):
                    context['rw_date'] = header_result.get('date_done')
                self.action_assign(cr, uid, [pick_id], context=context)
                if header_result.get('date_done', False):
                    context['rw_date'] = False

            message = "The OUT: " + pick_name + " has been well replicated in " + cr.dbname
        else:
            message = "Sorry, this case is not available!"
            self._logger.info(message)
            raise Exception, message

        self._logger.info(message)
        return message

    # Create a RW message when a Pick is converted to OUT for syncing back to its partner
    def _hook_create_rw_out_sync_messages(self, cr, uid, ids, context=None, out=True):
        if self._get_usb_entity_type(cr, uid) != self.REMOTE_WAREHOUSE:
            return
        if isinstance(ids, (int, long)):
            ids = [ids]
        context = context or {}

        rule_obj = self.pool.get("sync.client.message_rule")
        # Default it's an OUT message
        remote_call = "stock.picking.usb_convert_pick_to_out"
        already_replicated = False
        if not out: # convert to PICK --> do not resend this object again
            already_replicated = True
            remote_call = "stock.picking.usb_convert_out_to_pick"
        rule = rule_obj.get_rule_by_remote_call(cr, uid, remote_call, context)

        original_name = ''
        if 'original_name' in context:
            original_name = context.get('original_name', '')

        # If the PICK got successfully converted to OUT, then reupdate the value already_replicated, for sync purpose
        self.write(cr, uid, ids, {'already_replicated': already_replicated, 'associate_pick_name': original_name}, context=context)
        self._manual_create_rw_messages(cr, uid, context=context)

        so_po_common = self.pool.get('so.po.common')
        super(stock_picking, self)._hook_create_rw_out_sync_messages(cr, uid, ids, context=context)
        for pick in self.browse(cr, uid, ids, context=context):
            partner = pick.partner_id
            so_po_common.create_message_with_object_and_partner(cr, uid, rule.sequence_number, pick.id, partner, context, True)

    def _manual_create_rw_picking_message(self, cr, uid, res_id, return_info, rule_method, context=None):
        rule_obj = self.pool.get("sync.client.message_rule")
        rule_obj._manual_create_rw_message(cr, uid, self._name, res_id, return_info, rule_method, self._logger, context=context)

    # UF-2531: Create RW messages manually to keep the content of these messages correctly -- avoid the values have been changed by the return pack, convert PICK/OUT
    def _manual_create_rw_messages(self, cr, uid, context=None):
        context = context or {}
        entity = self.pool.get('sync.client.entity').get_entity(cr, uid, context)

        rw_type = self._get_usb_entity_type(cr, uid)
        if rw_type == self.CENTRAL_PLATFORM:
            return

        message_pool = self.pool.get('sync_remote_warehouse.message_to_send')
        rule_pool = self.pool.get("sync.client.message_rule")
        messages_count = 0
        message_direction = entity.usb_instance_type == 'central_platform' and \
            ['|', ('direction_usb', '=', 'cp_to_rw'), ('direction_usb', '=', 'bidirectional')] or \
            ['|', ('direction_usb', '=', 'rw_to_cp'), ('direction_usb', '=', 'bidirectional')]
        rule_ids = rule_pool.search(cr, uid, [('type','=','USB')] + message_direction, order='sequence_number',  context=context)
        if rule_ids:
            for rule in rule_pool.browse(cr, uid, rule_ids, context=context):
                order = "id asc"
                if 'usb_create_partial_int_moves' in rule.remote_call or 'usb_create_partial_in' in rule.remote_call:
                    # For this INT sync, create messages ordered by the date_done to make sure that the first INTs will be synced first
                    order = 'date_done asc'
                messages_count += message_pool.create_from_rule(cr, uid, rule, order, context=context)
            if messages_count:
                cr.commit()


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
        ori_pick = pick_dict['associate_pick_name']

        rw_type = self._get_usb_entity_type(cr, uid)
        if rw_type == self.CENTRAL_PLATFORM:
            if origin:
                search_name = [('origin', '=', origin), ('subtype', '=', 'picking'), ('type', '=', 'out'), ('state', 'in', ['draft', 'assigned'])]
                # UF-2531: When we have an OUT converted from a Pick, get the PickName for the search to make sure to retrieve the correct PICK
                # otherwise we could have several picks matched the search condition!
                if ori_pick:
                    search_name.append(('name', '=', ori_pick))

                # look for FO if it is a CP instance
                pick_ids = self.search(cr, uid, search_name, context=context)
                if pick_ids: # This is a real pick in draft, then convert it to OUT
                    old_name = self.read(cr, uid, pick_ids, ['name'], context=context)[0]['name']
                    context['rw_backorder_name'] = pick_name
                    # Before converting to OUT, the PICK needs to be updated as what sent from the RW
                    self.convert_to_standard(cr, uid, pick_ids, context)
                    self.write(cr, uid, pick_ids[0], {'name': pick_name, 'already_replicated': True}, context=context)
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
                pick_ids = self.search(cr, uid, [('origin', '=', origin), ('subtype', '=', 'standard'), ('type', '=', 'out'),('state', 'in', ['draft', 'confirmed', 'assigned'])], context=context)
                if pick_ids: # This is a real pick in draft, then convert it to OUT
                    old_name = self.read(cr, uid, pick_ids, ['name'], context=context)[0]['name']
                    context['rw_backorder_name'] = pick_name
                    # Before converting to OUT, the PICK needs to be updated as what sent from the RW
                    self.convert_to_pick(cr, uid, pick_ids, context)
                    # US-27: Do not change the status of this PICK, otherwise cannot close ship!
                    self.write(cr, uid, pick_ids[0], {'name': pick_name, 'already_replicated': True}, context=context)
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
            header_result = {}
            self.retrieve_picking_header_data(cr, uid, source, header_result, pick_dict, context)

            #US-702: In case of the OUT from scratch from RW, the partial closed must be checked in advance
            pick_ids = None
            if origin: # first search for the OUT with origin (normal OUT)
                pick_ids = self.search(cr, uid, [('origin', '=', origin), ('subtype', '=', 'standard'), ('state', 'in', ['confirmed', 'assigned'])], context=context)
            else: # this must be an OUT from scratch, search for backorder or name if full processed
                if 'backorder_ids' in pick_dict and pick_dict['backorder_ids']:
                    sdref, rw_sdref_counterpart = self.rw_get_backorders_values(cr, uid, pick_dict, context=context)
                    if sdref:
                        # US-779: Search only open pick
                        pick_ids = self.search(cr, uid, [('rw_sdref_counterpart', '=', sdref), ('state', 'in', ['confirmed', 'assigned'])], context=context)
                else:
                    pick_ids = self.search(cr, uid, [('name', '=', pick_name)], context=context)

            if pick_ids: # If exist the OUT, process it
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

    #UF-2531: Allow to cancel the PICK/OUT from CP to RW
    def usb_cancel_pick_out(self, cr, uid, source, in_info, context=None):
        if context is None:
            context = {}

        pick_dict = in_info.to_dict()
        pick_name = pick_dict['name']
        origin = pick_dict['origin']

        self._logger.info("+++ RW: Cancel the Picking/OUT: %s from %s to %s" % (pick_name, source, cr.dbname))

        rw_type = self._get_usb_entity_type(cr, uid)
        if rw_type == self.REMOTE_WAREHOUSE:
            if origin:
                existing_pick = self.search(cr, uid, [('origin', '=', origin), ('name', '=', pick_name), ('type', '=', 'out'), ('state', '!=', 'done')], context=context)
                if not existing_pick:
                    message = "Sorry, the IN: " + pick_name + " does not exist in " + cr.dbname
                    self._logger.info(message)
                    raise Exception, message

                self.action_cancel(cr, uid, existing_pick, context=context)
                message = "Cancelled successfully the Picking/OUT: " + pick_name
            else:
                message = "Sorry, the case without the origin PO is not yet available!"
                self._logger.info(message)
                raise Exception, message
        else:
            message = "Sorry, the given operation is only available for Remote Warehouse instance!"

        self._logger.info(message)
        return message

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
                ], limit=1, order='NO_ORDER', context=context)
                if same_ids:
                    message = "The Picking: " + pick_name + " is already replicated in " + cr.dbname
                    self._logger.info(message)
                    return message

                condition = [('origin', '=', origin), ('subtype', '=', 'picking'), ('state', 'in', ['draft'])]
                #US-803 Add also the backorder if exist to the search condition for retrieving the correct PICK
                if pick_dict['backorder_id'] and pick_dict['backorder_id']['name']:
                    condition.append(('name', '=', pick_dict['backorder_id']['name']))

                pick_ids = self.search(cr, uid, condition, context=context)
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

                        #self.cancel_moves_before_process(cr, uid, [pick_ids[0]], context=context)
                        self.action_assign(cr, uid, [pick_ids[0]], context=context)

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
                    #UF-2531, point 3): Added a check to help getting the right line from the wizard, maybe we need to check also with the original_qty?
                    if move.line_number == line_number and move.product_qty >= sline['product_qty']:
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

        line_to_del = wizard_line_obj.search(cr, uid, [('wizard_id', '=',
                                                        proc_id), ('quantity', '=', 0.00)], order='NO_ORDER', context=context)
        if line_to_del:
            wizard_line_obj.unlink(cr, uid, line_to_del, context=context)

        self.do_create_picking(cr, uid, [proc_id], context=context)
        return True


    #UF-2531: Create packs return for the shipment
    def usb_picking_return_products(self, cr, uid, source, out_info, context=None):
        '''
        Method to return packs from a shipped Shipment from RW
        '''
        if context is None:
            context = {}

        pick_obj = self.pool.get('stock.picking')
        rw_type = pick_obj._get_usb_entity_type(cr, uid)
        if rw_type != pick_obj.CENTRAL_PLATFORM:
            message = "Sorry, the given operation is not available for Remote Warehouse instance!"
            self._logger.info(message)
            return message

        state='assigned'
        picking_dict = out_info.to_dict()
        ppl_name = picking_dict['name']
        picking_dict = picking_dict['picking']

        self._logger.info("+++ RW: The Packing List %s has products returned" % (ppl_name))
        pick_ids = self.search(cr, uid, [('name', '=', ppl_name), ('state', '=', state)], context=context)
        if not pick_ids or not ppl_name:
            message = "Sorry, no Packing List %s in correct state available or invalid Pick, for making the return products!" % (ppl_name)
            self._logger.info(message)
            return message

        message = 'The Packing List %s has the following products returned: ' % (ppl_name)
        # UF-2531: Create processor for return packs in Shipment
        proc_obj = self.pool.get('return.ppl.processor')
        processor_id = proc_obj.create(cr, uid, {'picking_id': pick_ids[0]}, context=context)
        proc_obj.create_lines(cr, uid, processor_id, context=context)
        wizard = proc_obj.browse(cr, uid, processor_id, context=context)

        line_obj = self.pool.get(wizard._columns['move_ids']._obj)

        draft_picking_id = wizard.picking_id.previous_step_id.backorder_id
        move_pick_name = draft_picking_id.name

        # Make the full quantity process for this PICK to PPL
        for move in wizard.move_ids:

            for pick in picking_dict:
                pick_line = picking_dict[pick]
                pick_name = pick_line['name']
                if pick_name == move_pick_name and move.ordered_quantity == pick_line['ordered_quantity'] and move.line_number == pick_line['line_number']:
                    message += "%s (line number: %s, quantity returned: %s), " % (pick_name, pick_line['line_number'], pick_line['returned_quantity'])
                    line_obj.write(cr, uid, [move.id], {
                        'quantity': pick_line['returned_quantity'],
                    }, context=context)

                    break

        # Now process this return by call the method
        proc_obj.do_return_ppl(cr, uid, processor_id, context=context)

        message += ". The operation has successfully executed"
        self._logger.info(message)
        return message




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
                        if not self.pool.get('ppl.processor').search(cr, uid,
                                                                     [('picking_id', '=', pick)],
                                                                     limit=1, order='NO_ORDER'):
                            pick_id = pick
                            break
                    if pick_id:
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
            # UF-2531, point 3): We need to set the quantity received from the other instance, not the whole qty from the move!
            # but need to check the line number to make sure to get the correct line
            for line in picking_lines:
                sline = line[2]
                # UF-2531: If the PICK got split then all lines need to be created in here
                if sline['line_number'] == move.line_number and (move.original_qty_partial == -1 or (move.original_qty_partial == sline['original_qty_partial'])):
                    line_data['product_qty'] = sline['product_qty']
                    line_data['quantity'] = sline['product_qty']
                    line_obj.create(cr, uid, line_data, context=context)

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
                        self.rw_create_ppl_step_1_only(cr, uid, pick_ids[0], picking_lines, context)
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
