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

    # UF-1617: Handle the instance in the batch number object
    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({
            'instance_id': False,
        })
        return super(stock_production_lot, self).copy(cr, uid, id, default, context=context)
    
    # UF-1617: Handle the instance in the batch number object
    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        do not copy asset events
        '''
        if not default:
            default = {}
        default.update({
            'instance_id': False,
        })
        return super(stock_production_lot, self).copy_data(cr, uid, id, default, context=context)

    # UF-1617: Handle the instance in the batch number object
    def create(self, cr, uid, vals, context=None):
        '''
        override create method to set the instance id to the current instance if it has not been provided
        '''
        if 'instance_id' not in vals or not vals['instance_id']:
            company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
            if company and company.instance_id:
                vals['instance_id'] = company.instance_id.id

        return super(stock_production_lot, self).create(cr, uid, vals, context)

    _columns = {
        # renamed from End of Life Date
        'life_date': fields.date('Expiry Date',
            help='The date on which the lot may become dangerous and should not be consumed.', required=True),
        'use_date': fields.date('Best before Date',
            help='The date on which the lot starts deteriorating without becoming dangerous.'),
        'removal_date': fields.date('Removal Date',
            help='The date on which the lot should be removed.'),
        'alert_date': fields.date('Alert Date', help="The date on which an alert should be notified about the production lot."),

        # UF-1617: field only used for sync purpose
        'partner_id': fields.many2one('res.partner', string="Supplier", readonly=True, required=False),
        'instance_id': fields.many2one('msf.instance', 'Instance', readonly=True, required=True),
    }

    _defaults = {
        'life_date': _get_date('life_time'),
        'use_date': _get_date('use_time'),
        'removal_date': _get_date('removal_time'),
        'alert_date': _get_date('alert_time'),
    }
    
    _sql_constraints = [('name_inst_uniq', 'unique(name, instance_id)', 'Batch name must be unique per instance!'),]
    
stock_production_lot()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
