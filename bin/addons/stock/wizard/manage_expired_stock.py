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

from osv import osv, fields
from tools.translate import _

from datetime import date



class manage_expired_stock(osv.osv):
    _name = 'manage.expired.stock'

    _columns = {
        'location_id': fields.many2one(
            'stock.location',
            string='Location',
            help="The requested Location",
            required=True,
            domain=['&', '|', ('quarantine_location', '=', True), ('destruction_location', '=', False), ('usage', '!=', 'view')],
        ),
        'dest_loc_id': fields.many2one(
            'stock.location',
            string='Destination Location',
            help="The requested Destination Location",
            required=True,
            domain=['&', '|', ('quarantine_location', '=', True), ('destruction_location', '=', True), ('usage', '!=', 'view')],
        ),
    }

    def create_int_expired_stock(self, cr, uid, ids, context=False):
        '''
        Creates an Internal Picking to send all expired products to destruction or quarantine
        '''
        if context is None:
            context = {}

        ir_obj = self.pool.get('ir.model.data')
        lot_obj = self.pool.get('stock.production.lot')

        wizard = self.browse(cr, uid, ids[0], context=context)

        if wizard.location_id.id == wizard.dest_loc_id.id:
            raise osv.except_osv(
                _('Error'),
                _('You cannot have the sourcing location and destination location with the same location.')
            )

        lot_ids = lot_obj.search(cr, uid, [('life_date', '<=', date.today())])

        dest_loc_id = wizard.dest_loc_id.id
        exp_rt_id = ir_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_expiry')[1]

        moves_lines = []
        context['location_id'] = wizard.location_id.id

        for lot in lot_obj.browse(cr, uid, lot_ids, fields_to_fetch=['stock_available', 'product_id', 'life_date'], context=context):
            qty_available = lot.stock_available
            if qty_available > 0 and (lot.product_id.perishable or lot.product_id.batch_management):
                moves_lines.append((0, 0, {
                    'name': lot.product_id.name,
                    'product_id': lot.product_id.id,
                    'product_qty': qty_available,
                    'product_uom': lot.product_id.uom_id.id,
                    'location_id': wizard.location_id.id,
                    'location_dest_id': dest_loc_id,
                    'reason_type_id': exp_rt_id,
                    'prodlot_id': lot.id,
                    'expired_date': lot.life_date,
                }))

        if not moves_lines:
            raise osv.except_osv(_('Warning !'), _('There is no expired quantity for this location.'))

        int_values = {
            'name': self.pool.get('ir.sequence').get(cr, uid, 'stock.picking.internal'),
            'type': 'internal',
            'subtype': 'standard',
            'invoice_state': 'none',
            'reason_type_id': exp_rt_id,
            'from_manage_expired': True,
            'move_lines': moves_lines,
        }

        new_int_id = self.pool.get('stock.picking').create(cr, uid, int_values, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_type': 'form',
            'view_mode': 'form, tree',
            'target': 'crush',
            'view_id': [self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'view_picking_form')[1]],
            'res_id': new_int_id,
            'context': context,
        }


manage_expired_stock()
