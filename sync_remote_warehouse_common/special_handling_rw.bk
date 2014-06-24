# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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


##############################################################################
#
#    This class is a common place for special treatment for Remote Warehouse
#
##############################################################################

from osv import fields, osv
from tools.translate import _

'''
 This class extension is to treat special cases for remote warehouse
'''
class stock_move(osv.osv):
    # This is to treat the location requestor on Remote warehouse instance if IN comes from an IR
    _inherit = 'stock.move'
    _columns = {'location_requestor_rw': fields.many2one('stock.location', 'Location Requestor For RW-IR', required=False, ondelete="cascade"),
                }

    def create(self, cr, uid, vals, context=None):
        if not context:
            context = {}
        if not vals:
            vals = {}

        # Save the location requestor from IR into the field location_requestor_rw if exists
        res = super(stock_move, self).create(cr, uid, vals, context=context)
        move = self.browse(cr, uid, [res], context=context)[0]
        if move.purchase_line_id:
            proc = move.purchase_line_id.procurement_id
            if proc and proc.sale_order_line_ids and proc.sale_order_line_ids[0].order_id and proc.sale_order_line_ids[0].order_id.procurement_request:
                location_dest_id = proc.sale_order_line_ids[0].order_id.location_requestor_id.id
                cr.execute('update stock_move set location_requestor_rw=%s where id=%s', (location_dest_id, move.id))
        
        return res

    def _get_location_for_internal_request(self, cr, uid, context=None, **kwargs):
        '''
            If it is a remote warehouse instance, then take the location requestor from IR
        '''
        location_dest_id = super(stock_move, self)._get_location_for_internal_request(cr, uid, context=context, **kwargs)
        type = self.pool.get('sync.client.entity').get_entity(cr, uid).usb_instance_type
        if type == 'remote_warehouse':
            move = kwargs['move']
            if move.location_requestor_rw:
                return move.location_requestor_rw.id
        # for any case, just return False and let the caller to pick the normal loc requestor
        return False

stock_move()