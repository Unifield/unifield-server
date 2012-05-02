# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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

from tools.translate import _

class purchase_order_line(osv.osv):
    _name = 'purchase.order.line'
    _inherit = 'purchase.order.line'

    def _hook_product_id_change(self, cr, uid, *args, **kwargs):
        '''
        Override the computation of product qty to order
        '''                   
        product_id = kwargs['product']
        partner_id = kwargs['partner_id']
        product_qty = kwargs['product_qty']
        pricelist = kwargs['pricelist']
        order_date = kwargs['order_date']
        product_uom_id = kwargs['uom_id']
        seller_delay = kwargs['seller_delay']
        context = kwargs['context']
        res = kwargs['res']
        
        partner_price = self.pool.get('pricelist.partnerinfo')
        suppinfo_obj = self.pool.get('product.supplierinfo')
        prod_obj = self.pool.get('product.product')
        catalogue_obj = self.pool.get('supplier.catalogue')
        
        currency_id = self.pool.get('product.pricelist').browse(cr, uid, pricelist, context=context).currency_id.id
        
        sequence_ids = suppinfo_obj.search(cr, uid, [('name', '=', partner_id),
                                                     ('product_id', '=', product_id.product_tmpl_id.id)], 
                                                     order='sequence asc', limit=1, context=context)
            
        domain = [('min_quantity', '<=', product_qty),
                  ('uom_id', '=', product_uom_id),
                  ('currency_id', '=', currency_id),
                  '|', ('valid_from', '<=', order_date),
                  ('valid_from', '=', False),
                  '|', ('valid_till', '>=', order_date),
                  ('valid_till', '=', False)]
        
        if sequence_ids:
            min_seq = suppinfo_obj.browse(cr, uid, sequence_ids[0], context=context).sequence
            domain.append(('suppinfo_id.sequence', '=', min_seq))
        
        info_prices = partner_price.search(cr, uid, domain, order='min_quantity desc, id desc', limit=1, context=context)
            
        if info_prices:
#            info = partner_price.browse(cr, uid, info_price, context=context)[0]
            info = partner_price.browse(cr, uid, info_prices[0], context=context)
            seller_delay = info.suppinfo_id.delay
            
            if info.min_order_qty and product_qty < info.min_order_qty:
                product_qty = info.min_order_qty
                res.update({'warning': {'title': _('Warning'), 'message': _('The product unit price has been set for a minimal quantity of %s '\
                                                                            '(the min quantity of the price list), it might change at the '\
                                                                            'supplier confirmation.') % product_qty}})
                
            if info.rounding and product_qty%info.rounding != 0:
                if not res.get('warning', {}).get('message', False):
                    res.update({'warning': {'title': _('Warning'), 'message': _('The selected supplier has a packaging ' \
                                                                                'which is a multiple of %s.') % info.rounding}})
                product_qty = product_qty + (info.rounding - product_qty%info.rounding)
                    
        return res, product_qty, product_qty, seller_delay
    
purchase_order_line()
