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

from ..return_claim import CLAIM_TYPE

class add_event(osv.osv_memory):
    '''
    wizard called to confirm an action
    '''
    _name = "add.event"
    
    def _get_types(self, cr, uid, context=None):
        '''
        filter available types according to existing events
        '''
        claim_id = context['claim_id']
        available_list = context['data'][claim_id]['list']
        return available_list
    
    _columns = {'claim_id': fields.many2one('return.claim', string='Claim', readonly=True),
                'claim_type': fields.selection(CLAIM_TYPE, string='Claim Type', readonly=True),
                'claim_partner_id': fields.many2one('res.partner', string='Claim Partner', readonly=True),
                'creation_date': fields.date(string='Creation Date', required=True),
                'event_type': fields.selection(_get_types, string='Event Type', required=True),
                'dest_location_id': fields.many2one('stock.location', string='Destination Location', readonly=True),
                }
    
    _defaults = {'claim_id': lambda s, cr, uid, c: c.get('claim_id', False),
                 'claim_type': lambda s, cr, uid, c: c.get('claim_type', False),
                 'claim_partner_id': lambda s, cr, uid, c: c.get('claim_partner_id', False),
                 'creation_date': lambda *a: time.strftime('%Y-%m-%d'),
                 }
    
    def on_change_event_type(self, cr, uid, ids, event_type, claim_partner_id, claim_type, context=None):
        '''
        the event changes
        '''
        # objects
        event_obj = self.pool.get('claim.event')
        result = {'value': {}}
        dest_loc_id = event_obj.get_location_for_event_type(cr, uid, context=context, event_type=event_type, claim_partner_id=claim_partner_id, claim_type=claim_type)
        result['value'].update({'dest_location_id': dest_loc_id})
        return result
    
    def compute_date(self, cr, uid, ids, context=None):
        '''
        compute the date from items and write it to the wizard
        '''
        if context is None:
            context = {}
        # objects
        kit_obj = self.pool.get('composition.kit')
        kit_ids = context['active_ids']
        new_date = kit_obj._compute_expiry_date(cr, uid, kit_ids, context=context)
        self.write(cr, uid, ids, {'new_date': new_date}, context=context)
        return True

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
        claim_ids = context['active_ids']
        for obj in self.browse(cr, uid, ids, context=context):
            if not obj.creation_date:
                raise osv.except_osv(_('Warning !'), _('You need to specify a creation date.'))
            if not obj.event_type:
                raise osv.except_osv(_('Warning !'), _('You need to specify an event type.'))
            # event values
            event_values = {'return_claim_id_claim_event': 1,
                            'creation_date_claim_event': 1,
                            'type_claim_event': 1,
                            'description_claim_event': 1,
                            }
            # create event
            
        return {'type': 'ir.actions.act_window',
                'res_model': 'return.claim',
                'view_type': 'form',
                'view_mode': 'form,tree',
                'res_id': claim_ids[0],
                'target': 'crunch',
                'context': context}
    
add_event()
