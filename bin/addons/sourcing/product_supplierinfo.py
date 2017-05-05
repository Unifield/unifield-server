# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 TeMPO Consulting, MSF
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

from osv import fields
from osv import osv

from tools.translate import _


class product_supplierinfo(osv.osv):
    """
    override name_get to display name of the related supplier

    override create to be able to create a new supplierinfo from sourcing view
    """
    _name = 'product.supplierinfo'
    _inherit = 'product.supplierinfo'

    def _get_false(self, cr, uid, ids, field_name, arg, context=None):
        '''
        return false for each id
        '''
        if isinstance(ids, (long, int)):
            ids = [ids]

        result = {}
        for l_id in ids:
            result[l_id] = []
        return result

    def _get_product_ids(self, cr, uid, obj, name, args, context=None):
        '''
        from the product.template id returns the corresponding product.product
        '''
        if not args:
            return []
        if args[0][1] != '=':
            raise osv.except_osv(
                _('Error !'),
                _('Filter not implemented'),
            )
        # product id of sourcing line
        productId = args[0][2]
        # gather product template id for that product
        templateId = self.pool.get('product.product').browse(cr, uid, productId, context=context).product_tmpl_id.id
        # search filter on product_id of supplierinfo
        return [('product_id', '=', templateId)]

    _columns = {
        'product_product_ids': fields.function(
            _get_false,
            fnct_search=_get_product_ids,
            method=True,
            type='one2many',
            relation='product.product',
            string="Products",
        ),
    }

    def name_get(self, cr, uid, ids, context=None):
        '''
        product_supplierinfo
        display the name of the product instead of the id of supplierinfo
        '''
        if not ids:
            return []

        result = []
        for supinfo in self.browse(cr, uid, ids, context=context):
            supplier = supinfo.name
            result.append((supinfo.id, supplier.name_get(context=context)[0][1]))

        return result

    def create(self, cr, uid, values, context=None):
        '''
        product_supplierinfo
        inject product_id in newly created supplierinfo
        '''
        if not values:
            values = {}
        if context and 'sourcing-product_id' in context:
            productId = context['sourcing-product_id']
            product = self.pool.get('product.product').browse(cr, uid, productId, context=context)
            values.update({'product_id': product.product_tmpl_id.id})

        return super(product_supplierinfo, self).create(cr, uid, values, context)

product_supplierinfo()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
