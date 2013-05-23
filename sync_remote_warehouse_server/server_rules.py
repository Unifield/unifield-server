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

class sync_rule(osv.osv):

    _inherit = "sync_server.sync_rule"
    
    _columns = {
        # Specifies that this rule is a rule for USB synchronisations
        'usb': fields.boolean('USB Synchronisation Rule', help='Should this rule be used when using the USB Synchronization engine?', required=True),
        
        # specifies the direction of the USB synchronisation - like the 'direction' field
        'direction_usb': fields.selection((('rw_to_cp', 'Remote Warehouse to Central Platform'), ('cp_to_rw', 'Central Platform to Remote Warehouse'), ('bidirectional','Bidirectional')), 'Direction', help='The direction of the synchronization', required=True),
    }
    
    _defaults = {
        'usb': False,
        'direction_usb': 'bidirectional',
    }

    _rules_serialization_mapping = {
        'usb' : 'usb',
        'direction_usb' : 'direction_usb',
    }
    
    def _get_rules(self, cr, uid, entity, context=None):
        rules_ids = []
        for group in entity.group_ids:
            domain = ['|','|',
                    '&', ('group_id', '=', group.id), ('applies_to_type', '=', False),
                    '&', ('type_id', '=', group.type_id.id), ('applies_to_type', '=', True),
                    ('usb','=',True)]
            ids = self.search(cr, uid, domain, context=context)
            if ids:
                rules_ids.extend(ids)

sync_rule()

class sync_rule_message(osv.osv):

    _inherit = "sync_server.message_rule"
    
    _columns = {
        # Specifies that this rule is a rule for USB synchronisations
        'usb': fields.boolean('USB Synchronisation Rule', help='Should this rule be used when using the USB Synchronization engine?', required=True),
    }
    
    _defaults = {
        'usb': False,
    }

    _rules_serialization_mapping = {
        'usb' : 'usb',
    }
    
    def _get_rules(self, cr, uid, entity, context=None):
        rules_ids = []
        for group in entity.group_ids:
            domain = ['|', '|',
                    '&', ('group_id', '=', group.id), ('applies_to_type', '=', False),
                    '&', ('type_id', '=', group.type_id.id), ('applies_to_type', '=', True),
                    ('usb','=',True)]
            ids = self.search(cr, uid, domain, context=context)
            if ids:
                rules_ids.extend(ids)
        
        return list(set(rules_ids))

sync_rule_message()