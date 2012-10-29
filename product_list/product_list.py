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
import logging

class product_list(osv.osv):
    _name = 'product.list'
    _description = 'Products list'
    
    def _get_nb_products(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Returns the number of products on the list
        '''
        res = {}
        
        for list in self.browse(cr, uid, ids, context=context):
            res[list.id] = len(list.product_ids)
        
        return res
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        Adds update date and user information
        '''
        vals['reviewer_id'] = uid
        vals['last_update_date'] = time.strftime('%Y-%m-%d')
        
        return super(product_list, self).write(cr, uid, ids, vals, context=context)
    
        
    def copy(self, cr, uid, id, default=None, context=None):
        '''
        Remove the last update date and the reviewer on the new list
        '''
        if not context:
            context = {}

        name = self.browse(cr, uid, id, context=context).name + ' (copy)'
            
        return super(product_list, self).copy(cr, uid, id, {'last_update_date': False,
                                                            'name': name,
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
        'old_product_ids': fields.one2many('old.product.list.line', 'list_id', string='Old Products'),
        'nb_products': fields.function(_get_nb_products, method=True, type='integer', string='# of products'),
        
    }
    
    _defaults = {
        'creation_date': lambda *a: time.strftime('%Y-%m-%d'),
    }

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'A list or sublist with the same name already exists in the system!')
    ]

    def change_product_line(self, cr, uid, ids, context=None):
        '''
        Refresh the old product list
        '''
        res = {}
        old_products = []
        for list in self.browse(cr, uid, ids, context=context):
            for old_line in list.old_product_ids:
                old_products.append(old_line.id)

            res.update({'old_product_ids': old_products})

        return {'value': res}

    def call_add_products(self, cr, uid, ids, context=None):
        '''
        Call the add multiple products wizard
        '''
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for list in self.browse(cr, uid, ids, context=context):
            wiz_id = self.pool.get('product.list.add.products').create(cr, uid, {'list_id': list.id}, context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': 'product.list.add.products',
                'res_id': wiz_id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'context': context}


product_list()


class product_list_line(osv.osv):
    _name = 'product.list.line'
    _description = 'Line of product list'
    
    _columns = {
        'name': fields.many2one('product.product', string='Product Description', required=True),
        'list_id': fields.many2one('product.list', string='List', ondelete='cascade'),
        'ref': fields.related('name', 'default_code', string='Product Code', readonly=True, type='char'),
        'comment': fields.char(size=256, string='Comment'),
    }

    def unlink(self, cr, uid, ids, context=None):
        '''
        Create old product list line on product list line deletion
        '''
        if not context:
            context = {}

        if isinstance(ids, (int,long)):
            ids = [ids]

        if not context.get('import_error', False):
            for line in self.read(cr, uid, ids, context=context):
                self.pool.get('old.product.list.line').create(cr, uid, {'removal_date': time.strftime('%Y-%m-%d'),
                                                                        'comment': 'comment' in line and line['comment'] or '',
                                                                        'name': line['name'][0],
                                                                        'list_id': line['list_id'][0]}, context=context)

        return super(product_list_line, self).unlink(cr, uid, ids, context=context)


product_list_line()


class old_product_list_line(osv.osv):
    _name = 'old.product.list.line'
    _inherit = 'product.list.line'
    _order = 'removal_date'

    _columns = {
        'removal_date': fields.date(string='Removal date', readonly=True),
    }

    _defaults = {
        'removal_date': lambda *a: time.strftime('%Y-%m-%d'),
    }

old_product_list_line()


class product_product(osv.osv):
    _name = 'product.product'
    _inherit = 'product.product'


    def _get_list_sublist(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Returns all lists/sublists where the product is in
        '''
        if not context:
            context = {}
            
        if isinstance(ids, (long,int)):
            ids = [ids]
            
        res = {}
            
        for product in self.browse(cr, uid, ids, context=context):
            res[product.id] = []
            line_ids = self.pool.get('product.list.line').search(cr, uid, [('name', '=', product.id)], context=context)
            for line in self.pool.get('product.list.line').browse(cr, uid, line_ids, context=context):
                if line.list_id and line.list_id.id not in res[product.id]:
                    res[product.id].append(line.list_id.id)
                    
        return res
    
    def _search_list_sublist(self, cr, uid, obj, name, args, context=None):
        '''
        Filter the search according to the args parameter
        '''
        if not context:
            context = {}
            
        ids = []
            
        for arg in args:
            if arg[0] == 'list_ids' and arg[1] == '=' and arg[2]:
                list = self.pool.get('product.list').browse(cr, uid, int(arg[2]), context=context)
                for line in list.product_ids:
                    ids.append(line.name.id)
            elif arg[0] == 'list_ids' and arg[1] == 'in' and arg[2]:
                for list in self.pool.get('product.list').browse(cr, uid, arg[2], context=context):
                    for line in list.product_ids:
                        ids.append(line.name.id)
            else:
                return []
            
        return [('id', 'in', ids)]

    _columns = {
        'list_ids': fields.function(_get_list_sublist, fnct_search=_search_list_sublist, 
                                    type='many2many', relation='product.list', method=True, string='Lists'),
    }

product_product()

class product_template(osv.osv):
    _name = 'product.template'
    _inherit = 'product.template'

    _columns = {
        'name': fields.char(size=60, string='DESCRIPTION', required=True),
    }

    def _get_default_req(self, cr, uid, context=None):
        # Some verifications
        if context is None:
            context = {}
        res = {}
        res= {'default_code': datetime.now().strftime('%m%d%H%M%S'),
              'international_status': 'itc'}
        return res

    def create(self, cr, uid, vals, context=None):
        '''
        Set default values for datas.xml and tests.yml
        '''
        if context is None:
            context = {}
        if context.get('update_mode') in ['init', 'update']:
            required = ['default_code', 'international_status']
            has_required = False
            for req in required:
                if  req in vals:
                    has_required = True
                    break
            if not has_required:
                logging.getLogger('init').info('Loading default values for product.product')
                vals.update(self._get_default_req(cr, uid, context))
        logging.getLogger('init').info('Value of %s' % vals)
        return super(product_template, self).create(cr, uid, vals, context)

product_template()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
