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
        
        currency_id = self.pool.get('product.pricelist').browse(cr, uid, pricelist, context=context).currency_id.id
        
        # Search the good line for the price
        info_price = partner_price.search(cr, uid, [('suppinfo_id.name', '=', partner_id),
                                                    ('suppinfo_id.product_id', '=', product_id.product_tmpl_id.id),
                                                    ('min_quantity', '<=', product_qty),
                                                    ('uom_id', '=', product_uom_id),
                                                    ('currency_id', '=', currency_id),
                                                    '|', ('valid_till', '>', order_date),
                                                    ('valid_till', '=', False)],
                                                    order='valid_till asc, min_quantity desc', limit=1, context=context)
            
        if info_price:
            info = partner_price.browse(cr, uid, info_price, context=context)[0]
            seller_delay = info.suppinfo_id.delay
            
            if info.min_order_qty and product_qty < info.min_order_qty:
                product_qty = info.min_order_qty
                res.update({'warning': {'title': _('Warning'), 'message': _('The selected supplier has a minimal ' \
                                                                            'quantity set to %s, you cannot purchase less.') % product_qty}})
                
            if info.rounding and product_qty%info.rounding != 0:
                product_qty = product_qty + (info.rounding - product_qty%info.rounding)
                    
        return res, product_qty, product_qty, seller_delay
    
purchase_order_line()
    