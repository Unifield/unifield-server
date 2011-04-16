#!/usr/bin/env python
# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF.
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

class res_partner(osv.osv):
    _name= 'res.partner'
    _inherit = 'res.partner'
    
    _order = 'name'
    
    def _set_in_product(self, cr, uid, ids, field_name, arg, context={}):
        '''
        Returns according to the context if the partner is in product form
        '''
        res = {}
        
        product_obj = self.pool.get('product.product')
        
        # If we aren't in the context of choose supplier on procurement list
        if not context.get('product_id', False) or 'choose_supplier' not in context:
            for i in ids:
                res[i] = False
        else:
            product = product_obj.browse(cr, uid, context.get('product_id'))
            seller_ids = []
            # Get all suppliers defined on product form
            for s in product.seller_ids:
                seller_ids.append(s.name.id)
            # Check if the partner is in product form
            for i in ids:
                if i in seller_ids:
                    res[i] = True
                else:
                    res[i] = False
            
        return res
    
    _columns = {
        'in_product': fields.function(_set_in_product, string='In product', type="boolean", readonly=True, method=True),     
    }
    
    def read(self, cr, uid, ids, fields=None, context={}, load='_classic_read'):
        '''
        Sort the supplier according to the context
        '''
        res = super(res_partner, self).read(cr, uid, ids, fields, context=context, load=load)
        # If we are in the context of choose supplier on procurement list
        if context.get('product_id', False) and 'choose_supplier' in context:
            # Add in_product field in read
            if not 'in_product' in fields:
                fields.append('in_product')
            
            seller_ids =[]
            not_seller_ids = []
            
            for r in res:
                if r.get('in_product', False):
                    seller_ids.append(r)
                else:
                    not_seller_ids.append(r)
                    
            result = seller_ids + not_seller_ids
        else:
            result = res
        
        return result
    
res_partner()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

