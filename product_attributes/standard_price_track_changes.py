# encoding: utf-8
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 TeMPO consulting, MSF
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
import time

import decimal_precision as dp

from tools.translate import _
from osv import fields
from osv import osv


class standard_price_track_changes(osv.osv):
    """
    Records the modification of the cost price (standard_price) of a product.
    It is complementary (but independent) to the Track Changes feature.

    To record the modification of the cost price, the product Costing Method
    should always be average price. The recorded prices are always in
    functional currency.

    Here is the list of transactions where a modification of the cost price
    is recorded:
      * at original import/creation of Product,
      * at Initial stock inventory,
      * Each time product is received via IN, cost is re-calculated based on
        Moving Average Cost calculation,
      * When Product Cost re-valuation is done.

    These records are only available with an Excel report on the product form.
    """
    _name = 'standard.price.track.changes'
    _description = 'Product Cost Price Track Changes'
    _rec_name = 'change_date'

    _columns = {
        'change_date': fields.datetime(
            string='Date',
            required=True,
            readonly=True,
        ),
        'product_id': fields.many2one(
            'product.product',
            string='Product',
            required=True,
            readonly=True,
            ondelete='cascade',
        ),
        'old_standard_price': fields.float(
            string='Old Cost Price',
            digits_compute=dp.get_precision('Account'),
            required=False,
            readonly=True,
        ),
        'new_standard_price': fields.float(
            string='New Cost Price',
            digits_compute=dp.get_precision('Account'),
            required=True,
            readonly=True,
        ),
        'user_id': fields.many2one(
            'res.users',
            string='User',
            required=True,
            readonly=True,
            ondelete='set null',
        ),
        'transaction_name': fields.char(
            string='Transaction name',
            size=256,
            required=False,
            readonly=True,
            translate=True,
            help="Name of the transaction which changed the product cost price",
        ),
        'in_price_changed': fields.boolean(
            string='IN price changed',
            help="True if the price has been manually changed during reception",
        ),
    }

    _defaults = {
        'change_date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'user_id': lambda obj, cr, uid, c={}: uid,
        'in_price_changed': False,
    }

    def copy(self, cr, uid, obj_id, default=None, context=None):
        """
        Disallow the possibility to copy standard.price.track.changes object
        :param cr: Cursor to the database
        :param uid: ID of the user that copy the record
        :param obj_id: ID of the standard.price.track.changes to copy
        :param default: Default values for the new record
        :param context: Context of the call
        :return: The ID of the new standard.price.track.changes record
        """
        raise osv.except_osv(
            _('Operation not allowed'),
            _('Copy of standard.price.track.changes is not allowed'),
        )

standard_price_track_changes()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
