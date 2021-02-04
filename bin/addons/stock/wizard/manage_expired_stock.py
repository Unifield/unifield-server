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
from datetime import datetime
from dateutil.relativedelta import relativedelta


IN_NEXT_X_WEEKS = tuple([("%s" % i, _("%s weeks") % str(i)) for i in range(1, 13)])


class manage_expired_stock(osv.osv):
    _name = 'manage.expired.stock'

    _columns = {
        'location_id': fields.many2one(
            'stock.location',
            string='Location',
            help="The requested Location",
            required=True,
            domain=[('destruction_location', '=', False), ('usage', '!=', 'view'), ('usage', '=', 'internal')],
        ),
        'dest_loc_id': fields.many2one(
            'stock.location',
            string='Destination Location',
            help="The requested Destination Location",
            required=True,
            domain=['&', '|', ('quarantine_location', '=', True), ('destruction_location', '=', True), ('usage', '!=', 'view')],
        ),
        'bned_date_sel': fields.selection(
            [('exp_prod', 'Select expired products'), ('soon_exp_prod', 'Select expired products and soon to be expired')],
            'Batch/Expiry Date Selection'
        ),
        'in_next_x_weeks': fields.selection(
            IN_NEXT_X_WEEKS,
            'In the next',
        ),
    }

    def get_exp_data(self, cr, uid, ids, context=False, expiring=False):
        '''
        Fetch the data for the expired prodlot and sometimes soon to expire as well
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

        today = date.today()
        if expiring:
            expiring_date = (today + relativedelta(weeks=-int(wizard.in_next_x_weeks))).strftime('%Y-%m-%d 00:00:00')
            lot_ids = lot_obj.search(cr, uid, [('life_date', '<=', today), ('life_date', '>=', expiring_date)])
        else:
            lot_ids = lot_obj.search(cr, uid, [('life_date', '<=', today)])

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

        return moves_lines

    def open_view_expired_expiring_stock(self, cr, uid, ids, context=False):
        '''
        Open a wizard that displays all products with BN/ED according to set criteria
        '''
        if context is None:
            context = {}
        if not ids:
            return True

        v_exp_obj = self.pool.get('view.expired.expiring.stock')
        data = {'mng_exp_id': ids[0], 'v_mng_exp_lines_ids': self.get_exp_data(cr, uid, ids, context=context, expiring=True)}
        wiz_id = v_exp_obj.create(cr, uid, data, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'view.expired.expiring.stock',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': wiz_id,
            'context': context
        }

    def create_int_expired_stock(self, cr, uid, ids, context=False):
        '''
        Creates an Internal Picking to send all expired products to destruction or quarantine
        '''
        if context is None:
            context = {}
        if not ids:
            return True

        int_values = {
            'name': self.pool.get('ir.sequence').get(cr, uid, 'stock.picking.internal'),
            'type': 'internal',
            'subtype': 'standard',
            'invoice_state': 'none',
            'reason_type_id': self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_expiry')[1],
            'from_manage_expired': True,
            'move_lines': self.get_exp_data(cr, uid, ids, context=context, expiring=False),
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


class view_expired_expiring_stock(osv.osv):
    _name = 'view.expired.expiring.stock'
    _description = 'View Expired/Expiring Products'

    _columns = {
        'mng_exp_id': fields.many2one('manage.expired.stock', string='Manage Expired Stock Id', readonly=True),
        'v_mng_exp_lines_ids': fields.one2many('view.expired.expiring.stock.lines', 'v_mng_exp_id', 'View Expired/Expiring products', readonly=True),
    }

    def create_int_expired_expiring_stock(self, cr, uid, ids, context=None):
        return {'type': 'ir.actions.act_window_close'}

    def del_sel_prod(self, cr, uid, ids, context=None):
        return {'type': 'ir.actions.act_window_close'}

    def cancel(self, cr, uid, ids, context=None):
        return {'type': 'ir.actions.act_window_close'}


view_expired_expiring_stock()


class view_expired_expiring_stock_lines(osv.osv):
    _name = 'view.expired.expiring.stock.lines'
    _description = 'Expired/Expiring Products'

    _columns = {
        'v_mng_exp_id': fields.many2one('view.expired.expiring.stock', string='View Expired/Expiring Products', readonly=True),
        'name': fields.char('Description', size=256, readonly=True),
        'product_id': fields.many2one('product.product', string='Product', readonly=True),
        'prodlot_id': fields.many2one('stock.production.lot', string='Batch Number', readonly=True),
        'expired_date': fields.date(string='Expiry Date', readonly=True),
        'product_qty': fields.float(digits=(16, 2), string='Quantity', related_uom='product_uom', readonly=True),
        'product_uom': fields.many2one('product.uom', string='UoM', readonly=True),
        'location_id': fields.many2one('stock.location', 'Source Location', readonly=True),
        'location_dest_id': fields.many2one('stock.location', 'Destination Location', readonly=True),
        'reason_type_id': fields.many2one('stock.reason.type', string='Reason type', readonly=True),
    }


view_expired_expiring_stock_lines()
