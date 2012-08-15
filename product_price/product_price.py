# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF, Smile
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

class product_product(osv.osv):
    _name = 'product.product'
    _inherit = 'product.product'

    def onchange_sp(self, cr, uid, ids, standard_price, context=None):
        '''
        On change standard_price, update the list_price = Field Price according to standard_price = Cost Price and the sale_price of the unifield_setup_configuration
        '''
        res = {}
        setup_obj = self.pool.get('unifield.setup.configuration')
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
                percentage = setup_obj.browse(cr, uid, [1], context)[0].sale_price
                list_price = standard_price * (1 + percentage)
                if 'value' in res:
                    res['value'].update({'list_price': list_price})
                else:
                    res.update({'value': {'list_price': list_price}})
        return res
        
    def create(self, cr, uid, vals, context=None):
        '''
        On create, update the list_price = Field Price according to standard_price = Cost Price and the sale_price of the unifield_setup_configuration
        '''
        setup_obj = self.pool.get('unifield.setup.configuration')
        if vals.get('standard_price'):
            standard_price = vals.get('standard_price')
            percentage = setup_obj.browse(cr, uid, [1], context)[0].sale_price
            list_price = standard_price * (1 + percentage)
            vals.update({'list_price': list_price})
        return super(product_product, self).create(cr, uid, vals, context=context)
        
    def write(self, cr, uid, ids, vals, context=None):
        '''
        On write, update the list_price = Field Price according to standard_price = Cost Price and the sale_price of the unifield_setup_configuration
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        setup_obj = self.pool.get('unifield.setup.configuration')
        if vals.get('standard_price'):
            standard_price = vals.get('standard_price')
            percentage = setup_obj.browse(cr, uid, [1], context)[0].sale_price
            list_price = standard_price * (1 + percentage)
            vals.update({'list_price': list_price})
        return super(product_product, self).write(cr, uid, ids, vals, context=context)
    
product_product()