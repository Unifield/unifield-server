# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2011 MSF, TeMPO Consulting
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

from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta, relativedelta
from osv import osv, fields
from osv.orm import browse_record, browse_null
from tools.translate import _

import decimal_precision as dp
import netsvc
import pooler
import time

class stock_location(osv.osv):
    '''
    override stock location to add:
    - quarantine location (checkbox - boolean)
    - destruction location (checkbox - boolean)
    - location category (selection)
    '''
    _inherit = 'stock.location'
    
    _columns = {'quarantine_location': fields.boolean(string='Quarantine Location'),
                'destruction_location': fields.boolean(string='Destruction Loction'),
                'location_category': fields.selection([('stock', 'Stock'),
                                                       ('consumption_unit', 'Consumption Unit'),
                                                       ('transition', 'Transition'),
                                                       ('other', 'Other'),], string='Location Category', required=True),
                }
    
stock_location()


class procurement_order(osv.osv):
    _inherit = 'procurement.order'

    def _do_create_proc_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        hook to update defaults data
        '''
        # call super
        values = super(procurement_order, self)._do_create_proc_hook(cr, uid, ids, context=context, *args, **kwargs)
        # as location, we take the input of the warehouse
        op = kwargs.get('op', False)
        assert op, 'missing op'
        # update location value
        values.update(location_id=op.warehouse_id.lot_input_id.id)
        
        return values

procurement_order()