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

import time

class product_supplierinfo(osv.osv):
    _name = 'product.supplierinfo'
    _inherit = 'product.supplierinfo'
    
    def unlink(self, cr, uid, info_ids, context=None):
        '''
        Disallow the possibility to remove a supplier info if 
        it's linked to a catalogue
        If 'product_change' is set to True in context, allows the deletion
        because it says that the unlink method is called by the write method
        of supplier.catalogue.line and that the product of the line has changed.
        '''
        if context is None:
            context = {}
        if isinstance(info_ids, (int, long)):
            info_ids = [info_ids]
            
        for info in self.browse(cr, uid, info_ids, context=context):
            if info.catalogue_id and not context.get('product_change', False):
                raise osv.except_osv(_('Error'), _('You cannot remove a supplier information which is linked ' \
                                                   'to a supplier catalogue line ! Please remove the corresponding ' \
                                                   'supplier catalogue line to remove this supplier information.'))
        
        return super(product_supplierinfo, self).unlink(cr, uid, info_ids, context=context)
    
    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        if not context:
            context = {}
        
        new_res = [] 
        res = super(product_supplierinfo, self).search(cr, uid, args, offset, limit,
                order, context=context, count=count)
        
        if isinstance(res, (int, long)):
            res = [res]
        
        for r in self.browse(cr, uid, res, context=context):
            if not r.catalogue_id or r.catalogue_id.active:
                new_res.append(r.id)
        
        return new_res
    
    def _get_editable(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return True if no catalogue associated
        '''
        res = {}
        
        for x in self.browse(cr, uid, ids, context=context):
            res[x.id] = True
            if x.catalogue_id:
                res[x.id] = False
        
        return res
    
    _columns = {
        'catalogue_id': fields.many2one('supplier.catalogue', string='Associated catalogue', ondelete='cascade'),
        'editable': fields.function(_get_editable, method=True, string='Editable', store=False, type='boolean'),
        'min_qty': fields.float('Minimal Quantity', required=False, help="The minimal quantity to purchase to this supplier, expressed in the supplier Product UoM if not empty, in the default unit of measure of the product otherwise."),
        'product_uom': fields.related('product_id', 'uom_id', string="Supplier UoM", type='many2one', relation='product.uom',  
                                      help="Choose here the Unit of Measure in which the prices and quantities are expressed below."),
    }
    
    # Override the original method
    def price_get(self, cr, uid, supplier_ids, product_id, product_qty=1, context=None):
        """
        Calculate price from supplier pricelist.
        @param supplier_ids: Ids of res.partner object.
        @param product_id: Id of product.
        @param product_qty: specify quantity to purchase.
        """
        if type(supplier_ids) in (int,long,):
            supplier_ids = [supplier_ids]
        res = {}
        product_pool = self.pool.get('product.product')
        partner_pool = self.pool.get('res.partner')
        currency_id = context.get('currency_id', False) or self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        date = context.get('date', False) or time.strftime('%Y-%m-%d')
        uom_id = context.get('uom', False) or product_pool.browse(cr, uid, product_id, context=context).uom_id.id
        for supplier in partner_pool.browse(cr, uid, supplier_ids, context=context):
            res[supplier.id] = product_pool._get_partner_price(cr, uid, product_id, supplier.id, product_qty,
                                                                        currency_id, date, uom_id, context=context)
        return res
    
product_supplierinfo()


class pricelist_partnerinfo(osv.osv):
    _name = 'pricelist.partnerinfo'
    _inherit = 'pricelist.partnerinfo'
    
    def unlink(self, cr, uid, info_id, context=None):
        '''
        Disallow the possibility to remove a supplier pricelist 
        if it's linked to a catalogue line.
        If 'product_change' is set to True in context, allows the deletion
        because the product on catalogue line has changed and the current line
        should be removed.
        '''
        if context is None:
            context = {}
        info = self.browse(cr, uid, info_id, context=context)
        if info.suppinfo_id.catalogue_id and not context.get('product_change', False):
            raise osv.except_osv(_('Error'), _('You cannot remove a supplier pricelist line which is linked ' \
                                               'to a supplier catalogue line ! Please remove the corresponding ' \
                                               'supplier catalogue line to remove this supplier information.'))
        
        return super(pricelist_partnerinfo, self).unlink(cr, uid, info_id, context=context)
    
    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        if not context:
            context = {}
            
        res = super(pricelist_partnerinfo, self).search(cr, uid, args, offset, limit,
                order, context=context, count=count)
        
        new_res = []
        
        for r in self.browse(cr, uid, res, context=context):
            if not r.suppinfo_id or not r.suppinfo_id.catalogue_id or r.suppinfo_id.catalogue_id.active:
                new_res.append(r.id)
        
        return new_res
    
    _columns = {
        'uom_id': fields.many2one('product.uom', string='UoM', required=True),
        'rounding': fields.float(digits=(16,2), string='Rounding', 
                                 help='The ordered quantity must be a multiple of this rounding value.'),
        'min_order_qty': fields.float(digits=(16, 2), string='Min. Order Qty'),
    }
    
pricelist_partnerinfo()


class product_product(osv.osv):
    _name = 'product.product'
    _inherit = 'product.product'
    
    def _get_partner_price(self, cr, uid, product_ids, partner_id, product_qty, currency_id,
                                          order_date, product_uom_id, context=None):
        '''
        Search the good partner price line for products
        '''
        res = {}
        one_product = False
        partner_price = self.pool.get('pricelist.partnerinfo')
        suppinfo_obj = self.pool.get('product.supplierinfo')
        prod_obj = self.pool.get('product.product')
        
        if not context:
            context = {}
            
        if isinstance(product_ids, (int, long)):
            one_product = product_ids
            product_ids = [product_ids]
            
        for product in prod_obj.browse(cr, uid, product_ids, context=context):
            suppinfo_ids = suppinfo_obj.search(cr, uid, [('name', '=', partner_id),
                                                         ('product_id', '=', product.product_tmpl_id.id),
                                                         '|', ('catalogue_id.period_from', '<=', order_date),
                                                         ('catalogue_id', '=', False)],
                                               order='sequence', limit=1, context=context) 
            # Search the good line for the price
            info_price = partner_price.search(cr, uid, [('suppinfo_id', 'in', suppinfo_ids),
                                                        ('min_quantity', '<=', product_qty),
                                                        ('uom_id', '=', product_uom_id),
                                                        ('currency_id', '=', currency_id),
                                                        '|', ('valid_till', '>=', order_date),
                                                        ('valid_till', '=', False)],
                                                   order='valid_till asc, min_quantity desc', limit=1, context=context)
            
            if info_price:
                info = partner_price.browse(cr, uid, info_price, context=context)[0]
                res[product.id] = (info.price, info.rounding or 1.00, info.suppinfo_id.min_qty or 0.00) 
            else:
                res[product.id] = (False, 1.0, 1.0)
                        
        return not one_product and res or res[one_product]
    
product_product()


class product_pricelist(osv.osv):
    _name = 'product.pricelist'
    _inherit = 'product.pricelist'
    
    def _hook_product_partner_price(self, cr, uid, *args, **kwargs):
        '''
        Rework the computation of price from partner section in product form
        '''
        product_id = kwargs['product_id']
        partner = kwargs['partner']
        qty = kwargs['qty']
        currency_id = kwargs['currency_id']
        date = kwargs['date']
        uom = kwargs['uom']
        context = kwargs['context']
        uom_price_already_computed = kwargs['uom_price_already_computed']
        
        price, rounding, min_qty = self.pool.get('product.product')._get_partner_price(cr, uid, product_id, partner, qty, currency_id,
                                                                                       date, uom, context=context)
        uom_price_already_computed = 1
        
        return price, uom_price_already_computed
    
product_pricelist()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
