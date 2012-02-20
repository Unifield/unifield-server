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
    
    def copy(self, cr, uid, catalogue_id, default={}, context={}):
        '''
        Disallow the possibility to duplicate a catalogue
        '''
        raise osv.except_osv(_('Error'), _('You cannot duplicate a catalogue because you musn\'t have ' \
                               'overlapped catalogue !'))
        
        return False
    
    def _update_other_catalogue(self, cr, uid, cat_id, period_from, currency_id, partner_id, period_to=False, context={}):
        '''
        Check if other catalogues need to be updated according to the new dates of cat_id
        '''
        if not context:
            context = {}
            
        if not context.get('cat_ids', False):
            context.update({'cat_ids': []})
        
        if cat_id:
            context['cat_ids'].append(cat_id)
            
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
        if to_ids:
            over_cat = self.browse(cr, uid, to_ids[0], context=context)
            over_cat_from = self.pool.get('date.tools').get_date_formatted(cr, uid, d_type='date', datetime=over_cat.period_from, context=context)
            over_cat_to = self.pool.get('date.tools').get_date_formatted(cr, uid, d_type='date', datetime=over_cat.period_to, context=context)
            raise osv.except_osv(_('Error'), _('The \'To\' date of this catalogue is older than the \'From\' date of another catalogue - ' \
                                               'Please change the \'To\' date of this catalogue or the \'From\' date of the following ' \
                                               'catalogue : %s (\'From\' : %s - \'To\' : %s)' % (over_cat.name, over_cat_from, over_cat_to)))
            
        from_update_ids = self.search(cr, uid, [('id', 'not in', context.get('cat_ids', [])), ('currency_id', '=', currency_id),
                                                                                              ('partner_id', '=', partner_id),
                                                                                              '|', 
                                                                                              ('period_to', '>', period_from), 
                                                                                              ('period_to', '=', False),], context=context)
            
        period_from = DateFrom(period_from) + RelativeDate(days=-1)
        self.write(cr, uid, from_update_ids, {'period_to': period_from.strftime('%Y-%m-%d')}, context=context)
        
        return True
    
    def create(self, cr, uid, vals, context={}):
        '''
        Check if the new values override a catalogue
        '''
        self._update_other_catalogue(cr, uid, None, vals.get('period_from', False),
                                                    vals.get('currency_id', False),
                                                    vals.get('partner_id', context.get('partner_id', False)),
                                                    vals.get('period_to', False), context=context)
        return super(supplier_catalogue, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context={}):
        '''
        Update the supplierinfo and pricelist line according to the
        new values
        '''
        supinfo_obj = self.pool.get('product.supplierinfo')
        price_obj = self.pool.get('pricelist.partnerinfo')
        
        supplierinfo_ids = supinfo_obj.search(cr, uid, [('catalogue_id', 'in', ids)], context=context)
        
        for catalogue in self.browse(cr, uid, ids, context=context):
            pricelist_ids = []
            for line in catalogue.line_ids:
                pricelist_ids.append(line.partner_info_id.id)
                
            self._update_other_catalogue(cr, uid, catalogue.id, vals.get('period_from', catalogue.period_from),
                                                                vals.get('currency_id', False),
                                                                vals.get('partner_id', False),
                                                                vals.get('period_to', catalogue.period_to), context=context)
        
            new_supinfo_vals = {}            
            # Change the partner of all supplier info instances
            if 'partner_id' in vals and vals['partner_id'] != catalogue.partner_id.id:
                delay = self.pool.get('res.partner').browse(cr, uid, vals['partner_id'], context=context).default_delay
                new_supinfo_vals.update({'name': vals['partner_id'],
                                         'delay': delay})
            
            new_price_vals = {'valid_till': vals.get('period_to', None),
                              'currency_id': vals.get('currency_id', catalogue.currency_id.id),
                              'name': vals.get('name', catalogue.name),}
                
            # Update the supplier info and price lines
            supinfo_obj.write(cr, uid, supplierinfo_ids, new_supinfo_vals, context=context)
            price_obj.write(cr, uid, pricelist_ids, new_price_vals, context=context)
        
        return super(supplier_catalogue, self).write(cr, uid, ids, vals, context=context)
    
    def _search(self, cr, uid, args, offset=0, limit=None, order=None, context={}, count=False, access_rights_uid=None):
        '''
        If the search is called from the catalogue line list view, returns only list of the
        partner defined in the context
        '''
        if context.get('search_default_partner_id', False):
            args.append(('partner_id', '=', context.get('search_default_partner_id', False)))
            
        return super(supplier_catalogue, self)._search(cr, uid, args, offset, limit, order, context, count, access_rights_uid)
    
    def _get_active(self, cr, uid, ids, field_name, arg, context={}):
        '''
        Return True if today is into the period of the catalogue
        '''
        res = {}
        
        for catalogue in self.browse(cr, uid, ids, context=context):
            date_from = DateFrom(catalogue.period_from)
            date_to = DateFrom(catalogue.period_to)
            res[catalogue.id] = date_from < now() < date_to 
        
        return res
    
    def _search_active(self, cr, uid, obj, name, args, context={}):
        '''
        Returns all active catalogue
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
        'current': fields.function(_get_active, fnct_search=_search_active, method=True, string='Active', type='boolean', store=False, 
                                   readonly=True, help='Indicate if the catalogue is currently active.'),
    }
    
    _defaults = {
        # By default, use the currency of the user
        'currency_id': lambda obj, cr, uid, ctx: obj.pool.get('res.users').browse(cr, uid, uid, context=ctx).company_id.currency_id.id,
        'partner_id': lambda obj, cr, uid, ctx: ctx.get('partner_id', False),
        'period_from': lambda *a: time.strftime('%Y-%m-%d'),
    }
    
    def _check_period(self, cr, uid, ids):
        '''
        Check if the To date is older than the From date
        '''
        for catalogue in self.browse(cr, uid, ids):
            if catalogue.period_to and catalogue.period_to < catalogue.period_from:
                return False
        return True
    
    def open_lines(self, cr, uid, ids, context={}):
        '''
        Opens all lines of this catalogue 
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        cat = self.browse(cr, uid, ids[0], context=context)
        name = cat.name
        
        context.update({'search_default_partner_id': cat.partner_id.id,})
        
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'supplier_catalogue', 'non_edit_supplier_catalogue_line_tree_view')[1]
        
        return {'type': 'ir.actions.act_window',
                'name': name,
                'res_model': 'supplier.catalogue.line',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': [view_id],
                'domain': [('catalogue_id', '=', ids[0])],
                'context': context}
    
    _constraints = [(_check_period, 'The \'To\' date mustn\'t be younger than the \'From\' date !', ['period_from', 'period_to'])]
    
supplier_catalogue()

class supplier_catalogue_line(osv.osv):
    _name = 'supplier.catalogue.line'
    _description = 'Supplier catalogue line'
    _table = 'supplier_catalogue_line'
    _inherits = {'product.product': 'product_id'}
    
    def create(self, cr, uid, vals, context={}):
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
                                                  'product_id': vals['product_id'],
                                                  'catalogue_id': vals['catalogue_id'],
                                                  },
                                                  context=context)
            
        price_id = price_obj.create(cr, uid, {'name': catalogue.name,
                                              'suppinfo_id': sup_id,
                                              'min_quantity': vals['min_qty'],
                                              'uom_id': vals['line_uom_id'],
                                              'price': vals['unit_price'],
                                              'rounding': vals['rounding'],
                                              'min_order_qty': vals['min_order_qty'],
                                              'currency_id': catalogue.currency_id.id,
                                              'valid_till': catalogue.period_to,}, 
                                              context=context)
        
        vals.update({'supplier_info_id': sup_id,
                     'partner_info_id': price_id})
        
        return super(supplier_catalogue_line, self).create(cr, uid, vals, context={})
    
    def write(self, cr, uid, ids, vals, context={}):
        '''
        Update the pricelist line on product supplier information tab
        '''
        for line in self.browse(cr, uid, ids, context=context):
            pinfo_data = {'min_quantity': vals.get('min_qty', line.min_qty),
                          'price': vals.get('unit_price', line.unit_price),
                          'rounding': vals.get('rounding', line.rounding),
                          'min_order_qty': vals.get('min_order_qty', line.min_order_qty)
                          }
            
            # Update the pricelist line on product supplier information tab
            self.pool.get('pricelist.partnerinfo').write(cr, uid, [line.partner_info_id.id], 
                                                         pinfo_data, context=context) 
        
        return super(supplier_catalogue_line, self).write(cr, uid, ids, vals, context={})
    
    def unlink(self, cr, uid, line_id, context={}):
        '''
        Remove the pricelist line on product supplier information tab
        If the product supplier information has no line, remove it
        '''
        line = self.browse(cr, uid, line_id, context=context)
        # Remove the pricelist line in product tab
        self.pool.get('pricelist.partnerinfo').unlink(cr, uid, line.partner_info_id.id, context=context)
        
        # Check if the removed line wasn't the last line of the supplierinfo
        if len(line.supplier_info_id.pricelist_ids) == 0:
            # Remove the supplier info
            self.pool.get('product.supplierinfo').unlink(cr, uid, line.supplier_info_id.id, context=context)
        
        return super(supplier_catalogue_line, self).unlink(cr, uid, line_id, context=context)
    
    def _get_partner(self, cr, uid, ids, field_name, arg, context={}):
        '''
        Returns the partner linked to the associated catalogue
        '''
        res = {}
        
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = line.catalogue_id and line.catalogue_id.partner_id and line.catalogue_id.partner_id.id or False
        
        return res
    
    def _search_partner(self, cr, uid, obj, name, args, context={}):
        '''
        Returns all active catalogue
        '''
        cat_obj = self.pool.get('supplier.catalogue')
        ids = []
        
        for arg in args:
            if arg[0] == 'partner_id':
                operator = arg[1]            
                catalogue_ids = cat_obj.search(cr, uid, [('partner_id.name', operator, arg[2])], context=context)
                ids = self.search(cr, uid, [('catalogue_id', 'in', catalogue_ids)], context=context)
        
        return ids and [('id', 'in', ids)] or []
    
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
#        'partner_id': fields.function(_get_partner, fnct_search=_search_partner, method=True, string='Partner',
#                                      type='many2one', relation='res.partner', store=False),
        'supplier_info_id': fields.many2one('product.supplierinfo', string='Linked Supplier Info'),
        'partner_info_id': fields.many2one('pricelist.partnerinfo', string='Linked Supplier Info line'),
    }
    
    def product_change(self, cr, uid, ids, product_id, context={}):
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
        return self.pool.get('product.product').onChangeSearchNomenclature(cr, uid, [], position, line_type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=num, context=context)
    
supplier_catalogue_line()


class from_supplier_choose_catalogue(osv.osv_memory):
    _name = 'from.supplier.choose.catalogue'
    
    _columns = {
        'partner_id': fields.many2one('res.partner', string='Supplier', required=True),
        'catalogue_id': fields.many2one('supplier.catalogue', string='Catalogue', required=True),
    }
     
    def default_get(self, cr, uid, fields, context={}):
        '''
        Fill partner_id from context
        '''
        if not context.get('active_id', False):
            raise osv.except_osv(_('Error'), _('No catalogue found !'))
        
        partner_id = context.get('active_id')
        
        if not self.pool.get('supplier.catalogue').search(cr, uid, [('partner_id', '=', partner_id)], context=context):
            raise osv.except_osv(_('Error'), _('No catalogue found !'))
        
        res = super(from_supplier_choose_catalogue, self).default_get(cr, uid, fields, context=context)
        
        res.update({'partner_id': partner_id})
        
        return res
    
    def open_catalogue(self, cr, uid, ids, context={}):
        '''
        Open catalogue lines
        '''
        wiz = self.browse(cr, uid, ids[0], context=context)
        
        return self.pool.get('supplier.catalogue').open_lines(cr, uid, wiz.catalogue_id.id, context=context)
    
from_supplier_choose_catalogue()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: