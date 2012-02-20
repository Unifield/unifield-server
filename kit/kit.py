# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting
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
import netsvc
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import decimal_precision as dp
import netsvc
import logging
import tools
import time
from os import path


KIT_COMPOSITION_STATE = [('draft', 'Draft'),
                         ('completed', 'Completed'),
                         ('explosed', 'Explosed'),
                         ]

KIT_COMPOSITION_TYPE = [('theoretical', 'Theoretical'),
                        ('real', 'Real'),
                        ]

KIT_STATE = [('draft', 'Draft'),
             ('completed', 'Completed'),
             ('shipped', 'Shipped'),
             ('archived', 'Archived'),
             ]

class composition_kit(osv.osv):
    '''
    kit composition class, representing both theoretical composition and actual ones
    '''
    _name = 'composition.kit'
    
    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        multi fields function method
        '''
        result = {}
        # date tools object
        date_obj = self.pool.get('date.tools')
        db_date_format = date_obj.get_db_date_format(cr, uid, context=context)
        date_format = date_obj.get_date_format(cr, uid, context=context)
        
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {}
            # composition version
            if obj.composition_type == 'theoretical':
                result[obj.id].update({'composition_version': obj.composition_version_txt})
            elif obj.composition_type == 'real':
                result[obj.id].update({'composition_version': obj.composition_version_id and obj.composition_version_id.composition_version_txt or ''})
            # name - ex: ITC - 01/01/2012
            date = datetime.strptime(obj.composition_creation_date, db_date_format)
            result[obj.id].update({'name': result[obj.id]['composition_version'] + ' - ' + date.strftime(date_format)})
            # composition_combined_ref_lot: mix between both fields reference and batch number which are exclusive fields
            if obj.composition_batch_check:
                result[obj.id].update({'composition_combined_ref_lot': obj.composition_lot_id.name})
            else:
                result[obj.id].update({'composition_combined_ref_lot': obj.composition_reference})
        return result
    
    def copy(self, cr, uid, id, default=None, context=None):
        '''
        change version name. add (copy)
        
        - theoretical kit can be copied. version -> version (copy)
        - real kit with batch number cannot be copied.
        - real kit without batch but with reference can be copied. reference -> reference (copy)
        '''
        if default is None:
            default = {}
        # original reference
        data = self.read(cr, uid, id, ['composition_version_txt', 'composition_type', 'composition_reference', 'composition_lot_id'], context=context)
        if data['composition_type'] == 'theoretical':
            version = data['composition_version_txt']
            default.update(composition_version_txt='%s (copy)'%version, composition_creation_date=time.strftime('%Y-%m-%d'))
        elif data['composition_type'] == 'real' and data['composition_reference'] and not data['composition_lot_id']:
            reference = data['composition_reference']
            default.update(composition_reference='%s (copy)'%reference, composition_creation_date=time.strftime('%Y-%m-%d'))
        else:
            raise osv.except_osv(_('Warning !'), _('Kit Composition List with Batch Number cannot be copied!'))
            
        return super(composition_kit, self).copy(cr, uid, id, default, context=context)
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        columns for the tree
        """
        if context is None:
            context = {}
        # fields to be modified
        list = ['<field name="item_lot"/>', '<field name="item_exp"/>']
        # call super
        result = super(composition_kit, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        # columns depending on type - fields from one2many field
        if view_type == 'form' and context.get('composition_type', False) == 'theoretical':
            replace_text = result['fields']['composition_item_ids']['views']['tree']['arch']
            replace_text = reduce(lambda x, y: x.replace(y, ''), [replace_text] + list)
            result['fields']['composition_item_ids']['views']['tree']['arch'] = replace_text
        
        list = ['<field name="composition_lot_id"/>', '<field name="composition_exp"/>', '<field name="composition_reference"/>', '<field name="composition_combined_ref_lot"/>']
        # columns from kit composition tree
        if view_type == 'tree' and context.get('composition_type', False) == 'theoretical':
            replace_text = result['arch']
            replace_text = reduce(lambda x, y: x.replace(y, ''), [replace_text] + list)
            result['arch'] = replace_text
        
        return result
    
    def name_get(self, cr, uid, ids, context=None):
        '''
        override displayed name
        '''
        # date tools object
        date_obj = self.pool.get('date.tools')
        db_date_format = date_obj.get_db_date_format(cr, uid, context=context)
        date_format = date_obj.get_date_format(cr, uid, context=context)
        # result
        res = []
        
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.composition_type == 'theoretical':
                date = datetime.strptime(obj.composition_creation_date, db_date_format)
                name = obj.composition_version + ' - ' + date.strftime(date_format)
            elif obj.composition_batch_check:
                name = obj.composition_lot_id.name
            else:
                name = obj.composition_reference
                
            res += [(obj.id, name)]
        return res
    
    def on_change_product_id(self, cr, uid, ids, product_id, context=None):
        '''
        when the product is changed, lot checks are updated - mandatory workaround for attrs use
        '''
        # product object
        prod_obj = self.pool.get('product.product')
        res = {'value': {'composition_batch_check': False,
                         'composition_expiry_check': False,
                         'composition_lot_id': False,
                         'composition_reference': False}}
        if not product_id:
            return res
        
        data = prod_obj.read(cr, uid, [product_id], ['perishable', 'batch_management'], context=context)[0]
        res['value']['composition_batch_check'] = data['batch_management']
        res['value']['composition_expiry_check'] = data['perishable']
        return res

    _columns = {'composition_type': fields.selection(KIT_COMPOSITION_TYPE, string='Composition Type', readonly=True, required=True),
                'composition_description': fields.text(string='Composition Description'),
                'composition_product_id': fields.many2one('product.product', string='Product', required=True),
                'composition_version_txt': fields.char(string='Version', size=1024),
                'composition_version_id': fields.many2one('composition.kit', string='Version'),
                'composition_creation_date': fields.date(string='Creation Date', required=True),
                'composition_reference': fields.char(string='Reference', size=1024),
                'composition_lot_id': fields.many2one('stock.production.lot', string='Batch Nb', size=1024),
                'composition_exp': fields.date(string='Expiry Date'),
                'composition_item_ids': fields.one2many('composition.item', 'item_kit_id', string='Items'),
                'state': fields.selection(KIT_STATE, string='State', readonly=True, required=True),
                # functions
                'name': fields.function(_vals_get, method=True, type='char', size=1024, string='Name', multi='get_vals',
                                        store= {'composition.kit': (lambda self, cr, uid, ids, c=None: ids, ['composition_product_id'], 10),}),
                'composition_version': fields.function(_vals_get, method=True, type='char', size=1024, string='Version', multi='get_vals',
                                                       store= {'composition.kit': (lambda self, cr, uid, ids, c=None: ids, ['composition_version_txt', 'composition_version_id'], 10),}),
                'composition_batch_check': fields.related('composition_product_id', 'batch_management', type='boolean', string='Batch Number Mandatory', readonly=True, store=False),
                'composition_expiry_check': fields.related('composition_product_id', 'perishable', type='boolean', string='Expiry Date Mandatory', readonly=True, store=False),
                'composition_combined_ref_lot': fields.function(_vals_get, method=True, type='char', size=1024, string='Ref/Batch Num', multi='get_vals',
                                                                store= {'composition.kit': (lambda self, cr, uid, ids, c=None: ids, ['composition_lot_id', 'composition_reference'], 10),}),
                }
    
    def _get_default_type(self, cr, uid, context=None):
        '''
        default value for type
        '''
        if context is None:
            context= {}
        if context.get('composition_type', False):
            return context.get('composition_type')
        return False
    
    _defaults = {'composition_creation_date': lambda *a: time.strftime('%Y-%m-%d'),
                 'composition_type': _get_default_type,
                 'state': 'draft',
                 }
    
    def _composition_kit_constraint(self, cr, uid, ids, context=None):
        '''
        constraint on kit composition - two kits 
        '''
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.composition_type == 'theoretical':
                search_ids = self.search(cr, uid, [('id', '!=', obj.id),
                                                   ('composition_product_id', '=', obj.composition_product_id.id),
                                                   ('composition_version_txt', '=ilike', obj.composition_version_txt),
                                                   ('composition_creation_date', '=', obj.composition_creation_date)], context=context)
                if search_ids:
                    #print self.read(cr, uid, ids, ['composition_product_id', 'composition_version_txt', 'composition_creation_date'], context=context)
                    raise osv.except_osv(_('Warning !'), _('The dataset (Product - Version - Creation Date) must be unique!'))
            
        return True
    
    _constraints = [(_composition_kit_constraint, 'The joint data Product - Version and Creation Date must be unique!', []),
                    ]
    _sql_constraints = [('unique_composition_kit_real', "unique(composition_reference)", 'Kit Composition List Reference must be unique.'),
                        ('unique_composition_kit_theoretical', "unique(composition_lot_id)", 'Batch Number can only be used by one Kit Composition List.'),
                        ]

composition_kit()


class composition_item(osv.osv):
    '''
    kit composition items representing kit parts
    '''
    _name = 'composition.item'
    
    def on_product_change(self, cr, uid, id, product_id, context=None):
        '''
        product is changed, we update the UoM
        '''
        prod_obj = self.pool.get('product.product')
        result = {'value': {'item_uom_id': False, 'item_qty': 0.0}}
        if product_id:
            result['value']['item_uom_id'] = prod_obj.browse(cr, uid, product_id, context=context).uom_po_id.id
            
        return result
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        columns for the tree
        """
        if context is None:
            context = {}
        # fields to be modified
        list = ['<field name="item_lot"/>', '<field name="item_exp"/>']
        # call super
        result = super(composition_item, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        # columns depending on type
        if view_type == 'tree' and context.get('item_kit_type', False) == 'theoretical':
            replace_text = result['arch']
            replace_text = reduce(lambda x, y: x.replace(y, ''), [replace_text] + list)
            result['arch'] = replace_text
        
        return result
    
    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        multi fields function method
        '''
        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {}
            # name
            result[obj.id].update({'name': obj.item_product_id.name})
            # version
            result[obj.id].update({'item_kit_version': obj.item_kit_id.composition_version})
            # type
            result[obj.id].update({'item_kit_type': obj.item_kit_id.composition_type})
        return result
    
    def name_get(self, cr, uid, ids, context=None):
        '''
        override displayed name
        '''
        # date tools object
        date_obj = self.pool.get('date.tools')
        date_format = date_obj.get_date_format(cr, uid, context=context)
        # result
        res = []
        
        for obj in self.browse(cr, uid, ids, context=context):
            name = obj.item_product_id.name
            res += [(obj.id, name)]
        return res
    
    def _get_composition_item_ids(self, cr, uid, ids, context=None):
        '''
        ids represents the ids of composition.kit objects for which values have changed
        
        return the list of ids of composition.item objects which need to get their fields updated
        
        self is an composition.kit object
        '''
        item_obj = self.pool.get('composition.item')
        result = item_obj.search(cr, uid, [('item_kit_id', 'in', ids)], context=context)
        return result
    
    _columns = {'item_module': fields.char(string='Module', size=1024),
                'item_product_id': fields.many2one('product.product', string='Product', required=True),
                'item_qty': fields.float(string='Qty', digits_compute=dp.get_precision('Product UoM'), required=True),
                'item_uom_id': fields.many2one('product.uom', string='UoM', required=True),
                'item_lot': fields.char(string='Batch Nb', size=1024),
                'item_exp': fields.date(string='Expiry Date'),
                'item_kit_id': fields.many2one('composition.kit', string='Kit', ondelete='cascade', required=True, readonly=True),
                'item_description': fields.text(string='Item Description'),
                'state': fields.selection(KIT_STATE, string='State', readonly=True, required=True),
                # functions
                'name': fields.function(_vals_get, method=True, type='char', size=1024, string='Name', multi='get_vals',
                                        store= {'composition.item': (lambda self, cr, uid, ids, c=None: ids, ['item_product_id'], 10),}),
                'item_kit_version': fields.function(_vals_get, method=True, type='char', size=1024, string='Kit Version', multi='get_vals',
                                        store= {'composition.item': (lambda self, cr, uid, ids, c=None: ids, ['item_kit_id'], 10),
                                                'composition.kit': (_get_composition_item_ids, ['composition_version_txt', 'composition_version_id'], 10)}),
                'item_kit_type': fields.function(_vals_get, method=True, type='char', size=1024, string='Kit Type', multi='get_vals',
                                        store= {'composition.item': (lambda self, cr, uid, ids, c=None: ids, ['item_kit_id'], 10),
                                                'composition.kit': (_get_composition_item_ids, ['composition_type'], 10)}),
                }
    
    _defaults = {'state': 'draft',
                 }
    
composition_item()
