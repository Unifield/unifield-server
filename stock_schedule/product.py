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

'''
Add a new field on product object to allow you
to search a product when a category is selected
on procurement_auto or procurement_cycle object
form.
'''
class product_product(osv.osv):
    _name = 'product.product'
    _inherit = 'product.product'
    
    def _get_categ(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Returns the category of the product
        '''
        res = {}
        
        for product in self.browse(cr, uid, ids):
            res[product.id] = product.categ_id.id
            
        return res
    
    def _search_categ(self, cr, uid, obj, name, args, context=None):
        '''
        Return False if the research has no category
        '''
        ids = []
        for cond in args:
            if cond[0] == 'fnct_categ_id' and cond[1] == '=' and not cond[2]:
                res_ids = self.search(cr, uid, [])
            elif cond[0] == 'fnct_categ_id':
                res_ids = self.search(cr, uid, [('categ_id', 'child_of', cond[2])])
            else:
                res_ids = self.search(cr, uid, [cond])
            ids = ids + res_ids
                
        if ids:
            return [('id','in',tuple(ids))]
        else:
            return [('id', '=', '0')]

    
    _columns = {
        'fnct_categ_id': fields.function(_get_categ, fnct_search=_search_categ, string='Category', 
                                         method=True, type='many2one', relation='product.category'),
    }
    
product_product()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
