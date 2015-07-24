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


class product_to_list(osv.osv_memory):
    _name = 'product.to.list'
    _description = 'Import product to list'

    _columns = {
        'list_type': fields.selection(
            selection=[
                ('exist', 'Existing list'),
                ('new', 'New list'),
                ('replace', 'Replace list'),
            ],
            string='Existed/New list',
            required=True,
        ),
        'list_id': fields.many2one(
            'product.list',
            string='Existing list',
        ),
        'new_list_name': fields.char(
            size=128,
            string='Name of the new list',
        ),
        'new_list_type': fields.selection(
            selection=[
                ('list', 'List'),
                ('sublist', 'Sublist'),
            ],
            string='Type of the new list',
        ),
        'product_ids': fields.many2many(
            'product.product',
            'product_import_in_list',
            'list_id', 'product_id',
            string='Products to import',
            readonly=True,
        ),
    }

    def default_get(self, cr, uid, fields, context=None):
        """
        Set product from the selected IDs on the product search view.
        """
        if not context:
            context = {}

        res = super(product_to_list, self).\
            default_get(cr, uid, fields, context=context)

        res['product_ids'] = context.get('active_ids', [])
        res['list_type'] = 'exist'

        return res

    def import_products(self, cr, uid, ids, context=None):
        '''
        Import products in list
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        list_obj = self.pool.get('product.list')
        line_obj = self.pool.get('product.list.line')

        list_id = False
        line_ids = []
        product_ids = []

        for imp in self.browse(cr, uid, ids, context=context):
            if imp.list_type == 'new':
                list_id = list_obj.create(cr, uid, {
                    'name': imp.new_list_name,
                    'type': imp.new_list_type,
                }, context=context)
            else:
                list_id = imp.list_id.id

                # Remove all old lines
                if imp.list_type == 'replace':
                    list_brw = list_obj.\
                        browse(cr, uid, list_id, context=context).product_ids
                    for list_line in list_brw:
                        line_obj.unlink(cr, uid, list_line.id, context=context)

                for l in imp.list_id.product_ids:
                    if l.name.id not in product_ids:
                        product_ids.append(l.name.id)

            for prod in imp.product_ids:
                if prod.id not in product_ids:
                    line_ids.append(line_obj.create(cr, uid, {
                        'name': prod.id,
                        'list_id': list_id,
                    }, context=context))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.list',
            'res_id': list_id,
            'view_mode': 'form,tree',
            'view_type': 'form',
        }

product_to_list()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
