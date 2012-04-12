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

# category
from order_types import ORDER_CATEGORY
# claim type
CLAIM_TYPE = [('supplier', 'Supplier'),
              ('customer', 'Customer'),
              ('transport', 'Transport')]
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
        # we need the context for the wizard switch
        if context is None:
            context = {}
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
        claim_data = claim_type = self.read(cr, uid, ids, ['type_return_claim', 'partner_id_return_claim'], context=context)[0]
        # gather the corresponding claim type
        claim_type = claim_data['type_return_claim']
        # gather the corresponding claim partner
        claim_partner_id = claim_data['partner_id_return_claim']
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
                                                                                                claim_partner_id=claim_partner_id))
        return res
    
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
    
    _columns = {'sequence_id_return_claim': fields.many2one('ir.sequence', 'Events Sequence', required=True, ondelete='cascade'),
                'name': fields.char(string='Reference', size=1024, required=True),
                'creation_date_return_claim': fields.date(string='Creation Date', required=True),
                'partner_id_return_claim': fields.many2one('res.partner', string='Partner', required=True),
                'picking_id_return_claim': fields.many2one('stock.picking', string='Origin'), #origin
                'po_so_return_claim': fields.char(string='Order', size=1024),
                'type_return_claim': fields.selection(CLAIM_TYPE, string='Type', required=True),
                'category_return_claim': fields.selection(ORDER_CATEGORY, string='Category', required=True),
                'event_ids_return_claim': fields.one2many('claim.event', 'return_claim_id_claim_event', string='Events'),
                'product_line_ids_return_claim': fields.one2many('claim.product.line', 'return_claim_id', string='Products'),
                'default_src_location_id_return_claim': fields.many2one('stock.location', string='Default Source Location', required=True),
                'description_return_claim': fields.text(string='Description'),
                'follow_up_return_claim': fields.text(string='Follow Up'),
                'state': fields.selection(CLAIM_STATE, string='State', readonly=True),
                'from_picking_wizard_return_claim': fields.boolean(string='From Picking Wizard', readonly=True),
                # functions
                'contains_event_return_claim': fields.function(_vals_get_claim, method=True, string='Contains Events', type='boolean', readonly=True, multi='get_vals_claim'),
                }
    
    _defaults = {'creation_date_return_claim': lambda *a: time.strftime('%Y-%m-%d'),
                 'name': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'return.claim'),
                 'default_src_location_id_return_claim': lambda obj, cr, uid, c: obj.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_stock') and obj.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1] or False,
                 'state': 'draft',
                 'from_picking_wizard_return_claim': False,
                 }
    
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
        event_type = kwargs['event_type']
        # not event type
        if not event_type:
            return False
        # treat each event type
        if event_type == 'return':
            # we check the location from partner form, according to picking type (in or out)
            claim_type = kwargs['claim_type']
            claim_partner_id = kwargs['claim_partner_id']
            if claim_type == 'supplier':
                pass
        else:
            # we find the corresponding data reference from the dic
            module = EVENT_TYPE_DESTINATION.get(event_type).split('.')[0]
            name = EVENT_TYPE_DESTINATION.get(event_type).split('.')[1]
            location_id = obj_data.get_object_reference(cr, uid, module, name)[1]
        # return the id of the corresponding location
        return location_id
    
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
            dest_loc_id = self.get_location_for_event_type(cr, uid, context=context, event_type=obj.type_claim_event,
                                                           claim_partner_id=obj.return_claim_id_claim_event.partner_id_return_claim,
                                                           claim_type=obj.return_claim_id_claim_event.type_return_claim)
            result[obj.id] = {'dest_location_id_claim_event': dest_loc_id}
            
        return result
    
    _columns = {'return_claim_id_claim_event': fields.many2one('return.claim', string='Claim', required=True, ondelete='cascade'),
                'name': fields.char(string='Reference', size=1024, readonly=True), # from create function
                'order_claim_event': fields.integer(string='Creation Order', readonly=True), # from create function
                'creation_date_claim_event': fields.date(string='Creation Date', required=True),
                'type_claim_event': fields.selection(CLAIM_EVENT_TYPE, string='Type', required=True),
                'description_claim_event': fields.text(string='Description'),
                'state': fields.selection(CLAIM_EVENT_STATE, string='State', readonly=False),
                # functions
                'dest_location_id_claim_event': fields.function(_vals_get_claim, method=True, string='Destination Location', type='many2one', relation='stock.location', readonly=True, multi='get_vals_claim'),
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
    _columns = {'return_claim_id': fields.many2one('return.claim', string='Claim', required=True, ondelete='cascade'),
                }
    
claim_product_line()



