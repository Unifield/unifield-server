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

from osv import osv
from osv import fields

from tools.translate import _

from mx.DateTime import DateFrom, now, RelativeDate
from datetime import date

import time

class supplier_catalogue(osv.osv):
    _name = 'supplier.catalogue'
    _description = 'Supplier catalogue'
    _order = 'period_from, period_to'
    
    def copy(self, cr, uid, catalogue_id, default=None, context=None):
        '''
        Disallow the possibility to duplicate a catalogue.
        '''
        raise osv.except_osv(_('Error'), _('You cannot duplicate a catalogue because you musn\'t have ' \
                               'overlapped catalogue !'))
        
        return False
    
    def _update_other_catalogue(self, cr, uid, cat_id, period_from, currency_id, partner_id, period_to=False, context=None):
        '''
        Check if other catalogues with the same partner/currency exist and are defined in the period of the
        new catalogue. If yes, update the period_to of the old catalogue with the period_from - 1 day of
        the new catalogue.
        '''
        if not context:
            context = {}
            
        if not context.get('cat_ids', False):
            context.update({'cat_ids': []})
        
        # Add catalogues already written to avoid
        # loops in the same product
        if cat_id:
            context['cat_ids'].append(cat_id)
            
        # Search other catalogues for the same partner/currency
        # which are overrided by the new catalogue
        equal_ids = self.search(cr, uid, [('id', 'not in', context.get('cat_ids', [])), ('period_from', '=', period_from), 
                                                                                        ('currency_id', '=', currency_id),
                                                                                        ('partner_id', '=', partner_id)],
                                                                                        order='period_from asc',
                                                                                        limit=1,
                                                                                        context=context) 
        if period_to:
            to_ids = self.search(cr, uid, [('id', 'not in', context.get('cat_ids', [])), ('period_from', '>', period_from), 
                                                                                         ('period_from', '<', period_to),
                                                                                         ('currency_id', '=', currency_id),
                                                                                         ('partner_id', '=', partner_id)],
                                                                                         order='period_from asc',
                                                                                         limit=1,
                                                                                         context=context)
        else:
            to_ids = self.search(cr, uid, [('id', 'not in', context.get('cat_ids', [])), ('period_from', '>', period_from),
                                                                                         ('currency_id', '=', currency_id),
                                                                                         ('partner_id', '=', partner_id)],
                                                                                         order='period_from asc',
                                                                                         limit=1,
                                                                                         context=context)
        
        # If overrided catalogues exist, display an error message
        if equal_ids:
            over_cat = self.browse(cr, uid, equal_ids[0], context=context)
            over_cat_from = self.pool.get('date.tools').get_date_formatted(cr, uid, d_type='date', datetime=over_cat.period_from, context=context)
            over_cat_to = self.pool.get('date.tools').get_date_formatted(cr, uid, d_type='date', datetime=over_cat.period_to, context=context)
            raise osv.except_osv(_('Error'), _('This catalogue has the same \'From\' date than the following catalogue : %s (\'From\' : %s - \'To\' : %s) - ' \
                                               'Please change the \'From\' date of this new catalogue or delete the other catalogue.') % (over_cat.name, over_cat_from, over_cat_to))
        
        # If overrided catalogues exist, display an error message
        if to_ids:
            over_cat = self.browse(cr, uid, to_ids[0], context=context)
            over_cat_from = self.pool.get('date.tools').get_date_formatted(cr, uid, d_type='date', datetime=over_cat.period_from, context=context)
            over_cat_to = self.pool.get('date.tools').get_date_formatted(cr, uid, d_type='date', datetime=over_cat.period_to, context=context)
            raise osv.except_osv(_('Error'), _('The \'To\' date of this catalogue is older than the \'From\' date of another catalogue - ' \
                                               'Please change the \'To\' date of this catalogue or the \'From\' date of the following ' \
                                               'catalogue : %s (\'From\' : %s - \'To\' : %s)' % (over_cat.name, over_cat_from, over_cat_to)))
        
        # Search all catalogues with the same partner/currency which are done
        # after the beginning of the new catalogue
        from_update_ids = self.search(cr, uid, [('id', 'not in', context.get('cat_ids', [])), ('currency_id', '=', currency_id),
                                                                                              ('partner_id', '=', partner_id),
                                                                                              ('period_from', '<=', period_from),
                                                                                              '|', 
                                                                                              ('period_to', '>=', period_from), 
                                                                                              ('period_to', '=', False),], context=context)
        
        # Update these catalogues with an end date which is the start date - 1 day of
        # the new catalogue
        if isinstance(period_from, date):
            period_from = period_from.strftime('%Y-%m-%d')
        period_from = DateFrom(period_from) + RelativeDate(days=-1)
        self.write(cr, uid, from_update_ids, {'period_to': period_from.strftime('%Y-%m-%d')}, context=context)
        
        return True
    
    def create(self, cr, uid, vals, context=None):
        '''
        Check if the new values override a catalogue
        '''
        if context is None:
            context = {}
        # Check if other catalogues need to be updated because they finished
        # after the starting date of the new catalogue.
        if vals.get('active', True):
            self._update_other_catalogue(cr, uid, None, vals.get('period_from', False),
                                                        vals.get('currency_id', False),
                                                        vals.get('partner_id', context.get('partner_id', False)),
                                                        vals.get('period_to', False), context=context)
        return super(supplier_catalogue, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        Update the supplierinfo and pricelist line according to the
        new values
        '''
        if context is None:
            context = {}
        supinfo_obj = self.pool.get('product.supplierinfo')
        price_obj = self.pool.get('pricelist.partnerinfo')
        
        supplierinfo_ids = supinfo_obj.search(cr, uid, [('catalogue_id', 'in', ids)], context=context)
        
        for catalogue in self.browse(cr, uid, ids, context=context):
            pricelist_ids = []
            
            for line in catalogue.line_ids:
                pricelist_ids.append(line.partner_info_id.id)
            
            # Check if other catalogues need to be updated because they finished
            # after the starting date of the updated catalogue.
            if vals.get('active', catalogue.active):
                self._update_other_catalogue(cr, uid, catalogue.id, vals.get('period_from', catalogue.period_from),
                                                                    vals.get('currency_id', catalogue.currency_id.id),
                                                                    vals.get('partner_id', catalogue.partner_id.id),
                                                                    vals.get('period_to', catalogue.period_to), context=context)
        
            new_supinfo_vals = {}            
            # Change the partner of all supplier info instances
            if 'partner_id' in vals and vals['partner_id'] != catalogue.partner_id.id:
                delay = self.pool.get('res.partner').browse(cr, uid, vals['partner_id'], context=context).default_delay
                new_supinfo_vals.update({'name': vals['partner_id'],
                                         'delay': delay})
            
            # Change pricelist data according to new data
            new_price_vals = {'valid_till': vals.get('period_to', None),
                              'valid_from': vals.get('period_from', catalogue.period_from),
                              'currency_id': vals.get('currency_id', catalogue.currency_id.id),
                              'name': vals.get('name', catalogue.name),}
                
            # Update the supplier info and price lines
            supinfo_obj.write(cr, uid, supplierinfo_ids, new_supinfo_vals, context=context)
            price_obj.write(cr, uid, pricelist_ids, new_price_vals, context=context)
        
        return super(supplier_catalogue, self).write(cr, uid, ids, vals, context=context)
    
    def name_get(self, cr, uid, ids, context=None):
        '''
        Add currency to the name of the catalogue
        '''
        res = []
        
        for r in self.browse(cr, uid, ids, context=context):
            res.append((r.id, '%s (%s)' % (r.name, r.currency_id.name)))
            
        return res
    
    def _search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False, access_rights_uid=None):
        '''
        If the search is called from the catalogue line list view, returns only catalogues of the
        partner defined in the context
        '''
        if not context:
            context = {}
        
        if context.get('search_default_partner_id', False):
            args.append(('partner_id', '=', context.get('search_default_partner_id', False)))
            
        return super(supplier_catalogue, self)._search(cr, uid, args, offset, limit, order, context, count, access_rights_uid)
    
    def _get_active(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Return True if today is into the period of the catalogue
        '''
        res = {}
        
        for catalogue in self.browse(cr, uid, ids, context=context):
            date_from = DateFrom(catalogue.period_from)
            date_to = DateFrom(catalogue.period_to)
            res[catalogue.id] = date_from < now() < date_to 
        
        return res
    
    def _search_active(self, cr, uid, obj, name, args, context=None):
        '''
        Returns all active catalogues
        '''
        ids = []
        
        for arg in args:
            if arg[0] == 'current' and arg[1] == '=':
                ids = self.search(cr, uid, [('period_from', '<', date.today()), 
                                            ('period_to', '>', date.today())], context=context)
                return [('id', 'in', ids)]
            elif arg[0] == 'current' and arg[1] == '!=':
                ids = self.search(cr, uid, ['|', ('period_from', '>', date.today()), 
                                                 ('period_to', '<', date.today())], context=context)
                return [('id', 'in', ids)]
        
        return ids
    
    _columns = {
        'name': fields.char(size=64, string='Name', required=True),
        'partner_id': fields.many2one('res.partner', string='Partner', required=True,
                                      domain=[('supplier', '=', True)]),
        'period_from': fields.date(string='From', required=True,
                                   help='Starting date of the catalogue.'),
        'period_to': fields.date(string='To', required=False,
                                 help='End date of the catalogue'),
        'currency_id': fields.many2one('res.currency', string='Currency', required=True,
                                       help='Currency used in this catalogue.'),
        'comment': fields.text(string='Comment'),
        'line_ids': fields.one2many('supplier.catalogue.line', 'catalogue_id', string='Lines'),
        'supplierinfo_ids': fields.one2many('product.supplierinfo', 'catalogue_id', string='Supplier Info.'),
        'active': fields.boolean(string='Active'),
        'current': fields.function(_get_active, fnct_search=_search_active, method=True, string='Active', type='boolean', store=False, 
                                   readonly=True, help='Indicate if the catalogue is currently active.'),
    }
    
    _defaults = {
        # By default, use the currency of the user
        'currency_id': lambda obj, cr, uid, ctx: obj.pool.get('res.users').browse(cr, uid, uid, context=ctx).company_id.currency_id.id,
        'partner_id': lambda obj, cr, uid, ctx: ctx.get('partner_id', False),
        'period_from': lambda *a: time.strftime('%Y-%m-%d'),
        'active': lambda *a: True,
    }
    
    def _check_period(self, cr, uid, ids):
        '''
        Check if the To date is older than the From date
        '''
        for catalogue in self.browse(cr, uid, ids):
            if catalogue.period_to and catalogue.period_to < catalogue.period_from:
                return False
        return True
    
    _constraints = [(_check_period, 'The \'To\' date mustn\'t be younger than the \'From\' date !', ['period_from', 'period_to'])]
    
    def open_lines(self, cr, uid, ids, context=None):
        '''
        Opens all lines of this catalogue 
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        
        cat = self.browse(cr, uid, ids[0], context=context)
        name = '%s - %s' % (cat.partner_id.name, cat.name)
        
        context.update({'search_default_partner_id': cat.partner_id.id,})
        
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'supplier_catalogue', 'supplier_catalogue_line_tree_view')[1]
        
        return {'type': 'ir.actions.act_window',
                'name': name,
                'res_model': 'supplier.catalogue.line',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': [view_id],
                'domain': [('catalogue_id', '=', ids[0])],
                'context': context}
        
    def edit_catalogue(self, cr, uid, ids, context=None):
        '''
        Open an edit view of the selected catalogue
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'supplier.catalogue',
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': ids[0],
                'context': context}
        
    def catalogue_import_lines(self, cr, uid, ids, context=None):
        '''
        Open the wizard to import lines
        '''
        if not context:
            context = {}
        
        # TODO: To implement
        raise osv.except_osv(_('Error'), _('Not implemented !'))    
        
        res_id = self.pool.get('catalogue.import.lines').create(cr, uid, {'catalogue_id': ids[0]}, context=context)
            
        return {'type': 'ir.actions.act_window',
                'res_model': 'catalogue.import.lines',
                'view_mode': 'form',
                'view_type': 'form',
                'target': 'new',
                'res_id': res_id,
                'context': context}
    
supplier_catalogue()


class supplier_catalogue_line(osv.osv):
    _name = 'supplier.catalogue.line'
    _description = 'Supplier catalogue line'
    _table = 'supplier_catalogue_line'
    # Inherits of product.product to an easier search of lines
    # with product attributes
    _inherits = {'product.product': 'product_id'}
    _order = 'product_id, line_uom_id, min_qty'
    
    def _create_supplier_info(self, cr, uid, vals, context=None):
        '''
        Create a pricelist line on product supplier information tab
        '''
        supinfo_obj = self.pool.get('product.supplierinfo')
        cat_obj = self.pool.get('supplier.catalogue')
        price_obj = self.pool.get('pricelist.partnerinfo')
        prod_obj = self.pool.get('product.product')
        
        tmpl_id = prod_obj.browse(cr, uid, vals['product_id'], context=context).product_tmpl_id.id
        catalogue = cat_obj.browse(cr, uid, vals['catalogue_id'], context=context)
        
        # Search if a product_supplierinfo exists for the catalogue, if not, create it !
        sup_ids = supinfo_obj.search(cr, uid, [('product_id', '=', tmpl_id), 
                                               ('catalogue_id', '=', vals['catalogue_id'])],
                                               context=context)
        sup_id = sup_ids and sup_ids[0] or False
        if not sup_id:
            sup_id = supinfo_obj.create(cr, uid, {'name': catalogue.partner_id.id,
                                                  'sequence': 0,
                                                  'delay': catalogue.partner_id.default_delay,
                                                  'product_id': tmpl_id,
                                                  'catalogue_id': vals['catalogue_id'],
                                                  },
                                                  context=context)
            
        price_id = price_obj.create(cr, uid, {'name': catalogue.name,
                                              'suppinfo_id': sup_id,
                                              'min_quantity': vals.get('min_qty', 0.00),
                                              'uom_id': vals['line_uom_id'],
                                              'price': vals['unit_price'],
                                              'rounding': vals.get('rounding', 1.00),
                                              'min_order_qty': vals.get('min_order_qty', 0.00),
                                              'currency_id': catalogue.currency_id.id,
                                              'valid_from': catalogue.period_from,
                                              'valid_till': catalogue.period_to,}, 
                                              context=context)
        
        vals.update({'supplier_info_id': sup_id,
                     'partner_info_id': price_id})
        
        return vals
    
    def create(self, cr, uid, vals, context=None):
        '''
        Create a pricelist line on product supplier information tab
        '''
        vals = self._create_supplier_info(cr, uid, vals, context=context)
        
        return super(supplier_catalogue_line, self).create(cr, uid, vals, context={})
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        Update the pricelist line on product supplier information tab
        '''
        if context is None:
            context = {}
        for line in self.browse(cr, uid, ids, context=context):            
            # If product is changed
            if 'product_id' in vals and vals['product_id'] != line.product_id.id:
                c = context.copy()
                c.update({'product_change': True})
                # Remove the old pricelist.partnerinfo and create a new one
                self.pool.get('pricelist.partnerinfo').unlink(cr, uid, line.partner_info_id.id, context=c)
        
                # Check if the removed line wasn't the last line of the supplierinfo
                if len(line.supplier_info_id.pricelist_ids) == 0:
                    # Remove the supplier info
                    self.pool.get('product.supplierinfo').unlink(cr, uid, line.supplier_info_id.id, context=c)
                    
                # Create new partnerinfo line
                vals.update({'catalogue_id': vals.get('catalogue_id', line.catalogue_id.id),
                             'product_id': vals.get('product_id', line.product_id.id),
                             'min_qty': vals.get('min_qty', line.min_qty),
                             'line_uom_id': vals.get('line_uom_id', line.line_uom_id.id),
                             'unit_price': vals.get('unit_price', line.unit_price),
                             'rounding': vals.get('rounding', line.rounding),
                             'min_order_qty': vals.get('min_order_qty', line.min_order_qty),
                             'comment': vals.get('comment', line.comment),
                             })
                vals = self._create_supplier_info(cr, uid, vals, context=context)
            else:
                pinfo_data = {'min_quantity': vals.get('min_qty', line.min_qty),
                          'price': vals.get('unit_price', line.unit_price),
                          'uom_id': vals.get('line_uom_id', line.line_uom_id.id),
                          'rounding': vals.get('rounding', line.rounding),
                          'min_order_qty': vals.get('min_order_qty', line.min_order_qty)
                          }
                # Update the pricelist line on product supplier information tab
                self.pool.get('pricelist.partnerinfo').write(cr, uid, [line.partner_info_id.id], 
                                                         pinfo_data, context=context) 
        
        return super(supplier_catalogue_line, self).write(cr, uid, ids, vals, context={})
    
    def unlink(self, cr, uid, line_id, context=None):
        '''
        Remove the pricelist line on product supplier information tab
        If the product supplier information has no line, remove it
        '''
        if isinstance(line_id, (int, long)):
            line_id = [line_id]
            
        for l in line_id:
            line = self.browse(cr, uid, l, context=context)
            c = context.copy()
            c.update({'product_change': True})
            # Remove the pricelist line in product tab
            self.pool.get('pricelist.partnerinfo').unlink(cr, uid, line.partner_info_id.id, context=c)
            
            # Check if the removed line wasn't the last line of the supplierinfo
            if line.supplier_info_id and len(line.supplier_info_id.pricelist_ids) == 0:
                # Remove the supplier info
                self.pool.get('product.supplierinfo').unlink(cr, uid, line.supplier_info_id.id, context=c)
        
        return super(supplier_catalogue_line, self).unlink(cr, uid, line_id, context=context)
    
    def _check_min_quantity(self, cr, uid, ids, context=None):
        '''
        Check if the min_qty field is set
        '''
        for line in self.browse(cr, uid, ids, context=context):
            if line.min_qty <= 0.00:
                raise osv.except_osv(_('Error'), _('The line of product [%s] %s has a negative or zero min. qty !') % (line.product_id.default_code, line.product_id.name))
                return False
            
        return True
    
    _columns = {
        'catalogue_id': fields.many2one('supplier.catalogue', string='Catalogue', required=True, ondelete='cascade'),
        'product_id': fields.many2one('product.product', string='Product', required=True, ondelete='cascade'),
        'min_qty': fields.float(digits=(16,2), string='Min. Qty', required=True,
                                  help='Minimal order quantity to get this unit price.'),
        'line_uom_id': fields.many2one('product.uom', string='Product UoM', required=True,
                                  help='UoM of the product used to get this unit price.'),
        'unit_price': fields.float(digits=(16,2), string='Unit Price', required=True),
        'rounding': fields.float(digits=(16,2), string='Rounding', 
                                   help='The ordered quantity must be a multiple of this rounding value.'),
        'min_order_qty': fields.float(digits=(16,2), string='Min. Order Qty'),
        'comment': fields.char(size=64, string='Comment'),
        'supplier_info_id': fields.many2one('product.supplierinfo', string='Linked Supplier Info'),
        'partner_info_id': fields.many2one('pricelist.partnerinfo', string='Linked Supplier Info line'),
    }
    
    _constraints = [
        (_check_min_quantity, 'You cannot have a line with a negative or zero quantity!', ['min_qty']),
    ]
    
    def product_change(self, cr, uid, ids, product_id, context=None):
        '''
        When the product change, fill automatically the line_uom_id field of the
        catalogue line.
        @param product_id: ID of the selected product or False
        '''
        v = {'line_uom_id': False}
        
        if product_id:
            product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            v.update({'line_uom_id': product.uom_id.id})
        
        return {'value': v}
    
    def onChangeSearchNomenclature(self, cr, uid, line_id, position, line_type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, context=None):
        '''
        Method to fill nomenclature fields in search view
        '''
        return self.pool.get('product.product').onChangeSearchNomenclature(cr, uid, [], position, line_type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=num, context=context)
        
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        Override the tree view to display historical prices according to context
        '''
        if context is None:
            context = {}
        res = super(supplier_catalogue_line, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        
        # If the context is set to open historical view
        if context.get('catalogue_ids', False) and view_type == 'tree':
            catalogues = self.pool.get('supplier.catalogue').browse(cr, uid, context.get('catalogue_ids'), context=context)
            
            # Modify the tree view to add one column by pricelist
            line_view = """<tree string="Historical prices" editable="top" noteditable="1" notselectable="0"
                    hide_new_button="1" hide_delete_button="1">
                   <field name="product_id"/>
                   <field name="line_uom_id" />
                   <field name="min_qty" />"""
                   
            for cat in catalogues:
                line_view += """<field name="%s" />""" % cat.period_from

            line_view += "</tree>"

            if res['type'] == 'tree':
                res['arch'] = line_view
        
        return res
    
    def fields_get(self, cr, uid, fields=None, context=None):
        '''
        Override the fields to display historical prices according to context
        '''
        if context is None:
            context = {}
        res = super(supplier_catalogue_line, self).fields_get(cr, uid, fields, context)
        
        if context.get('catalogue_ids', False):
            catalogues = self.pool.get('supplier.catalogue').browse(cr, uid, context.get('catalogue_ids'), context=context)
            for cat in catalogues:
                cat_from = self.pool.get('date.tools').get_date_formatted(cr, uid, d_type='date', datetime=cat.period_from, context=context)
                cat_to = ''
                if cat.period_to:
                    cat_to = self.pool.get('date.tools').get_date_formatted(cr, uid, d_type='date', datetime=cat.period_to, context=context)
                res.update({cat.period_from: {'size': 64,
                                              'selectable': True,
                                              'string': '%s-%s' % (cat_from, cat_to),
                                              'type': 'char',}})
            
        return res
    
    def read(self, cr, uid, ids, fields=None, context=None, load="_classic_write"):
        if context is None:
            context = {}
        if context.get('catalogue_ids', False):
            line_dict = {}
            new_context = context.copy()
            new_context.pop('catalogue_ids')
            catalogues = self.pool.get('supplier.catalogue').browse(cr, uid, context.get('catalogue_ids'), context=new_context)
            for cat in catalogues:
                period_name = '%s' % cat.period_from
                for line in cat.line_ids:
                    line_name = '%s_%s_%s' % (line.product_id.id, line.min_qty, line.line_uom_id.id)
                    if line_name not in line_dict:
                        line_dict.update({line_name: {}})
                    
                    line_dict[line_name].update({period_name: '%s' % line.unit_price})
            
            res = super(supplier_catalogue_line, self).read(cr, uid, ids, fields, context=context)
            
            for r in res:
                line_name = '%s_%s_%s' % (r['product_id'][0], r['min_qty'], r['line_uom_id'][0])
                for period in line_dict[line_name]:
                    r.update({period: line_dict[line_name][period]})
            
        else:
            res = super(supplier_catalogue_line, self).read(cr, uid, ids, fields, context=context)
        
        return res
        
    
supplier_catalogue_line()


class supplier_historical_catalogue(osv.osv_memory):
    _name = 'supplier.historical.catalogue'
    
    _columns = {
        'partner_id': fields.many2one('res.partner', string='Supplier'),
        'currency_id': fields.many2one('res.currency', string='Currency', required=True),
        'from_date': fields.date(string='From', required=True),
        'to_date': fields.date(string='To', required=True),
    }
    
    _defaults = {
        'partner_id': lambda obj, uid, ids, ctx: ctx.get('active_id'),
        'to_date': lambda *a: time.strftime('%Y-%m-%d'),
    }
    
    def open_historical_prices(self, cr, uid, ids, context=None):
        '''
        Open the historical prices view
        '''
        if not context:
            context = {}
            
        for hist in self.browse(cr, uid, ids, context=context):
            catalogue_ids = self.pool.get('supplier.catalogue').search(cr, uid, [('partner_id', '=', hist.partner_id.id),
                                                                                 ('active', 'in', ['t', 'f']),
                                                                                 ('currency_id', '=', hist.currency_id.id),
                                                                                 ('period_from', '<=', hist.to_date),
                                                                                 '|', ('period_to', '=', False),
                                                                                 ('period_to', '>=', hist.from_date)])
            
            if not catalogue_ids:
                raise osv.except_osv(_('Error'), _('No catalogues found for this supplier and this currency in the period !'))
            
            line_dict = {}
            line_ids = []
            catalogues = self.pool.get('supplier.catalogue').browse(cr, uid, catalogue_ids, context=context)
            for cat in catalogues:
                for line in cat.line_ids:
                    line_name = '%s_%s_%s' % (line.product_id.id, line.min_qty, line.line_uom_id.id)
                    if line_name not in line_dict:
                        line_dict.update({line_name: {}})
                        line_ids.append(line.id)
                    
            context.update({'from_date': hist.from_date,
                            'to_date': hist.to_date,
                            'partner_id': hist.partner_id.id,
                            'currency_id': hist.currency_id.id,
                            'catalogue_ids': catalogue_ids})
        
        from_str = self.pool.get('date.tools').get_date_formatted(cr, uid, d_type='date', datetime=context.get('from_date'), context=context)
        to_str = self.pool.get('date.tools').get_date_formatted(cr, uid, d_type='date', datetime=context.get('to_date'), context=context)
        
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'supplier_catalogue', 'non_edit_supplier_catalogue_line_tree_view')[1]
        
        return {'type': 'ir.actions.act_window',
                'name': '%s - Historical prices (%s) - from %s to %s' % (hist.partner_id.name, hist.currency_id.name, from_str, to_str),
                'res_model': 'supplier.catalogue.line',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', line_ids)],
                'view_id': [view_id],
                'context': context}
    
supplier_historical_catalogue()


class from_supplier_choose_catalogue(osv.osv_memory):
    _name = 'from.supplier.choose.catalogue'
    
    _columns = {
        'partner_id': fields.many2one('res.partner', string='Supplier', required=True),
        'catalogue_id': fields.many2one('supplier.catalogue', string='Catalogue', required=True),
    }
     
    def default_get(self, cr, uid, fields, context=None):
        '''
        Fill partner_id from context
        '''
        if context is None:
            context = {}
        if not context.get('active_id', False):
            raise osv.except_osv(_('Error'), _('No catalogue found !'))
        
        partner_id = context.get('active_id')
        
        if not self.pool.get('supplier.catalogue').search(cr, uid, [('partner_id', '=', partner_id)], context=context):
            raise osv.except_osv(_('Error'), _('No catalogue found !'))
        
        res = super(from_supplier_choose_catalogue, self).default_get(cr, uid, fields, context=context)
        
        res.update({'partner_id': partner_id})
        
        return res
    
    def open_catalogue(self, cr, uid, ids, context=None):
        '''
        Open catalogue lines
        '''
        wiz = self.browse(cr, uid, ids[0], context=context)
        
        return self.pool.get('supplier.catalogue').open_lines(cr, uid, wiz.catalogue_id.id, context=context)
    
from_supplier_choose_catalogue() 

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
