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

class sale_order_line_compute_currency(osv.osv):
    _inherit = "sale.order.line"

    def _amount_currency_line(self, cr, uid, ids, field_name, arg, context=None):
        cur_obj = self.pool.get('res.currency')
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = cur_obj.compute(cr, uid, line.currency_id.id,
                    line.functional_currency_id.id, line.price_subtotal, round=True)
        return res
    
    _columns = {
        'currency_id': fields.related('order_id', 'currency_id', type="many2one", relation="res.currency", string="Currency", store=False, readonly=True),
        'functional_subtotal': fields.function(_amount_currency_line, method=True, store=False, string='Functional Subtotal', readonly=True),
        'functional_currency_id': fields.related('company_id', 'currency_id', type="many2one", relation="res.currency", string="Functional Currency", store=False, readonly=True),
    }
    
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
                ctx['date'] = order.date_confirm
            res[order.id] = {
                            'functional_amount_untaxed':cur_obj.compute(cr, uid, order.currency_id.id,
                                                                        order.functional_currency_id.id, order.amount_untaxed, round=True, context=ctx),
                            'functional_amount_tax':cur_obj.compute(cr, uid, order.currency_id.id,
                                                                    order.functional_currency_id.id, order.amount_tax, round=True, context=ctx),
                            'functional_amount_total':cur_obj.compute(cr, uid, order.currency_id.id,
                                                                      order.functional_currency_id.id, order.amount_total, round=True, context=ctx),
                            }
        return res
    
    _columns = {
        'currency_id': fields.related('pricelist_id', 'currency_id', type="many2one", relation="res.currency", string="Currency", store=False, readonly=True),
        'functional_amount_untaxed': fields.function(_amount_currency, method=True, store=False, type='float', string='Functional Untaxed Amount', multi='amount_untaxed, amount_tax, amount_total'),
        'functional_amount_tax': fields.function(_amount_currency, method=True, store=False, type='float', string='Functional Taxes', multi='amount_untaxed, amount_tax, amount_total'),
        'functional_amount_total': fields.function(_amount_currency, method=True, store=False, type='float', string='Functional Total', multi='amount_untaxed, amount_tax, amount_total'),
        'functional_currency_id': fields.related('company_id', 'currency_id', type="many2one", relation="res.currency", string="Functional Currency", store=False, readonly=True),
    }
    
sale_order_compute_currency()

class purchase_order_line_compute_currency(osv.osv):
    _inherit = "purchase.order.line"

    def _amount_currency_line(self, cr, uid, ids, field_name, arg, context=None):
        cur_obj = self.pool.get('res.currency')
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = cur_obj.compute(cr, uid, line.currency_id.id,
                    line.functional_currency_id.id, line.price_subtotal, round=True)
        return res
    
    _columns = {
        'currency_id': fields.related('order_id', 'currency_id', type="many2one", relation="res.currency", string="Currency", store=False, readonly=True),
        'functional_subtotal': fields.function(_amount_currency_line, method=True, store=False, string='Functional Subtotal'),
        'functional_currency_id': fields.related('company_id', 'currency_id', type="many2one", relation="res.currency", string="Functional Currency", store=False, readonly=True),
    }
    
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
            res[order.id] = {
                            'functional_amount_untaxed':cur_obj.compute(cr, uid, order.currency_id.id,
                                                                        order.functional_currency_id.id, order.amount_untaxed, round=True, context=ctx),
                            'functional_amount_tax':cur_obj.compute(cr, uid, order.currency_id.id,
                                                                    order.functional_currency_id.id, order.amount_tax, round=True, context=ctx),
                            'functional_amount_total':cur_obj.compute(cr, uid, order.currency_id.id,
                                                                      order.functional_currency_id.id, order.amount_total, round=True, context=ctx),
                            }
        return res
    
    _columns = {
        'currency_id': fields.related('pricelist_id', 'currency_id', type="many2one", relation="res.currency", string="Currency", store=False, readonly=True),
        'functional_amount_untaxed': fields.function(_amount_currency, method=True, store=False, type='float', string='Functional Untaxed Amount', multi='amount_untaxed, amount_tax, amount_total'),
        'functional_amount_tax': fields.function(_amount_currency, method=True, store=False, type='float', string='Functional Taxes', multi='amount_untaxed, amount_tax, amount_total'),
        'functional_amount_total': fields.function(_amount_currency, method=True, store=False, type='float', string='Functional Total', multi='amount_untaxed, amount_tax, amount_total'),
        'functional_currency_id': fields.related('company_id', 'currency_id', type="many2one", relation="res.currency", string="Functional Currency", store=False, readonly=True),
    }
    
purchase_order_compute_currency()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
