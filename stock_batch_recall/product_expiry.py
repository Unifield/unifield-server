##############################################################################
#    
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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
from dateutil.relativedelta import relativedelta

class stock_production_lot(osv.osv):
    _inherit = 'stock.production.lot'
    
    # @@@override@product_expiry.product_expiry._get_date(dtype)
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
                date = duration and (datetime.datetime.today() + relativedelta(months=duration))
            return date and date.strftime('%Y-%m-%d') or False
        return calc_date
    # @@@end

    _columns = {
        # renamed from End of Life Date
        'life_date': fields.date('Expiry Date',
            help='The date on which the lot may become dangerous and should not be consumed.', required=True),
        'use_date': fields.date('Best before Date',
            help='The date on which the lot starts deteriorating without becoming dangerous.'),
        'removal_date': fields.date('Removal Date',
            help='The date on which the lot should be removed.'),
        'alert_date': fields.date('Alert Date', help="The date on which an alert should be notified about the production lot."),
        'partner_id': fields.many2one('res.partner', string="Supplier", readonly=True, required=False), # UF-1617: added this field, only used for the sync module
    }

    _defaults = {
        'life_date': _get_date('life_time'),
        'use_date': _get_date('use_time'),
        'removal_date': _get_date('removal_time'),
        'alert_date': _get_date('alert_time'),
    }
stock_production_lot()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
