#-*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
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

import datetime
from osv import fields, osv
import pooler
import logging


class stock_production_lot(osv.osv):
    _inherit = 'stock.production.lot'
    _logger = logging.getLogger('------ BATCH MIGRATIONS ')

    def _get_date(dtype):
        """Return a function to compute the limit date for this type"""
        def calc_date(self, cr, uid, context=None):
            """Compute the limit date for a given date"""
            if context is None:
                context = {}
            if not context.get('product_id', False):
                date = False
            else:
                product = pooler.get_pool(cr.dbname).get('product.product').browse(
                    cr, uid, context['product_id'])
                duration = getattr(product, dtype)
                # set date to False when no expiry time specified on the product
                date = duration and (datetime.datetime.today()
                                     + datetime.timedelta(days=duration))
            return date and date.strftime('%Y-%m-%d %H:%M:%S') or False
        return calc_date

    _columns = {
        'life_date': fields.datetime('End of Life Date',
                                     help='The date on which the lot may become dangerous and should not be consumed.'),
        'use_date': fields.datetime('Best before Date',
                                    help='The date on which the lot starts deteriorating without becoming dangerous.'),
        'removal_date': fields.datetime('Removal Date',
                                        help='The date on which the lot should be removed.'),
        'alert_date': fields.datetime('Alert Date', help="The date on which an alert should be notified about the production lot."),
    }
    # Assign dates according to products data
    def create(self, cr, uid, vals, context=None):

        if self.violate_ed_unique(cr, uid, False, vals, context):
            raise osv.except_osv('Error', 'An expiry date with same date for this product exists already!.')

        newid = super(stock_production_lot, self).create(cr, uid, vals, context=context)
        obj = self.browse(cr, uid, newid, context=context)
        towrite = []
        for f in ('life_date', 'use_date', 'removal_date', 'alert_date'):
            if not getattr(obj, f):
                towrite.append(f)
        if context is None:
            context = {}
        context['product_id'] = obj.product_id.id
        self.write(cr, uid, [obj.id], self.default_get(cr, uid, towrite, context=context))
        return newid

    # US-838: this method is to check if the expiry date values are valid
    def violate_ed_unique(self, cr, uid, ids, vals, context):
        if not('product_id' in vals and 'life_date' in vals):
            return False

        prod_obj = self.pool.get('product.product')
        prod = prod_obj.browse(cr, uid, vals['product_id'], context=context)

        # In case it's a EP only product, then search for date and product, no need to search for batch name
        if prod.perishable and not prod.batch_management:
            search_arg = [('life_date', '=', vals['life_date']), ('type', '=', 'internal'), ('product_id', '=', prod.id)]

            if ids: # in case it's a write call, then exclude the current ids
                search_arg.append(('id', 'not in', ids))

            lot_ids = self.search(cr, uid, search_arg, context=context)
            if lot_ids:
                return True
        return False

    def write(self, cr, uid, ids, vals, context=None):
        '''
        force writing of expired_date which is readonly for batch management products
        '''
        if not ids:
            return True
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # US-838: Check if the values are in conflict with the existing data
        if self.violate_ed_unique(cr, uid, ids, vals, context):
            raise osv.except_osv('Error', 'An expiry date with same date for this product exists already!')

        return super(stock_production_lot, self).write(cr, uid, ids, vals, context=context)


    _defaults = {
        'life_date': _get_date('life_time'),
        'use_date': _get_date('use_time'),
        'removal_date': _get_date('removal_time'),
        'alert_date': _get_date('alert_time'),
    }
stock_production_lot()

class product_product(osv.osv):
    _inherit = 'product.product'
    _columns = {
        'life_time': fields.integer('Product Life Time',
                                    help='The number of days before a production lot may become dangerous and should not be consumed.'),
        'use_time': fields.integer('Product Use Time',
                                   help='The number of days before a production lot starts deteriorating without becoming dangerous.'),
        'removal_time': fields.integer('Product Removal Time',
                                       help='The number of days before a production lot should be removed.'),
        'alert_time': fields.integer('Product Alert Time', help="The number of days after which an alert should be notified about the production lot."),
    }
product_product()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
