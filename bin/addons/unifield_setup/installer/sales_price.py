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

        setup_id = setup_obj.get_config(cr, uid)


        setup_obj.write(cr, uid, [setup_id.id], {'sale_price': payload.sale_price}, context=context)

sale_price_setup()
