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

#
# Please note that these reports are not multi-currency !!!
#

from osv import fields,osv
import tools
from order_types import ORDER_PRIORITY, ORDER_CATEGORY
from msf_order_date import ZONE_SELECTION

class purchase_report(osv.osv):
    _name = "purchase.report"
    _description = "Purchases Orders"
    _auto = False

    def _invoiced(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for id in ids:
            res[id] = False
        return res

    STATE_SELECTION = [
        ('draft', 'Draft'),
        ('wait', 'Wait'),
        ('confirmed', 'Validated'),
        ('approved', 'Confirmed'),
        ('except_picking', 'Receipt Exception'),
        ('except_invoice', 'Invoice Exception'),
        ('done', 'Closed'),
        ('cancel', 'Cancelled'),
        ('rfq_sent', 'Sent'),
        ('rfq_updated', 'Updated'),
        ('rfq_done', 'Closed'),]

    _columns = {
        'date': fields.date('Order Date', readonly=True, help="Date on which this document has been created"),
        'name': fields.char('Year',size=64,required=False, readonly=True),
        'day': fields.char('Day', size=128, readonly=True),
        'state': fields.selection(STATE_SELECTION, 'Order State', readonly=True),
        'product_id':fields.many2one('product.product', 'Product', readonly=True),
        'product_code': fields.char(size=256, string='Product Code', readonly=True),
        'product_name': fields.char(size=512, string='Product Name', readonly=True),
        'warehouse_id': fields.many2one('stock.warehouse', 'Warehouse', readonly=True),
        'partner_id':fields.many2one('res.partner', 'Supplier', readonly=True),
        'partner_zone': fields.selection(ZONE_SELECTION, string='Supplier Zone', readonly=True),
        'partner_address_id':fields.many2one('res.partner.address', 'Address Contact Name', readonly=True),
        'dest_address_id':fields.many2one('res.partner.address', 'Dest. Address Contact Name',readonly=True),
        'pricelist_id':fields.many2one('product.pricelist', 'Currency', readonly=True),
        'date_approve':fields.date('Date Approved', readonly=True),
        'expected_date':fields.date('Expected Date', readonly=True),
        'validator' : fields.many2one('res.users', 'Validated By', readonly=True),
        'product_uom' : fields.many2one('product.uom', 'Reference UoM', required=True),
        'company_id':fields.many2one('res.company', 'Company', readonly=True),
        'user_id':fields.many2one('res.users', 'Responsible', readonly=True),
        'delay':fields.float('Days to Validate', digits=(16,2), readonly=True),
        'delay_pass':fields.float('Days to Deliver', digits=(16,2), readonly=True),
        'quantity': fields.float('Quantity', readonly=True, related_uom='product_uom'),
        'price_total': fields.float('Subtotal', readonly=True),
        'price_average': fields.float('Average Price', readonly=True, group_operator="avg"),
        'negociation': fields.float('Purchase-Standard Price', readonly=True, group_operator="avg"),
        'price_standard': fields.float('Products Value', readonly=True, group_operator="sum"),
        'nbr': fields.integer('# of Lines', readonly=True),
        'month':fields.selection([('01','January'), ('02','February'), ('03','March'), ('04','April'), ('05','May'), ('06','June'),
                                  ('07','July'), ('08','August'), ('09','September'), ('10','October'), ('11','November'), ('12','December')],'Month',readonly=True),
        'category_id': fields.many2one('product.nomenclature', 'Family', readonly=True),
        'order_name': fields.char('Order Reference', size=64, required=True,
                                  readonly=True, states={'draft': [('readonly', False)]}, select=True),
        'invoiced': fields.function(_invoiced, method=True, string='Paid',
                                    type='boolean', help="It indicates that an invoice has been paid."),
        'order_type': fields.selection([('regular', 'Regular'), ('donation_exp', 'Donation before expiry'),
                                        ('donation_st', 'Standard donation'), ('loan', 'Loan'),
                                        ('loan_return', 'Loan Return'), ('in_kind', 'In Kind Donation'),
                                        ('purchase_list', 'Purchase List'), ('direct', 'Direct Purchase Order')],
                                       string='Order Type', required=True, readonly=True),
        'priority': fields.selection(ORDER_PRIORITY, string='Priority', readonly=True, states={'draft': [('readonly', False)]}),
        'categ': fields.selection(ORDER_CATEGORY, string='Order category', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'currency_id': fields.many2one('res.currency', string='Currency'),
        'cost_center_id': fields.many2one('account.analytic.account', string='Cost Center', readonly=True),
        'location_id': fields.many2one('stock.location', string='Location'),
    }
    _order = 'name desc,price_total desc'
    def init(self, cr):
        tools.sql.drop_view_if_exists(cr, 'purchase_report')
        cr.execute("""
            create or replace view purchase_report as (
                select
                    row_number() OVER(ORDER BY s.name) AS id,
                    s.date_order as date,
                    to_char(s.date_order, 'YYYY') as name,
                    to_char(s.date_order, 'MM') as month,
                    to_char(s.date_order, 'YYYY-MM-DD') as day,
                    s.state,
                    s.date_approve,
                    date_trunc('day',s.minimum_planned_date) as expected_date,
                    s.partner_address_id,
                    s.dest_address_id,
                    s.pricelist_id,
                    s.validator,
                    l.reception_dest_id as location_id,
                    s.warehouse_id as warehouse_id,
                    (case when cc.percentage is not null then
                        cc.analytic_id
                    else ccp.analytic_id
                    end) as cost_center_id,
                    s.partner_id as partner_id,
                    part.zone as partner_zone,
                    s.create_uid as user_id,
                    s.company_id as company_id,
                    l.product_id,
                    pp.default_code as product_code,
                    pt.name as product_name,
                    t.nomen_manda_2 as category_id,
                    s.name as order_name,
                    s.order_type as order_type,
                    s.priority as priority,
                    s.categ as categ,
                    t.uom_id as product_uom,
                    (case when cc.percentage is not null then
                        sum(l.product_qty/u.factor*pu.factor*(cc.percentage/100.00))
                    when ccp.percentage is not null then
                        sum(l.product_qty/u.factor*pu.factor*(ccp.percentage/100.00))
                    else
                        sum(l.product_qty/u.factor*pu.factor)
                    end) as quantity,
                    extract(epoch from age(s.date_approve,s.date_order))/(24*60*60)::decimal(16,2) as delay,
                    extract(epoch from age(l.date_planned,s.date_order))/(24*60*60)::decimal(16,2) as delay_pass,
                    count(*) as nbr,
                    (case when cc.percentage is not null then
                        (l.price_unit*l.product_qty*u.factor*(1/rcr_fr.rate)*(cc.percentage/100.00))::decimal(16,2)
                    when ccp.percentage is not null then
                        (l.price_unit*l.product_qty*u.factor*(1/rcr_fr.rate)*(ccp.percentage/100.00))::decimal(16,2)
                    else
                        (l.price_unit*l.product_qty*u.factor*(1/rcr_fr.rate))::decimal(16,2)
                    end) as price_total,
                    avg(100.0 * (l.price_unit*l.product_qty*u.factor*(1/rcr_fr.rate)) / NULLIF(t.standard_price*l.product_qty*u.factor*(1/rcr_fr.rate), 0.0))::decimal(16,2) as negociation,

                    sum(t.standard_price*l.product_qty*u.factor*(1/rcr_fr.rate))::decimal(16,2) as price_standard,
                    (sum(l.product_qty*l.price_unit*(1/rcr_fr.rate))/NULLIF(sum(l.product_qty*u.factor*(1/rcr_fr.rate)),0.0))::decimal(16,2) as price_average,
                    
                    1 as currency_id
                from purchase_order s
                    left join purchase_order_line l on (s.id=l.order_id)
                        left join product_product p on (l.product_id=p.id)
                            left join product_template t on (p.product_tmpl_id=t.id)
                                left join product_uom pu on (t.uom_id = pu.id)
                    left join analytic_distribution pd on s.analytic_distribution_id = pd.id
                    left join cost_center_distribution_line ccp on ccp.distribution_id = pd.id
                    left join analytic_distribution d on l.analytic_distribution_id = d.id
                    left join cost_center_distribution_line cc on cc.distribution_id = d.id
                    left join product_uom u on (u.id=l.product_uom)
                    left join product_pricelist ppl on (ppl.id = s.pricelist_id)
                    left join product_product pp on l.product_id = pp.id
                    left join product_template pt on pp.product_tmpl_id = pt.id
                    left join res_partner part on (part.id = s.partner_id)
                    left join res_currency_rate rcr_fr on rcr_fr.currency_id = ppl.currency_id 
                        AND rcr_fr.id IN (SELECT rcrd.id from res_currency_rate rcrd WHERE rcrd.currency_id = ppl.currency_id AND rcrd.name <= COALESCE(s.date_approve,NOW()) ORDER BY name desc LIMIT 1 )
                where l.product_id is not null and s.rfq_ok = False
                group by
                    s.company_id,
                    s.create_uid,
                    l.product_qty,
                    pp.default_code,
                    pt.name,
                    u.factor,
                    cc.analytic_id,
                    cc.percentage,
                    ccp.analytic_id,
                    ccp.percentage,
                    s.partner_id,
                    part.zone,
                    l.reception_dest_id,
                    l.price_unit,
                    s.date_approve,
                    l.date_planned,
                    l.product_uom,
                    t.uom_id,
                    date_trunc('day',s.minimum_planned_date),
                    s.partner_address_id,
                    s.pricelist_id,
                    s.validator,
                    s.dest_address_id,
                    l.product_id,
                    t.nomen_manda_2,
                    s.date_order,
                    to_char(s.date_order, 'YYYY'),
                    to_char(s.date_order, 'MM'),
                    to_char(s.date_order, 'YYYY-MM-DD'),
                    s.state,
                    s.warehouse_id,
                    u.uom_type, 
                    u.category_id,
                    u.id,
                    s.name,
                    s.order_type,
                    s.priority,
                    s.categ,
                    rcr_fr.rate
            )
        """)

    _replace_exported_fields = {
        'product_id': [
            (['product_code', 'Product Code'], 10),
            (['product_name', 'Product Name'], 20),
        ],
    }

    def read_group(self, cr, uid, domain, fields, groupby, offset=0, limit=None, context=None, orderby=False, count=False):
        '''
        Add functional currency on all lines
        '''
        res = super(purchase_report, self).read_group(cr, uid, domain, fields, groupby, offset, limit, context, orderby, count=count)
        if self._name == 'purchase.report':
            for data in res:
                # If no information to display, don't display the currency
                if not '__count' in data or data['__count'] != 0:
                    currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id
                    data.update({'currency_id': (currency.id, currency.name)})

                product_id = 'product_id' in data and data['product_id'] and data['product_id'][0] or False
                if data.get('__domain'):
                    for x in data.get('__domain'):
                        if x[0] == 'product_id':
                            product_id = x[2]

                if product_id:
                    product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
                    data.update({
                        'product_uom': (product.uom_id.id, product.uom_id.name),
                        'product_code': product.default_code,
                        'product_name': product.name,
                    })

                if not product_id and 'quantity' in data:
                    data.update({'quantity': ''})

        return res

purchase_report()

