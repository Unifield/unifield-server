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

KIT_COMPOSITION_TYPE = [('theoretical', 'Theoretical'),
                        ('real', 'Real'),
                        ]

KIT_STATE = [('draft', 'Draft'),
             ('completed', 'Completed'),
             ('done', 'Closed'),
             ]

class composition_kit(osv.osv):
    '''
    kit composition class, representing both theoretical composition and actual ones
    '''
    _name = 'composition.kit'
    
    def mark_as_completed(self, cr, uid, ids, context=None):
        '''
        button function
        set the state to 'completed'
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        for obj in self.browse(cr, uid, ids, context=context):
            if not len(obj.composition_item_ids):
                raise osv.except_osv(_('Warning !'), _('Kit Composition cannot be empty.'))
            if not obj.active:
                raise osv.except_osv(_('Warning !'), _('Cannot complete inactive kit.'))
        self.write(cr, uid, ids, {'state': 'completed'}, context=context)
        return True
    
    def mark_as_inactive(self, cr, uid, ids, context=None):
        '''
        button function
        set the active flag to False
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.composition_type != 'theoretical':
                raise osv.except_osv(_('Warning !'), _('Only theoretical kit can manipulate "active" field.'))
        self.write(cr, uid, ids, {'active': False}, context=context)
        return True
    
    def mark_as_active(self, cr, uid, ids, context=None):
        '''
        button function
        set the active flag to False
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.composition_type != 'theoretical':
                raise osv.except_osv(_('Warning !'), _('Only theoretical kit can manipulate "active" field.'))
        self.write(cr, uid, ids, {'active': True}, context=context)
        return True
    
    def close_kit(self, cr, uid, ids, context=None):
        '''
        button function
        set the state to 'done'
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        self.write(cr, uid, ids, {'state': 'done'}, context=context)
        return True
    
    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        multi fields function method
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
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
            if obj.composition_expiry_check:
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
        # state
        default.update(state='draft')
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
    
    def unlink(self, cr, uid, ids, context=None):
        '''
        cannot delete composition kit not draft
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.state != 'draft':
                raise osv.except_osv(_('Warning !'), _("Cannot delete Kits not in 'draft' state."))
        return super(composition_kit, self).unlink(cr, uid, ids, context=context)
    
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
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
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
            elif obj.composition_expiry_check: # do we need to treat expiry and batch differently ?
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
                'active': fields.boolean('Active', readonly=True),
                'state': fields.selection(KIT_STATE, string='State', readonly=True, required=True),
                # related
                'composition_batch_check': fields.related('composition_product_id', 'batch_management', type='boolean', string='Batch Number Mandatory', readonly=True, store=False),
                # expiry is always true if batch_check is true. we therefore use expry_check for now in the code
                'composition_expiry_check': fields.related('composition_product_id', 'perishable', type='boolean', string='Expiry Date Mandatory', readonly=True, store=False),
                # functions
                'name': fields.function(_vals_get, method=True, type='char', size=1024, string='Name', multi='get_vals',
                                        store= {'composition.kit': (lambda self, cr, uid, ids, c=None: ids, ['composition_product_id'], 10),}),
                'composition_version': fields.function(_vals_get, method=True, type='char', size=1024, string='Version', multi='get_vals',
                                                       store= {'composition.kit': (lambda self, cr, uid, ids, c=None: ids, ['composition_version_txt', 'composition_version_id'], 10),}),
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
    
    def _get_default_product_id(self, cr, uid, context=None):
        '''
        default value for type
        '''
        if context is None:
            context= {}
        if context.get('composition_product_id', False):
            return context.get('composition_product_id')
        return False
    
    def _get_default_lot_id(self, cr, uid, context=None):
        '''
        default value for type
        '''
        if context is None:
            context= {}
        if context.get('composition_lot_id', False):
            return context.get('composition_lot_id')
        return False
    
    def _get_default_exp(self, cr, uid, context=None):
        '''
        default value for type
        '''
        if context is None:
            context= {}
        if context.get('composition_exp', False):
            return context.get('composition_exp')
        return False
    
    _defaults = {'composition_creation_date': lambda *a: time.strftime('%Y-%m-%d'),
                 'composition_type': lambda s, cr, uid, c: c.get('composition_type', False),
                 'composition_product_id': lambda s, cr, uid, c: c.get('composition_product_id', False),
                 'composition_lot_id': lambda s, cr, uid, c: c.get('composition_lot_id', False),
                 'composition_exp': lambda s, cr, uid, c: c.get('composition_exp', False),
                 'composition_batch_check': lambda s, cr, uid, c: c.get('composition_batch_check', False),
                 'composition_expiry_check': lambda s, cr, uid, c: c.get('composition_expiry_check', False),
                 'active': True,
                 'state': 'draft',
                 }
    
    def _composition_kit_constraint(self, cr, uid, ids, context=None):
        '''
        constraint on kit composition - two kits 
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        for obj in self.browse(cr, uid, ids, context=context):
            # global
            if obj.composition_product_id.type != 'product' or obj.composition_product_id.subtype != 'kit':
                raise osv.except_osv(_('Warning !'), _('Only Kit products can be used for kits.'))
            # theoretical constraints
            if obj.composition_type == 'theoretical':
                search_ids = self.search(cr, uid, [('id', '!=', obj.id),
                                                   ('composition_product_id', '=', obj.composition_product_id.id),
                                                   ('composition_version_txt', '=ilike', obj.composition_version_txt),
                                                   ('composition_creation_date', '=', obj.composition_creation_date)], context=context)
                if search_ids:
                    #print self.read(cr, uid, ids, ['composition_product_id', 'composition_version_txt', 'composition_creation_date'], context=context)
                    raise osv.except_osv(_('Warning !'), _('The dataset (Product - Version - Creation Date) must be unique.'))
                # constraint on lot_id/reference/expiry date - forbidden for theoretical
                if obj.composition_reference or obj.composition_lot_id or obj.composition_exp:
                    raise osv.except_osv(_('Warning !'), _('Composition Reference / Batch Number / Expiry date is not available for Theoretical Kit.'))
                # constraint on version_id - forbidden for theoretical
                if obj.composition_version_id:
                    raise osv.except_osv(_('Warning !'), _('Composition Version Object is not available for Theoretical Kit.'))
                
            # real constraints
            if obj.composition_type == 'real':
                # constraint on lot_id/reference - mandatory for real kit
                if obj.composition_batch_check or obj.composition_expiry_check:
                    if obj.composition_reference:
                        raise osv.except_osv(_('Warning !'), _('Composition List with Batch Management Product does not allow Reference.'))
                    if not obj.composition_lot_id:
                        raise osv.except_osv(_('Warning !'), _('Composition List with Batch Management Product needs Batch Number.'))
                else:
                    if not obj.composition_reference:
                        raise osv.except_osv(_('Warning !'), _('Composition List without Batch Management Product needs Reference.'))
                    if obj.composition_lot_id:
                        raise osv.except_osv(_('Warning !'), _('Composition List without Batch Management Product does not allow Batch Number.'))
                # real composition must always be active
                if not obj.active:
                    raise osv.except_osv(_('Warning !'), _('Composition List cannot be inactive.'))
            
        return True
    
    _constraints = [(_composition_kit_constraint, 'Constraint error on Composition Kit.', []),
                    ]
    _sql_constraints = [('unique_composition_kit_real_ref', "unique(composition_reference)", 'Kit Composition List Reference must be unique.'),
                        ('unique_composition_kit_real_lot', "unique(composition_lot_id)", 'Batch Number can only be used by one Kit Composition List.'),
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
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {}
            # name
            result[obj.id].update({'name': obj.item_product_id.name})
            # version
            result[obj.id].update({'item_kit_version': obj.item_kit_id.composition_version})
            # type
            result[obj.id].update({'item_kit_type': obj.item_kit_id.composition_type})
            # state
            result[obj.id].update({'state': obj.item_kit_id.state})
        return result
    
    def name_get(self, cr, uid, ids, context=None):
        '''
        override displayed name
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
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
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
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
                # functions
                'name': fields.function(_vals_get, method=True, type='char', size=1024, string='Name', multi='get_vals',
                                        store= {'composition.item': (lambda self, cr, uid, ids, c=None: ids, ['item_product_id'], 10),}),
                'item_kit_version': fields.function(_vals_get, method=True, type='char', size=1024, string='Kit Version', multi='get_vals',
                                        store= {'composition.item': (lambda self, cr, uid, ids, c=None: ids, ['item_kit_id'], 10),
                                                'composition.kit': (_get_composition_item_ids, ['composition_version_txt', 'composition_version_id'], 10)}),
                'item_kit_type': fields.function(_vals_get, method=True, type='char', size=1024, string='Kit Type', multi='get_vals',
                                        store= {'composition.item': (lambda self, cr, uid, ids, c=None: ids, ['item_kit_id'], 10),
                                                'composition.kit': (_get_composition_item_ids, ['composition_type'], 10)}),
                'state': fields.function(_vals_get, method=True, type='selection', selection=KIT_STATE, size=1024, string='State', readonly=True, multi='get_vals',
                                store= {'composition.item': (lambda self, cr, uid, ids, c=None: ids, ['item_kit_id'], 10),
                                        'composition.kit': (_get_composition_item_ids, ['state'], 10)}),
                }
    
    
composition_item()


class product_product(osv.osv):
    '''
    add a constraint - a product of subtype 'kit' cannot be perishable only, should be batch management or nothing
    '''
    _inherit = 'product.product'
    
    def _kit_product_constraints(self, cr, uid, ids, context=None):
        '''
        constraint on product
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        for obj in self.browse(cr, uid, ids, context=context):
            # kit
            if obj.type == 'product' and obj.subtype == 'kit':
                if obj.perishable and not obj.batch_management:
                    raise osv.except_osv(_('Warning !'), _('The Kit product cannot be Expiry Date Mandatory only.'))
            
        return True
    
    _constraints = [(_kit_product_constraints, 'Constraint error on Kit Product.', []),
                    ]
    
product_product()


class stock_move(osv.osv):
    '''
    add the new method self.create_composition_list
    '''
    _inherit= 'stock.move'
    
    def create_composition_list(self, cr, uid, ids, context=None):
        '''
        return the form view of composition_list (real) with corresponding values from the context
        '''
        obj = self.browse(cr, uid, ids[0], context=context)
        composition_type = 'real'
        composition_product_id = obj.product_id.id
        composition_lot_id = obj.prodlot_id and obj.prodlot_id.id or False
        composition_exp = obj.expired_date
        composition_batch_check = obj.product_id.batch_management
        composition_expiry_check = obj.product_id.perishable
        
        return {'name': 'Kit Composition List',
                'view_id': False,
                'view_type': 'form',
                'view_mode': 'form,tree',
                'res_model': 'composition.kit',
                'res_id': False,
                'type': 'ir.actions.act_window',
                'nodestroy': False,
                'target': False,
                'domain': "[('composition_type', '=', 'real')]",
                'context': dict(context,
                                composition_type=composition_type,
                                composition_product_id=composition_product_id,
                                composition_lot_id=composition_lot_id,
                                composition_exp=composition_exp,
                                composition_batch_check=composition_batch_check,
                                composition_expiry_check=composition_expiry_check,
                                )
                }
        
    
stock_move()


