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

from osv import osv
from osv import fields
import decimal_precision as dp

from tools.translate import _


class sale_price_setup(osv.osv_memory):
    _name = 'sale.price.setup'
    _inherit = 'res.config'
    
    _columns = {
        'sale_price': fields.float(digits=(16,2), string='Fields price percentage', required=True,
                                   help="""This percentage will be applied on field price from product form view.
  The Field Price is computed as follow: [Standard Price * (1 + Fields price percentage)]"""),
    }
    
    def _check_sale_price_negative_value(self, cr, uid, ids, context=None):
        '''
        Check if the entered value is more than 0.00%
        '''
        for price in self.browse(cr, uid, ids, context=context):
            if price.sale_price < 0.00:
                return False
        
        return True
    
    _constraints = [
        (_check_sale_price_negative_value, 'You cannot have a negative field price percentage !', ['sale_price']),
    ]
    
    def sale_price_change(self, cr, uid, ids, sale_price, context=None):
        '''
        Check if the entered value is more than 0.00%
        '''
        res = {}
        
        if sale_price < 0.00:
            res.update({'value': {'sale_price': 0.00},
                        'warning': {'title': 'Wrong value !',
                                    'message': 'You cannot have a negative field price percentage !'}})
        
        return res
    
    def default_get(self, cr, uid, fields, context=None):
        '''
        Display the default value for sale price
        '''
        setup_id = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        
        res = super(sale_price_setup, self).default_get(cr, uid, fields, context=context)
        
        res['sale_price'] = setup_id.sale_price
        
        return res
    
    def execute(self, cr, uid, ids, context=None):
        '''
        Fill the delivery process field in company
        '''
        assert len(ids) == 1, "We should only get one object from the form"
        payload = self.browse(cr, uid, ids[0], context=context)
        
        setup_obj = self.pool.get('unifield.setup.configuration')
        pricelist_obj = self.pool.get('product.pricelist')
        version_obj = self.pool.get('product.pricelist.version')
        item_obj = self.pool.get('product.pricelist.item')
        
        setup_id = setup_obj.get_config(cr, uid)
            
        # Update all sale pricelists QT wanted to remove it
#        pricelist_ids = pricelist_obj.search(cr, uid, [('type', '=', 'sale')], context=context)
#        version_ids = version_obj.search(cr, uid, [('pricelist_id', 'in', pricelist_ids)], context=context)
#        item_ids = item_obj.search(cr, uid, [('price_version_id', 'in', version_ids)], context=context)
#        item_obj.write(cr, uid, item_ids, {'price_discount': payload.sale_price/100}, context=context)
    
        setup_obj.write(cr, uid, [setup_id.id], {'sale_price': payload.sale_price}, context=context)
        
sale_price_setup()

# QT wanted to remove it
#class product_pricelist_item(osv.osv):
#    _name = 'product.pricelist.item'
#    _inherit = 'product.pricelist.item'
#    
#    def create(self, cr, uid, vals, context=None):
#        '''
#        if the item is related to a sale price list, get the Unifield
#        configuration value for price_discount
#        '''
#        setup_id = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
#        version_obj = self.pool.get('product.pricelist.version')
#        
#        if 'price_version_id' in vals:
#            price_type = version_obj.browse(cr, uid, vals['price_version_id'], context=context).pricelist_id.type
#            if price_type == 'sale':
#                # Get the price from Unifield configuration
#                if setup_id:
#                    price_discount = setup_id.sale_price
#                    vals.update({'price_discount': price_discount/100})
#        
#        return super(product_pricelist_item, self).create(cr, uid, vals, context=context)
#    
#product_pricelist_item()

class product_template(osv.osv):
    _name = 'product.template'
    _inherit = 'product.template'
    
    def _get_list_price(self, cr, uid, ids, fields, arg, context=None):
        '''
        Update the list_price = Field Price according to standard_price = Cost Price and the sale_price of the unifield_setup_configuration
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        setup_obj = self.pool.get('unifield.setup.configuration')
        for obj in self.browse(cr, uid, ids, context=context):
            res[obj.id] = False
            standard_price = obj.standard_price
            #US-1035: Fixed the wrong hardcoded id given when calling config setup object 
            setup_br = setup_obj.get_config(cr, uid)
            if not setup_br:
                return res
            percentage = setup_obj.browse(cr, uid, [setup_br.id], context)[0].sale_price
            list_price = standard_price * (1 + (percentage/100.00))
            res[obj.id] = list_price
        return res
    
    _columns = {
            'standard_price': fields.float('Cost Price', required=True, digits_compute=dp.get_precision('Account Computation'), help="Product's cost for accounting stock valuation. It is the base price for the supplier price."),
            'list_price': fields.function(_get_list_price, method=True, type='float', string='Sale Price', 
            store = {
                'product.template': (lambda self, cr, uid, ids, c=None: ids, ['standard_price'], 10),
            },
            digits_compute=dp.get_precision('Sale Price Computation'),
            help="Base price for computing the customer price. Sometimes called the catalog price."),
    }
    
product_template()

class product_product(osv.osv):
    _name = 'product.product'
    _inherit = 'product.product'

    def onchange_sp(self, cr, uid, ids, standard_price, context=None):
        '''
        On change standard_price, update the list_price = Field Price according to standard_price = Cost Price and the sale_price of the unifield_setup_configuration
        '''
        res = {}
        if standard_price :
            if standard_price < 0.0:
                warn_msg = {
                    'title': _('Warning'), 
                    'message': _("The Cost Price must be greater than 0 !")
                }
                res.update({'warning': warn_msg, 
                            'value': {'standard_price': 1, 
                                      'list_price': self.onchange_sp(cr, uid, ids, standard_price=1, context=context).get('value').get('list_price')}})
            else:
                setup_obj = self.pool.get('unifield.setup.configuration')
                #US-1035: Fixed the wrong hardcoded id given when calling config setup object 
                setup_br = setup_obj.get_config(cr, uid)
                if not setup_br:
                    return res
                
                percentage = setup_obj.browse(cr, uid, setup_br.id, context)[0].sale_price
                list_price = standard_price * (1 + (percentage/100.00))
                if 'value' in res:
                    res['value'].update({'list_price': list_price})
                else:
                    res.update({'value': {'list_price': list_price}})
        return res

product_product()
