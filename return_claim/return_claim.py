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

from tools.translate import _
from dateutil.relativedelta import relativedelta
from datetime import datetime
import decimal_precision as dp

# category
from order_types import ORDER_CATEGORY
# integrity
from msf_outgoing import INTEGRITY_STATUS_SELECTION
# claim type
CLAIM_TYPE = [('supplier', 'Supplier'),
              ('customer', 'Customer'),
              ('transport', 'Transport')]

CLAIM_TYPE_RELATION = {'in': 'supplier',
                       'out': 'customer'}
# claim state
CLAIM_STATE = [('draft', 'Draft'),
               ('in_progress', 'In Progress'),
               ('done', 'Done')]
# claim rules - define which new event is available after the key designated event
# missing event as key does not accept any event after him
CLAIM_RULES = {'quarantine': ['accept', 'scrap', 'return']}
# does the claim type allows event creation
CLAIM_TYPE_RULES = {'supplier': True,
                    'customer': True,
                    'transport': False,
                    }
# event type
CLAIM_EVENT_TYPE = [('accept', 'Accept'),
                    ('quarantine', 'Move to Quarantine'),
                    ('scrap', 'Scrap'),
                    ('return', 'Return')]
# event state
CLAIM_EVENT_STATE = [('draft', 'Draft'),
                     ('in_progress', 'In Progress'),
                     ('done', 'Done')]
# event type destination - for return event, the destination depends on 
EVENT_TYPE_DESTINATION = {'accept': 'stock.stock_location_stock', #move to stock
                          'quarantine': 'msf_config_locations.stock_location_quarantine_analyze',
                          'scrap': 'msf_config_locations.stock_location_quarantine_scrap',
                          }
# import partner_type from msf_partner
from msf_partner import PARTNER_TYPE
from msf_order_date import TRANSPORT_TYPE
from msf_order_date import ZONE_SELECTION
from purchase_override import PURCHASE_ORDER_STATE_SELECTION
from sale_override import SALE_ORDER_STATE_SELECTION


class return_claim(osv.osv):
    '''
    claim class
    '''
    _name = 'return.claim'
    
    def create(self, cr, uid, vals, context=None):
        '''
        - add sequence for events
        '''
        seq_tools = self.pool.get('sequence.tools')
        seq_id = seq_tools.create_sequence(cr, uid, vals, 'Return Claim', 'return.claim', prefix='', padding=5, context=context)
        vals.update({'sequence_id_return_claim': seq_id})
        return super(return_claim, self).create(cr, uid, vals, context=context)
    
    def add_event(self, cr, uid, ids, context=None):
        '''
        open add event wizard
        '''
        # we test if new event are allowed
        data = self.allow_new_event(cr, uid, ids, context=context)
        if not all(x['allow'] for x in data.values()):
            event_type_name = [x['last_type'][1] for x in data.values() if (not x['allow'] and x['last_type'])]
            if event_type_name:
                # not allowed previous event (last_type is present)
                raise osv.except_osv(_('Warning !'), _('Previous event (%s) does not allow further event.')%event_type_name[0])
            else:
                # not allowed claim type (no last_type)
                claim_type_name = [x['claim_type'][1] for x in data.values()][0]
                raise osv.except_osv(_('Warning !'), _('Claim Type (%s) does not allow events.')%claim_type_name)
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
    
    def allow_new_event(self, cr, uid, ids, context=None):
        '''
        return True if last event type allows successor event
        the tuple of the last event type (key, name)
        the available type tuple list
        '''
        # objects
        event_obj = self.pool.get('claim.event')
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
            # we first check if the claim type supports events
            if self.get_claim_type_rules().get(claim_type[0]):
                # order by order_claim_event, so we can easily get the last event
                ids = event_obj.search(cr, uid, [('return_claim_id_claim_event', '=', obj.id)], order='order_claim_event', context=context)
                # if no event, True
                if not ids:
                    allow = True
                    list = self.get_claim_event_type()
                else:
                    # we are interested in the last value of returned list -> -1
                    data = event_obj.read(cr, uid, ids[-1], ['type_claim_event'], context=context)
                    # event type key
                    last_event_type_key = data['type_claim_event']
                    # event type name
                    event_type = self.get_claim_event_type()
                    last_event_type_name = [x[1] for x in event_type if x[0] == last_event_type_key][0]
                    last_event_type = (last_event_type_key, last_event_type_name)
                    # get available selection
                    claim_rules = self.get_claim_rules()
                    available_list = claim_rules.get(last_event_type_key, False)
                    if available_list:
                        allow = True
                        list = [(x, y[1]) for x in available_list for y in self.get_claim_event_type() if y[0] == x]
            # update result
            result[obj.id] = {'allow': allow,
                              'last_type': last_event_type,
                              'list': list,
                              'claim_type': claim_type}
        return result
    
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
        
        # errors
        errors = {'missing_src_location': False,
                  'missing_lot': False,
                  'wrong_lot_type_need_standard': False,
                  'wrong_lot_type_need_internal': False,
                  'no_lot_needed': False,
                  }
        for obj in self.browse(cr, uid, ids, context=context):
            for item in obj.product_line_ids_return_claim:
                # reset the integrity status
                item.write({'integrity_status_claim_product_line': 'empty'}, context=context)
                # product management type
                data = prod_obj.read(cr, uid, [item.product_id_claim_product_line.id], ['batch_management', 'perishable', 'type', 'subtype'], context=context)[0]
                management = data['batch_management']
                perishable = data['perishable']
                asset = data['type'] == 'product' and data['subtype'] == 'asset'
                kit = data['type'] == 'product' and data['subtype'] == 'kit'
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
                        data = lot_obj.read(cr, uid, [item.lot_id_claim_product_line.id], ['life_date','name','type'], context=context)
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
                        data = lot_obj.read(cr, uid, [item.lot_id_claim_product_line.id], ['life_date','name','type'], context=context)
                        lot_type = data[0]['type']
                        if lot_type != 'internal':
                            errors.update(wrong_lot_type_need_internal=True)
                            item.write({'integrity_status': 'wrong_lot_type_need_internal'}, context=context)
                else:
                    # no lot needed - no date needed
                    if item.lot_id_claim_product_line:
                        errors.update(no_lot_needed=True)
                        item.write({'integrity_status': 'no_lot_needed'}, context=context)
                
        # check the encountered errors
        return all([not x for x in errors.values()])
    
    def load_products(self, cr, uid, ids, context=None):
        '''
        load products data from selected origin
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        # objects
        product_line_obj = self.pool.get('claim.product.line')
        for obj in self.browse(cr, uid, ids, context=context):
            for move in obj.move_lines:
                # create corresponding product line
                product_line_values = {}
    
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
            partner_id = data['partner_id2']
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
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # results
        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {'contains_event_return_claim': len(obj.event_ids_return_claim) > 0}
            
        return result
    
    _columns = {'name': fields.char(string='Reference', size=1024, required=True), # default value
                'creation_date_return_claim': fields.date(string='Creation Date', required=True), # default value
                'po_so_return_claim': fields.char(string='Order', size=1024),
                'type_return_claim': fields.selection(CLAIM_TYPE, string='Type', required=True),
                'category_return_claim': fields.selection(ORDER_CATEGORY, string='Category'),
                'description_return_claim': fields.text(string='Description'),
                'follow_up_return_claim': fields.text(string='Follow Up'),
                'state': fields.selection(CLAIM_STATE, string='State', readonly=True), # default value
                'from_picking_wizard_return_claim': fields.boolean(string='From Picking Wizard', readonly=True),
                # many2one
                'sequence_id_return_claim': fields.many2one('ir.sequence', 'Events Sequence', required=True, ondelete='cascade'), # from create function
                'partner_id_return_claim': fields.many2one('res.partner', string='Partner', required=True),
                'po_id_return_claim': fields.many2one('purchase.order', string='Purchase Order'),
                'so_id_return_claim': fields.many2one('sale.order', string='Sale Order'),
                'picking_id_return_claim': fields.many2one('stock.picking', string='Origin', required=True), #origin
                'event_picking_id_return_claim': fields.many2one('stock.picking', string='Chained Picking from IN'), #chained picking from incoming shipment
                'default_src_location_id_return_claim': fields.many2one('stock.location', string='Default Source Location', required=True), # default value
                # one2many
                'event_ids_return_claim': fields.one2many('claim.event', 'return_claim_id_claim_event', string='Events'),
                'product_line_ids_return_claim': fields.one2many('claim.product.line', 'claim_id_claim_product_line', string='Products'),
                # functions
                'contains_event_return_claim': fields.function(_vals_get_claim, method=True, string='Contains Events', type='boolean', readonly=True, multi='get_vals_claim'),
                }
    
    _defaults = {'creation_date_return_claim': lambda *a: time.strftime('%Y-%m-%d'),
                 'name': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'return.claim'),
                 'default_src_location_id_return_claim': lambda obj, cr, uid, c: obj.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_stock') and obj.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1] or False,
                 'state': 'draft',
                 'from_picking_wizard_return_claim': False,
                 'po_id_return_claim': False,
                 'so_id_return_claim': False,
                 }
    
    def _check_claim(self, cr, uid, ids, context=None):
        """
        claim checks
        """
        if not context:
            context={}
        for obj in self.browse(cr, uid, ids, context=context):
            # the selected origin must contain stock moves
            if not len(obj.picking_id_return_claim.move_lines) > 0:
                raise osv.except_osv(_('Warning !'), _('Selected Origin must contain at least one stock move.'))
            # the selected origin must be done
            if obj.picking_id_return_claim.state != 'done':
                raise osv.except_osv(_('Warning !'), _('Selected Origin must be in Done state.'))
            # origin type
            if obj.picking_id_return_claim.type not in ['in', 'out']:
                raise osv.except_osv(_('Warning !'), _('Selected Origin must be either an Incoming Shipment or a Delivery Order or a Picking Ticket.'))
            # origin subtype
            if obj.picking_id_return_claim.subtype not in ['standard', 'picking']:
                raise osv.except_osv(_('Warning !'), _('PPL or Packing should not be selected.'))
            # not draft picking ticket, even if done
            if obj.picking_id_return_claim.subtype == 'picking' and not obj.picking_id_return_claim.backorder_id:
                raise osv.except_osv(_('Warning !'), _('Draft Picking Tickets are not allowed as Origin, Picking Ticket must be selected.'))
            # if claim type does not allow events, no events should be present
            if not self.get_claim_type_rules().get(obj.type_return_claim) and (len(obj.event_ids_return_claim) > 0):
                raise osv.except_osv(_('Warning !'), _('Events are not allowed for selected Claim Type.'))
            # if supplier, origin must be in
            if obj.type_return_claim == 'supplier' and obj.picking_id_return_claim.type != 'in':
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
    
    _order = 'name desc'
    
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
        line = sequence.get_id(test='id', context=context)
        vals.update({'name': 'EV/%s'%line, 'order_claim_event': int(line)})
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
        # location_id
        location_id = False
        # event type
        event_type = kwargs['event_type']
        # origin browse object
        origin = kwargs['claim_picking']
        # claim type
        claim_type = kwargs['claim_type']
        # not event type
        if not event_type or not origin:
            return False
        # treat each event type
        if event_type == 'return':
            if claim_type == 'supplier':
                # take the source location of the first move of origin picking object
                # property_stock_supplier
                location_id = origin.move_lines[0].location_id.id
            elif claim_type == 'customer':
                # take the destination location of the first move of origin picking object
                # property_stock_customer
                location_id = origin.move_lines[0].location_dest_id.id
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
    
    def _do_process_accept(self, cr, uid, obj, context=None):
        '''
        process logic for accept event
        
        - no change to event picking
        '''
        return True
        
    def _do_process_quarantine(self, cr, uid, obj, context=None):
        '''
        process logic for quarantine event
        
        - destination of picking moves becomes Quarantine (Analyze)
        '''
        # objects
        move_obj = self.pool.get('stock.move')
        # event picking object
        event_picking = obj.return_claim_id_claim_event.event_picking_id_return_claim
        # update the destination location for each move
        move_ids = [move.id for move in event_picking.move_lines]
        move_obj.write(cr, uid, move_ids, {'location_dest_id': context['common']['quarantine_anal']}, context=context)
        # validate the event picking
        event_picking_id = obj.return_claim_id_claim_event.event_picking_id_return_claim.id
        self._validate_picking(cr, uid, event_picking_id, context=context)
        return True
        
    def _do_process_scrap(self, cr, uid, obj, context=None):
        '''
        process logic for scrap event
        
        - destination of picking moves becomes Quarantine (before scrap)
        '''
        # objects
        move_obj = self.pool.get('stock.move')
        # event picking object
        event_picking = obj.return_claim_id_claim_event.event_picking_id_return_claim
        # update the destination location for each move
        move_ids = [move.id for move in event_picking.move_lines]
        move_obj.write(cr, uid, move_ids, {'location_dest_id': context['common']['quarantine_scrap']}, context=context)
        # validate the event picking
        event_picking_id = obj.return_claim_id_claim_event.event_picking_id_return_claim.id
        self._validate_picking(cr, uid, event_picking_id, context=context)
        return True
        
    def _do_process_return(self, cr, uid, obj, context=None):
        '''
        process logic for return event
        
        - depends on the type of claim - supplier or customer
        - destination of picking moves becomes original Supplier/Customer [property_stock_supplier or property_stock_customer from res.partner]
        - name of picking becomes IN/0001 -> IN/0001-return type 'out' for supplier
        - name of picking becomes OUT/0001 -> OUT/0001-return type 'in' for customer
        - (is not set to done - defined in _picking_done_cond)
        - if replacement is needed, we create a new picking
        '''
        # objects
        move_obj = self.pool.get('stock.move')
        pick_obj = self.pool.get('stock.picking')
        picking_tools = self.pool.get('picking.tools')
        # event picking object
        event_picking = obj.return_claim_id_claim_event.event_picking_id_return_claim
        # origin picking in/out
        origin_picking = obj.return_claim_id_claim_event.picking_id_return_claim
        # claim
        claim = obj.return_claim_id_claim_event
        # claim type
        claim_type = claim.type_return_claim
        # new name, previous name + -return
        new_name = origin_picking.name + '-return'
        # get the picking values and move values according to claim type
        picking_values = {'name': new_name,
                          'partner_id': claim.partner_id_return_claim.id, # both partner needs to be filled??
                          'partner_id2': claim.partner_id_return_claim.id,
                          'reason_type_id': context['common']['rt_goods_return']}
        move_values = {}
        if claim_type == 'supplier':
            picking_values.update({'type': 'out'})
            # moves go back to supplier, source location comes from input (if dynamic) or from claim product values
            move_values.update({'location_dest_id': claim.partner_id_return_claim.property_stock_supplier.id})
        elif claim_type == 'customer':
            picking_values.update({'type': 'in'})
            # receive return from customer, and go into input
            move_values.update({'location_id': claim.partner_id_return_claim.property_stock_customer.id,
                                'location_dest_id': context['common']['input_id']})
        # update the picking
        event_picking.write(picking_values, context=context)
        # update the destination location for each move
        move_ids = [move.id for move in event_picking.move_lines]
        # get the move values according to claim type
        move_obj.write(cr, uid, move_ids, move_values, context=context)
        # check assign for event picking
        picking_tools.check_assign(cr, uid, event_picking.id, context=context)
        # do we need replacement?
        if obj.replacement_picking_expected_claim_event:
            # we update the replacement picking object and lines
            # new name, previous name + -return
            replacement_name = origin_picking.name + '-replacement'
            replacement_values = {'name': replacement_name,
                                  'partner_id': claim.partner_id_return_claim.id, #both partner needs to be filled??
                                  'partner_id2': claim.partner_id_return_claim.id,
                                  'reason_type_id': context['common']['rt_goods_replacement'],
                                  'purchase_id': origin_picking.purchase_id.id,
                                  'sale_id': origin_picking.sale_id.id,
                                  }
            replacement_move_values = {}
            
            if claim_type == 'supplier':
                replacement_values.update({'type': 'in'})
                # receive back from supplier, destination default input
                replacement_move_values.update({'location_id': claim.partner_id_return_claim.property_stock_supplier.id,
                                                'location_dest_id': context['common']['input_id']})
            elif claim_type == 'customer':
                replacement_values.update({'type': 'out'})
                # resend to customer, from stock by default (can be changed by user later)
                replacement_move_values.update({'location_id': context['common']['stock_id'],
                                                'location_dest_id': claim.partner_id_return_claim.property_stock_customer.id})
            # we copy the event return picking
            replacement_id = pick_obj.copy(cr, uid, event_picking.id, replacement_values, context=context)
            # update the moves
            replacement_move_ids = move_obj.search(cr, uid, [('picking_id', '=', replacement_id)], context=context)
            # get the move values according to claim type
            move_obj.write(cr, uid, replacement_move_ids, replacement_move_values, context=context)
            # confirm and check availability of replacement picking
            picking_tools.confirm(cr, uid, replacement_id, context=context)
            picking_tools.check_assign(cr, uid, replacement_id, context=context)
                
        return True
    
    def do_process_event(self, cr, uid, ids, context=None):
        '''
        button function call - from_picking is False
        '''
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
        '''
        process the events
        
        - create a picking if not coming from chained picking processing
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # objects
        claim_obj = self.pool.get('return.claim')
        fields_tools = self.pool.get('fields.tools')
        data_tools = self.pool.get('data.tools')
        pick_obj = self.pool.get('stock.picking')
        picking_tools = self.pool.get('picking.tools')
        # load common data
        data_tools.load_common_data(cr, uid, ids, context=context)
        # base of function names
        base_func = '_do_process_'
        for obj in self.browse(cr, uid, ids, context=context):
            # integrity check on product lines for corresponding claim
            integrity_check = claim_obj.check_product_lines_integrity(cr, uid, obj.return_claim_id_claim_event.id, context=context)
            if not integrity_check:
                # return False
                return False
            # create picking object if not coming from chained IN picking process
            if not obj.return_claim_id_claim_event.from_picking_wizard_return_claim:
                # we use default values as if the picking was from chained creation (so type is 'internal')
                # different values need according to event type is then replaced during specific do_process functions
                claim = obj.return_claim_id_claim_event
                event_picking_values = {'type': 'internal',
                                        'partner_id2': claim.partner_id_return_claim.id,
                                        'origin': claim.po_so_return_claim,
                                        'order_category': claim.category_return_claim,
                                        'reason_type_id': context['common']['rt_internal_supply'],
                                        'move_lines': [(0, 0, {'name': x.name,
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
                                                               'location_id': x.src_location_id_claim_product_line.id,
                                                               'location_dest_id': context['common']['stock_id'],
                                                               'company_id': context['common']['company_id'],
                                                               'reason_type_id': context['common']['rt_internal_supply']}) for x in claim.product_line_ids_return_claim]
                                        }
   
                # create picking
                new_event_picking_id = pick_obj.create(cr, uid, event_picking_values, context=context)
                # confirm the picking + check availability
                picking_tools.confirm(cr, uid, new_event_picking_id, context=context)
                picking_tools.check_assign(cr, uid, new_event_picking_id, context=context)
                # update the claim setting the link to created event picking
                claim_obj.write(cr, uid, [claim.id], {'event_picking_id_return_claim': new_event_picking_id}, context=context)
        
        for obj in self.browse(cr, uid, ids, context=context):
            # we start a new loop in order to have browse object reloaded, taking into account possible previous modification to claim object
            result = getattr(self, base_func + obj.type_claim_event)(cr, uid, obj, context=context)
            # event is done
            obj.write({'state': 'done'}, context=context)
            # log process message
            event_type_name = fields_tools.get_selection_name(cr, uid, object=self, field='type_claim_event', key=obj.type_claim_event, context=context)
            self.log(cr, uid, obj.id, _('%s Event %s has been processed.')%(event_type_name, obj.name))
            # we force the state of claim to in_progress
            obj.return_claim_id_claim_event.write({'state': 'in_progress'}, context=context)
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
            result[obj.id].update({'location_id_claim_event': dest_loc_id})
            # hidden state (attrs in tree view)
            result[obj.id].update({'hidden_state': obj.state})
            
        return result
    
    _columns = {'return_claim_id_claim_event': fields.many2one('return.claim', string='Claim', required=True, ondelete='cascade', readonly=True),
                'creation_date_claim_event': fields.date(string='Creation Date', required=True, readonly=True), # default value
                'type_claim_event': fields.selection(CLAIM_EVENT_TYPE, string='Type', required=True),
                'replacement_picking_expected_claim_event': fields.boolean(string='Replacement expected for Return Claim?', help="An Incoming Shipment will be automatically created corresponding to returned products."),
                'description_claim_event': fields.text(string='Description'),
                'state': fields.selection(CLAIM_EVENT_STATE, string='State', readonly=True), # default value
                # auto fields from create function
                'name': fields.char(string='Reference', size=1024, readonly=True), # from create function
                'order_claim_event': fields.integer(string='Creation Order', readonly=True), # from create function
                # functions
                'location_id_claim_event': fields.function(_vals_get_claim, method=True, string='Associated Location', type='many2one', relation='stock.location', readonly=True, multi='get_vals_claim'),
                'hidden_state': fields.function(_vals_get_claim, method=True, string='Hidden State', type='selection', selection=CLAIM_EVENT_STATE, readonly=True, multi='get_vals_claim'),
                }
    
    _defaults = {'creation_date_claim_event': lambda *a: time.strftime('%Y-%m-%d'),
                 'state': 'draft',
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
                    data = prodlot_obj.read(cr, uid, [vals.get('lot_id_claim_product_line')], ['life_date'], context=context)
                    expired_date = data[0]['life_date']
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
        
        # objects
        loc_obj = self.pool.get('stock.location')
        prod_obj = self.pool.get('product.product')
        # corresponding product object
        product_obj = prod_obj.browse(cr, uid, product_id, context=context)
        # uom from product is taken by default if needed
        uom_id = uom_id or product_obj.uom_id.id
        # we do not want the children location
        stock_context = dict(context, compute_child=False)
        # we check for the available qty (in:done, out: assigned, done)
        res = loc_obj.compute_availability(cr, uid, [location_id], False, product_id, uom_id, context=context)
        if prodlot_id:
            # if a lot is specified, we take this specific qty info - the lot may not be available in this specific location
            qty = res[location_id].get(prodlot_id, False) and res[location_id][prodlot_id]['total'] or 0.0
        else:
            # otherwise we take total according to the location
            qty = res[location_id]['total']
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
    
    def on_change_product_id(self, cr, uid, ids, location_id, product_id, prodlot_id, uom_id=False, context=None):
        '''
        the product changes, set the hidden flag if necessary
        '''
        result = {}
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
        
        if product_id:
            product_obj = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            # set the default uom
            uom_id = product_obj.uom_id.id
            result.setdefault('value', {})['uom_id_claim_product_line'] = uom_id
            result.setdefault('value', {})['hidden_batch_management_mandatory_claim_product_line'] = product_obj.batch_management
            result.setdefault('value', {})['hidden_perishable_mandatory_claim_product_line'] = product_obj.perishable
            asset_check = product_obj.type == 'product' and product_obj.subtype == 'asset'
            result.setdefault('value', {})['hidden_asset_claim_product_line'] = asset_check
            kit_check = product_obj.type == 'product' and product_obj.subtype == 'kit'
            result.setdefault('value', {})['hidden_kit_claim_product_line'] = kit_check
            
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
            
        return result
        
    _columns = {'integrity_status_claim_product_line': fields.selection(string=' ', selection=INTEGRITY_STATUS_SELECTION, readonly=True),
                'name': fields.char(string='Name', size=1024), # auto data from create/write
                'qty_claim_product_line': fields.float(string='Qty', digits_compute=dp.get_precision('Product UoM'), required=True),
                # many2one
                'claim_id_claim_product_line': fields.many2one('return.claim', string='Claim', required=True, ondelete='cascade'),
                'product_id_claim_product_line': fields.many2one('product.product', string='Product', required=True),
                'uom_id_claim_product_line': fields.many2one('product.uom', string='UoM', required=True),
                'lot_id_claim_product_line': fields.many2one('stock.production.lot', string='Batch N.'),
                'expiry_date_claim_product_line': fields.many2one('stock.production.lot', string='Exp'),
                'asset_id_claim_product_line' : fields.many2one('product.asset', string='Asset'),
                'composition_list_id_claim_product_line': fields.many2one('composition.kit', string='Kit'),
                'src_location_id_claim_product_line': fields.many2one('stock.location', string='Src Location'),
                'stock_move_id_claim_product_line': fields.many2one('stock.move', string='Corresponding IN stock move'), # value from wizard process
                'type_check': fields.char(string='Type Check', size=1024,), # default value
                # functions
                'claim_type_claim_product_line': fields.function(_vals_get_claim, method=True, string='Claim Type', type='selection', selection=CLAIM_TYPE, store=False, readonly=True, multi='get_vals_claim'),
                'hidden_stock_available_claim_product_line': fields.float(string='Available Stock', digits_compute=dp.get_precision('Product UoM'), invisible=True),
                'claim_state_claim_product_line': fields.function(_vals_get_claim, method=True, string='Claim State', type='selection', selection=CLAIM_STATE, store=False, readonly=True, multi='get_vals_claim'),
                'hidden_perishable_mandatory_claim_product_line': fields.function(_vals_get_claim, method=True, type='boolean', string='Exp', store=False, readonly=True, multi='get_vals_claim'),
                'hidden_batch_management_mandatory_claim_product_line': fields.function(_vals_get_claim, method=True, type='boolean', string='B.Num', store=False, readonly=True, multi='get_vals_claim'),
                'hidden_asset_claim_product_line': fields.function(_vals_get_claim, method=True, type='boolean', string='Asset Check', store=False, readonly=True, multi='get_vals_claim'),
                'hidden_kit_claim_product_line': fields.function(_vals_get_claim, method=True, type='boolean', string='Kit Check', store=False, readonly=True, multi='get_vals_claim'),
                }
    
    _defaults = {'type_check': 'out',
                 'integrity_status_claim_product_line': 'empty',
                 'claim_type_claim_product_line': lambda obj, cr, uid, c: c.get('claim_type', False),
                 'src_location_id_claim_product_line': lambda obj, cr, uid, c: c.get('claim_type', False) in ['supplier', 'transport'] and c.get('default_src', False) or False,
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
        # if return claim: we do not close the processed picking, it is now an out picking which need to be processed
        if partial_datas['register_a_claim_partial_picking']:
            if partial_datas['claim_type_partial_picking'] == 'return':
                return False
        
        return True
    
    def _custom_code(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the do_partial method from stock_override>stock.py>stock_picking
        
        - allow to execute specific custom code before processing picking to done
        - no supposed to modify partial_datas
        '''
        # objects
        claim_obj = self.pool.get('return.claim')
        event_obj = self.pool.get('claim.event')
        move_obj = self.pool.get('stock.move')
        fields_tools = self.pool.get('fields.tools')
        # get the partial_datas from the wizard
        partial_datas = kwargs['partial_datas']
        # get the processed picking (pick if no backorder, new_picking if backorder, both under concerned_picking name) - this is an internal chained picking
        concerned_picking = kwargs['concerned_picking']
        # test if we need a claim
        if partial_datas['register_a_claim_partial_picking']:
            # this is theoretically only possible for internal picking, which are linked to an incoming shipment
            if concerned_picking.type != 'internal':
                raise osv.except_osv(_('Warning !'), _('Claim registration during picking process is only available for internal picking.'))
            # we create a claim
            # corresponding move_id from incoming shipment
            in_move_id = False
            if not len(concerned_picking.move_lines):
                # no lines, we cannot register a claim because the link to original picking is missing
                raise osv.except_osv(_('Warning !'), _('Processed an internal picking without moves, cannot find original Incoming shipment for claim registration.'))
            for move in concerned_picking.move_lines:
                src_move_ids = move_obj.search(cr, uid, [('move_dest_id', '=', move.id)], context=context)
                if not src_move_ids:
                    # we try to find the incoming shipment with by backorder link
                    back_ids = self.search(cr, uid, [('backorder_id', '=', concerned_picking.id)], context=context)
                    if len(back_ids) != 1:
                        # cannot find corresponding stock move in incoming shipment
                        raise osv.except_osv(_('Warning !'), _('Corresponding Incoming Shipment cannot be found. Registration of claim cannot be processed. (no back order)'))
                    else:
                        # we try with the backorder
                        for b_move in self.browse(cr, uid, back_ids[0], context=context).move_lines:
                            b_src_move_ids = move_obj.search(cr, uid, [('move_dest_id', '=', b_move.id)], context=context)
                            if not b_src_move_ids:
                                raise osv.except_osv(_('Warning !'), _('Corresponding Incoming Shipment cannot be found. Registration of claim cannot be processed. (no IN for back order moves)'))
                            else:
                                in_move_id = b_src_move_ids[0]
                else:
                    in_move_id = src_move_ids[0]
            # get corresponding stock move browse
            in_move = move_obj.browse(cr, uid, in_move_id, context=context)
            # check that corresponding picking is incoming shipment
            if in_move.picking_id.type != 'in':
                raise osv.except_osv(_('Warning !'), _('Corresponding picking object is not an Incoming Shipment. Registration of claim cannot be processed.'))
            # po reference
            po_reference = in_move.picking_id.origin
            # po_id
            po_id = in_move.picking_id.purchase_id.id
            # category
            category = in_move.picking_id.order_category
            # partner id - from the wizard, as partner is not mandatory for Incoming Shipment
            partner_id = partial_datas['partner_id_partial_picking']
            # picking id
            picking_id = in_move.picking_id.id
            # we get the stock move of incoming shipment, we get the origin of picking
            claim_values = {'po_so_return_claim': po_reference,
                            'po_id_return_claim': po_id,
                            'type_return_claim': 'supplier',
                            'category_return_claim': category,
                            'description_return_claim': partial_datas['description_partial_picking'],
                            'follow_up_return_claim': False,
                            'from_picking_wizard_return_claim': True,
                            'event_picking_id_return_claim': concerned_picking.id,
                            'partner_id_return_claim': partner_id,
                            'picking_id_return_claim': picking_id,
                            'product_line_ids_return_claim': [(0, 0, {'qty_claim_product_line': x.product_qty,
                                                                      'product_id_claim_product_line': x.product_id.id,
                                                                      'uom_id_claim_product_line': x.product_uom.id,
                                                                      'lot_id_claim_product_line': x.prodlot_id.id,
                                                                      'expiry_date_claim_product_line': x.expired_date,
                                                                      'asset_id_claim_product_line': x.asset_id.id,
                                                                      'composition_list_id_claim_product_line': x.composition_list_id.id,
                                                                      'src_location_id_claim_product_line': x.location_id.id,
                                                                      'stock_move_id_claim_product_line': x.id}) for x in concerned_picking.move_lines]
                            }
            
            new_claim_id = claim_obj.create(cr, uid, claim_values, context=context)
            # log creation message
            claim_name = claim_obj.read(cr, uid, new_claim_id, ['name'], context=context)['name']
            claim_obj.log(cr, uid, new_claim_id, _('The new Claim %s to supplier has been registered during internal chained Picking process.')%claim_name)
            # depending on the claim type, we create corresponding event
            selected_event_type = partial_datas['claim_type_partial_picking']
            event_values = {'return_claim_id_claim_event': new_claim_id,
                            'type_claim_event': selected_event_type,
                            'replacement_picking_expected_claim_event': partial_datas['replacement_picking_expected_partial_picking'],
                            'description_claim_event': partial_datas['description_partial_picking'],
                            }
            new_event_id = event_obj.create(cr, uid, event_values, context=context)
            event_type_name = fields_tools.get_selection_name(cr, uid, object='claim.event', field='type_claim_event', key=selected_event_type, context=context)
            event_obj.log(cr, uid, new_event_id, _('The new %s Event %s has been created.')%(event_type_name, claim_name))
            # we process the event
            event_obj._do_process_event(cr, uid, [new_event_id], context=context)
        
#        raise osv.except_osv(_('Warning !'), _('End'))
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

