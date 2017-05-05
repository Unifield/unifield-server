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
        # specifies the direction of the USB synchronisation - like the 'direction' field
        'direction_usb': fields.selection((('rw_to_cp', 'Remote Warehouse to Central Platform'), ('cp_to_rw', 'Central Platform to Remote Warehouse'), ('bidirectional','Bidirectional')), 'Direction', help='The direction of the synchronization'),
    }
    
    _defaults = {
        'direction_usb': 'bidirectional',
    }

    _rules_serialization_mapping = {
        'direction_usb' : 'direction_usb',
    }
    
sync_rule()

class sync_rule_message(osv.osv):

    _inherit = "sync_server.message_rule"
    
    _columns = {
        # specifies the direction of the USB synchronisation
        'direction_usb': fields.selection((('rw_to_cp', 'Remote Warehouse to Central Platform'), ('cp_to_rw', 'Central Platform to Remote Warehouse'), ('bidirectional','Bidirectional')), 'Direction', help='The direction of the synchronization'),
        'destination_name': fields.char('Field to extract destination', size=256, required=False),
    }
    
    _defaults = {
        'direction_usb': 'bidirectional',
    }

    _rules_serialization_mapping = {
        'direction_usb' : 'direction_usb',
    }
    
sync_rule_message()

