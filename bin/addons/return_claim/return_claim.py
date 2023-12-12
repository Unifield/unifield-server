# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF
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

import time
import logging
import netsvc

from tools.translate import _
import decimal_precision as dp

# category
from order_types import ORDER_CATEGORY
# integrity
from msf_outgoing import INTEGRITY_STATUS_SELECTION
# claim type
CLAIM_TYPE = [('supplier', 'Supplier'),
              ('customer', 'Customer'),
              ('transport', 'Transport')]

TYPES_FOR_SRC_LOCATION = ['supplier', 'transport']

TYPES_FOR_INTEGRITY = ['supplier']

CLAIM_TYPE_RELATION = {'in': 'supplier',
                       'out': 'customer'}
# claim state
CLAIM_STATE = [('draft', 'Draft'),
               ('draft_progress', 'Draft - In progress'),
               ('in_progress', 'Validated - In progress'),
               ('done', 'Closed')]
# claim rules - define which new event is available after the key designated event
# missing event as key does not accept any event after him
CLAIM_RULES = {'supplier': {'quarantine': ['accept', 'scrap', 'return', 'surplus']}}
# does the claim type allows event creation
CLAIM_TYPE_RULES = {'supplier': ['accept', 'quarantine', 'scrap', 'return', 'surplus', 'missing'],
                    'customer': ['accept', 'quarantine', 'scrap', 'return', 'surplus', 'missing'],
                    'transport': False,
                    }
# event type
CLAIM_EVENT_TYPE = [('accept', 'Accept'),
                    ('quarantine', 'Move to Quarantine'),
                    ('scrap', 'Scrap'),
                    ('return', 'Return'),
                    ('surplus', 'Return (surplus)')]
# from scratch event type
CLAIM_FROM_SCRATCH_EVENT_TYPE = [('accept', 'Accept'),
                                 ('scrap', 'Scrap'),
                                 ('return', 'Return'),
                                 ('surplus', 'Return (surplus)')]
# IN event type
IN_CLAIM_EVENT_TYPE = [('accept', 'Accept'),
                       ('quarantine', 'Move to Quarantine'),
                       ('scrap', 'Scrap'),
                       ('return', 'Return'),
                       ('surplus', 'Return (surplus)'),
                       ('missing', 'Request missing products/quantities')]
# event state
CLAIM_EVENT_STATE = [('draft', 'Draft'),
                     ('in_progress', 'In progress'),
                     ('done', 'Done')]
# event type destination - for return event, the destination depends on
EVENT_TYPE_DESTINATION = {'accept': 'stock.stock_location_stock',  # move to stock
                          'quarantine': 'stock_override.stock_location_quarantine_analyze',
                          'scrap': 'stock_override.stock_location_quarantine_scrap',
                          }


class return_claim(osv.osv):
    '''
    claim class
    '''
    _name = 'return.claim'
    _description = 'Claim'

    def create(self, cr, uid, vals, context=None):
        '''
        - add sequence for events
        '''
        seq_tools = self.pool.get('sequence.tools')
        seq_id = seq_tools.create_sequence(cr, uid, vals, 'Return Claim', 'return.claim', prefix='', padding=5, context=context)
        vals.update({'sequence_id_return_claim': seq_id})
        return super(return_claim, self).create(cr, uid, vals, context=context)

    def unlink(self, cr, uid, ids, context=None):
        '''
        only draft claim can be deleted
        '''
        data = self.read(cr, uid, ids, ['state'], context=context)
        if not all([x['state'] == 'draft' for x in data]):
            raise osv.except_osv(_('Warning !'), _('Only Claims in draft state can be deleted.'))
        return super(return_claim, self).unlink(cr, uid, ids, context=context)

    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        reset data

        sequence_id is reset in the create method
        '''
        if default is None:
            default = {}

        # state is set to draft
        default.update(state='draft')
        # reset the name to get default from sequence
        default.update(name=self.pool.get('ir.sequence').get(cr, uid, 'return.claim'))
        # reset creation date, get today
        default.update(creation_date_return_claim=time.strftime('%Y-%m-%d'))
        # no event
        default.update(event_ids_return_claim=[])
        # reset description
        default.update(description_return_claim=False)
        # reset follow up
        default.update(follow_up_return_claim=False)
        # reset is processor origin
        default.update(processor_origin='')
        # reset is original claim ref
        default.update(origin_claim='')
        # reset is forwarded
        default.update(is_forwarded=False)
        # return super
        return super(return_claim, self).copy_data(cr, uid, id, default, context=context)

    def add_event(self, cr, uid, ids, context=None):
        '''
        open add event wizard
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # objects
        # we test if new event are allowed
        data = self.allow_new_event(cr, uid, ids, context=context)
        fields_tools = self.pool.get('fields.tools')
        if not all(x['allow'] for x in data.values()):
            # we get an event type and new event are not allowed, the specified type does not allow further events
            event_type_name = [x['last_type'][1] for x in data.values() if (not x['allow'] and x['last_type'])]
            # we get a state, the state of the previous event does not allow further events
            state = [x['state'] for x in data.values() if not x['allow']]
            if event_type_name:
                # not allowed previous event (last_type is present)
                raise osv.except_osv(_('Warning !'), _('Previous event (%s) does not allow further event.') % event_type_name[0])
            elif state:
                # not allowed because of state of last event
                state_name = fields_tools.get_selection_name(cr, uid, object='claim.event', field='state', key=state[0], context=context)
                raise osv.except_osv(_('Warning !'), _('State of previous event (%s) does not allow further event.') % state_name)
            else:
                # not allowed claim type (no last_type)
                claim_type_name = [x['claim_type'][1] for x in data.values()][0]
                raise osv.except_osv(_('Warning !'), _('Claim Type (%s) does not allow events.') % claim_type_name)
        # claim data
        claim_data = claim_type = self.read(cr, uid, ids, ['type_return_claim', 'partner_id_return_claim', 'picking_id_return_claim'], context=context)[0]
        # gather the corresponding claim type
        claim_type = claim_data['type_return_claim']
        # gather the corresponding claim partner
        claim_partner_id = claim_data['partner_id_return_claim']
        # claim origin
        claim_picking_id = claim_data['picking_id_return_claim']
        # data
        name = _("Add an Event")
        model = 'add.event'
        step = 'default'
        wiz_obj = self.pool.get('wizard')
        # open the selected wizard
        res = wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=dict(context,
                                                                                                claim_id=ids[0],
                                                                                                data=data,
                                                                                                claim_type=claim_type,
                                                                                                claim_partner_id=claim_partner_id,
                                                                                                claim_picking_id=claim_picking_id))
        return res

    def claim_to_external_partner(self, cr, uid, ids, context=None):
        '''
        In the case of a claim created by synchro from customer where an IN-replacement/-missing was created,
        the user can use this button to create a claim to the external supplier,
        and an IN from scratch linked to the PICK created after the FO created by the customer's IN-replacement/-missing.
        '''
        if context is None:
            context = {}

        # load context data
        self.pool.get('data.tools').load_common_data(cr, uid, ids, context=context)

        wf_service = netsvc.LocalService("workflow")
        event_obj = self.pool.get('claim.event')
        address_obj = self.pool.get('res.partner.address')
        sale_obj = self.pool.get('sale.order')
        sol_obj = self.pool.get('sale.order.line')
        pick_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')

        for claim in self.browse(cr, uid, ids, context=context):
            sale_with_claim_id = sale_obj.search(cr, uid, [('claim_name_goods_return', '=', claim.origin_claim)],
                                                 limit=1, context=context)
            if not sale_with_claim_id:
                raise osv.except_osv(_('Warning !'),
                                     _('No Field Order found with the Original Claim %s. Impossible to forward the claim.')
                                     % (claim.origin_claim))

            sale_with_claim = sale_obj.browse(cr, uid, sale_with_claim_id[0], context=context)
            is_from_missing = False
            other_supplier_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_suppliers')[1]
            lines_to_confirm = []
            for line in sale_with_claim.order_line:
                if line.state not in ('draft', 'validated'):
                    if line.type != 'make_to_stock':
                        raise osv.except_osv(_('Warning !'),
                                             _('Field Order Line %s of %s has already been sourced from order. Impossible to forward the claim.')
                                             % (line.line_number, sale_with_claim.name))
                    move_id = move_obj.search(cr, uid, [('sale_line_id', '=', line.id)], limit=1, context=context)[0]
                    if move_id:
                        move = move_obj.browse(cr, uid, move_id, fields_to_fetch=['state', 'picking_id'], context=context)
                        if move.state not in ('draft', 'assigned'):
                            raise osv.except_osv(_('Warning !'),
                                                 _('Field Order Line %s of %s has already been processed to the Picking Ticket %s \
                                 and is not available anymore. Impossible to forward the claim.')
                                                 % (line.line_number, sale_with_claim.name, move.picking_id.name))
                        else:
                            move_obj.write(cr, uid, move_id, ({'location_id': context['common']['cross_docking']}), context=context)
                else:
                    sol_obj.write(cr, uid, line.id, ({'type': 'make_to_stock',
                                                      'location_id': context['common']['cross_docking']}), context=context)
                    wf_service.trg_validate(uid, 'sale.order.line', line.id, 'validated', cr)
                    lines_to_confirm.append(line.id)

                # check if the origin claim event type from customer is missing
                if 'missing' in line.in_name_goods_return:
                    is_from_missing = True

            if len(lines_to_confirm) > 0:
                sol_obj.confirmLine(cr, uid, lines_to_confirm, context=context)

            # Searching for the Original IN
            in_domain = [
                ('type', '=', 'in'),
                ('subtype', '=', 'standard'),
                ('origin', 'like', claim.picking_id_return_claim.origin),
            ]
            original_in_id = pick_obj.search(cr, uid, in_domain, order='id asc', limit=1, context=context)[0]
            original_in = pick_obj.browse(cr, uid, original_in_id, fields_to_fetch=['name', 'partner_id', 'origin', 'purchase_id'], context=context)

            # Creating the new Claim
            current_instance = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id
            claim_values = {
                'type_return_claim': 'supplier',
                'picking_id_return_claim': original_in_id,
                'partner_id_return_claim': original_in.partner_id.id,
                'po_so_return_claim': sale_with_claim.name,
            }
            new_claim_id = self.copy(cr, uid, claim.id, claim_values, context=context)
            self.write(cr, uid, new_claim_id, ({'origin_claim': current_instance.name + '.' + claim.name}), context=context)
            # Create the event and link it to the newly created Claim
            event_values = {
                'type_claim_event': 'missing' if is_from_missing else 'accept',
                'replacement_picking_expected_claim_event': True,
                'description_claim_event': '',
                'from_picking_wizard_claim_event': False,
                'creation_date_claim_event': time.strftime('%Y-%m-%d'),
                'event_picking_id_claim_event': original_in_id,
                'return_claim_id_claim_event': new_claim_id,
            }
            new_event_id = event_obj.create(cr, uid, event_values, context=context)
            # Create the IN-replacement/-missing with gathered data
            new_claim_name = self.browse(cr, uid, new_claim_id, fields_to_fetch=["name"], context=context).name
            address = address_obj.search(cr, uid, [('partner_id', '=', original_in.partner_id.id)], context=context)[0] or False
            original_in_from_scratch = original_in.type == 'in' and not original_in.purchase_id or False
            inv_status = (original_in.partner_id.partner_type in ['internal', 'intermission'] or original_in_from_scratch) and 'none' or '2binvoiced'
            name_suffix = '-missing' if is_from_missing else '-replacement'
            in_values = {
                'name': self.pool.get('ir.sequence').get(cr, uid, 'stock.picking.in') + name_suffix,
                'type': 'in',
                'subtype': 'standard',
                'partner_id': original_in.partner_id.id,
                'partner_id2': original_in.partner_id.id,
                'origin': original_in.origin,
                'purchase_id': original_in.purchase_id.id,
                'sale_id': sale_with_claim.id,
                'backorder_id': original_in.id,
                'address_id': address,
                'invoice_state': inv_status,
                'reason_type_id': context['common']['rt_goods_replacement'],
                'claim': True,
                'claim_name': new_claim_name,
                'move_lines': [(0, 0, {
                    'name': x.name,
                    'sale_line_id': x.id,
                    'line_number': x.line_number,
                    'product_id': x.product_id.id,
                    'product_qty': x.product_uom_qty,
                    'product_uom': x.product_uom.id,
                    'location_id': other_supplier_id,
                    'location_dest_id': context['common']['cross_docking'],
                    'reason_type_id': context['common']['rt_goods_replacement'],
                }) for x in sale_with_claim.order_line],
            }
            new_in = pick_obj.create(cr, uid, in_values, context=context)
            # Confirm the new IN
            pick_obj.action_move(cr, uid, [new_in], context=context)
            wf_service.trg_validate(uid, 'stock.picking', new_in, 'button_confirm', cr)
            # Close new event
            event_obj.write(cr, uid, new_event_id, ({'state': 'done'}), context=context)
            # To prevent more than one forwarding
            self.write(cr, uid, claim.id, ({'is_forwarded': True}), context=context)
            # Validate the new claim
            self.write(cr, uid, new_claim_id, ({'state': 'in_progress'}), context=context)

            # log the claim action
            self.log(cr, uid, claim.id, _('The Claim %s has been forwarded to a new Claim %s.') % (
                claim.name, new_claim_name))
            self.infolog(cr, uid, "The Claim id:%s (%s) has been forwarded to a new Claim id:%s (%s)." % (
                claim.id, claim.name, new_claim_id, new_claim_name,
            ))
            # log the new claim action
            self.log(cr, uid, claim.id, _('The New Claim %s has been validated.') % (new_claim_name))
            self.infolog(cr, uid, "The New Claim id:%s (%s) has been validated." % (
                new_claim_id, new_claim_name,
            ))

        return True

    def validate_draft_progress_claim(self, cr, uid, ids, context=None):
        '''
        Change the claim state from 'Draft - In progress' to 'Validated - In progress'
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        pick_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')
        address_obj = self.pool.get('res.partner.address')
        loc_obj = self.pool.get('stock.location')

        # load context data
        self.pool.get('data.tools').load_common_data(cr, uid, ids, context=context)

        for claim in self.browse(cr, uid, ids, context=context):
            # To prevent discrepancies if the customer claim is missing-type
            if claim.prevent_stock_discrepancies:
                out_origin = pick_obj.browse(cr, uid, claim.picking_id_return_claim.id, fields_to_fetch=['origin'], context=context).origin
                linked_in_id = pick_obj.search(cr, uid, [('origin', 'like', out_origin)], order='id', limit=1, context=context)[0]
                in_partner = pick_obj.browse(cr, uid, linked_in_id, context=context).partner_id
                stock_loc = loc_obj.browse(cr, uid, context['common']['stock_id'], context=context)
                in_values = {
                    'name': self.pool.get('ir.sequence').get(cr, uid, 'stock.picking.in'),
                    'type': 'in',
                    'subtype': 'standard',
                    'partner_id': in_partner.id,
                    'partner_id2': in_partner.id,
                    'address_id': address_obj.search(cr, uid, [('partner_id', '=', in_partner.id)], context=context)[0] or False,
                    'invoice_state': 'none',
                    'reason_type_id': context['common']['rt_goods_replacement'],
                    'move_lines': [(0, 0, {
                        'name': x.name,
                        'product_id': x.product_id_claim_product_line.id,
                        'product_qty': x.qty_claim_product_line,
                        'product_uom': x.uom_id_claim_product_line.id,
                        'location_id': context['common']['input_id'],
                        'location_dest_id': loc_obj.chained_location_get(cr, uid, stock_loc, product=x.product_id_claim_product_line)[0].id,
                        'reason_type_id': context['common']['rt_goods_replacement'],
                        'prodlot_id':  x.lot_id_claim_product_line and x.lot_id_claim_product_line.id or False,
                        'expired_date': x.expiry_date_claim_product_line,
                    }) for x in claim.product_line_ids_return_claim],
                }
                # creation of the new IN
                new_in = pick_obj.create(cr, uid, in_values, context=context)
                # confirm and close IN
                move_ids = move_obj.search(cr, uid, [('picking_id', '=', new_in)], context=context)
                pick_obj.action_move(cr, uid, [new_in], context=context)
                move_obj.action_done(cr, uid, move_ids, context=context)
                pick_obj.action_done(cr, uid, [new_in], context=context)

                # log the incoming action
                new_in_name = pick_obj.browse(cr, uid, new_in, fields_to_fetch=['name'], context=context).name
                self.log(cr, uid, new_in, _('The Incoming Shipment %s has been created and processed.') % (new_in_name))
                self.infolog(cr, uid, "The Incoming Shipment id:%s (%s) has been created and processed." % (
                    new_in, new_in_name,
                ))

            self.write(cr, uid, ids, {'state': 'in_progress'}, context=context)
            # log the claim action
            self.log(cr, uid, claim.id, _('The Claim %s has been validated.') % (claim.name))
            self.infolog(cr, uid, "The Claim id:%s (%s) has been validated." % (
                claim.id, claim.name,
            ))

        return True

    def close_claim(self, cr, uid, ids, context=None):
        '''
        close the claim
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        self.write(cr, uid, ids, {'state': 'done'}, context=context)

        claim_name = self.browse(cr, uid, ids[0], fields_to_fetch=['name'], context=context).name
        # log the claim action
        self.log(cr, uid, ids[0], _('The Claim %s has been closed.') % (claim_name))
        self.infolog(cr, uid, "The Claim id:%s (%s) has been closed." % (
            ids[0], claim_name,
        ))

        return True

    def allow_new_event(self, cr, uid, ids, context=None):
        '''
        return True if last event type allows successor event
        the tuple of the last event type (key, name)
        the available type tuple list
        '''
        # objects
        event_obj = self.pool.get('claim.event')
        field_trans = self.pool.get('ir.model.fields').get_selection
        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            # allow flag
            allow = False
            # last event type
            last_event_type = False
            # available list
            list = []
            # claim type (key, name)
            claim_type = (obj.type_return_claim, [x[1] for x in self.get_claim_type() if x[0] == obj.type_return_claim][0])
            # state of last event
            state = False
            # we first check if the claim type supports events
            if self.get_claim_type_rules().get(claim_type[0]):
                # order by order_claim_event, so we can easily get the last event
                previous_id = self.get_last_event(cr, uid, obj.id, context=context)[obj.id]
                # if no event, True
                if not previous_id:
                    # depend on the claim type
                    available_list = self.get_claim_type_rules().get(claim_type[0])
                    list = [(x, field_trans(cr, uid, 'claim.event', 'type_claim_event', y[1], context)) for x in available_list for y in self.get_claim_from_scratch_event_type() if y[0] == x]
                    allow = True  # list cannot be empty, because other we would not be here!
                else:
                    # we are interested in the last value of returned list -> -1
                    data = event_obj.read(cr, uid, previous_id, ['type_claim_event', 'state'], context=context)
                    # check event state, if not done, allow is False, and list empty
                    if data['state'] != 'done':
                        state = data['state']
                    else:
                        # event type key
                        last_event_type_key = data['type_claim_event']
                        # event type name
                        event_type = self.get_in_claim_event_type()
                        last_event_type_name = [x[1] for x in event_type if x[0] == last_event_type_key][0]
                        last_event_type = (last_event_type_key, last_event_type_name)
                        # get available selection
                        claim_rules = self.get_claim_rules()
                        # claim type level
                        available_list = claim_rules.get(claim_type[0], False)
                        # event type level
                        available_list = available_list and available_list.get(last_event_type_key, False) or False
                        if available_list:
                            allow = True
                            list = [(x, field_trans(cr, uid, 'claim.event', 'type_claim_event', y[1], context)) for x in available_list for y in self.get_claim_from_scratch_event_type() if y[0] == x]
            # update result
            result[obj.id] = {'allow': allow,
                              'last_type': last_event_type,
                              'list': list,
                              'claim_type': claim_type,
                              'state': state}
        return result

    def set_src_location(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if not context.get('button_selected_ids'):
            raise osv.except_osv(_('Warning!'), _('Please select at least one line'))

        claim = self.browse(cr, uid, ids[0], fields_to_fetch=['default_src_location_id_return_claim'], context=context)
        self.pool.get('claim.product.line').write(cr, uid, context['button_selected_ids'], {'src_location_id_claim_product_line': claim.default_src_location_id_return_claim.id}, context=context)
        return True

    def check_product_lines_integrity(self, cr, uid, ids, context=None):
        '''
        integrity check on product lines
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # objects
        prod_obj = self.pool.get('product.product')
        lot_obj = self.pool.get('stock.production.lot')
        move_obj = self.pool.get('stock.move')

        # errors
        errors = {'missing_src_location': False,  # source location is missing
                  'missing_lot': False,  # production lot is missing for product with batch management or perishable
                  'wrong_lot_type_need_standard': False,  # the selected production lot type is wrong
                  'wrong_lot_type_need_internal': False,  # the selected production lot type is wrong
                  'no_lot_needed': False,  # this line should not have production lot
                  'not_exist_in_picking': False,  # corresponding product does not exist in the selected origin picking
                  'must_be_greater_than_0': False,  # the selected quantity must be greater than 0.0
                  'not_available': False,  # the selected quantity is not available for selected product and lot from the selected location
                  }
        for obj in self.browse(cr, uid, ids, context=context):
            # products must not be empty
            if not len(obj.product_line_ids_return_claim):
                raise osv.except_osv(_('Warning !'), _('Product list is empty.'))
            for item in obj.product_line_ids_return_claim:
                # reset the integrity status
                item.write({'integrity_status_claim_product_line': 'empty'}, context=context)
                # product management type
                data = prod_obj.read(cr, uid, [item.product_id_claim_product_line.id], ['batch_management', 'perishable', 'type', 'subtype'], context=context)[0]
                management = data['batch_management']
                perishable = data['perishable']
                # check qty
                if item.qty_claim_product_line <= 0.0:
                    errors.update(must_be_greater_than_0=True)
                    item.write({'integrity_status_claim_product_line': 'must_be_greater_than_0'}, context=context)
                # check availability
                if item.qty_claim_product_line > item.hidden_stock_available_claim_product_line:
                    errors.update(not_available=True)
                    item.write({'integrity_status_claim_product_line': 'not_available'}, context=context)
                # check the src location
                if obj.type_return_claim == 'supplier':
                    if not item.src_location_id_claim_product_line:
                        # src location is missing and claim type is supplier
                        errors.update(missing_src_location=True)
                        item.write({'integrity_status_claim_product_line': 'missing_src_location'}, context=context)
                # check management
                if management:
                    if not item.lot_id_claim_product_line:
                        # lot is needed
                        errors.update(missing_lot=True)
                        item.write({'integrity_status': 'missing_lot'}, context=context)
                    else:
                        # we check the lot type is standard
                        data = lot_obj.read(cr, uid, [item.lot_id_claim_product_line.id], ['life_date', 'name', 'type'], context=context)
                        lot_type = data[0]['type']
                        if lot_type != 'standard':
                            errors.update(wrong_lot_type_need_standard=True)
                            item.write({'integrity_status': 'wrong_lot_type_need_standard'}, context=context)
                elif perishable:
                    if not item.lot_id_claim_product_line:
                        # lot is needed
                        errors.update(missing_lot=True)
                        item.write({'integrity_status': 'missing_lot'}, context=context)
                    else:
                        # we check the lot type is internal
                        data = lot_obj.read(cr, uid, [item.lot_id_claim_product_line.id], ['life_date', 'name', 'type'], context=context)
                        lot_type = data[0]['type']
                        if lot_type != 'internal':
                            errors.update(wrong_lot_type_need_internal=True)
                            item.write({'integrity_status': 'wrong_lot_type_need_internal'}, context=context)
                else:
                    # no lot needed - no date needed
                    if item.lot_id_claim_product_line:
                        errors.update(no_lot_needed=True)
                        item.write({'integrity_status': 'no_lot_needed'}, context=context)
                # verify existence in selected picking
                move_ids = move_obj.search(cr, uid, [('picking_id', '=', obj.picking_id_return_claim.id),
                                                     ('product_id', '=', item.product_id_claim_product_line.id),
                                                     ('asset_id', '=', item.asset_id_claim_product_line.id),
                                                     ('composition_list_id', '=', item.composition_list_id_claim_product_line.id),
                                                     ('prodlot_id', '=', item.lot_id_claim_product_line.id),
                                                     ('product_qty', '>=', item.qty_claim_product_line),
                                                     ], context=context)
                if not move_ids:
                    errors.update(not_exist_in_picking=True)
                    item.write({'integrity_status_claim_product_line': 'not_exist_in_picking'}, context=context)

        # check the encountered errors
        return all([not x for x in errors.values()])

    def get_last_event(self, cr, uid, ids, pos=-1, context=None):
        '''
        get the last id of event for each claim
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # objects
        event_obj = self.pool.get('claim.event')
        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            # false as default
            result[obj.id] = False
            # gather previous events - thanks to order, we have the event in the correct order
            previous_ids = event_obj.search(cr, uid, [('return_claim_id_claim_event', '=', obj.id)], order='order_claim_event', context=context)
            try:
                # -1, get the last one (by default)
                result[obj.id] = previous_ids[pos]
            except IndexError:
                # do nothing, we'll get False as a result
                pass

        return result

    def load_products(self, cr, uid, ids, context=None):
        """
        Load claim.product.line into the return.claim from the stock.picking linked to the claim
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of return.claim on which claim.product.line must be created
        :param context: Context of the call
        :return: True
        """
        # Objects
        pl_obj = self.pool.get('claim.product.line')

        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for claim in self.browse(cr, uid, ids, context=context):
            # Clear existing products
            line_ids = pl_obj.search(cr, uid, [
                ('claim_id_claim_product_line', '=', claim.id),
            ], context=context)
            pl_obj.unlink(cr, uid, line_ids, context=context)

            if not claim.picking_id_return_claim:
                raise osv.except_osv(
                    _('Error'),
                    _('No Reception/Shipment reference selected on the %s claim.') % claim.name,
                )

            src_location_id = False
            if claim.type_return_claim in TYPES_FOR_SRC_LOCATION and claim.default_src_location_id_return_claim:
                src_location_id = claim.default_src_location_id_return_claim.id

            # Create new claim.product.line on the return.claim from stock.move of the linked stock.picking
            for move in claim.picking_id_return_claim.move_lines:
                # Create corresponding product line
                product_line_values = {
                    'qty_claim_product_line': move.product_qty,
                    'price_unit_claim_product_line': move.price_unit,
                    'price_currency_claim_product_line': move.price_currency_id.id,
                    'claim_id_claim_product_line': claim.id,
                    'product_id_claim_product_line': move.product_id.id,
                    'uom_id_claim_product_line': move.product_uom.id,
                    'lot_id_claim_product_line': move.prodlot_id.id,
                    'expiry_date_claim_product_line': move.expired_date,
                    'asset_id_claim_product_line': move.asset_id.id,
                    'stock_move_id_claim_product_line': move.id,
                    'composition_list_id_claim_product_line': move.composition_list_id.id,
                    'src_location_id_claim_product_line': src_location_id,
                }
                pl_obj.create(cr, uid, product_line_values, context=context)

        return True

    def on_change_origin(self, cr, uid, ids, picking_id, context=None):
        '''
        origin on change function
        '''
        # objects
        pick_obj = self.pool.get('stock.picking')
        result = {'value': {'partner_id_return_claim': False,
                            'type_return_claim': False,
                            'category_return_claim': False,
                            'po_so_return_claim': False}}
        if picking_id:
            # partner from picking
            data = pick_obj.read(cr, uid, picking_id, ['partner_id2', 'type', 'order_category', 'origin'], context=context)
            partner_id = data.get('partner_id2', False)
            if partner_id:
                partner_id = partner_id[0]
            type = data['type']
            # convert the picking type for the corresponding claim type
            type = CLAIM_TYPE_RELATION.get(type, False)
            # category
            category = data['order_category']
            # origin
            origin = data['origin']
            # update result dictionary
            result['value'].update({'partner_id_return_claim': partner_id,
                                    'type_return_claim': type,
                                    'category_return_claim': category,
                                    'po_so_return_claim': origin})

        return result

    def _vals_get_claim(self, cr, uid, ids, fields, arg, context=None):
        '''
        multi fields function method
        '''
        event_obj = self.pool.get('claim.event')
        pick_obj = self.pool.get('stock.picking')
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # results
        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {
                'contains_event_return_claim': len(obj.event_ids_return_claim) > 0,
                'fake_state_return_claim': obj.state,
            }

            missing_events_ids = event_obj.search(cr, uid, [('return_claim_id_claim_event', '=', obj.id),
                                                            ('type_claim_event', '=', 'missing')], context=context)
            if len(missing_events_ids) > 0:
                result[obj.id].update({'has_missing_events': True})

            if obj.origin_claim and obj.partner_id_return_claim.partner_type in ('internal', 'intermission', 'section') \
                    and obj.picking_id_return_claim.type == 'out':
                if not self.pool.get('sale.order').search_exists(cr, uid, [('claim_name_goods_return', '=', obj.origin_claim)], context=context):
                    continue
                # Searching for the Original IN
                in_domain = [
                    ('type', '=', 'in'),
                    ('subtype', '=', 'standard'),
                    ('origin', 'like', obj.picking_id_return_claim.origin),
                ]
                original_in_id = pick_obj.search(cr, uid, in_domain, order='id asc', limit=1, context=context)
                if len(original_in_id) > 0:
                    original_in = pick_obj.browse(cr, uid, original_in_id[0], fields_to_fetch=['partner_id'], context=context)
                    if original_in.partner_id and original_in.partner_id.partner_type in ('external', 'esc'):
                        result[obj.id].update({'original_pick_partner_external_or_esc': True})

        return result

    _columns = {
        'name': fields.char(
            string='Reference',
            size=1024,
            required=True,
        ),
        'creation_date_return_claim': fields.date(
            string='Creation Date',
            required=True,
        ),
        'po_so_return_claim': fields.char(
            string='Order reference',
            size=1024,
        ),
        'order_line_number_return_claim': fields.char(
            string='Order line number',
            size=1024,
        ),
        'type_return_claim': fields.selection(
            selection=CLAIM_TYPE,
            string='Type',
            required=True,
        ),
        'category_return_claim': fields.selection(
            selection=ORDER_CATEGORY,
            string='Category',
        ),
        'description_return_claim': fields.text(
            string='Description',
        ),
        'follow_up_return_claim': fields.text(
            string='Follow Up',
        ),
        'state': fields.selection(
            selection=CLAIM_STATE,
            string='State',
            readonly=True,
        ),
        'goods_expected': fields.boolean(
            string='Goods replacement/balance expected to be received'
        ),
        'processor_origin': fields.char(
            string='IN or INT processor',
            size=512,
        ),
        'origin_claim': fields.char(
            string='Original Claim Reference',
            size=512,
        ),
        'prevent_stock_discrepancies': fields.boolean(
            string='Create & process IN to re-add products directly to stock'
        ),
        'is_forwarded': fields.boolean(
            string='True if customer claim with origin has created a claim to external customer'
        ),
        # Many2one
        'sequence_id_return_claim': fields.many2one(
            'ir.sequence',
            string='Events Sequence',
            required=True,
            ondelete='cascade',
        ),  # from create function
        'partner_id_return_claim': fields.many2one(
            'res.partner',
            string='Partner',
            required=True,
        ),
        'po_id_return_claim': fields.many2one(
            'purchase.order',
            string='Purchase Order',
        ),
        'so_id_return_claim': fields.many2one(
            'sale.order',
            string='Sale Order',
        ),
        'picking_id_return_claim': fields.many2one(
            'stock.picking',
            string='Reception/Shipment reference',
            required=True,
        ),  # origin
        'default_src_location_id_return_claim': fields.many2one(
            'stock.location',
            string='Default Source Location',
            required=True,
        ),  # default value
        # One2many
        'event_ids_return_claim': fields.one2many(
            'claim.event',
            'return_claim_id_claim_event',
            string='Events',
        ),
        'product_line_ids_return_claim': fields.one2many(
            'claim.product.line',
            'claim_id_claim_product_line',
            readonly=True,
            states={'draft': [('readonly', False)]},
            string='Products',
        ),
        # Functions
        'contains_event_return_claim': fields.function(
            _vals_get_claim,
            method=True,
            string='Contains Events',
            type='boolean',
            readonly=True,
            multi='get_vals_claim',
        ),
        'fake_state_return_claim': fields.function(
            _vals_get_claim,
            method=True,
            string='Fake State',
            type='selection',
            selection=CLAIM_STATE,
            readonly=True,
            multi='get_vals_claim',
        ),
        'has_missing_events': fields.function(
            _vals_get_claim,
            method=True,
            string='Check if Return Claim has a missing type Claim Event',
            type='boolean',
            readonly=True,
            multi='get_vals_claim',
        ),
        'original_pick_partner_external_or_esc': fields.function(
            _vals_get_claim,
            method=True,
            string='Check if Return Claim is picking ticket and its origin\'s partner is external or esc',
            type='boolean',
            readonly=True,
            multi='get_vals_claim',
        ),
        'old_version': fields.boolean('Claim in old version with no sync', internal=True),
    }

    def _get_default_src_loc_id(self, cr, uid, context=None):
        """
        Return the stock.location Stock as default source location
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param context: Context of the call
        :return: The ID of the stock.location named Stock
        """
        data_obj = self.pool.get('ir.model.data')

        data_ids = data_obj.get_object_reference(cr, uid, 'stock', 'stock_location_stock')
        if data_ids:
            return data_ids[1]

        return False

    _defaults = {
        'creation_date_return_claim': lambda *a: time.strftime('%Y-%m-%d'),
        'name': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'return.claim'),
        'default_src_location_id_return_claim': _get_default_src_loc_id,
        'state': 'draft',
        'fake_state_return_claim': 'draft',
        'po_id_return_claim': False,
        'so_id_return_claim': False,
        'old_version': False,
    }

    def _check_claim(self, cr, uid, ids, context=None):
        """
        claim checks
        """
        if not context:
            context = {}

        # objects
        fields_tools = self.pool.get('fields.tools')
        for obj in self.browse(cr, uid, ids, context=context):
            # the selected origin must contain stock moves
            if not len(obj.picking_id_return_claim.move_lines) > 0:
                raise osv.except_osv(_('Warning !'), _('Selected Origin must contain at least one stock move.'))
            # the selected origin must be done for INT
            if obj.processor_origin == 'internal.picking.processor' and obj.picking_id_return_claim.state != 'done':
                raise osv.except_osv(_('Warning !'), _('Selected Origin must be in Done state for Internal Moves.'))
            # the selected origin or new IN created within split process must be draft/assigned for IN
            if obj.state not in ('in_progress', 'done') and obj.processor_origin == 'stock.incoming.processor' \
                    and obj.picking_id_return_claim.state == 'cancel':
                raise osv.except_osv(_('Warning !'),  _('Selected Origin must not be in Cancelled state for Incoming Shipments.'))
            # origin type
            if obj.picking_id_return_claim.type not in ['in', 'out']:
                raise osv.except_osv(_('Warning !'), _('Selected Origin must be either an Incoming Shipment or a Delivery Order or a Picking Ticket.'))
            # origin subtype
            if obj.picking_id_return_claim.subtype not in ['standard', 'picking']:
                raise osv.except_osv(_('Warning !'), _('PPL or Packing should not be selected.'))
            # not draft picking ticket, even if done except if it comes from syncho
            if obj.picking_id_return_claim.subtype == 'picking' and not obj.picking_id_return_claim.backorder_id\
                    and not obj.origin_claim:
                raise osv.except_osv(_('Warning !'), _('Draft Picking Tickets are not allowed as Origin, Picking Ticket must be selected.'))
            # if claim type does not allow events, no events should be present
            if not self.get_claim_type_rules().get(obj.type_return_claim) and (len(obj.event_ids_return_claim) > 0):
                raise osv.except_osv(_('Warning !'), _('Events are not allowed for selected Claim Type.'))
            # if claim type does not allow the selected event type, this event should not be present
            if self.get_claim_type_rules().get(obj.type_return_claim) and (len(obj.event_ids_return_claim) > 0):
                # event must be part of allowed types
                for event in obj.event_ids_return_claim:
                    if event.type_claim_event not in self.get_claim_type_rules().get(obj.type_return_claim):
                        event_name = fields_tools.get_selection_name(cr, uid, object='claim.event', field='type_claim_event', key=event.type_claim_event, context=context)
                        raise osv.except_osv(_('Warning !'), _('Event (%s) is not allowed for selected Claim Type.') % event_name)
            # if supplier, origin must be in
            if obj.type_return_claim == 'supplier' and obj.picking_id_return_claim.type != 'in'\
                    and ('return' not in obj.picking_id_return_claim.name and 'surplus' not in obj.picking_id_return_claim.name):
                raise osv.except_osv(_('Warning !'), _('Origin for supplier claim must be Incoming Shipment.'))
            # if customer, origin must be out
            if obj.type_return_claim == 'customer' and obj.picking_id_return_claim.type != 'out':
                raise osv.except_osv(_('Warning !'), _('Origin for customer claim must be Deliery Order or Picking Ticket.'))
        return True

    _constraints = [
        (_check_claim, 'Claim Error', []),
    ]

    def get_claim_type(self):
        '''
        return claim types
        '''
        return CLAIM_TYPE

    def get_claim_rules(self):
        '''
        return claim rules
        '''
        return CLAIM_RULES

    def get_claim_type_rules(self):
        '''
        return claim_type_rules
        '''
        return CLAIM_TYPE_RULES

    def get_claim_event_type(self):
        '''
        return claim_event_type
        '''
        return CLAIM_EVENT_TYPE

    def get_claim_from_scratch_event_type(self):
        '''
        return claim_event_type
        '''
        return CLAIM_FROM_SCRATCH_EVENT_TYPE

    def get_in_claim_event_type(self):
        '''
        return claim_event_type
        '''
        return IN_CLAIM_EVENT_TYPE

    _order = 'name desc'

    # Synchro
    _logger = logging.getLogger('------sync.return.claim')

    def check_existing_claim(self, cr, uid, source, claim_dict):
        if not source:
            raise osv.except_osv(_('Error'), _('The partner is missing.'))

        claim_ids = self.search(cr, uid, [('origin_claim', '=', claim_dict.get('origin_claim')), ('state', '!=', 'cancelled')])
        if not claim_ids:
            return False
        return claim_ids[0]

    def validated_claim_create_claim(self, cr, uid, source, claim_info, context=None):
        '''
        Synchronisation method for claims customer->supplier
        - create counterpart claims for validated claims
        '''
        claim_line_obj = self.pool.get('claim.product.line')
        warehouse_obj = self.pool.get('stock.warehouse')
        event_obj = self.pool.get('claim.event')
        sale_obj = self.pool.get('sale.order')
        pick_obj = self.pool.get('stock.picking')
        curr_obj = self.pool.get('res.currency')
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        lot_obj = self.pool.get('stock.production.lot')

        if context is None:
            context = {}

        claim_data = {}
        event_data = claim_info.event_ids_return_claim[0]
        product_line_data = claim_info.product_line_ids_return_claim

        sale_id = sale_obj.search(cr, uid, [('client_order_ref', 'ilike', claim_info.po_id_return_claim.name)],
                                  limit=1, order='id', context=context)[0]
        # fetch the original picking, ticket or out
        origin_pick_ids = pick_obj.search(cr, uid, [('sale_id', '=', sale_id), ('type', '=', 'out'),
                                                    ('subtype', '=', 'picking'), ('backorder_id', '=', False)],
                                          limit=1, context=context)
        if len(origin_pick_ids) > 0:
            origin_pick_id = origin_pick_ids[0]
        else:
            origin_pick_id = pick_obj.search(cr, uid, [('sale_id', '=', sale_id), ('type', '=', 'out'),
                                                       ('subtype', '=', 'standard'), ('backorder_id', '=', False)],
                                             limit=1, context=context)[0]

        event_values = {
            'type_claim_event': event_data.type_claim_event,
            'replacement_picking_expected_claim_event': event_data.replacement_picking_expected_claim_event,
            'description_claim_event': event_data.description_claim_event,
            'from_picking_wizard_claim_event': event_data.from_picking_wizard_claim_event,
            'creation_date_claim_event': event_data.creation_date_claim_event,
            'event_picking_id_claim_event': origin_pick_id,
        }

        warehouse_ids = warehouse_obj.search(cr, uid, [], limit=1)
        # Location defined by claim event type
        if event_data.type_claim_event in ('return', 'surplus'):
            location_id = warehouse_obj.read(cr, uid, warehouse_ids, ['lot_input_id'])[0]['lot_input_id'][0]
        else:
            location_id = warehouse_obj.read(cr, uid, warehouse_ids, ['lot_stock_id'])[0]['lot_stock_id'][0]

        claim_data.update({
            'origin_claim': source + "." + claim_info.name,
            'partner_id_return_claim': self.pool.get('res.partner').search(cr, uid, [('name', '=', source)], context=context)[0],
            'default_src_location_id_return_claim': location_id,
            'category_return_claim': claim_info.category_return_claim,
            'description_return_claim': claim_info.description_return_claim,
            'follow_up_return_claim': claim_info.follow_up_return_claim,
            'po_so_return_claim': claim_info.po_so_return_claim,
            'goods_expected': claim_info.goods_expected,
            'processor_origin': claim_info.processor_origin,
            'creation_date_return_claim': claim_info.creation_date_return_claim,
            'picking_id_return_claim': origin_pick_id,
        })

        claim_id = self.check_existing_claim(cr, uid, source, claim_data)

        if not claim_id:
            # create a new customer claim in the state Draft - In Progress
            claim_data.update({
                'state': 'draft_progress',
                'type_return_claim': 'customer',
            })
            claim_id = self.create(cr, uid, claim_data, context=context)
            # create the new event
            event_values.update({
                'return_claim_id_claim_event': claim_id,
                'state': 'done',  # the event must not be processed again
            })
            event_obj.create(cr, uid, event_values, context=context)

        # Create lines
        for x in product_line_data:
            if hasattr(x.product_id_claim_product_line, 'id') and hasattr(x.product_id_claim_product_line, 'default_code'):
                prod_id = self.pool.get('so.po.common').get_product_id(cr, uid, x.product_id_claim_product_line, x.product_id_claim_product_line.default_code, context=context)
            else:
                prod_id = product_obj.search(cr, uid, [('name', '=', x.product_id_claim_product_line.name)], context=context)[0]
            prod_data = product_obj.browse(cr, uid, prod_id, fields_to_fetch=['perishable', 'batch_management'], context=context)
            batch_id = False
            if prod_data.perishable and not prod_data.batch_management and x.expiry_date_claim_product_line:
                batch_id = lot_obj._get_prodlot_from_expiry_date(cr, uid, x.expiry_date_claim_product_line, prod_id, context=context)
            elif prod_data.perishable and prod_data.batch_management and x.expiry_date_claim_product_line and x.lot_id_claim_product_line.name:
                batch_id = lot_obj.get_or_create_prodlot(cr, uid, x.lot_id_claim_product_line.name, x.expiry_date_claim_product_line, prod_id, context=context)
            line_data = {
                'claim_id_claim_product_line': claim_id,
                'qty_claim_product_line': x.qty_claim_product_line,
                'price_unit_claim_product_line': x.price_unit_claim_product_line,
                'price_currency_claim_product_line': curr_obj.search(cr, uid, [('name', '=', x.price_currency_claim_product_line.name)],
                                                                     context=context)[0],
                'product_id_claim_product_line': prod_id,
                'uom_id_claim_product_line': uom_obj.search(cr, uid, [('name', '=', x.uom_id_claim_product_line.name)], context=context)[0],
                'type_check': x.type_check,
                'lot_id_claim_product_line': batch_id,
                'expiry_date_claim_product_line': x.expiry_date_claim_product_line,
                'src_location_id_claim_product_line': location_id,
            }
            claim_line_obj.create(cr, uid, line_data, context=context)

        name = self.browse(cr, uid, claim_id, context=context).name
        message = _('The claim %s is created by sync and linked to the claim %s by Push Flow at %s.') % (name, claim_info.name, source)
        self._logger.info(message)

        return message

    def origin_claim_close_claim(self, cr, uid, source, claim_info, context=None):
        '''
        Synchronisation method for claims customer->supplier:
        - close counterpart claim if the original is closed
        '''
        if context is None:
            context = {}

        # search for the claim
        origin_claim = source + '.' + claim_info.name
        claim_ids = self.search(cr, uid, [('origin_claim', '=', origin_claim)], limit=1, context=context)
        if not claim_ids:
            raise osv.except_osv(_('Error !'), _('Counterpart claim of %s not found') % (origin_claim))

        claim_id = claim_ids[0]

        self.write(cr, uid, claim_id, ({'state': 'done'}), context=context)

        name = self.browse(cr, uid, claim_id, context=context).name
        message = _("The claim %s has been closed by the closed claim %s by Push Flow at %s.") % (name, claim_info.name, source)
        self._logger.info(message)

        return message


return_claim()


class claim_event(osv.osv):
    '''
    event for claims
    '''
    _name = 'claim.event'

    def create(self, cr, uid, vals, context=None):
        '''
        set default name value
        '''
        obj = self.pool.get('return.claim').browse(cr, uid, vals['return_claim_id_claim_event'], context=context)
        sequence = obj.sequence_id_return_claim
        line = sequence.get_id(code_or_id='id', context=context)
        vals.update({'name': 'EV/%s' % line, 'order_claim_event': int(line)})
        return super(claim_event, self).create(cr, uid, vals, context=context)

    def unlink(self, cr, uid, ids, context=None):
        '''
        only draft event can be deleted
        '''
        data = self.read(cr, uid, ids, ['state'], context=context)
        if not all([x['state'] == 'draft' for x in data]):
            raise osv.except_osv(_('Warning !'), _('Only Event in draft state can be deleted.'))
        return super(claim_event, self).unlink(cr, uid, ids, context=context)

    def get_location_for_event_type(self, cr, uid, context=None, *args, **kwargs):
        '''
        get the destination location for event type
        '''
        # objects
        obj_data = self.pool.get('ir.model.data')
        partner_obj = self.pool.get('res.partner')
        # location_id
        location_id = False
        # event type
        event_type = kwargs['event_type']
        # origin browse object
        origin = kwargs['claim_picking']
        # claim type
        claim_type = kwargs['claim_type']
        # partner
        partner_id = kwargs['claim_partner_id']
        # not event type
        if not event_type or not origin:
            return False
        # treat each event type
        if event_type in ('return', 'surplus', 'missing'):
            if claim_type == 'supplier':
                # property_stock_supplier from partner
                data = partner_obj.read(cr, uid, partner_id, ['property_stock_supplier'], context=context)
                location_id = data['property_stock_supplier'][0]
            elif claim_type == 'customer':
                # property_stock_customer from partner
                data = partner_obj.read(cr, uid, partner_id, ['property_stock_customer'], context=context)
                location_id = data['property_stock_customer'][0]
            else:
                # should not be called for other types
                pass
        else:
            # we find the corresponding data reference from the dic
            module = EVENT_TYPE_DESTINATION.get(event_type).split('.')[0]
            name = EVENT_TYPE_DESTINATION.get(event_type).split('.')[1]
            location_id = obj_data.get_object_reference(cr, uid, module, name)[1]
        # return the id of the corresponding location
        return location_id

    def _validate_picking(self, cr, uid, ids, context=None):
        '''
        validate the picking full process
        '''
        # objects
        picking_tools = self.pool.get('picking.tools')
        picking_tools.all(cr, uid, ids, context=context)
        return True

    def _cancel_out_line_linked_to_extcu_ir(self, cr, uid, picking, claim_from_popup, context=None):
        '''
        Check if IN/INT moves are linked to an IR and if this IR has an ExtCU location Requestor.
        If that is the case, we cancel the qty from processed non-cancelled move lines of the linked OUT for normal
        claims, and non-closed/cancelled moves lines of the linked OUT for claims from scratch
        '''
        if context is None:
            context = {}

        move_obj = self.pool.get('stock.move')

        for move in picking.move_lines:
            if move.purchase_line_id:
                if move.purchase_line_id.linked_sol_id and move.purchase_line_id.linked_sol_id.procurement_request:
                    current_sol = move.purchase_line_id.linked_sol_id
                    origin_ir = current_sol.order_id
                    if origin_ir.location_requestor_id.usage == 'customer' \
                            and origin_ir.location_requestor_id.location_category == 'consumption_unit' \
                            and origin_ir.location_requestor_id.chained_picking_type == 'out':
                        out_domain = [('sale_line_id', '=', current_sol.id)]
                        if not claim_from_popup:
                            out_domain.append(('state', 'not in', ['done', 'cancel']))
                        else:
                            out_domain.append(('state', '!=', 'cancel'))
                        out_move_ids = move_obj.search(cr, uid, out_domain, order='create_date desc', context=context)
                        for out_move in move_obj.browse(cr, uid, out_move_ids,
                                                        fields_to_fetch=['product_qty', 'product_id'], context=context):
                            # Check for same data
                            if move.product_id.id == out_move.product_id.id and move.product_qty == out_move.product_qty:
                                move_obj.action_cancel(cr, uid, [out_move.id], context=context)
                                # prevent cancel on multiple lines if they have the same qty
                                break
                            elif move.product_id.id == out_move.product_id.id and move.product_qty != out_move.product_qty\
                                    and picking.type == 'internal':
                                # Manually create the split line in case of internal
                                split_out_move_data = ({
                                    'product_qty': move.product_qty,
                                    'picking_id': out_move.picking_id.id,
                                    'line_number': out_move.line_number,
                                })
                                split_out_move_id = move_obj.copy(cr, uid, out_move.id, split_out_move_data, context=context)
                                updated_move_data = ({
                                    'product_qty': out_move.product_qty - move.product_qty,
                                })
                                move_obj.write(cr, uid, out_move.id, updated_move_data, context=context)
                                move_obj.action_cancel(cr, uid, [split_out_move_id], context=context)
                                # prevent cancel on multiple lines if they have the same qty
                                break

        return True

    def _do_process_accept(self, cr, uid, obj, context=None):
        '''
        process logic for accept event

        - no change to event picking, replacement possible if agreement with supplier
        '''
        context = context.copy()
        context.update({'keep_prodlot': True, 'keepPoLine': True})

        # objects
        picking_tools = self.pool.get('picking.tools')
        # event picking object
        event_picking = obj.event_picking_id_claim_event
        # confirm the picking - in custom event function because we need to take the type of picking into account for self.log messages
        picking_tools.confirm(cr, uid, event_picking.id, context=context)
        # we check availability for created or wizard picking (wizard picking can be waiting as it is chained picking)
        picking_tools.check_assign(cr, uid, event_picking.id, context=context)
        # validate the event picking if not from picking wizard or doesn't need replacement
        if not obj.from_picking_wizard_claim_event and not obj.replacement_picking_expected_claim_event:
            self._validate_picking(cr, uid, event_picking.id, context=context)

        self._process_replacement(cr, uid, obj, event_picking, context=context)
        context.update({'keep_prodlot': False, 'keepPoLine': False})

        return True

    def _do_process_quarantine(self, cr, uid, obj, context=None):
        '''
        process logic for quarantine event

        - destination of picking moves becomes Quarantine (Analyze), replacement possible if agreement with supplier
        '''
        context = context.copy()
        context.update({'keep_prodlot': True, 'keepPoLine': True})

        # objects
        move_obj = self.pool.get('stock.move')
        pick_obj = self.pool.get('stock.picking')
        picking_tools = self.pool.get('picking.tools')
        get_object_reference = self.pool.get('ir.model.data').get_object_reference
        origin_picking = obj.return_claim_id_claim_event.picking_id_return_claim
        # event picking object
        event_picking = obj.event_picking_id_claim_event
        # We cancel the lines of the OUT linked to the IN/INT lines processed
        # if the linked PO lines has an IR whose Location Requestor is ExtCU
        if not obj.replacement_picking_expected_claim_event:
            if event_picking.type == 'in':
                self._cancel_out_line_linked_to_extcu_ir(cr, uid, origin_picking, obj.from_picking_wizard_claim_event, context=context)
            else:
                self._cancel_out_line_linked_to_extcu_ir(cr, uid, event_picking, obj.from_picking_wizard_claim_event, context=context)
        # confirm the picking - in custom event function because we need to take the type of picking into account for self.log messages
        picking_tools.confirm(cr, uid, event_picking.id, context=context)
        # we check availability for created or wizard picking (wizard picking can be waiting as it is chained picking)
        picking_tools.check_assign(cr, uid, event_picking.id, context=context)
        # update the destination location for each move
        move_ids = [move.id for move in event_picking.move_lines]
        move_obj.write(cr, uid, move_ids, {'location_dest_id': context['common']['quarantine_anal']}, context=context)
        # validate the event picking if not from picking wizard
        if not obj.from_picking_wizard_claim_event and not obj.replacement_picking_expected_claim_event:
            self._validate_picking(cr, uid, event_picking.id, context=context)

        self._process_replacement(cr, uid, obj, event_picking, context=context)

        # change the reason type of the picking to loss/damage
        loss_id = get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_damage')[1]
        pick_obj.write(cr, uid, [event_picking.id], ({'reason_type_id': loss_id}), context=context)

        context.update({'keep_prodlot': False, 'keepPoLine': False})

        return True

    def _do_process_scrap(self, cr, uid, obj, context=None):
        '''
        process logic for scrap event

        - destination of picking moves becomes Expired/Damaged/For Scrap
        '''
        context = context.copy()
        context.update({'keep_prodlot': True, 'keepPoLine': True})

        # objects
        move_obj = self.pool.get('stock.move')
        pick_obj = self.pool.get('stock.picking')
        picking_tools = self.pool.get('picking.tools')
        get_object_reference = self.pool.get('ir.model.data').get_object_reference
        origin_picking = obj.return_claim_id_claim_event.picking_id_return_claim
        # event picking object
        event_picking = obj.event_picking_id_claim_event
        # We cancel the lines of the OUT linked to the IN/INT lines processed
        # if the linked PO lines has an IR whose Location Requestor is ExtCU
        if not obj.replacement_picking_expected_claim_event:
            if event_picking.type == 'in':
                self._cancel_out_line_linked_to_extcu_ir(cr, uid, origin_picking, obj.from_picking_wizard_claim_event, context=context)
            else:
                self._cancel_out_line_linked_to_extcu_ir(cr, uid, event_picking, obj.from_picking_wizard_claim_event, context=context)
        # confirm the picking - in custom event function because we need to take the type of picking into account for self.log messages
        picking_tools.confirm(cr, uid, event_picking.id, context=context)
        # we check availability for created or wizard picking (wizard picking can be waiting as it is chained picking)
        picking_tools.check_assign(cr, uid, event_picking.id, context=context)
        # update the destination location for each move
        move_ids = [move.id for move in event_picking.move_lines]
        move_obj.write(cr, uid, move_ids, {'location_dest_id': context['common']['exp_dam_scrap']}, context=context)
        # validate the event picking if not from picking wizard or doesn't need replacement
        if not obj.from_picking_wizard_claim_event and not obj.replacement_picking_expected_claim_event:
            self._validate_picking(cr, uid, event_picking.id, context=context)

        self._process_replacement(cr, uid, obj, event_picking, context=context)
        # change the reason type of the picking to loss/damage
        loss_id = get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_damage')[1]
        pick_obj.write(cr, uid, [event_picking.id], ({'reason_type_id': loss_id}), context=context)

        context.update({'keep_prodlot': False, 'keepPoLine': False})

        return True

    def _do_process_return(self, cr, uid, obj, context=None):
        '''
        process logic for return event

        - depends on the type of claim - supplier or customer
        - destination of picking moves becomes original Supplier/Customer [property_stock_supplier or property_stock_customer from res.partner]
        - name of picking becomes IN/0001 -> PICK/0001-return
        - (is not set to done - defined in _picking_done_cond)
        - if replacement is needed, we create a new picking
        '''
        context = context.copy()
        context.update({'from_claim': True, 'keep_prodlot': True, 'keepPoLine': True})

        # objects
        data_obj = self.pool.get('ir.model.data')
        move_obj = self.pool.get('stock.move')
        pick_obj = self.pool.get('stock.picking')
        # new picking ticket name + -return
        new_pt_name = self.pool.get('ir.sequence').get(cr, uid, 'picking.ticket') + '-return'
        # event picking object
        event_picking_id = pick_obj.copy(cr, uid, obj.event_picking_id_claim_event.id, ({'name': new_pt_name}),
                                         context=context)
        event_picking = pick_obj.browse(cr, uid, event_picking_id, context=context)
        # origin picking in/out
        origin_picking = obj.return_claim_id_claim_event.picking_id_return_claim
        # claim
        claim = obj.return_claim_id_claim_event
        # We cancel the lines of the OUT linked to the IN/INT lines processed
        # if the linked PO lines has an IR whose Location Requestor is ExtCU
        if not obj.replacement_picking_expected_claim_event:
            if obj.event_picking_id_claim_event.type == 'in':
                self._cancel_out_line_linked_to_extcu_ir(cr, uid, origin_picking, obj.from_picking_wizard_claim_event, context=context)
            else:
                self._cancel_out_line_linked_to_extcu_ir(cr, uid, obj.event_picking_id_claim_event, obj.from_picking_wizard_claim_event, context=context)
        # don't generate financial documents if the claim is linked to an internal or intermission partner
        inv_status = claim.partner_id_return_claim.partner_type in ['internal', 'intermission'] and 'none' or '2binvoiced'
        # get the picking values and move values according to claim type
        picking_values = {
            'partner_id': claim.partner_id_return_claim.id,  # both partner needs to be filled??
            'partner_id2': claim.partner_id_return_claim.id,
            'backorder_id': obj.event_picking_id_claim_event.id,
            'origin': origin_picking.origin,
            'purchase_id': origin_picking.purchase_id.id,
            'sale_id': origin_picking.sale_id.id,
            'reason_type_id': context['common']['rt_goods_return'],
            'invoice_state': inv_status,
            'converted_to_standard': False,
            'type': 'out',
            'subtype': 'picking',
            'sequence_id': pick_obj.create_sequence(cr, uid, {'name': new_pt_name, 'code': new_pt_name,
                                                              'prefix': '', 'padding': 2}, context=context),
            'claim': True,
            'claim_name': obj.return_claim_id_claim_event.name,
            'already_shipped': False,
        }
        move_values = {
            'type': 'out',
            'reason_type_id': context['common']['rt_goods_return'],
            'location_dest_id': data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'stock_location_packing')[1],
        }
        # update the picking
        pick_obj.write(cr, uid, [event_picking_id], picking_values, context=context)
        # update the picking again - strange bug on runbot, the type was internal again...
        pick_obj.write(cr, uid, [event_picking_id], picking_values, context=context)

        # the src location of OUT must be the destination of the pick that raises the claim
        for i, move in enumerate(event_picking.move_lines):
            move_values_set_loc = move_values
            if obj.from_picking_wizard_claim_event:
                move_values_set_loc.update({'location_id': origin_picking.move_lines[i].location_dest_id.id})
            move_obj.write(cr, uid, move.id, move_values_set_loc, context=context)
        # update the destination location for each move
        move_ids = [move.id for move in event_picking.move_lines]
        # confirm the moves but not the pick to be able to convert to OUT
        move_obj.action_confirm(cr, uid, move_ids, context=context)
        # Update some fields.function data in the Pick
        self.pool.get('stock.picking')._store_set_values(cr, uid, [event_picking_id], ['overall_qty', 'line_state'], context)
        # do we need replacement?
        self._process_replacement(cr, uid, obj, event_picking, context=context)
        context.update({'keep_prodlot': False, 'keepPoLine': False})

        return True

    def _process_replacement(self, cr, uid, event, event_picking, replace_type='replacement', context=None):

        if replace_type == 'replacement' and not event.replacement_picking_expected_claim_event:
            return False

        pick_obj = self.pool.get('stock.picking')
        split_obj = self.pool.get('split.purchase.order.line.wizard')
        move_obj = self.pool.get('stock.move')
        picking_tools = self.pool.get('picking.tools')
        claim = event.return_claim_id_claim_event
        origin_picking = claim.picking_id_return_claim
        original_in_from_scratch = origin_picking.type == 'in' and not origin_picking.purchase_id or False
        inv_status = (claim.partner_id_return_claim.partner_type in ['internal', 'intermission'] or original_in_from_scratch) and 'none' or '2binvoiced'

        # we copy the event return picking
        new_name = self.pool.get('ir.sequence').get(cr, uid, 'stock.picking.in') + '-' + replace_type
        replacement_id = pick_obj.copy(cr, uid, event.event_picking_id_claim_event.id, ({'name': new_name}),
                                       context=dict(context, keepLineNumber=True))
        # we update the replacement picking object and lines
        replacement_values = {
            'partner_id': claim.partner_id_return_claim.id,  # both partner needs to be filled??
            'partner_id2': claim.partner_id_return_claim.id,
            'reason_type_id': context['common']['rt_goods_replacement'],
            'origin': origin_picking.origin,
            'backorder_id': event.event_picking_id_claim_event.id,
            'purchase_id': origin_picking.purchase_id.id,
            'sale_id': origin_picking.sale_id.id,
            'invoice_state': inv_status,
            'claim': True,
            'claim_name': event.return_claim_id_claim_event.name,
        }
        replacement_move_values = {'reason_type_id': context['common']['rt_goods_replacement']}

        if claim.type_return_claim == 'supplier':
            replacement_values.update({'type': 'in'})
            # receive back from supplier, destination default input
            replacement_move_values.update({'location_id': claim.partner_id_return_claim.property_stock_supplier.id,
                                            'location_dest_id': context['common']['input_id']})
        elif claim.type_return_claim == 'customer':
            replacement_values.update({'type': 'out'})
            # resend to customer, from stock by default (can be changed by user later)
            replacement_move_values.update({'location_id': context['common']['stock_id'],
                                            'location_dest_id': claim.partner_id_return_claim.property_stock_customer.id})

        # write new values
        pick_obj.write(cr, uid, replacement_id, replacement_values, context=context)
        # update the moves
        replacement_move_ids = move_obj.search(cr, uid, [('picking_id', '=', replacement_id)], context=context)
        # update the destination location for each move
        event_moves = [move for move in event_picking.move_lines]
        for i, move_id in enumerate(replacement_move_ids):
            replacement_move_values_with_more = replacement_move_values.copy()
            check_po_line_to_close = False
            # set the same line number as the original move
            if event.event_picking_id_claim_event.move_lines[i].purchase_line_id:
                if event.event_picking_id_claim_event.move_lines[i].purchase_line_id.order_id.state != 'done':
                    remaining_po_qty =  event.event_picking_id_claim_event.move_lines[i].purchase_line_id.product_qty - event.event_picking_id_claim_event.move_lines[i].product_qty
                    if remaining_po_qty <= 0.001:
                        # full qty expected, do not cancel the PO line with the IN cancellation
                        replacement_move_values_with_more.update({'purchase_line_id': event.event_picking_id_claim_event.move_lines[i].purchase_line_id.id})
                    else:
                        new_ctx = context.copy()
                        new_ctx['return_new_line_id'] = True
                        split_id = split_obj.create(cr, uid, {
                            'purchase_line_id': event.event_picking_id_claim_event.move_lines[i].purchase_line_id.id,
                            'original_qty': event.event_picking_id_claim_event.move_lines[i].purchase_line_id.product_qty,
                            'new_line_qty': event.event_picking_id_claim_event.move_lines[i].product_qty
                        }, context=new_ctx)
                        new_pol = split_obj.split_line(cr, uid, split_id, context=new_ctx, for_claim=True)
                        check_po_line_to_close = event.event_picking_id_claim_event.move_lines[i].purchase_line_id.id,
                        replacement_move_values_with_more.update({'purchase_line_id': new_pol})

                move_obj.write(cr, uid, event.event_picking_id_claim_event.move_lines[i].id, {'purchase_line_id': False}, context=context)

            replacement_move_values_with_more.update({'line_number': event_moves[i].line_number})
            # update destination to cross docking if the original move goes to cross docking
            if event.event_picking_id_claim_event.move_lines[i].location_dest_id.id == context['common']['cross_docking']:
                replacement_move_values_with_more.update({
                    'location_dest_id': context['common']['cross_docking'],
                })
            # get the move values according to claim type
            move_obj.write(cr, uid, move_id, replacement_move_values_with_more, context=context)
            if check_po_line_to_close and not move_obj.search_exist(cr, uid, [('purchase_line_id', '=', check_po_line_to_close), ('type', '=', 'in'), ('state', 'not in', ['cancel', 'cancel_r', 'done'])], context=context):
                # IN linked to split pol has been fully processed: close the pol
                netsvc.LocalService("workflow").trg_validate(uid, 'purchase.order.line', check_po_line_to_close, 'done', cr)

        # confirm and check availability of replacement picking
        picking_tools.confirm(cr, uid, replacement_id, context=context)
        picking_tools.check_assign(cr, uid, replacement_id, context=context)

    def _do_process_surplus(self, cr, uid, obj, context=None):
        '''
        process logic for return surplus event

        - depends on the type of claim - supplier or customer
        - destination of picking moves becomes original Supplier/Customer [property_stock_supplier or property_stock_customer from res.partner]
        - name of picking becomes IN/0001 -> PICK/0001-surplus
        - (is not set to done - defined in _picking_done_cond)
        '''

        context = context.copy()
        context.update({'from_claim': True, 'keep_prodlot': True})

        # objects
        data_obj = self.pool.get('ir.model.data')
        move_obj = self.pool.get('stock.move')
        pick_obj = self.pool.get('stock.picking')
        # new picking ticket name + -surplus
        new_pt_name = self.pool.get('ir.sequence').get(cr, uid, 'picking.ticket') + '-surplus'
        # event picking object
        event_picking_id = pick_obj.copy(cr, uid, obj.event_picking_id_claim_event.id, ({'name': new_pt_name}),
                                         context=context)
        event_picking = pick_obj.browse(cr, uid, event_picking_id, context=context)
        # origin picking in/out
        origin_picking = obj.return_claim_id_claim_event.picking_id_return_claim
        # claim
        claim = obj.return_claim_id_claim_event
        # don't generate financial documents if the claim is linked to an internal or intermission partner
        inv_status = claim.partner_id_return_claim.partner_type in ['internal', 'intermission'] and 'none' or '2binvoiced'
        # get the picking values and move values according to claim type
        picking_values = {
            'partner_id': claim.partner_id_return_claim.id,  # both partner needs to be filled??
            'partner_id2': claim.partner_id_return_claim.id,
            'backorder_id': obj.event_picking_id_claim_event.id,
            'origin': origin_picking.origin,
            'purchase_id': origin_picking.purchase_id.id,
            'sale_id': origin_picking.sale_id.id,
            'reason_type_id': context['common']['rt_goods_return'],
            'invoice_state': inv_status,
            'converted_to_standard': False,
            'type': 'out',
            'subtype': 'picking',
            'sequence_id': pick_obj.create_sequence(cr, uid, {'name': new_pt_name, 'code': new_pt_name,
                                                              'prefix': '', 'padding': 2}, context=context),
            'claim': True,
            'claim_name': obj.return_claim_id_claim_event.name,
            'already_shipped': False,
        }
        move_values = {'type': 'out',
                       'reason_type_id': context['common']['rt_goods_return'],
                       'location_dest_id': data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'stock_location_packing')[1],
                       }
        # update the picking
        pick_obj.write(cr, uid, [event_picking.id], picking_values, context=context)
        # update the picking again - strange bug on runbot, the type was internal again...
        pick_obj.write(cr, uid, [event_picking.id], picking_values, context=context)

        # the src location of OUT must be the destination of the pick that raises the claim
        for i, move in enumerate(event_picking.move_lines):
            move_values_set_loc = move_values
            if obj.from_picking_wizard_claim_event:
                move_values_set_loc.update({'location_id': origin_picking.move_lines[i].location_dest_id.id})
            # get the move values according to claim type
            move_obj.write(cr, uid, move.id, move_values_set_loc, context=context)
        # update the destination location for each move
        move_ids = [move.id for move in event_picking.move_lines]
        # confirm the moves but not the pick to be able to convert to OUT
        move_obj.action_confirm(cr, uid, move_ids, context=context)
        # Update some fields.function data in the Pick
        self.pool.get('stock.picking')._store_set_values(cr, uid, [event_picking_id], ['overall_qty', 'line_state'], context)

        context.update({'keep_prodlot': False})

        return True

    def _do_process_missing(self, cr, uid, obj, context=None):
        '''
        process logic for missing product/qty event

        - name of new picking is IN/0001 -> IN/0001-missing type
        - state becomes "Available" when created
        - (is not set to done - defined in _picking_done_cond)
        '''
        context = context.copy()
        context.update({'from_claim': True, 'keep_prodlot': True})
        # objects
        self._process_replacement(cr, uid, obj, obj.event_picking_id_claim_event, replace_type='missing', context=context)
        context.update({'keep_prodlot': False})
        return True

    def do_process_event(self, cr, uid, ids, context=None):
        '''
        button function call - from_picking is False
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        claim_ids = context['active_ids']
        self._do_process_event(cr, uid, ids, context=context)

        return {'name': _('Claim'),
                'view_mode': 'form,tree',
                'view_id': False,
                'view_type': 'form',
                'res_model': 'return.claim',
                'res_id': claim_ids,
                'type': 'ir.actions.act_window',
                'target': 'crash',
                'domain': '[]',
                'context': context}


    def _do_process_event(self, cr, uid, ids, context=None):
        """
        Process the claim.event of the return.claim.
        If the return.claim not coming from a chained picking processing, create a stock.picking
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of the claim.event to process
        :param context: Context of the call
        :return: True
        """
        # Objects
        claim_obj = self.pool.get('return.claim')
        data_tools = self.pool.get('data.tools')
        pick_obj = self.pool.get('stock.picking')

        # Some verifications
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        # Load common data
        data_tools.load_common_data(cr, uid, ids, context=context)

        no_draft_event_ids = self.search(cr, uid, [
            ('state', '!=', 'draft'),
            ('id', 'in', ids)
        ], limit=1, order='NO_ORDER', context=context)
        if no_draft_event_ids:
            raise osv.except_osv(
                _('Warning !'),
                _('Only events in Draft state can be processed'),
            )

        def _get_po_line_id(x):
            """
            Return the ID of the purchase.order.line associated to the stock.move
            :param x: The browse_record of a stock.move
            :return: The ID of the purchase.order.line associated to the stock.move
            """
            if x.stock_move_id_claim_product_line.purchase_line_id:
                return x.stock_move_id_claim_product_line.purchase_line_id.id
            return False

        for event in self.browse(cr, uid, ids, context=context):
            """
            Integrity check on product lines for corresponding claim:
                - only for first event
                - only if from scratch
                - if from wizard, the check must be done from the wizard logic
            We do not check integrity from wizard because of force_availability option at picking level
              -> processing even if no stock available
            """
            events = event.return_claim_id_claim_event.event_ids_return_claim
            integrity_check = True
            if event.return_claim_id_claim_event.type_return_claim in TYPES_FOR_INTEGRITY:
                if len(events) == 1 and not events[0].from_picking_wizard_claim_event:
                    integrity_check = claim_obj.\
                        check_product_lines_integrity(cr, uid, event.return_claim_id_claim_event.id, context=context)

            if not integrity_check:
                return False


            # claim from scratch: create the template picking
            if not event.from_picking_wizard_claim_event:
                claim = event.return_claim_id_claim_event
                # we use default values as if the picking was from chained creation (so type is 'internal')
                # different values need according to event type is then replaced during specific do_process functions
                event_picking_values = {
                    'type': 'internal',
                    'partner_id2': claim.partner_id_return_claim.id,
                    'origin': claim.po_so_return_claim,
                    'order_category': claim.category_return_claim,
                    'purchase_id': claim.picking_id_return_claim.purchase_id.id,
                    'reason_type_id': context['common']['rt_internal_supply'],
                    'claim': True,
                }

                new_event_picking_id = pick_obj.create(cr, uid, event_picking_values, context=context)

                # We are interested in the previous value, as we are processing the last one, we must seek for -2 index
                previous_id = claim_obj.get_last_event(cr, uid, claim.id, pos=-2, context=context)[claim.id]
                if previous_id:
                    previous = self.browse(cr, uid, previous_id, context=context)
                    # we've got a previous event, so we copy the moves from the previous event picking
                    # with destination as source for the new picking event
                    moves_lines = [(0, 0, {
                        'name': x.name,
                        'product_id': x.product_id.id,
                        'asset_id': x.asset_id.id,
                        'composition_list_id': x.composition_list_id.id,
                        'prodlot_id': x.prodlot_id.id,
                        'date': context['common']['date'],
                        'date_expected': context['common']['date'],
                        'product_qty': x.product_qty,
                        'product_uom': x.product_uom.id,
                        'product_uos_qty': x.product_uos_qty,
                        'product_uos': x.product_uos.id,
                        'price_unit': x.price_unit,
                        'price_currency_id': x.price_currency_id.id,
                        'location_id': x.location_dest_id.id,
                        'location_dest_id': context['common']['stock_id'],
                        'purchase_line_id': x.purchase_line_id and x.purchase_line_id.id or False,
                        'company_id': context['common']['company_id'],
                        'reason_type_id': context['common']['rt_internal_supply'],
                    }) for x in previous.event_picking_id_claim_event.move_lines]
                else:
                    moves_lines = [(0, 0, {
                        'name': x.name,
                        'product_id': x.product_id_claim_product_line.id,
                        'asset_id': x.asset_id_claim_product_line.id,
                        'composition_list_id': x.composition_list_id_claim_product_line.id,
                        'prodlot_id': x.lot_id_claim_product_line.id,
                        'date': context['common']['date'],
                        'date_expected': context['common']['date'],
                        'product_qty': x.qty_claim_product_line,
                        'product_uom': x.uom_id_claim_product_line.id,
                        'product_uos_qty': x.qty_claim_product_line,
                        'product_uos': x.uom_id_claim_product_line.id,
                        'price_unit': x.price_unit_claim_product_line,
                        'price_currency_id': x.price_currency_claim_product_line.id,
                        'purchase_line_id': _get_po_line_id(x),
                        'location_id': x.src_location_id_claim_product_line.id,
                        'location_dest_id': context['common']['stock_id'],
                        'company_id': context['common']['company_id'],
                        'reason_type_id': context['common']['rt_internal_supply'],
                    }) for x in claim.product_line_ids_return_claim]

                # Update the created picking with stock moves
                pick_obj.write(cr, uid, [new_event_picking_id], {
                    'move_lines': moves_lines,
                }, context=context)
                # Update the claim setting the link to created event picking
                self.write(cr, uid, [event.id], {
                    'event_picking_id_claim_event': new_event_picking_id,
                }, context=context)

        claim_dict_write = {}
        log_msgs = []
        base_func = '_do_process_'
        # Reload browse_record values to get last updated values
        event_type_dict = dict(self.fields_get(cr, uid, ['type_claim_event'], context=context).get('type_claim_event', {}).get('selection', []))
        for event in self.browse(cr, uid, ids, context=context):
            getattr(self, base_func + event.type_claim_event)(cr, uid, event, context=context)
            # Log process message
            event_type_name = event_type_dict.get(event.type_claim_event, event.type_claim_event)
            # Cancel created INT backorder in case of claim from scratch
            if not event.from_picking_wizard_claim_event and event.event_picking_id_claim_event.type == 'internal' \
                    and event.type_claim_event in ('return', 'surplus'):
                # To cancel the created INT
                netsvc.LocalService("workflow").trg_validate(uid, 'stock.picking', event.event_picking_id_claim_event.id,
                                                             'button_cancel', cr)
            log_msgs.append((event.id, _('%s Event %s has been processed.') % (event_type_name, event.name)))
            claim_dict_write[event.return_claim_id_claim_event.id] = {}
            if not event.return_claim_id_claim_event.po_id_return_claim and event.return_claim_id_claim_event.picking_id_return_claim.purchase_id:
                claim_dict_write[event.return_claim_id_claim_event.id] = {'po_id_return_claim': event.return_claim_id_claim_event.picking_id_return_claim.purchase_id.id}

        # Update events
        self.write(cr, uid, ids, {
            'state': 'done',
        }, context=context)

        # Create res.log
        for log_msg in log_msgs:
            self.log(cr, uid, log_msg[0], log_msg[1])

        # Update claims
        for claim_id in claim_dict_write:
            claim_dict_write[claim_id]['state'] = 'in_progress'
            claim_obj.write(cr, uid, claim_id, claim_dict_write[claim_id], claim_dict_write)

        return True

    def _vals_get_claim(self, cr, uid, ids, fields, arg, context=None):
        '''
        multi fields function method
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # results
        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {}
            # associated location
            dest_loc_id = self.get_location_for_event_type(cr, uid, context=context,
                                                           event_type=obj.type_claim_event,
                                                           claim_partner_id=obj.return_claim_id_claim_event.partner_id_return_claim.id,
                                                           claim_type=obj.return_claim_id_claim_event.type_return_claim,
                                                           claim_picking=obj.return_claim_id_claim_event.picking_id_return_claim)
            result[obj.id].update({'location_id_claim_event': int(dest_loc_id)})
            # hidden state (attrs in tree view)
            result[obj.id].update({'hidden_state': obj.state})

        return result

    _columns = {
        'return_claim_id_claim_event': fields.many2one(
            'return.claim',
            string='Claim',
            required=True,
            ondelete='cascade',
            readonly=True,
        ),
        'creation_date_claim_event': fields.date(
            string='Creation Date',
            required=True,
            readonly=True,
        ),  # default value
        'type_claim_event': fields.selection(
            selection=IN_CLAIM_EVENT_TYPE,
            string='Type',
            required=True,
            readonly=True,
        ),
        'replacement_picking_expected_claim_event': fields.boolean(
            string='Replacement expected for Claim ?',
            help="An Incoming Shipment will be automatically created corresponding to returned products.",
        ),
        'description_claim_event': fields.char(
            size=1024,
            string='Comment',
        ),
        'state': fields.selection(
            selection=CLAIM_EVENT_STATE,
            string='State',
            readonly=True,
        ),  # default value
        'from_picking_wizard_claim_event': fields.boolean(
            string='From Picking Wizard',
            readonly=True,
        ),
        'event_picking_id_claim_event': fields.many2one(
            'stock.picking',
            string='Event Picking',
        ),
        # Auto fields from create function
        'name': fields.char(
            string='Reference',
            size=1024,
            readonly=True,
        ),
        'order_claim_event': fields.integer(
            string='Creation Order',
            readonly=True,
        ),
        # Functions
        'location_id_claim_event': fields.function(
            _vals_get_claim,
            method=True,
            string='Associated Location',
            type='many2one',
            relation='stock.location',
            readonly=True,
            multi='get_vals_claim',
        ),
        'hidden_state': fields.function(
            _vals_get_claim,
            method=True,
            string='Hidden State',
            type='selection',
            selection=CLAIM_EVENT_STATE,
            readonly=True,
            multi='get_vals_claim',
        ),
    }

    _defaults = {
        'creation_date_claim_event': lambda *a: time.strftime('%Y-%m-%d'),
        'state': 'draft',
        'from_picking_wizard_claim_event': False,
    }

claim_event()


class claim_product_line(osv.osv):
    '''
    product line for claim
    '''
    _name = 'claim.product.line'

    def _orm_checks(self, cr, uid, vals, context=None):
        '''
        common checks for create/write
        '''
        # objects
        prod_obj = self.pool.get('product.product')
        prodlot_obj = self.pool.get('stock.production.lot')
        partner_obj = self.pool.get('res.partner')
        claim_obj = self.pool.get('return.claim')

        if 'product_id_claim_product_line' in vals:
            if vals['product_id_claim_product_line']:
                product_id = vals['product_id_claim_product_line']
                data = prod_obj.read(cr, uid, [product_id], ['name', 'perishable', 'batch_management', 'type', 'subtype'], context=context)[0]
                # update the name
                vals.update({'name': data['name']})
                # batch management
                management = data['batch_management']
                # perishable
                perishable = data['perishable']
                # if management and we have a lot_id, we fill the expiry date
                if management and vals.get('lot_id_claim_product_line'):
                    data_prodlot = prodlot_obj.read(cr, uid, [vals.get('lot_id_claim_product_line')], ['life_date'], context=context)
                    expired_date = data_prodlot[0]['life_date']
                    vals.update({'expiry_date_claim_product_line': expired_date})
                elif perishable:
                    # nothing special here
                    pass
                else:
                    # not perishable nor management, exp and lot are False
                    vals.update(lot_id_claim_product_line=False, expiry_date_claim_product_line=False)
                # check asset
                asset_check = data['type'] == 'product' and data['subtype'] == 'asset'
                if not asset_check:
                    vals.update(asset_id_claim_product_line=False)
                # kit check
                kit_check = data['type'] == 'product' and data['subtype'] == 'kit'
                if not kit_check:
                    vals.update(composition_list_id_claim_product_line=False)
            else:
                # product is False, exp and lot are set to False
                vals.update(lot_id_claim_product_line=False, expiry_date_claim_product_line=False,
                            asset_id_claim_product_line=False, composition_list_id_claim_product_line=False)

        if vals.get('claim_id_claim_product_line', False):
            # claim_id
            claim_id = vals.get('claim_id_claim_product_line')
            # check the type and set the location accordingly
            data = claim_obj.read(cr, uid, claim_id, ['type_return_claim', 'partner_id_return_claim'], context=context)
            claim_type = data['type_return_claim']
            if claim_type == 'customer':
                partner_id = data['partner_id_return_claim'][0]
                data = partner_obj.read(cr, uid, partner_id, ['property_stock_customer'], context=context)
                location_id = data['property_stock_customer'][0]
                vals.update({'src_location_id_claim_product_line': location_id})

        return True

    def create(self, cr, uid, vals, context=None):
        '''
        set the name
        '''
        # common check
        self._orm_checks(cr, uid, vals, context=context)
        return super(claim_product_line, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        '''
        set the name
        '''
        # common check
        if not ids:
            return True
        self._orm_checks(cr, uid, vals, context=context)
        return super(claim_product_line, self).write(cr, uid, ids, vals, context=context)

    def common_on_change(self, cr, uid, ids, location_id, product_id, prodlot_id, uom_id=False, result=None, context=None):
        '''
        commmon qty computation
        '''
        if context is None:
            context = {}
        if result is None:
            result = {}
        if not product_id or not location_id:
            result.setdefault('value', {}).update({'qty_claim_product_line': 0.0, 'hidden_stock_available_claim_product_line': 0.0})
            return result

        prod_obj = self.pool.get('product.product')
        # corresponding product object
        ctx = context.copy()
        if uom_id:
            ctx['uom'] = uom_id
        if prodlot_id:
            ctx['prodlot_id'] = prodlot_id
        ctx['location'] = location_id
        product_obj = prod_obj.browse(cr, uid, product_id, fields_to_fetch=['qty_allocable'], context=ctx)
        # uom from product is taken by default if needed
        uom_id = uom_id or product_obj.uom_id.id
        qty = product_obj.qty_allocable
        # update the result
        result.setdefault('value', {}).update({'qty_claim_product_line': qty,
                                               'uom_id_claim_product_line': uom_id,
                                               'hidden_stock_available_claim_product_line': qty,
                                               })
        return result

    def change_lot(self, cr, uid, ids, location_id, product_id, prodlot_id, uom_id=False, context=None):
        '''
        prod lot changes, update the expiry date
        '''
        prodlot_obj = self.pool.get('stock.production.lot')
        result = {'value':{}}
        # reset expiry date or fill it
        if prodlot_id:
            result['value'].update(expiry_date_claim_product_line=prodlot_obj.browse(cr, uid, prodlot_id, context=context).life_date)
        else:
            result['value'].update(expiry_date_claim_product_line=False)
        # compute qty
        result = self.common_on_change(cr, uid, ids, location_id, product_id, prodlot_id, uom_id, result=result, context=context)
        return result

    def change_expiry(self, cr, uid, ids, expiry_date, product_id, type_check, location_id, prodlot_id, uom_id, context=None):
        '''
        expiry date changes, find the corresponding internal prod lot
        '''
        prodlot_obj = self.pool.get('stock.production.lot')
        result = {'value':{}}

        if expiry_date and product_id:
            prod_ids = prodlot_obj.search(cr, uid, [('life_date', '=', expiry_date),
                                                    ('type', '=', 'internal'),
                                                    ('product_id', '=', product_id)], context=context)
            if not prod_ids:
                if type_check == 'in':
                    # the corresponding production lot will be created afterwards
                    result['warning'] = {'title': _('Info'),
                                         'message': _('The selected Expiry Date does not exist in the system. It will be created during validation process.')}
                    # clear prod lot
                    result['value'].update(lot_id_claim_product_line=False)
                else:
                    # display warning
                    result['warning'] = {'title': _('Error'),
                                         'message': _('The selected Expiry Date does not exist in the system.')}
                    # clear date
                    result['value'].update(expiry_date_claim_product_line=False, lot_id_claim_product_line=False)
            else:
                # return first prodlot
                prodlot_id = prod_ids[0]
                result['value'].update(lot_id_claim_product_line=prodlot_id)
        else:
            # clear expiry date, we clear production lot
            result['value'].update(lot_id_claim_product_line=False,
                                   expiry_date_claim_product_line=False,
                                   )
        # compute qty
        result = self.common_on_change(cr, uid, ids, location_id, product_id, prodlot_id, uom_id, result=result, context=context)
        return result

    def on_change_location_id(self, cr, uid, ids, location_id, product_id, prodlot_id, uom_id=False, context=None):
        """
        location changes
        """
        result = {}
        # compute qty
        result = self.common_on_change(cr, uid, ids, location_id, product_id, prodlot_id, uom_id, result=result, context=context)
        return result

    def on_change_product_id(self, cr, uid, ids, location_id, product_id, prodlot_id, uom_id=False, picking_id=False, context=None):
        '''
        the product changes, set the hidden flag if necessary
        '''
        result = {}
        print picking_id
        # product changes, prodlot is always cleared
        result.setdefault('value', {})['lot_id_claim_product_line'] = False
        result.setdefault('value', {})['expiry_date_claim_product_line'] = False
        # clear uom
        result.setdefault('value', {})['uom_id_claim_product_line'] = False
        # reset the hidden flags
        result.setdefault('value', {})['hidden_batch_management_mandatory_claim_product_line'] = False
        result.setdefault('value', {})['hidden_perishable_mandatory_claim_product_line'] = False
        result.setdefault('value', {})['hidden_asset_claim_product_line'] = False
        result.setdefault('value', {})['hidden_kit_claim_product_line'] = False
        result['value']['stock_move_id_claim_product_line'] = False

        if product_id:
            product_obj = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            if picking_id:
                move_ids = self.pool.get('stock.move').search(cr, uid, [('picking_id', '=', picking_id), ('product_id', '=', product_id)], context=context)
                if move_ids:
                    result['value']['stock_move_id_claim_product_line'] = move_ids[0]
            # set the default uom
            uom_id = product_obj.uom_id.id
            result.setdefault('value', {})['uom_id_claim_product_line'] = uom_id
            result.setdefault('value', {})['hidden_batch_management_mandatory_claim_product_line'] = product_obj.batch_management
            result.setdefault('value', {})['hidden_perishable_mandatory_claim_product_line'] = product_obj.perishable
            asset_check = product_obj.type == 'product' and product_obj.subtype == 'asset'
            result.setdefault('value', {})['hidden_asset_claim_product_line'] = asset_check
            kit_check = product_obj.type == 'product' and product_obj.subtype == 'kit'
            result.setdefault('value', {})['hidden_kit_claim_product_line'] = kit_check
            result.setdefault('value', {})['price_unit_claim_product_line'] = product_obj.product_tmpl_id.standard_price
            result.setdefault('value', {})['price_currency_claim_product_line'] = product_obj.currency_id.id

        # compute qty
        result = self.common_on_change(cr, uid, ids, location_id, product_id, prodlot_id, uom_id, result=result, context=context)
        return result

    def _vals_get_claim(self, cr, uid, ids, fields, arg, context=None):
        '''
        multi fields function method
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # results
        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {}
            # claim state
            result[obj.id].update({'claim_state_claim_product_line': obj.claim_id_claim_product_line.state})
            # claim_type_claim_product_line
            result[obj.id].update({'claim_type_claim_product_line': obj.claim_id_claim_product_line.type_return_claim})
            # batch management
            result[obj.id].update({'hidden_batch_management_mandatory_claim_product_line': obj.product_id_claim_product_line.batch_management})
            # perishable
            result[obj.id].update({'hidden_perishable_mandatory_claim_product_line': obj.product_id_claim_product_line.perishable})
            # hidden_asset_claim_product_line
            asset_check = obj.product_id_claim_product_line.type == 'product' and obj.product_id_claim_product_line.subtype == 'asset'
            result[obj.id].update({'hidden_asset_claim_product_line': asset_check})
            # hidden_kit_claim_product_line
            kit_check = obj.product_id_claim_product_line.type == 'product' and obj.product_id_claim_product_line.subtype == 'kit'
            result[obj.id].update({'hidden_kit_claim_product_line': kit_check})
            # product availability
            ctx = context.copy()
            ctx['uom'] = obj.uom_id_claim_product_line.id
            ctx['location'] = obj.src_location_id_claim_product_line.id
            ctx['compute_child'] = False
            if obj.lot_id_claim_product_line:
                ctx['prodlot_id'] = obj.lot_id_claim_product_line.id
            prod = self.pool.get('product.product').browse(cr, uid, obj.product_id_claim_product_line.id, fields_to_fetch=['qty_allocable'], context=ctx)
            result[obj.id].update({'hidden_stock_available_claim_product_line': prod.qty_allocable})

        return result

    def onchange_uom_qty(self, cr, uid, ids, uom_id, qty):
        '''
        Check round of qty according to UoM
        '''
        res = {}

        if qty:
            res = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_id, qty, 'qty_claim_product_line', result=res)

        return res

    _columns = {'integrity_status_claim_product_line': fields.selection(string=' ', selection=INTEGRITY_STATUS_SELECTION, readonly=True),
                'name': fields.char(string='Name', size=1024),  # auto data from create/write
                'qty_claim_product_line': fields.float(string='Qty', digits_compute=dp.get_precision('Product UoM'), required=True, related_uom='uom_id_claim_product_line'),
                'price_unit_claim_product_line': fields.float(string='Price Unit', digits_compute=dp.get_precision('Account'), required=True),
                # many2one
                'claim_id_claim_product_line': fields.many2one('return.claim', string='Claim', required=True, ondelete='cascade'),
                'product_id_claim_product_line': fields.many2one('product.product', string='Product', required=True),
                'uom_id_claim_product_line': fields.many2one('product.uom', string='UoM', required=True),
                'lot_id_claim_product_line': fields.many2one('stock.production.lot', string='Batch N.'),
                'expiry_date_claim_product_line': fields.date(string='Exp'),
                'asset_id_claim_product_line' : fields.many2one('product.asset', string='Asset'),
                'composition_list_id_claim_product_line': fields.many2one('composition.kit', string='Kit'),
                'src_location_id_claim_product_line': fields.many2one('stock.location', string='Src Location'),
                'price_currency_claim_product_line': fields.many2one('res.currency', string='Currency', required=1),
                'stock_move_id_claim_product_line': fields.many2one('stock.move', string='Corresponding IN stock move'),  # value from wizard process
                'type_check': fields.char(string='Type Check', size=1024,),  # default value
                # functions
                'claim_type_claim_product_line': fields.function(_vals_get_claim, method=True, string='Claim Type', type='selection', selection=CLAIM_TYPE, store=False, readonly=True, multi='get_vals_claim'),
                'hidden_stock_available_claim_product_line': fields.function(_vals_get_claim, method=True, string='Available Stock', type='float', digits_compute=dp.get_precision('Product UoM'), store=False, readonly=True, multi='get_vals_claim', related_uom='uom_id_claim_product_line'),
                'claim_state_claim_product_line': fields.function(_vals_get_claim, method=True, string='Claim State', type='selection', selection=CLAIM_STATE, store=False, readonly=True, multi='get_vals_claim'),
                'hidden_perishable_mandatory_claim_product_line': fields.function(_vals_get_claim, method=True, type='boolean', string='Exp', store=False, readonly=True, multi='get_vals_claim'),
                'hidden_batch_management_mandatory_claim_product_line': fields.function(_vals_get_claim, method=True, type='boolean', string='B.Num', store=False, readonly=True, multi='get_vals_claim'),
                'hidden_asset_claim_product_line': fields.function(_vals_get_claim, method=True, type='boolean', string='Asset Check', store=False, readonly=True, multi='get_vals_claim'),
                'hidden_kit_claim_product_line': fields.function(_vals_get_claim, method=True, type='boolean', string='Kit Check', store=False, readonly=True, multi='get_vals_claim'),
                }

    def _get_default_location(self, cr, uid, context=None):
        '''
        get default location:
        - supplier: default_src from claim
        - customer: default customer location from claim partner
        '''
        # objects
        partner_obj = self.pool.get('res.partner')

        claim_type = context['claim_type']
        default_loc_id = context['default_src']
        claim_partner_id = context['claim_partner']

        if claim_type == 'supplier':
            location_id = default_loc_id
        elif claim_type == 'customer':
            data = partner_obj.read(cr, uid, claim_partner_id, ['property_stock_customer'], context=context)
            location_id = data['property_stock_customer'][0]

        return location_id

    _defaults = {'type_check': 'out',
                 'integrity_status_claim_product_line': 'empty',
                 'claim_type_claim_product_line': lambda obj, cr, uid, c: c.get('claim_type', False),
                 'src_location_id_claim_product_line': _get_default_location,
                 }

claim_product_line()


class stock_picking(osv.osv):
    '''
    add a column
    '''
    _inherit = 'stock.picking'

    def _vals_get_claim(self, cr, uid, ids, fields, arg, context=None):
        '''
        multi fields function method
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # objects
        move_obj = self.pool.get('stock.move')
        data_tools = self.pool.get('data.tools')
        # load common data
        data_tools.load_common_data(cr, uid, ids, context=context)
        # results
        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            # set result dic
            result[obj.id] = {}
            # chained_from_in_stock_picking
            test_chained = True
            # type of picking must be 'internal'
            if obj.type != 'internal':
                test_chained = False
            # in picking
            in_picking_id = False
            for move in obj.move_lines:
                # source location must be input for all moves
                input_location_id = context['common']['input_id']
                if move.location_id.id != input_location_id:
                    test_chained = False
                # all moves must be created from another stock move from IN picking (chained location)
                src_ids = move_obj.search(cr, uid, [('move_dest_id', '=', move.id)], context=context)
                # no stock move source of current stock move
                if len(src_ids) != 1:
                    test_chained = False
                else:
                    move_browse = move_obj.browse(cr, uid, src_ids[0], context=context)
                    # all should belong to the same incoming shipment
                    if in_picking_id and in_picking_id != move_browse.picking_id.id:
                        test_chained = False
                    in_picking_id = move_browse.picking_id.id
                    if move_browse.picking_id.type != 'in':
                        # source stock move is not part of incoming shipment
                        test_chained = False
            result[obj.id].update({'chained_from_in_stock_picking': test_chained})
            # corresponding_in_picking_stock_picking
            if test_chained:
                result[obj.id].update({'corresponding_in_picking_stock_picking': in_picking_id})
            else:
                result[obj.id].update({'corresponding_in_picking_stock_picking': False})

        return result

    def _picking_done_cond(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the do_partial method from stock_override>stock.py>stock_picking

        - allow to conditionally execute the picking processing to done
        - no supposed to modify partial_datas
        '''
        partial_datas = kwargs['partial_datas']
        assert partial_datas is not None, 'missing partial_datas'
        # if a claim is needed:
        # if return claim: we do not close the processed picking, it is now a pick which need to be processed
        if 'register_a_claim_partial_picking' in partial_datas and partial_datas['register_a_claim_partial_picking']:
            if partial_datas['claim_type_partial_picking'] in ('return', 'surplus'):
                return False

        return True

    def _claim_registration(self, cr, uid, wizards, picking, context=None, *args, **kwargs):
        """
        Create a new claim from picking
        """
        # Objects
        claim_obj = self.pool.get('return.claim')
        event_obj = self.pool.get('claim.event')
        move_obj = self.pool.get('stock.move')
        fields_tools = self.pool.get('fields.tools')

        if not isinstance(wizards, list):
            wizards = [wizards]

        if not isinstance(picking, (int, long)):
            raise osv.except_osv(
                _('Processing Error'),
                _('No picking found !'),
            )

        if not wizards or not picking:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        picking = self.browse(cr, uid, picking, context=context)

        for wizard in wizards:
            # Test if we need a claim
            if wizard.register_a_claim:
                if picking.type not in ('in', 'internal'):
                    raise osv.except_osv(
                        _('Warning !'),
                        _('Claim registration during picking process is only available for incoming shipment and \
                        internal picking.'),
                    )
                # We create a claim
                in_move_id = False
                if not len(picking.move_lines):
                    # No lines, we cannot register a claim because the link to original picking is missing
                    raise osv.except_osv(
                        _('Warning !'),
                        _('Processed a picking without moves for claim registration.'),
                    )

                move_lines = picking.move_lines
                for move in move_lines:
                    if picking.type == 'internal':
                        src_move_ids = move_obj.search(cr, uid, [('move_dest_id', '=', move.id)], context=context)
                    elif picking.type == 'in':
                        src_move_ids = move_obj.search(cr, uid, [('id', '=', move.id)], context=context)
                    else:
                        raise osv.except_osv(
                            _('Warning !'),
                            _('Claim registration during picking process is only available for incoming shipment and \
                            internal picking.'),
                        )
                    if not src_move_ids:
                        # We try to find the incoming shipment with by backorder line
                        back_ids = self.search(cr, uid, [
                            ('backorder_id', '=', picking.id),
                        ], context=context)
                        if len(back_ids) != 1:
                            # Cannot find corresponding stock move in incoming shipment
                            raise osv.except_osv(
                                _('Warning !'),
                                _('Corresponding Incoming Shipment cannot be found. Registration of claim cannot '\
                                  'be processed. (no back order)'),
                            )
                        else:
                            # We try with the backorder
                            for b_move in self.browse(cr, uid, back_ids[0], context=context).move_lines:
                                b_src_move_ids = move_obj.search(cr, uid, [
                                    ('move_dest_id', '=', b_move.id),
                                ], context=context)
                                if not b_src_move_ids:
                                    raise osv.except_osv(
                                        _('Warning !'),
                                        _('Corresponding Incoming Shipment cannot be found. Registration of '\
                                          'claim cannot be processed. (no IN for back order moves)'),
                                    )
                                else:
                                    in_move_id = b_src_move_ids[0]
                    else:
                        in_move_id = src_move_ids[0]

                # Get corresponding stock move browse
                in_move = move_obj.browse(cr, uid, in_move_id, context=context)
                # Check that corresponding picking is incoming shipment
                if in_move.picking_id.type != 'in':
                    raise osv.except_osv(
                        _('Warning !'),
                        _('Corresponding picking object is not an Incoming Shipment. Registration of claim cannot be processed.'),)
                # PO reference
                po_reference = in_move.picking_id.origin
                po_id = in_move.picking_id.purchase_id.id
                category = in_move.picking_id.order_category
                # Partner ID - from the wizard, as partner is not mandatory for Incoming Shipment
                partner_id = wizard.claim_partner_id
                # Picking ID
                picking_id = in_move.picking_id.id

                # We get the stock move of incoming shipment, we get the origin of picking
                claim_values = {
                    'po_so_return_claim': po_reference,
                    'po_id_return_claim': po_id,
                    'type_return_claim': 'supplier',
                    'category_return_claim': category,
                    'description_return_claim': wizard.claim_description,
                    'follow_up_return_claim': False,
                    'partner_id_return_claim': partner_id.id,
                    'picking_id_return_claim': picking_id,
                    'processor_origin': wizard._table_name,
                    'goods_expected': wizard.claim_replacement_picking_expected,
                    'product_line_ids_return_claim': [(0, 0, {
                        'qty_claim_product_line': x.product_qty,
                        'price_unit_claim_product_line': x.price_unit,
                        'price_currency_claim_product_line': x.price_currency_id.id,
                        'product_id_claim_product_line': x.product_id.id,
                        'uom_id_claim_product_line': x.product_uom.id,
                        'lot_id_claim_product_line': x.prodlot_id.id,
                        'expiry_date_claim_product_line': x.expired_date,
                        'asset_id_claim_product_line': x.asset_id.id,
                        'composition_list_id_claim_product_line': x.composition_list_id.id,
                        'src_location_id_claim_product_line': x.location_id.id,
                        'stock_move_id_claim_product_line': x.id}) for x in move_lines]
                }

                new_claim_id = claim_obj.create(cr, uid, claim_values, context=context)
                # log creation message
                claim_name = claim_obj.read(cr, uid, new_claim_id, ['name'], context=context)['name']
                claim_obj.log(cr, uid, new_claim_id, _('The new Claim %s to supplier has been registered during internal chained Picking process.') % claim_name)
                # depending on the claim type, we create corresponding event
                selected_event_type = wizard.claim_type
                event_values = {'return_claim_id_claim_event': new_claim_id,
                                'type_claim_event': selected_event_type,
                                'replacement_picking_expected_claim_event': wizard.claim_replacement_picking_expected,
                                'description_claim_event': wizard.claim_description,
                                'from_picking_wizard_claim_event': True,
                                'event_picking_id_claim_event': picking.id,
                                }
                new_event_id = event_obj.create(cr, uid, event_values, context=context)
                event_type_name = fields_tools.get_selection_name(cr, uid, object='claim.event', field='type_claim_event', key=selected_event_type, context=context)
                event_obj.log(cr, uid, new_event_id, _('The new %s Event %s has been created.') % (event_type_name, claim_name))
                # we process the event
                event_obj._do_process_event(cr, uid, [new_event_id], context=context)

        return True

    _columns = {'chained_from_in_stock_picking': fields.function(_vals_get_claim, method=True, string='Chained Internal Picking from IN', type='boolean', readonly=True, multi='get_vals_claim'),
                'corresponding_in_picking_stock_picking': fields.function(_vals_get_claim, method=True, string='Corresponding IN for chained internal', type='many2one', relation='stock.picking', readonly=True, multi='get_vals_claim')}

stock_picking()


class product_product(osv.osv):
    _name = 'product.product'
    _inherit = 'product.product'


    def _vals_get_claim(self, cr, uid, ids, fields, arg, context=None):
        '''
        return false for all
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for id in ids:
            res[id] = {}
            for f in fields:
                res[id].update({f:False})

        return res

    def _search_picking_claim(self, cr, uid, obj, name, args, context=None):
        '''
        Filter the search according to the args parameter
        '''
        # Some verifications
        if context is None:
            context = {}
        # objects
        pick_obj = self.pool.get('stock.picking')

        # ids of products
        ids = []

        for arg in args:
            if arg[0] == 'picking_ids':
                if arg[1] == '=' and arg[2]:
                    picking = pick_obj.browse(cr, uid, int(arg[2]), context=context)
                    for move in picking.move_lines:
                        ids.append(move.product_id.id)
                else:
                    raise osv.except_osv(_('Error !'), _('Operator is not supported.'))
            else:
                return []

        return [('id', 'in', ids)]

    _columns = {
        'picking_ids': fields.function(_vals_get_claim, fnct_search=_search_picking_claim,
                                       type='boolean', method=True, string='Picking', multi='get_vals_claim'),
    }

product_product()


class res_partner(osv.osv):
    '''
    add a link to claims
    '''
    _inherit = 'res.partner'

    _columns = {'claim_ids_res_partner': fields.one2many('return.claim', 'partner_id_return_claim', string='Claims')}

    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        erase claim_ids
        '''
        if default is None:
            default = {}
        if context is None:
            context = {}
        default.update({'claim_ids_res_partner': []})
        res = super(res_partner, self).copy_data(cr, uid, id, default=default, context=context)
        return res

res_partner()
