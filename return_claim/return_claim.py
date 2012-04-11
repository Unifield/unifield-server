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
# event type
CLAIM_EVENT_TYPE = [('accept', 'Accept'),
                    ('quarantine', 'Move to Quarantine'),
                    ('scrap', 'Scrap'),
                    ('return', 'Return')]
# event state
CLAIM_EVENT_STATE = [('draft', 'Draft'),
                     ('in_progress', 'In Progress'),
                     ('done', 'Done')]
# import partner_type from msf_partner
from msf_partner import PARTNER_TYPE
from msf_order_date import TRANSPORT_TYPE
from msf_order_date import ZONE_SELECTION
from purchase_override import PURCHASE_ORDER_STATE_SELECTION
from sale_override import SALE_ORDER_STATE_SELECTION

class return_claim(osv.osv):
    _name = 'return.claim'
    
    _columns = {'name_return_claim': fields.char(string='Reference', size=1024),
                'creation_date_return_claim': fields.date(string='Creation Date', required=True),
                'partner_return_claim': fields.many2one('res.partner', string='Partner', required=True),
                'picking_id_return_claim': fields.many2one('stock.picking', string='Origin'), #origin
                'po_so_return_claim': fields.char(string='Order', size=1024),
                'type_return_claim': fields.selection(CLAIM_TYPE, string='Type'),
                'category_return_claim': fields.selection(ORDER_CATEGORY, string='Category'),
                'event_ids_return_claim': fields.one2many('claim.event', 'return_claim_id_claim_event', string='Events'),
                'product_line_ids_return_claim': fields.one2many('claim.product.line', 'return_claim_id', string='Products'),
                'default_src_location_id_return_claim': fields.many2one('stock.location', string='Default Source Location', required=True),
                'dest_location_id_return_claim': fields.many2one('stock.location', string='Destination Location'), #function depending on type
                'description_return_claim': fields.text(string='Description'),
                'follow_up_return_claim': fields.text(string='Follow Up'),
                'state': fields.selection(CLAIM_STATE, string='State'),
                }
    
    
return_claim()


class claim_event(osv.osv):
    '''
    event for claims
    '''
    _name = 'claim.event'
    _columns = {'return_claim_id_claim_event': fields.many2one('return.claim', string='Claim', required=True, ondelete='cascade'),
                'name_claim_event': fields.char(string='Reference', size=1024),
                'creation_date_claim_event': fields.date(string='Creation Date', required=True),
                'type_claim_event': fields.selection(CLAIM_EVENT_TYPE, string='Type'),
                'description_claim_event': fields.text(string='Description'),
                'state': fields.selection(CLAIM_EVENT_STATE, string='State'),
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



