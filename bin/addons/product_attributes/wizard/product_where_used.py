# -*- coding: utf-8 -*-
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

from osv import osv
from osv import fields


class product_where_used(osv.osv_memory):
    _name = 'product.where.used'

    def _get_data(self, cr, uid, ids, field_name, args, context=None):
        '''
        Fill data according to product
        '''
        line_obj = self.pool.get('product.list.line')
        item_obj = self.pool.get('composition.item')
        prod_obj = self.pool.get('product.product')

        if not context:
            context= {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}

        for where in self.browse(cr, uid, ids, context=context):
            product = where.product_id
            list_ids = []
            lines = line_obj.search(cr, uid, [('name', '=', product.id)], context=context)
            for l in line_obj.browse(cr, uid, lines, context=context):
                list_ids.append(l.list_id.id)

            kit_ids = []
            items = item_obj.search(cr, uid, [('item_product_id', '=', product.id),
                                              ('item_kit_id.composition_type', '=', 'theoretical')],
                                            context=context)
            for i in item_obj.browse(cr, uid, items, context=context):
                kit_ids.append(i.item_kit_id.id)

            product_ids = [x.id for x in product.options_ids_inv]

            res[where.id] = {'list_ids': list_ids,
                             'product_ids': product_ids,
                             'kit_ids': kit_ids}

        return res

    _columns = {
        'product_id': fields.many2one('product.product', string='Product', required=True),
        'default_code': fields.related('product_id', 'default_code', type='char', string='Default Code', readonly=True),
        'product_description': fields.related('product_id', 'name', type='char', string='Name', readonly=True),
        'list_ids': fields.function(_get_data, method=True, type='one2many', relation='product.list',
                                    store=False, string='Lists/Sublists', readonly=True, multi='data'),
        'product_ids': fields.function(_get_data, method=True, type='one2many', relation='product.product',
                                       store=False, string='Parent products', readonly=True, multi='data'),
        'kit_ids': fields.function(_get_data, method=True, type='one2many', relation='composition.kit',
                                   store=False, string='Theoretical Kit Composition', readonly=True, multi='data'),
    }

    def where_used(self, cr, uid, ids, context=None):
        '''
        Return the good view
        '''
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        return {'type': 'ir.actions.act_window',
                'res_model': 'product.where.used',
                'res_id': ids[0],
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'crush',
                'context': context}

product_where_used()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
