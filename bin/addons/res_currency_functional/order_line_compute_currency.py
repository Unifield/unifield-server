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

from osv import fields, osv

import decimal_precision as dp

class sale_order_line_compute_currency(osv.osv):
    _inherit = "sale.order.line"

    def _amount_currency_line(self, cr, uid, ids, field_name, arg, context=None):
        cur_obj = self.pool.get('res.currency')
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            try:
                res[line.id] = cur_obj.compute(cr, uid, line.currency_id.id,
                                               line.functional_currency_id.id, line.price_subtotal, round=True)
            except osv.except_osv:
                res[line.id] = 0
        return res

    _columns = {
        'currency_id': fields.related('order_id', 'currency_id', type="many2one", relation="res.currency", string="Currency", store=False, readonly=True),
        'functional_subtotal': fields.function(_amount_currency_line, method=True, store=False, string='Functional Subtotal', readonly=True, digits_compute=dp.get_precision('Sale Price')),
        'functional_currency_id': fields.related('company_id', 'currency_id', type="many2one", relation="res.currency", string="Functional Currency", store=False, readonly=True, write_relate=False),
    }

    def default_get(self, cr, uid, fields, context=None):
        '''
        Fill currency and functional currency fields
        '''
        if not context:
            context = {}

        res = super(sale_order_line_compute_currency, self).default_get(cr, uid, fields, context=context)

        res['functional_currency_id'] = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
#        if context.get('pricelist_id'):
#            res['currency_id'] = self.pool.get('product.pricelist').browse(cr, uid, context.get('pricelist_id'), context=context).currency_id.id
        if context.get('sale_id'):
            res['currency_id'] = self.pool.get('sale.order').browse(cr, uid, context.get('sale_id')).pricelist_id.currency_id.id
        else:
            res['currency_id'] = res['functional_currency_id']

        return res

sale_order_line_compute_currency()

class sale_order_compute_currency(osv.osv):
    _inherit = "sale.order"

    def _amount_currency(self, cr, uid, ids, field_name, arg, context=None):
        cur_obj = self.pool.get('res.currency')
        res = {}
        for order in self.browse(cr, uid, ids, context=context):
            # The confirmed date, if present, is used as a "freeze" date
            # for the currency rate
            ctx = {}
            if order.date_confirm:
                ctx['currency_date'] = order.date_confirm
            try:
                res[order.id] = {
                    'functional_amount_untaxed':cur_obj.compute(cr, uid, order.currency_id.id,
                                                                order.functional_currency_id.id, order.amount_untaxed, round=True, context=ctx),
                    'functional_amount_tax':cur_obj.compute(cr, uid, order.currency_id.id,
                                                            order.functional_currency_id.id, order.amount_tax, round=True, context=ctx),
                    'functional_amount_total':cur_obj.compute(cr, uid, order.currency_id.id,
                                                              order.functional_currency_id.id, order.amount_total, round=True, context=ctx),
                }
            except osv.except_osv:
                res[order.id] = {
                    'functional_amount_untaxed':0,
                    'functional_amount_tax':0,
                    'functional_amount_total':0
                }
        return res

    _columns = {
        'currency_id': fields.related('pricelist_id', 'currency_id', type="many2one", relation="res.currency", string="Currency", store=False, readonly=True),
        'functional_amount_untaxed': fields.function(_amount_currency, method=True, store=False, type='float', digits_compute=dp.get_precision('Sale Price'), string='Functional Untaxed Amount', multi='amount_untaxed, amount_tax, amount_total'),
        'functional_amount_tax': fields.function(_amount_currency, method=True, store=False, type='float', digits_compute=dp.get_precision('Sale Price'), string='Functional Taxes', multi='amount_untaxed, amount_tax, amount_total'),
        'functional_amount_total': fields.function(_amount_currency, method=True, store=False, type='float', digits_compute=dp.get_precision('Sale Price'), string='Functional Total', multi='amount_untaxed, amount_tax, amount_total'),
        'functional_currency_id': fields.related('company_id', 'currency_id', type="many2one", relation="res.currency", string="Functional Currency", store=False, readonly=True, write_relate=False),
    }

sale_order_compute_currency()

class purchase_order_line_compute_currency(osv.osv):
    _inherit = "purchase.order.line"

    def _amount_currency_line(self, cr, uid, ids, field_name, arg, context=None):
        cur_obj = self.pool.get('res.currency')
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            try:
                res[line.id] = cur_obj.compute(cr, uid, line.currency_id.id,
                                               line.functional_currency_id.id, line.price_subtotal, round=True)
            except osv.except_osv:
                res[line.id] = 0
        return res

    _columns = {
        'currency_id': fields.related('order_id', 'currency_id', type="many2one", relation="res.currency", string="Currency", store=False, readonly=True),
        'functional_subtotal': fields.function(_amount_currency_line, method=True, store=False, string='Functional Subtotal', digits_compute=dp.get_precision('Purchase Price')),
        'functional_currency_id': fields.related('company_id', 'currency_id', type="many2one", relation="res.currency", string="Functional Currency", store=False, readonly=True, write_relate=False),
    }

    def default_get(self, cr, uid, fields, context=None):
        '''
        Fill currency and functional currency fields
        '''
        if not context:
            context = {}

        res = super(purchase_order_line_compute_currency, self).default_get(cr, uid, fields, context=context)

        res['functional_currency_id'] = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        if context.get('pricelist_id'):
            res['currency_id'] = self.pool.get('product.pricelist').browse(cr, uid, context.get('pricelist_id'), context=context).currency_id.id

        return res

purchase_order_line_compute_currency()

class purchase_order_compute_currency(osv.osv):
    _inherit = "purchase.order"

    def _amount_currency(self, cr, uid, ids, field_name, arg, context=None):
        cur_obj = self.pool.get('res.currency')
        res = {}
        for order in self.browse(cr, uid, ids, context=context):
            # The approved date, if present, is used as a "freeze" date
            # for the currency rate
            ctx = {}
            if order.date_approve:
                ctx['date'] = order.date_approve
            try:
                res[order.id] = {
                    'functional_amount_untaxed':cur_obj.compute(cr, uid, order.currency_id.id,
                                                                order.functional_currency_id.id, order.amount_untaxed, round=True, context=ctx),
                    'functional_amount_tax':cur_obj.compute(cr, uid, order.currency_id.id,
                                                            order.functional_currency_id.id, order.amount_tax, round=True, context=ctx),
                    'functional_amount_total':cur_obj.compute(cr, uid, order.currency_id.id,
                                                              order.functional_currency_id.id, order.amount_total, round=True, context=ctx),
                }
            except osv.except_osv:
                res[order.id] = {
                    'functional_amount_untaxed':0,
                    'functional_amount_tax':0,
                    'functional_amount_total':0
                }
        return res

    _columns = {
        'currency_id': fields.related('pricelist_id', 'currency_id', type="many2one", relation="res.currency", string="Currency", store=False, readonly=True),
        'functional_amount_untaxed': fields.function(_amount_currency, method=True, store=False, type='float', string='Functional Untaxed Amount', digits_compute=dp.get_precision('Purchase Price'), multi='amount_untaxed, amount_tax, amount_total'),
        'functional_amount_tax': fields.function(_amount_currency, method=True, store=False, type='float', string='Functional Taxes', digits_compute=dp.get_precision('Purchase Price'), multi='amount_untaxed, amount_tax, amount_total'),
        'functional_amount_total': fields.function(_amount_currency, method=True, store=False, type='float', string='Functional Total', digits_compute=dp.get_precision('Purchase Price'), multi='amount_untaxed, amount_tax, amount_total'),
        'functional_currency_id': fields.related('company_id', 'currency_id', type="many2one", relation="res.currency", string="Functional Currency", store=False, readonly=True, write_relate=False),
    }

purchase_order_compute_currency()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
