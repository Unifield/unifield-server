#!/usr/bin/env python
# -*- encoding: utf-8 -*-
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
from msf_partner import PARTNER_TYPE


class res_partner(osv.osv):
    _name = 'res.partner'
    _inherit = 'res.partner'
    
    def search_in_product(self, cr, uid, obj, name, args, context={}):
        '''
        Search function of related field 'in_product'
        '''
        if not len(args):
            return []
        
        if not context.get('product_id', False) or 'choose_supplier' not in context:
            return []

        supinfo_obj = self.pool.get('product.supplierinfo')
        sup_obj = self.pool.get('res.partner')
        res = []

        info_ids = supinfo_obj.search(cr, uid, [('product_product_ids', '=', context.get('product_id'))])
        info = supinfo_obj.read(cr, uid, info_ids, ['name'])

        sup_in = [x['name'] for x in info]
        
        for arg in args:
            if arg[1] == '=':
                if arg[2]:
                    res = sup_in
            else:
                    res = sup_obj.search(cr, uid, [('id', 'not in', sup_in)])
        
        if not res:
            return [('id', '=', 0)]
        return [('id', 'in', [x[0] for x in res])]
        
    
    def _set_in_product(self, cr, uid, ids, field_name, arg, context={}):
        '''
        Returns according to the context if the partner is in product form
        '''
        res = {}
        
        product_obj = self.pool.get('product.product')
        
        # If we aren't in the context of choose supplier on procurement list
        if not context.get('product_id', False) or 'choose_supplier' not in context:
            for i in ids:
                res[i] = {'in_product': False, 'min_qty': 'N/A', 'delay': 'N/A'}
        else:
            product = product_obj.browse(cr, uid, context.get('product_id'))
            seller_ids = []
            seller_info = {}
            # Get all suppliers defined on product form
            for s in product.seller_ids:
                seller_ids.append(s.name.id)
                seller_info.update({s.name.id: {'min_qty': s.min_qty, 'delay': s.delay}})
            # Check if the partner is in product form
            for i in ids:
                if i in seller_ids:
                    res[i] = {'in_product': True, 'min_qty': '%s' %seller_info[i]['min_qty'], 'delay': '%s' %seller_info[i]['delay']}
                else:
                    res[i] = {'in_product': False, 'min_qty': 'N/A', 'delay': 'N/A'}
                    
        return res

    _columns = {
        'manufacturer': fields.boolean(string='Manufacturer', help='Check this box if the partner is a manufacturer'),
        'partner_type': fields.selection(PARTNER_TYPE, string='Partner type', required=True),
        'in_product': fields.function(_set_in_product, fnct_search=search_in_product, string='In product', type="boolean", readonly=True, method=True, multi='in_product'),
        'min_qty': fields.function(_set_in_product, string='Min. Qty', type='char', readonly=True, method=True, multi='in_product'),
        'delay': fields.function(_set_in_product, string='Delivery Lead time', type='char', readonly=True, method=True, multi='in_product'),
    }

    _defaults = {
        'manufacturer': lambda *a: False,
        'partner_type': lambda *a: 'external',
    }
    
    def search(self, cr, uid, args=[], offset=0, limit=None, order=None, context={}, count=False):
        '''
        Sort suppliers to have all suppliers in product form at the top of the list
        '''
        supinfo_obj = self.pool.get('product.supplierinfo')
        
        # Get all supplier
        tmp_res = super(res_partner, self).search(cr, uid, args, offset, limit, order, context=context, count=count)
        if not context.get('product_id', False) or 'choose_supplier' not in context or count:
            return tmp_res
        else:
            # Get all supplier in product form
            args.append(('in_product', '=', True))
            res_in_prod = super(res_partner, self).search(cr, uid, args, offset, limit, order, context=context, count=count)
            new_res = []

            # Sort suppliers by sequence in product form
            if 'product_id' in context:
                supinfo_ids = supinfo_obj.search(cr, uid, [('name', 'in', res_in_prod), ('product_product_ids', '=', context.get('product_id'))], order='sequence')
            
                for result in supinfo_obj.read(cr, uid, supinfo_ids, ['name']):
                    try:
                        tmp_res.remove(result['name'][0])
                        new_res.append(result['name'][0])
                    except:
                        pass

            #return new_res  # comment this line to have all suppliers (with suppliers in product form at the top of the list)

            new_res.extend(tmp_res)
            
            return new_res

res_partner()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

