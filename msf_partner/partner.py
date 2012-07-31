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

from osv import osv
from osv import fields
from msf_partner import PARTNER_TYPE 
import time


class res_partner(osv.osv):
    _name = 'res.partner'
    _inherit = 'res.partner'
    
    def search_in_product(self, cr, uid, obj, name, args, context=None):
        '''
        Search function of related field 'in_product'
        '''
        if not len(args):
            return []
        if context is None:
            context = {}
        if not context.get('product_id', False) or 'choose_supplier' not in context:
            return []

        supinfo_obj = self.pool.get('product.supplierinfo')
        sup_obj = self.pool.get('res.partner')
        res = []

        info_ids = supinfo_obj.search(cr, uid, [('product_product_ids', '=', context.get('product_id'))])
        info = supinfo_obj.read(cr, uid, info_ids, ['name'])

        sup_in = [x['name'] for x in info]
        
        for arg in args:
            if arg[1] == '=':
                if arg[2]:
                    res = sup_in
            else:
                    res = sup_obj.search(cr, uid, [('id', 'not in', sup_in)])
        
        if not res:
            return [('id', '=', 0)]
        return [('id', 'in', [x[0] for x in res])]
        
    
    def _set_in_product(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Returns according to the context if the partner is in product form
        '''
        if context is None:
            context = {}
        res = {}
        
        product_obj = self.pool.get('product.product')
        
        # If we aren't in the context of choose supplier on procurement list
        if not context.get('product_id', False) or 'choose_supplier' not in context:
            for i in ids:
                res[i] = {'in_product': False, 'min_qty': 'N/A', 'delay': 'N/A'}
        else:
            product = product_obj.browse(cr, uid, context.get('product_id'))
            seller_ids = []
            seller_info = {}
            # Get all suppliers defined on product form
            for s in product.seller_ids:
                seller_ids.append(s.name.id)
                seller_info.update({s.name.id: {'min_qty': s.min_qty, 'delay': s.delay}})
            # Check if the partner is in product form
            for i in ids:
                if i in seller_ids:
                    res[i] = {'in_product': True, 'min_qty': '%s' %seller_info[i]['min_qty'], 'delay': '%s' %seller_info[i]['delay']}
                else:
                    res[i] = {'in_product': False, 'min_qty': 'N/A', 'delay': 'N/A'}

        return res
    
    def _get_price_info(self, cr, uid, ids, fiedl_name, args, context=None):
        '''
        Returns information from product supplierinfo if product_id is in context
        '''
        if not context:
            context = {}
            
        partner_price = self.pool.get('pricelist.partnerinfo')
        res = {}
        
        for id in ids:
            res[id] = {'price_currency': False,
                       'price_unit': 0.00,
                       'valide_until_date': False}
            
        if context.get('product_id'):
            for partner in self.browse(cr, uid, ids, context=context):
                product = self.pool.get('product.product').browse(cr, uid, context.get('product_id'), context=context)
                uom = context.get('uom', product.uom_id.id)
                pricelist = partner.property_product_pricelist_purchase
                context.update({'uom': uom})
                price_list = self.pool.get('product.product')._get_partner_info_price(cr, uid, product, partner.id, context.get('product_qty', 1.00), pricelist.currency_id.id, time.strftime('%Y-%m-%d'), uom, context=context)
                if not price_list:
                    func_currency_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
                    price = self.pool.get('res.currency').compute(cr, uid, func_currency_id, pricelist.currency_id.id, product.standard_price, round=True, context=context)
                    res[partner.id] = {'price_currency': pricelist.currency_id.id,
                                       'price_unit': price,
                                       'valide_until_date': False}
                else:
                    info_price = partner_price.browse(cr, uid, price_list[0], context=context)
                    partner_currency_id = pricelist.currency_id.id
                    price = self.pool.get('res.currency').compute(cr, uid, info_price.currency_id.id, partner_currency_id, info_price.price)
                    currency = partner_currency_id
                    # Uncomment the following 2 lines if you want the price in currency of the pricelist.partnerinfo instead of partner default currency
#                    currency = info_price.currency_id.id
#                    price = info_price.price
                    res[partner.id] = {'price_currency': currency,
                                       'price_unit': price,
                                       'valide_until_date': info_price.valid_till}
            
        return res

## QT : Remove _get_price_unit

## QT : Remove _get_valide_until_date 

    _columns = {
        'manufacturer': fields.boolean(string='Manufacturer', help='Check this box if the partner is a manufacturer'),
        'partner_type': fields.selection(PARTNER_TYPE, string='Partner type', required=True),
        'in_product': fields.function(_set_in_product, fnct_search=search_in_product, string='In product', type="boolean", readonly=True, method=True, multi='in_product'),
        'min_qty': fields.function(_set_in_product, string='Min. Qty', type='char', readonly=True, method=True, multi='in_product'),
        'delay': fields.function(_set_in_product, string='Delivery Lead time', type='char', readonly=True, method=True, multi='in_product'),
        'property_product_pricelist_purchase': fields.property(
          'product.pricelist',
          type='many2one', 
          relation='product.pricelist', 
          domain=[('type','=','purchase')],
          string="Purchase default currency", 
          method=True,
          view_load=True,
          required=True,
          help="This currency will be used, instead of the default one, for purchases from the current partner"),
        'property_product_pricelist': fields.property(
            'product.pricelist',
            type='many2one', 
            relation='product.pricelist', 
            domain=[('type','=','sale')],
            string="Field orders default currency", 
            method=True,
            view_load=True,
            required=True,
            help="This currency will be used, instead of the default one, for field orders to the current partner"),
        'price_unit': fields.function(_get_price_info, method=True, type='float', string='Unit price', multi='info'),
        'valide_until_date' : fields.function(_get_price_info, method=True, type='char', string='Valide untill date', multi='info'),
        'price_currency': fields.function(_get_price_info, method=True, type='many2one', relation='res.currency', string='Currency', multi='info'),
    }

    _defaults = {
        'manufacturer': lambda *a: False,
        'partner_type': lambda *a: 'external',
    }

    def create(self, cr, uid, vals, context=None):
        if 'partner_type' in vals and vals['partner_type'] in ('internal', 'section', 'esc', 'intermission'):
            msf_customer = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_internal_customers')
            msf_supplier = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_internal_suppliers')
            if msf_customer and not 'property_stock_customer' in vals:
                vals['property_stock_customer'] = msf_customer[1]
            if msf_supplier and not 'property_stock_supplier' in vals:
                vals['property_stock_supplier'] = msf_supplier[1]

        return super(res_partner, self).create(cr, uid, vals, context=context)
    
    def on_change_partner_type(self, cr, uid, ids, partner_type, sale_pricelist, purchase_pricelist):
        '''
        Change the procurement method according to the partner type
        '''
        price_obj = self.pool.get('product.pricelist')
        cur_obj = self.pool.get('res.currency')
        user_obj = self.pool.get('res.users')
        
        r = {'po_by_project': 'project'}
        
        if not partner_type or partner_type in ('external', 'internal'):
            r.update({'po_by_project': 'all'})
        
        sale_authorized_price = price_obj.search(cr, uid, [('type', '=', 'sale'), ('in_search', '=', partner_type)])
        if sale_authorized_price and sale_pricelist not in sale_authorized_price:
            r.update({'property_product_pricelist': sale_authorized_price[0]})
            
        purchase_authorized_price = price_obj.search(cr, uid, [('type', '=', 'purchase'), ('in_search', '=', partner_type)])
        if purchase_authorized_price and purchase_pricelist not in purchase_authorized_price:
            r.update({'property_product_pricelist_purchase': purchase_authorized_price[0]})
        
        if partner_type and partner_type in ('internal', 'section', 'esc', 'intermission'):
            msf_customer = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_internal_customers')
            if msf_customer:
                r.update({'property_stock_customer': msf_customer[1]})
            msf_supplier = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_internal_suppliers')
            if msf_supplier:
                r.update({'property_stock_supplier': msf_supplier[1]})
        else:
            other_customer = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_customers')
            if other_customer:
                r.update({'property_stock_customer': other_customer[1]})
            other_supplier = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_suppliers')
            if other_supplier:
                r.update({'property_stock_supplier': other_supplier[1]}) 
        
        return {'value': r}
    
    def search(self, cr, uid, args=None, offset=0, limit=None, order=None, context=None, count=False):
        '''
        Sort suppliers to have all suppliers in product form at the top of the list
        '''
        supinfo_obj = self.pool.get('product.supplierinfo')
        if context is None:
            context = {}
        if args is None:
            args = []
        
        # Get all supplier
        tmp_res = super(res_partner, self).search(cr, uid, args, offset, limit, order, context=context, count=count)
        if not context.get('product_id', False) or 'choose_supplier' not in context or count:
            return tmp_res
        else:
            # Get all supplier in product form
            args.append(('in_product', '=', True))
            res_in_prod = super(res_partner, self).search(cr, uid, args, offset, limit, order, context=context, count=count)
            new_res = []

            # Sort suppliers by sequence in product form
            if 'product_id' in context:
                supinfo_ids = supinfo_obj.search(cr, uid, [('name', 'in', res_in_prod), ('product_product_ids', '=', context.get('product_id'))], order='sequence')
            
                for result in supinfo_obj.read(cr, uid, supinfo_ids, ['name']):
                    try:
                        tmp_res.remove(result['name'][0])
                        new_res.append(result['name'][0])
                    except:
                        pass

            #return new_res  # comment this line to have all suppliers (with suppliers in product form at the top of the list)

            new_res.extend(tmp_res)
            
            return new_res

res_partner()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

