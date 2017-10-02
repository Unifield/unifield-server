#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Olivier DOSSMANN
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

class account_invoice_line(osv.osv):
    _name = 'account.invoice.line'
    _inherit = 'account.invoice.line'

    _columns = {
        'sale_order_lines': fields.many2many('sale.order.line', 'sale_order_line_invoice_rel', 'invoice_id', 'order_line_id', 'Sale Order Lines', readonly=True),
        'sale_order_line_id': fields.many2one('sale.order.line', string="Sale Order Line", readonly=True,
                                              help="Sale Order Line from which this line have been generated (when coming from a sale order)"),
    }

account_invoice_line()

class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    _columns = {
        'order_ids': fields.many2many('sale.order', 'sale_order_invoice_rel', 'invoice_id', 'order_id', 'Sale Order',
                                      help="Sale Order from which invoice have been generated"),
    }

    def fetch_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Recover distribution from purchase order. If a commitment is attached to purchase order, then retrieve analytic distribution from commitment voucher.
        NB: This method only works because there is a link between purchase and invoice.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        invl_obj = self.pool.get('account.invoice.line')
        ana_obj = self.pool.get('analytic.distribution')
        # Browse all invoices
        for inv in self.browse(cr, uid, ids, context=context):
            # Set analytic distribution from purchase order to invoice
            for po in inv.purchase_ids:
                # First set invoice global distribution
                if not inv.analytic_distribution_id and po.analytic_distribution_id:
                    # Fetch PO analytic distribution
                    distrib_id = po.analytic_distribution_id and po.analytic_distribution_id.id or False
                    # If commitment for this PO, fetch analytic distribution. Else take default distrib_id
                    if po.commitment_ids:
                        distrib_id = po.commitment_ids[0].analytic_distribution_id and po.commitment_ids[0].analytic_distribution_id.id or distrib_id
                    if distrib_id:
                        new_distrib_id = ana_obj.copy(cr, uid, distrib_id, {})
                        if not new_distrib_id:
                            raise osv.except_osv(_('Error'), _('An error occurred for analytic distribution copy for invoice.'))
                        # create default funding pool lines
                        ana_obj.create_funding_pool_lines(cr, uid, [new_distrib_id])
                        self.pool.get('account.invoice').write(cr, uid, [inv.id], {'analytic_distribution_id': new_distrib_id,})
            for so in inv.order_ids:
                # Create analytic distribution on invoices regarding FO
                if so.analytic_distribution_id:
                    distrib_id = so.analytic_distribution_id and so.analytic_distribution_id.id or False
                    if distrib_id:
                        new_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, distrib_id, {})
                        if not new_distrib_id:
                            raise osv.except_osv(_('Error'), _('An error occurred for analytic distribution copy for invoice.'))
                        # create default funding pool lines
                        self.pool.get('analytic.distribution').create_funding_pool_lines(cr, uid, [new_distrib_id])
                        self.pool.get('account.invoice').write(cr, uid, [inv.id], {'analytic_distribution_id': new_distrib_id,})
            # Then set distribution on invoice line regarding purchase order line distribution
            for invl in inv.invoice_line:
                if invl.order_line_id:
                    # Fetch PO line analytic distribution or nothing (that implies it take those from PO)
                    distrib_id = invl.order_line_id.analytic_distribution_id and invl.order_line_id.analytic_distribution_id.id or False
                    # Attempt to fetch commitment line analytic distribution or commitment voucher analytic distribution or default distrib_id
                    if invl.order_line_id.commitment_line_ids:
                        distrib_id = invl.order_line_id.commitment_line_ids[0].analytic_distribution_id \
                            and invl.order_line_id.commitment_line_ids[0].analytic_distribution_id.id or distrib_id
                    if distrib_id:
                        new_invl_distrib_id = ana_obj.copy(cr, uid, distrib_id, {})
                        if not new_invl_distrib_id:
                            raise osv.except_osv(_('Error'), _('An error occurred for analytic distribution copy for invoice.'))
                        # create default funding pool lines
                        ana_obj.create_funding_pool_lines(cr, uid, [new_invl_distrib_id], invl.account_id.id)
                        invl_obj.write(cr, uid, [invl.id], {'analytic_distribution_id': new_invl_distrib_id})
                # Fetch SO line analytic distribution
                if invl.sale_order_line_id:
                    distrib_id = invl.sale_order_line_id.analytic_distribution_id and invl.sale_order_line_id.analytic_distribution_id.id or False
                    if distrib_id:
                        new_invl_distrib_id = ana_obj.copy(cr, uid, distrib_id, {})
                        if not new_invl_distrib_id:
                            raise osv.except_osv(_('Error'), _('An error occurred for analytic distribution copy for invoice.'))
                        # create default funding pool lines
                        ana_obj.create_funding_pool_lines(cr, uid, [new_invl_distrib_id], invl.account_id.id)
                        invl_obj.write(cr, uid, [invl.id], {'analytic_distribution_id': new_invl_distrib_id})
        return True

    def update_commitments(self, cr, uid, ids, context=None):
        """
        Update engagement lines for given invoice.
        NB: We use COMMITMENT VOUCHER ANALYTIC DISTRIBUTION for updating!
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Browse given invoices
        cv_ids = {}
        grouped_invl = {}
        for inv in self.browse(cr, uid, ids, context=context):
            for invl in inv.invoice_line:
                # Do not take invoice line that have no order_line_id (so that are not linked to a purchase order line)
                if not invl.order_line_id:
                    if not inv.is_merged_by_account:
                        continue
                    # US-357 tolerate merge lines without PO line link

                # Fetch purchase order line account
                if inv.is_merged_by_account:
                    if not invl.account_id:
                        continue
                    # US-357: lines without product (get directly account)
                    a = invl.account_id.id
                else:
                    pol = invl.order_line_id
                    if pol.product_id:
                        a = pol.product_id.product_tmpl_id.property_account_expense.id
                        if not a:
                            a = pol.product_id.categ_id.property_account_expense_categ.id
                        if not a:
                            raise osv.except_osv(_('Error !'), _('There is no expense account defined for this product: "%s" (id:%d)') % (pol.product_id.name, pol.product_id.id,))
                    else:
                        a = self.pool.get('ir.property').get(cr, uid, 'property_account_expense_categ', 'product.category').id
                for cv_line in invl.order_line_id.commitment_line_ids:
                        cv_ids[cv_line.commit_id.id] = True
                        key = cv_line
                        if key not in grouped_invl:
                            grouped_invl[key] = 0
                        grouped_invl[key] += invl.price_subtotal
            if cv_ids:
                co_ids = self.pool.get('account.commitment').search(cr, uid, [('id', 'in', cv_ids.keys()), ('state', '=', 'draft')], context=context)
                if co_ids:
                # If Commitment voucher in draft state we change it to 'validated' without using workflow and engagement lines generation
                # NB: This permits to avoid modification on commitment voucher when receiving some goods
                    self.pool.get('account.commitment').write(cr, uid, co_ids, {'state': 'open'}, context=context)

            # Browse result
            diff_lines = []
            for cl in grouped_invl.keys():
                # if no difference between invoice lines and commitment line: delete engagement lines that come from this commitment_line
                eng_ids = self.pool.get('account.analytic.line').search(cr, uid, [('commitment_line_id', '=', cl.id)], context=context)
                if abs(cl.amount - grouped_invl[key]) < 0.001:
                    if eng_ids:
                        self.pool.get('account.analytic.line').unlink(cr, uid, eng_ids, context=context)
                    self.pool.get('account.commitment.line').write(cr, uid, [cl.id], {'amount': 0.0}, context=context)
                else:
                    # Remember difference in diff_lines list
                    diff_lines.append({'cl': cl, 'diff': cl.amount - grouped_invl[key], 'new_mnt': grouped_invl[key]})
            # Difference lines process
            if diff_lines:
                for diff_line in diff_lines:
                    # Prepare some values
                    cl = diff_line.get('cl', False)
                    diff = diff_line.get('diff', 0.0)
                    new_mnt = diff_line.get('new_mnt', 0.0)
                    company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
                    if not cl:
                        raise osv.except_osv(_('Error'), _('No commitment line found. Please contact an administrator to resolve this problem.'))
                    distrib_id = cl.analytic_distribution_id and cl.analytic_distribution_id.id or cl.commit_id and cl.commit_id.analytic_distribution_id \
                        and cl.commit_id.analytic_distribution_id.id or False
                    if not distrib_id:
                        raise osv.except_osv(_('Error'), _('No analytic distribution found.'))
                    # Browse distribution
                    distrib = self.pool.get('analytic.distribution').browse(cr, uid, [distrib_id], context=context)[0]
                    engagement_lines = distrib.analytic_lines
                    for distrib_lines in [distrib.cost_center_lines, distrib.funding_pool_lines, distrib.free_1_lines, distrib.free_2_lines]:
                        for distrib_line in distrib_lines:
                            vals = {
                                'account_id': distrib_line.analytic_id.id,
                                'general_account_id': cl.account_id.id,
                            }
                            if distrib_line._name == 'funding.pool.distribution.line':
                                vals.update({'cost_center_id': distrib_line.cost_center_id and distrib_line.cost_center_id.id or False,})
                            # Browse engagement lines to found out matching elements
                            for i in range(0,len(engagement_lines)):
                                if engagement_lines[i]:
                                    eng_line = engagement_lines[i]
                                    cmp_vals = {
                                        'account_id': eng_line.account_id.id,
                                        'general_account_id': eng_line.general_account_id.id,
                                    }
                                    if eng_line.cost_center_id:
                                        cmp_vals.update({'cost_center_id': eng_line.cost_center_id.id})
                                    if cmp_vals == vals:
                                        # Update analytic line with new amount
                                        anal_amount = (distrib_line.percentage * diff) / 100
                                        amount = -1 * self.pool.get('res.currency').compute(cr, uid, inv.currency_id.id, company_currency,
                                                                                            anal_amount, round=False, context=context)
                                        # write new amount to corresponding engagement line
                                        self.pool.get('account.analytic.line').write(cr, uid, [eng_line.id],
                                                                                     {'amount': amount, 'amount_currency': -1 * anal_amount}, context=context)
                                        # delete processed engagement lines
                                        engagement_lines[i] = None
                    # update existent commitment line with new amount (new_mnt)
                    commitment_line_new_amount = cl.amount - new_mnt
                    if commitment_line_new_amount < 0.0:
                        commitment_line_new_amount = 0.0
                    self.pool.get('account.commitment.line').write(cr, uid, [cl.id], {'amount': commitment_line_new_amount}, context=context)
            # Update commitment voucher state (if total_amount is inferior to 0.0, then state is done)
            for cv in self.pool.get('account.commitment').read(cr, uid, cv_ids.keys(), ['total'], context=context):
                if abs(cv['total']) < 0.001:
                    self.pool.get('account.commitment').action_commitment_done(cr, uid, [cv['id']], context=context)
        return True

    def action_open_invoice(self, cr, uid, ids, context=None):
        """
        Launch engagement lines updating if a commitment is attached to PO that generate this invoice.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        to_process = []
        # Verify if all invoice have a po that have a commitment
        for inv in self.browse(cr, uid, ids, context=context):
            for po in inv.purchase_ids:
                if po.commitment_ids:
                    to_process.append(inv.id)
                    # UTP-536 : Check if the PO is closed and all SI are draft, then close the CV
                    if po.state == 'done' and all(x.id in ids or x.state != 'draft' for x in po.invoice_ids):
                        self.pool.get('purchase.order')._finish_commitment(cr, uid, [po.id], context=context)

        # Process invoices
        self.update_commitments(cr, uid, to_process, context=context)
        return super(account_invoice, self).action_open_invoice(cr, uid, ids, context=context)

account_invoice()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
