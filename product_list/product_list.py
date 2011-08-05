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

import time


class product_list(osv.osv):
    _name = 'product.list'
    _description = 'Products list'
    
    def _get_nb_products(self, cr, uid, ids, field_name, arg, context={}):
        '''
        Returns the number of products on the list
        '''
        res = {}
        
        for list in self.browse(cr, uid, ids, context=context):
            res[list.id] = len(list.product_ids)
        
        return res
    
    def write(self, cr, uid, ids, vals, context={}):
        '''
        Adds update date and user information
        '''
        vals['reviewer_id'] = uid
        vals['last_update_date'] = time.strftime('%Y-%m-%d')
        
        return super(product_list, self).write(cr, uid, ids, vals=vals, context=context)
    
        
    def copy(self, cr, uid, id, defaults={}, context={}):
        '''
        Remove the last update date and the reviewer on the new list
        '''
        if not context:
            context = {}
            
        return super(product_list, self).copy(cr, uid, id, {'last_update_date': False,
                                                            'reviewer_id': False}, context=context)
    
    _columns = {
        'name': fields.char(size=128, string='Name', required=True),
        'ref': fields.char(size=128, string='Ref.'),
        'type': fields.selection([('list', 'List'), ('sublist', 'Sublist')], string='Type', required=True),
        'description': fields.char(size=256, string='Description'),
        'creation_date': fields.date(string='Creation date', readonly=True),
        'last_update_date': fields.date(string='Last update date', readonly=True),
        'standard_list_ok': fields.boolean(string='Standard List'),
        'order_list_print_ok': fields.boolean(string='Order list print'),
        'reviewer_id': fields.many2one('res.users', string='Reviewed by', readonly=True),
        'parent_id': fields.many2one('product.list', string='Parent list'),
        'warehouse_id': fields.many2one('stock.warehouse', string='Warehouse'),
        'location_id': fields.many2one('stock.location', string='Stock Location'),
        'product_ids': fields.one2many('product.list.line', 'list_id', string='Products'),
        'nb_products': fields.function(_get_nb_products, method=True, type='integer', string='# of products'),
        
    }
    
    _defaults = {
        'creation_date': lambda *a: time.strftime('%Y-%m-%d'),
    }
    
product_list()


class product_list_line(osv.osv):
    _name = 'product.list.line'
    _description = 'Line of product list'
    
    _columns = {
        'name': fields.many2one('product.product', string='Product name', required=True),
        'list_id': fields.many2one('product.list', string='List', ondelete='cascade'),
        'ref': fields.related('name', 'default_code', string='Product reference', readonly=True, type='char'),
        'comment': fields.char(size=256, string='Comment'),
    }

product_list_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: