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

from osv import osv, fields

from tools.translate import _


class product_list_add_products(osv.osv_memory):
    _name = 'product.list.add.products'
    _description = 'Add product to list'

    _columns = {
        'list_id': fields.many2one(
            'product.list',
            string='List',
            readonly=True,
        ),
        'parent_list_id': fields.many2one(
            'product.list',
            string='Parent List',
            readonly=True,
        ),
        'product_ids': fields.many2many(
            'product.product',
            'product_add_product_list_rel',
            'wiz_list_id',
            'product_id',
            string='Products',
        ),
    }

    def default_get(self, cr, uid, fields, context=None):
        '''
        To get default values for the object.
        '''
        list_obj = self.pool.get('product.list')

        if not context:
            context = {}

        list_id = context and context.get('active_id', False) or False
        if not list_id:
            raise osv.except_osv(_('Error'), _('No list found !'))

        res = super(product_list_add_products, self).\
            default_get(cr, uid, fields, context=context)
        res.update({
            'list_id': list_id,
            'parent_list_id': list_obj.browse(cr, uid, list_id, context=context).parent_id.id,
        })

        return res

    def fill_list(self, cr, uid, ids, context=None):
        '''
        Fill the list with the selected products
        '''
        line_obj = self.pool.get('product.list.line')

        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for wiz in self.browse(cr, uid, ids, context=context):
            products = []
            for line in wiz.list_id.product_ids:
                products.append(line.name.id)

            for product in wiz.product_ids:
                if product.id not in products:
                    line_obj.create(cr, uid, {
                        'name': product.id,
                        'list_id': wiz.list_id.id,
                    }, context=context)

            context.update({'active_id': wiz.list_id.id})

        return {'type': 'ir.actions.act_window_close'}

product_list_add_products()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
