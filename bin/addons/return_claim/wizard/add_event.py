# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Copyright (C) 2011 MSF, TeMPO Consulting.
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

from osv import fields, osv
from tools.translate import _
import decimal_precision as dp
import time

import netsvc

class add_event(osv.osv_memory):
    '''
    wizard called to confirm an action
    '''
    _name = "add.event"
    
    def _get_types(self, cr, uid, context=None):
        '''
        filter available types according to existing events
        '''
        if not context:
            context = {}
        claim_id = context.get('claim_id', False)
        # when coming from unique_fields_views.yml, inherited_views.yml, we do not have corresponding claim_id in context
        if not claim_id:
            return []
        available_list = context['data'][claim_id]['list']
        return available_list
    
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
            dest_loc_id = self.pool.get('claim.event').get_location_for_event_type(cr, uid, context=context,
                                                           event_type=obj.event_type,
                                                           claim_partner_id=obj.claim_partner_id.id,
                                                           claim_type=obj.claim_type,
                                                           claim_picking=obj.claim_id.picking_id_return_claim)
            result[obj.id] = {'location_id_claim_event': dest_loc_id}
            
        return result
    
    _columns = {'claim_id': fields.many2one('return.claim', string='Claim', readonly=True),
                'claim_type': fields.selection(lambda s, cr, uid, c: s.pool.get('return.claim').get_claim_type(), string='Claim Type', readonly=True),
                'claim_partner_id': fields.many2one('res.partner', string='Claim Partner', readonly=True),
                'claim_picking_id': fields.many2one('stock.picking', string='Claim Origin', readonly=True),
                'creation_date': fields.date(string='Creation Date', required=True),
                'event_type': fields.selection(_get_types, string='Event Type', required=True),
                'replacement_picking_expected_partial_picking': fields.boolean(string='Replacement expected ?'),
                # functions
                'dest_location_id': fields.function(_vals_get_claim, method=True, string='Associated Location', type='many2one', relation='stock.location', readonly=True, multi='get_vals_claim'),
                }
    
    _defaults = {'claim_id': lambda s, cr, uid, c: c.get('claim_id', False),
                 'claim_type': lambda s, cr, uid, c: c.get('claim_type', False),
                 'claim_partner_id': lambda s, cr, uid, c: c.get('claim_partner_id', False),
                 'claim_picking_id': lambda s, cr, uid, c: c.get('claim_picking_id', False),
                 'creation_date': lambda *a: time.strftime('%Y-%m-%d'),
                 }
    
    def on_change_event_type(self, cr, uid, ids, event_type, claim_partner_id, claim_type, claim_picking_id, context=None):
        '''
        the event changes
        '''
        # objects
        event_obj = self.pool.get('claim.event')
        result = {'value': {}}
        dest_loc_id = event_obj.get_location_for_event_type(cr, uid, context=context,
                                                            event_type=event_type,
                                                            claim_partner_id=claim_partner_id,
                                                            claim_type=claim_type,
                                                            claim_picking=self.pool.get('stock.picking').browse(cr, uid, claim_picking_id, context=context)),
        result['value'].update({'dest_location_id': dest_loc_id})
        return result

    def do_add_event(self, cr, uid, ids, context=None):
        '''
        create an event
        '''
        # quick integrity check
        assert context, 'No context defined, problem on method call'
        if isinstance(ids, (int, long)):
            ids = [ids]
        # objects
        event_obj = self.pool.get('claim.event')
        claim_id = False
        for obj in self.browse(cr, uid, ids, context=context):
            claim_id = obj.claim_id.id
            if not obj.creation_date:
                raise osv.except_osv(_('Warning !'), _('You need to specify a creation date.'))
            if not obj.event_type:
                raise osv.except_osv(_('Warning !'), _('You need to specify an event type.'))
            # reset replacement if not return
            if obj.event_type not in ('accept', 'scrap', 'return'):
                replacement = False
            else:
                replacement = obj.replacement_picking_expected_partial_picking
            # event values
            event_values = {'return_claim_id_claim_event': obj.claim_id.id,
                            'creation_date_claim_event': obj.creation_date,
                            'type_claim_event': obj.event_type,
                            'description_claim_event': False,
                            'replacement_picking_expected_claim_event': replacement,
                            }
            # create event
            event_id = event_obj.create(cr, uid, event_values, context=context)
#        return {'type': 'ir.actions.act_window_close'}
        return {'type': 'ir.actions.act_window',
                'res_model': 'return.claim',
                'view_type': 'form',
                'view_mode': 'form,tree',
                'res_id': claim_id,
                'target': 'crunch',
                'context': context}
    
add_event()
