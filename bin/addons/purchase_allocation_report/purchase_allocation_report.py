# -*- coding: utf-8 -*-
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
from tools.translate import _

import decimal_precision as dp

import tools

from purchase import ORDER_CATEGORY, PURCHASE_ORDER_STATE_SELECTION, PURCHASE_ORDER_LINE_STATE_SELECTION


class purchase_order_line_allocation_report(osv.osv):
    _name = 'purchase.order.line.allocation.report'
    _table = 'purchase_order_line_allocation_report'
    _rec_name = 'order_id'
    _auto = False

    _replace_exported_fields = {
        'product_id': [
            (['product_code', 'Product Code'], 10),
            (['product_name', 'Product Name'], 20),
        ],
    }

    def _get_product_account(self, cr, uid, ids, field_name, args, context=None):
        res = {}

        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = False
            if line.product_id:
                res[line.id] = line.product_id.product_tmpl_id.property_account_expense.id
                if not res[line.id]:
                    res[line.id] = line.product_id.categ_id.property_account_expense_categ.id

        return res

    _columns = {
        'order_id': fields.many2one('purchase.order', string='PO', domain=[('rfq_ok', '=', False)]),
        'order_type': fields.selection([('regular', 'Regular'), ('donation_exp', 'Donation to prevent losses'),
                                        ('donation_st', 'Standard donation'), ('loan', 'Loan'),
                                        ('loan_return', 'Loan Return'), ('in_kind', 'In Kind Donation'),
                                        ('purchase_list', 'Purchase List'), ('direct', 'Direct Purchase Order')],
                                       string='Type'),
        'order_category': fields.selection(ORDER_CATEGORY, string='Cat.'),
        'line_number': fields.integer(string='#'),
        'product_id': fields.many2one('product.product', string='Product'),
        'product_code': fields.related(
            'product_id',
            'default_code',
            type='char',
            size=64,
            string='Product Code',
            store=False,
            write_relate=False,
        ),
        'product_name': fields.related(
            'product_id',
            'name',
            type='char',
            size=128,
            string='Product Name',
            store=False,
            write_relate=False,
        ),
        'product_qty': fields.float(digits=(16,2), string='Qty', related_uom='uom_id'),
        'uom_id': fields.many2one('product.uom', string='UoM'),
        'unit_price': fields.float(string='Unit Price', digits_compute=dp.get_precision('Purchase Price Computation')),
        'analytic_id': fields.many2one('analytic.distribution', string='Distribution'),
        'percentage': fields.float(digits=(16,2), string='%'),
        'subtotal': fields.float(digits=(16,2), string='Subtotal'),
        'currency_id': fields.many2one('res.currency', string='Cur.'),
        'cost_center_id': fields.many2one('account.analytic.account', string='C.C.'),
        'destination_id': fields.many2one('account.analytic.account', string='Destination'),
        #'cost_center_id': fields.many2one('cost.center.distribution.line', string='Cost center'),
        #'account_id': fields.many2one('account.account', string='Account'),
        'account_id': fields.function(_get_product_account, method=True, string='Account', type='many2one', relation='account.account', store=False),
        'source_doc': fields.char(size=128, string='Source Doc.'),
        'requestor': fields.char(size=128, string='Requestor'),
        'partner_doc': fields.char(size=128, string='Partner Doc.'),
        'state': fields.selection(PURCHASE_ORDER_STATE_SELECTION, string='State'),
        'line_state': fields.selection(PURCHASE_ORDER_LINE_STATE_SELECTION, string='PO Line Status'),
        'supplier': fields.many2one('res.partner', string='Supplier'),
        'creation_date': fields.date(string='Creation date'),
        'comment': fields.char('Comment', size=1024),
    }

    def init(self, cr):
        tools.drop_view_if_exists(cr, 'purchase_order_line_allocation_report')
        cr.execute("""
            CREATE OR REPLACE view purchase_order_line_allocation_report AS (
                SELECT
                    row_number() OVER(ORDER BY al.line_id) AS id,
                    al.order_id,
                    al.order_type,
                    al.order_category,
                    al.line_id,
                    al.line_number,
                    al.product_id,
                    al.product_qty,
                    al.uom_id,
                    al.unit_price,
                    al.analytic_id,
                    al.destination_id,
                    al.percentage,
                    (al.unit_price*al.product_qty*al.percentage)/100.00 as subtotal,
                    al.currency_id,
                    al.cost_center_id,
                    al.source_doc,
                    al.requestor,
                    al.supplier,
                    al.state,
                    al.line_state,
                    al.creation_date,
                    al.partner_doc,
                    al.comment
                FROM
                ((SELECT 
                    po.id AS order_id,
                    po.order_type AS order_type,
                    po.categ AS order_category,
                    pol.id AS line_id,
                    pol.line_number AS line_number,
                    pol.product_id AS product_id,
                    pol.product_qty AS product_qty,
                    pol.product_uom AS uom_id,
                    pol.price_unit AS unit_price,
                    pol.analytic_distribution_id AS analytic_id,
                    aaa2.id AS destination_id,
                    cc.percentage AS percentage,
                    cc.amount AS subtotal,
                    ppl.currency_id AS currency_id,
                    aaa.id AS cost_center_id,
                    so.name AS source_doc,
                    (CASE WHEN so.procurement_request = 't' THEN loc.name 
                        WHEN pol.linked_sol_id IS NOT NULL THEN sop.name ELSE '' END) AS requestor,
                    po.partner_id AS supplier,
                    po.state AS state,
                    pol.state AS line_state,
                    po.date_order AS creation_date,
                    so.client_order_ref AS partner_doc,
                    pol.comment AS comment
                FROM
                    purchase_order_line pol
                  LEFT JOIN
                    purchase_order po
                    ON
                    pol.order_id = po.id
                  LEFT JOIN
                    product_pricelist ppl
                    ON
                    po.pricelist_id = ppl.id
                  LEFT JOIN
                    analytic_distribution ad
                    ON
                    pol.analytic_distribution_id = ad.id
                  LEFT JOIN
                    cost_center_distribution_line cc
                    ON
                    cc.distribution_id = ad.id
                  LEFT JOIN
                    account_analytic_account aaa
                    ON
                    cc.analytic_id = aaa.id
                  LEFT JOIN
                    account_analytic_account aaa2
                    ON
                    cc.destination_id = aaa2.id
                  LEFT JOIN
                    sale_order_line sol
                    ON
                    sol.id = pol.linked_sol_id
                  LEFT JOIN
                    sale_order so
                    ON
                    sol.order_id = so.id
                  LEFT JOIN
                    res_partner sop
                    ON
                    so.partner_id = sop.id
                  LEFT JOIN
                    stock_location loc
                    ON
                    so.location_requestor_id = loc.id
                WHERE pol.analytic_distribution_id IS NOT NULL
		    AND po.rfq_ok = 'f' AND pol.state not in ('cancel', 'cancel_r'))
                UNION
                (SELECT 
                    po.id AS order_id,
                    po.order_type AS order_type,
                    po.categ AS order_category,
                    pol.id AS line_id,
                    pol.line_number AS line_number,
                    pol.product_id AS product_id,
                    pol.product_qty AS product_qty,
                    pol.product_uom AS uom_id,
                    pol.price_unit AS unit_price,
                    po.analytic_distribution_id AS analytic_id,
                    aaa2.id AS destination_id,
                    cc.percentage AS percentage,
                    cc.amount AS subtotal,
                    ppl.currency_id AS currency_id,
                    aaa.id AS cost_center_id,
                    so.name AS source_doc,
                    (CASE WHEN so.procurement_request = 't' THEN loc.name 
                        WHEN pol.linked_sol_id IS NOT NULL THEN sop.name ELSE '' END) AS requestor,
                    po.partner_id AS supplier,
                    po.state AS state,
                    pol.state AS line_state,
                    po.date_order AS creation_date,
                    so.client_order_ref AS partner_doc,
                    pol.comment AS comment
                FROM
                    purchase_order_line pol
                  LEFT JOIN
                    purchase_order po
                    ON
                    pol.order_id = po.id
                  LEFT JOIN
                    product_pricelist ppl
                    ON
                    po.pricelist_id = ppl.id
                  LEFT JOIN
                    analytic_distribution ad
                    ON
                    po.analytic_distribution_id = ad.id
                  LEFT JOIN
                    cost_center_distribution_line cc
                    ON
                    cc.distribution_id = ad.id
                  LEFT JOIN
                    account_analytic_account aaa
                    ON
                    cc.analytic_id = aaa.id
                  LEFT JOIN 
                    account_analytic_account aaa2
                    ON
                    cc.destination_id = aaa2.id
                  LEFT JOIN
                    sale_order_line sol
                    ON
                    sol.id = pol.linked_sol_id
                  LEFT JOIN
                    sale_order so
                    ON
                    sol.order_id = so.id
                  LEFT JOIN
                    res_partner sop
                    ON
                    so.partner_id = sop.id
                  LEFT JOIN
                    stock_location loc
                    ON
                    so.location_requestor_id = loc.id
                WHERE 
                    pol.analytic_distribution_id IS NULL
		    AND po.rfq_ok = 'f' AND pol.state not in ('cancel', 'cancel_r'))) AS al
            );""")


purchase_order_line_allocation_report()


class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit = 'purchase.order'

    def copy(self, cr, uid, ids, default=None, context=None):
        if default is None:
            default = {}
        default.update({'allocation_report_lines': []})
        return super(purchase_order, self).copy(cr, uid, ids, default, context=context)

    _columns = {
        'allocation_report_lines': fields.one2many('purchase.order.line.allocation.report', 'order_id', string='Allocation lines'),
    }

    def open_allocation_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if not 'active_id' in context:
            raise osv.except_osv(_('Error'), _('No active purchase order found !'))

        for order in self.browse(cr, uid, ids, context=context):
            if order.rfq_ok:
                raise osv.except_osv(_('Error'), _('The document %s is a Request for Quotation, you cannot have an allocation report on RfQ !') % order.name)

        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'purchase_allocation_report', 'purchase_order_allocation_line_report_from_po')

        return {'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'res_id': context.get('active_id'),
                'view_id': view_id and [view_id[1]] or False,
                'view_type': 'form',
                'view_mode': 'form'}

purchase_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
