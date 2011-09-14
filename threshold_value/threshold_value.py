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

from osv import osv, fields


class threshold_value(osv.osv):
    _name = 'threshold.value'
    _description = 'Threshold value'
    
    _columns = {
        'name': fields.char(size=128, string='Name', required=True),
        'active': fields.boolean(string='Active'),
        'category_id': fields.many2one('product.category', string='Category'),
        'product_id': fields.many2one('product.product', string='Product'),
        'uom_id': fields.many2one('product.uom', string='UoM'),
        'warehouse_id': fields.many2one('stock.warehouse', string='Warehouse'),
        'location_id': fields.many2one('stock.location', string='Location', required=True),
    }
    
    _defaults = {
        'name': lambda obj, cr, uid, context={}: obj.pool.get('ir.sequence').get(cr, uid, 'threshold.value') or '',
    }
    
    def product_on_change(self, cr, uid, ids, product_id=False, context={}):
        '''
        Update the UoM when the product change
        '''
        v = {}
        
        if not product_id:
            v.update({'uom_id': False})
        else:
            uom_id = self.pool.get('product.product').browse(cr, uid, product_id, context=context).uom_id.id
            v.update({'uom_id': uom_id})
            
        return {'value': v}
    
    def category_on_change(self, cr, uid, ids, category_id=False, context={}):
        '''
        If a category is selected, remove values of product and uom on the form
        '''
        v = {}
        
        if category_id:
            v.update({'product_id': False,
                      'uom_id': False})
            
        return {'value': v}
    
threshold_value()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

