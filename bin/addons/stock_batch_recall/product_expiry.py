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
            'partner_name': False,
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
            'partner_name': False,
        })
        return super(stock_production_lot, self).copy_data(cr, uid, id, default, context=context)

    # UF-1617: Handle the instance in the batch number object
    # US-838: this method is removed in integration, because the 2 fields are no more used, xmlid_name and partner name
    
    
#    def create(self, cr, uid, vals, context=None):
        '''
        override create method to set the instance id to the current instance if it has not been provided
        
        # UF-2148: make the xmlid_name from batch name for building xmlid if the value is not given in vals
        if 'product_id' in vals and ('xmlid_name' not in vals or not vals['xmlid_name']):
            prod_name = self.pool.get('product.product').browse(cr, uid, vals['product_id'], context=context)
            #US-838: xmlid_name now takes product code, batch name and expiry date as value, this value must be unique (soft constraint) 
            vals['xmlid_name'] = '%s_%s_%s' % (prod_name.default_code, vals['name'], vals['life_date'])
        
        if 'partner_name' not in vals or not vals['partner_name']:
            company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
            if company and company.partner_id:
                vals['partner_name'] = company.partner_id.name
        
        return super(stock_production_lot, self).create(cr, uid, vals, context)

        '''

    # US-838: This method got moved from addons/msf_outgoing/wizard/incoming_shipment_processor.py
    def _get_prodlot_from_expiry_date(self, cr, uid, expiry_date, product_id, context=None):
        """
        Search if an internal batch exists in the system with this expiry date.
        If no, create the batch.
        """ 
        # Objects
        seq_obj = self.pool.get('ir.sequence')

        # Double check to find the corresponding batch
        lot_ids = self.search(cr, uid, [
                            ('life_date', '=', expiry_date),
                            ('type', '=', 'internal'),
                            ('product_id', '=', product_id),
                            ], context=context)

        # No batch found, create a new one
        if not lot_ids:
            seq_ed = seq_obj.get(cr, uid, 'stock.lot.serial')
            vals = {
                'product_id': product_id,
                'life_date': expiry_date,
                'name': seq_ed,
                'type': 'internal',
            }
            lot_id = self.create(cr, uid, vals, context)
        else:
            lot_id = lot_ids[0]

        return lot_id

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
        'partner_name': fields.char('Partner', size=128),
        'xmlid_name': fields.char('XML Code, hidden field', size=128), # UF-2148, this field is used only for xml_id
    }

    _defaults = {
        'life_date': _get_date('life_time'),
        'use_date': _get_date('use_time'),
        'removal_date': _get_date('removal_time'),
        'alert_date': _get_date('alert_time'),
    }
    
    # UF-2148: Removed the name unique constraint in specific_rules and use only this constraint with 3 attrs: name, prod and instance 
    _sql_constraints = [('batch_name_uniq', 'unique(name, product_id, partner_name)', 'Batch name must be unique per instance and product!'),]
    
stock_production_lot()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
