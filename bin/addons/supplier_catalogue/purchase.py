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
        rounding_qty = product_qty

        partner_price = self.pool.get('pricelist.partnerinfo')
        currency_id = self.pool.get('product.pricelist').browse(cr, uid, pricelist, context=context).currency_id.id
        info_prices = []
        suppinfo_ids = self.pool.get('product.supplierinfo').search(cr, uid, [('name', '=', partner_id), ('product_id', '=', product_id.product_tmpl_id.id)], context=context)
        domain = [('min_quantity', '<=', product_qty),
                  ('uom_id', '=', product_uom_id),
                  ('suppinfo_id', 'in', suppinfo_ids),
                  '|', ('valid_from', '<=', order_date),
                  ('valid_from', '=', False),
                  '|', ('valid_till', '>=', order_date),
                  ('valid_till', '=', False)]

        domain_cur = [('currency_id', '=', currency_id)]
        domain_cur.extend(domain)
        info_prices = partner_price.search(cr, uid, domain_cur, order='sequence asc, min_quantity desc, id desc', limit=1, context=context)
        if not info_prices:
            info_prices = partner_price.search(cr, uid, domain, order='sequence asc, min_quantity desc, id desc', limit=1, context=context)

        if info_prices:
            #            info = partner_price.browse(cr, uid, info_price, context=context)[0]
            info = partner_price.browse(cr, uid, info_prices[0], context=context)
            seller_delay = info.suppinfo_id.delay

            if info.min_order_qty and product_qty < info.min_order_qty:
                product_qty = info.min_order_qty
                res.update({'warning': {'title': _('Warning'), 'message': _('The product unit price has been set for a minimal quantity of %s '\
                                                                            '(the min quantity of the price list), it might change at the '\
                                                                            'supplier confirmation.') % product_qty}})
            if info.rounding and rounding_qty%info.rounding != 0:
                if not res.get('warning', {}).get('message', False):
                    res.update({'warning': {'title': _('Warning'), 'message': _('A rounding value of %s UoM has been set for ' \
                                                                                'this product, you should then modify ' \
                                                                                'the quantity ordered to match the supplier criteria.') % info.rounding}})
                else:
                    message = _('A rounding value of %s UoM has been set for ' \
                                'this product, you should then modify ' \
                                'the quantity ordered to match the supplier criteria.') % info.rounding
                    message = '%s \n %s' % (res.get('warning', {}).get('message', ''), message)
                    res['warning'].update({'message': message})
                product_qty = rounding_qty + (info.rounding - rounding_qty%info.rounding)

        return res, product_qty, product_qty, seller_delay

purchase_order_line()
