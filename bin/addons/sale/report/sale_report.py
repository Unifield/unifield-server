# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

import tools
from osv import fields, osv
from order_types import ORDER_PRIORITY, ORDER_CATEGORY
from sale import SALE_ORDER_STATE_SELECTION

class sale_report(osv.osv):
    _name = "sale.report"
    _description = "Sales Orders Statistics"
    _auto = False
    _rec_name = 'date'

    def _invoiced(self, cr, uid, ids, name, arg, context=None):
        '''
        Return True is the sale order is an uninvoiced order
        '''
        partner_obj = self.pool.get('res.partner')
        partner = False
        res = {}
        for report in self.browse(cr, uid, ids):
            sale = report.order_id
            if sale.partner_id:
                partner = partner_obj.browse(cr, uid, [sale.partner_id.id])[0]
            if sale.state != 'draft' and (sale.order_type not in ['regular', 'donation_prog']
                                          or (partner and partner.partner_type == 'internal')):
                res[report.id] = True
            else:
                res[report.id] = True
                for invoice in sale.invoice_ids:
                    if invoice.state not in ('paid', 'inv_close'):
                        res[report.id] = False
                        break
                if not sale.invoice_ids:
                    res[report.id] = False
        return res

    _columns = {
        'date': fields.date('Date Order', readonly=True),
        'date_confirm': fields.date('Date Confirm', readonly=True),
        'shipped': fields.boolean('Shipped', readonly=True),
        'shipped_qty_1': fields.integer('Shipped Qty', readonly=True),
        'year': fields.char('Year', size=4, readonly=True),
        'month': fields.selection([('01', 'January'), ('02', 'February'), ('03', 'March'), ('04', 'April'),
                                   ('05', 'May'), ('06', 'June'), ('07', 'July'), ('08', 'August'), ('09', 'September'),
                                   ('10', 'October'), ('11', 'November'), ('12', 'December')], 'Month', readonly=True),
        'day': fields.char('Day', size=128, readonly=True),
        'product_id': fields.many2one('product.product', 'Product', readonly=True),
        'product_code': fields.char(size=256, string='Product code', readonly=True),
        'product_name': fields.char(size=512, string='Product Name', readonly=True),
        'uom_name': fields.char('Reference UoM', size=128, readonly=True),
        'product_uom_qty': fields.float('# of Qty', readonly=True),
        'partner_id': fields.many2one('res.partner', 'Partner', readonly=True),
        'shop_id': fields.many2one('sale.shop', 'Shop', readonly=True),
        'company_id': fields.many2one('res.company', 'Company', readonly=True),
        'user_id': fields.many2one('res.users', 'Salesman', readonly=True),
        'price_total': fields.float('Total Price', readonly=True),
        'delay': fields.float('Commitment Delay', digits=(16,2), readonly=True),
        'categ_id': fields.many2one('product.category','Category of Product', readonly=True),
        'nbr': fields.integer('# of Lines', readonly=True),
        'state': fields.selection(selection=SALE_ORDER_STATE_SELECTION,
                                  string='Order State', readonly=True),
        'pricelist_id': fields.many2one('product.pricelist', 'Currency', readonly=True),
        'analytic_account_id': fields.many2one('account.analytic.account', 'Analytic Account', readonly=True),
        'name': fields.char('Order Reference', size=64, required=True,
                            readonly=True, states={'draft': [('readonly', False)]}, select=True),
        'invoiced': fields.function(_invoiced, method=True, string='Paid',
                                    type='boolean', help="It indicates that an invoice has been paid."),
        'order_type': fields.selection([('regular', 'Regular'), ('donation_prog', 'Programmatic Donation'),
                                        ('donation_exp', 'Donation to prevent losses'), ('donation_st', 'Standard donation'),
                                        ('loan', 'Loan'), ('loan_return', 'Loan Return'),],
                                       string='Order Type', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'priority': fields.selection(ORDER_PRIORITY, string='Priority', readonly=True, states={'draft': [('readonly', False)]}),
        'categ': fields.selection(ORDER_CATEGORY, string='Order category', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'order_id': fields.many2one('sale.order', string='Order'),
        'currency_id': fields.many2one('res.currency',string='Currency'),
    }
    _order = 'date desc'
    _replace_exported_fields = {
        'product_id': [
            (['product_code', 'Product Code'], 10),
            (['product_name', 'Product Name'], 20),
        ],
    }

    def read_group(self, cr, uid, domain, fields, groupby, offset=0,limit=None, context=None, orderby=False, count=False):
        res = super(sale_report, self).read_group(cr, uid, domain,fields, groupby, offset, limit, context, orderby, count=count)
        if self._name == 'sale.report':
            for data in res:
                if not '__count' in data or data['__count'] != 0:
                    currency = self.pool.get('res.users').browse(cr,uid, uid, context=context).company_id.currency_id
                    data.update({'currency_id': (currency.id,currency.name)})

                product_id = 'product_id' in data and data['product_id'] and data['product_id'][0] or False
                if data.get('__domain'):
                    for x in data.get('__domain'):
                        if x[0] == 'product_id':
                            product_id = x[2]

                if product_id:
                    product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
                    data.update({
                        'uom_name': product.uom_id.name,
                        'product_code': product.default_code,
                        'product_name': product.name,
                    })

                if not product_id and 'product_uom_qty' in data:
                    data.update({'product_uom_qty': ''})

        return res

    def init(self, cr):
        tools.drop_view_if_exists(cr, 'sale_report')
        cr.execute("""
            create or replace view sale_report as (
                select el.*,
                   -- (select count(1) from sale_order_line where order_id = s.id) as nbr,
                    (select 1) as nbr,
                     s.date_order as date,
                     s.name as name,
                     s.order_type as order_type,
                     s.priority as priority,
                     s.categ as categ,
                     s.date_confirm as date_confirm,
                     to_char(s.date_order, 'YYYY') as year,
                     to_char(s.date_order, 'MM') as month,
                     to_char(s.date_order, 'YYYY-MM-DD') as day,
                     s.partner_id as partner_id,
                     s.user_id as user_id,
                     s.shop_id as shop_id,
                     s.company_id as company_id,
                     extract(epoch from avg(date_trunc('day',s.date_confirm)-date_trunc('day',s.create_date)))/(24*60*60)::decimal(16,2) as delay,
                     s.state,
                     s.shipped,
                     s.shipped::integer as shipped_qty_1,
                     s.pricelist_id as pricelist_id,
                     s.project_id as analytic_account_id,
                     0 as currency_id
                from
                sale_order s,
                    (
                    select l.id as id,
                        l.product_id as product_id,
                        p.default_code as product_code,
                        pt.name as product_name,
                        u.name as uom_name,
                        sum(l.product_uom_qty / u.factor * pu.factor) as product_uom_qty,
                        sum(l.product_uom_qty * l.price_unit) as price_total,
                        pt.categ_id, l.order_id
                    from
                     sale_order_line l ,product_uom u, product_product p, product_template pt, product_uom pu
                     where u.id = l.product_uom
                     and pt.id = p.product_tmpl_id
                     and p.id = l.product_id
                     and pu.id = pt.uom_id
                      group by l.id, l.order_id, l.product_id, u.name, pt.categ_id, u.uom_type, u.category_id, p.default_code, pt.name) el
                where s.id = el.order_id
                group by el.id,
                    el.product_id,
                    el.product_code,
                    el.product_name,
                    el.uom_name,
                    el.product_uom_qty,
                    el.price_total,
                    el.categ_id,
                    el.order_id,
                    s.date_order,
                    s.date_confirm,
                    s.partner_id,
                    s.user_id,
                    s.shop_id,
                    s.company_id,
                    s.state,
                    s.shipped,
                    s.pricelist_id,
                    s.project_id,
                    s.name,
                    s.order_type,
                    s.priority,
                    s.categ
            )
        """)
sale_report()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
