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
from osv import orm
from osv import fields
from tools.translate import _
from base import currency_date


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
                line_distrib_id = False
                if invl.cv_line_ids:
                    # CV STARTING FROM VERSION 2
                    # the first CV line found is used since there can be only one at this step (merging lines by account could
                    # generate an invoice line linked to several CV lines but this action can only be done later in the process)
                    line_distrib_id = invl.cv_line_ids[0].analytic_distribution_id and invl.cv_line_ids[0].analytic_distribution_id.id or False
                elif invl.order_line_id:
                    # Fetch PO line analytic distribution or nothing (that implies it take those from PO)
                    line_distrib_id = invl.order_line_id.analytic_distribution_id and invl.order_line_id.analytic_distribution_id.id or False
                    # Attempt to fetch commitment line analytic distribution or commitment voucher analytic distribution or default distrib_id
                    # CV IN VERSION 1
                    if invl.order_line_id.commitment_line_ids:
                        line_distrib_id = invl.order_line_id.commitment_line_ids[0].analytic_distribution_id \
                            and invl.order_line_id.commitment_line_ids[0].analytic_distribution_id.id or line_distrib_id
                if line_distrib_id:
                    new_invl_distrib_id = ana_obj.copy(cr, uid, line_distrib_id, {})
                    if not new_invl_distrib_id:
                        raise osv.except_osv(_('Error'), _('An error occurred for analytic distribution copy for invoice.'))
                    # create default funding pool lines
                    ana_obj.create_funding_pool_lines(cr, uid, [new_invl_distrib_id], invl.account_id.id)
                    invl_obj.write(cr, uid, [invl.id], {'analytic_distribution_id': new_invl_distrib_id})
                # Fetch SO line analytic distribution
                    # sol AD copy moved into _invoice_line_hook
        return True

    def update_commitments(self, cr, uid, ids, context=None):
        """
        Update engagement lines for given invoice.
        Deduce Amount Left on the oldest CV for the SI line account used
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # Browse invoices
        for inv in self.browse(cr, uid, ids, context=context):
            grouped_invl_by_acc = {}
            grouped_invl_by_cvl = {}
            co_ids = self.pool.get('account.commitment').search(cr, uid, [('purchase_id', 'in', [x.id for x in inv.purchase_ids]), ('state', 'in', ['open', 'draft'])], order='date desc', context=context)
            if not co_ids:
                continue

            for invl in inv.invoice_line:
                # Do not take invoice line that have no order_line_id (so that are not linked to a purchase order line)
                if not invl.order_line_id and not inv.is_merged_by_account:
                    continue
                old_cv_version = True
                # CV STARTING FROM VERSION 2
                for cv_line in invl.cv_line_ids:
                    old_cv_version = False  # the field cv_line_ids exist for CVs starting from version 2
                    if cv_line.id not in grouped_invl_by_cvl:
                        grouped_invl_by_cvl[cv_line.id] = 0
                    # TODO: adapt the following line to better handle the computation for inv. lines merged by account
                    grouped_invl_by_cvl[cv_line.id] += round(invl.price_subtotal / len(invl.cv_line_ids), 2)
                # CV IN VERSION 1
                if old_cv_version:
                    # Fetch purchase order line account
                    if inv.is_merged_by_account:
                        if not invl.account_id:
                            continue
                        # US-357: lines without product (get directly account)
                        a = invl.account_id.id
                    else:
                        pol = invl.order_line_id
                        a = self._get_expense_account(cr, uid, pol, context=context)
                        if pol.product_id and not a:
                            raise osv.except_osv(_('Error !'), _('There is no expense account defined for this product: "%s" (id:%d)') %
                                                 (pol.product_id.name, pol.product_id.id))
                        elif not a:
                            raise osv.except_osv(_('Error !'), _('There is no expense account defined for this PO line: "%s" (id:%d)') %
                                                 (pol.line_number, pol.id))
                    if a not in grouped_invl_by_acc:
                        grouped_invl_by_acc[a] = 0
                    grouped_invl_by_acc[a] += invl.price_subtotal

            po_ids = [x.id for x in inv.purchase_ids]
            self._update_commitments_lines(cr, uid, po_ids, account_amount_dic=grouped_invl_by_acc,
                                           cvl_amount_dic=grouped_invl_by_cvl, from_cancel=False, context=context)

        return True

    def _get_expense_account(self, cr, uid, pol_browse, context=None):
        assert isinstance(pol_browse, orm.browse_record)

        account_id = False
        if pol_browse.product_id:
            account_id = pol_browse.product_id.product_tmpl_id.property_account_expense.id
            if not account_id:
                account_id = pol_browse.product_id.categ_id.property_account_expense_categ.id
        else:
            account_id = self.pool.get('ir.property').get(cr, uid, 'property_account_expense_categ', 'product.category').id

        return account_id

    def _update_commitments_lines(self, cr, uid, po_ids, account_amount_dic=None, cvl_amount_dic=None, from_cancel=False, context=None):
        """
            po_ids: list of PO ids
            account_amount_dic: dict, keys are G/L account_id, values are amount to deduce


        """
        if not po_ids or not account_amount_dic and not cvl_amount_dic:
            return True

        if context is None:
            context = {}
        if account_amount_dic is None:
            account_amount_dic = {}
        if cvl_amount_dic is None:
            cvl_amount_dic = {}

        # po is state=cancel on last IN cancel
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        # avoids empty lists so that the SQL request can be executed
        account_list = account_amount_dic.keys() or [0]
        cvl_list = cvl_amount_dic.keys() or [0]
        cr.execute('''select l.id, l.account_id, l.commit_id, c.state, l.amount, l.analytic_distribution_id, c.analytic_distribution_id, 
            c.id, c.currency_id, c.type, c.version from
            account_commitment_line l, account_commitment c
            where l.commit_id = c.id and
            l.amount > 0 and
            c.purchase_id in %s and
            (c.version < 2 and l.account_id in %s or c.version >= 2 and l.id in %s) and
            c.state in ('open', 'draft')
            order by c.date asc
            ''', (tuple(po_ids), tuple(account_list), tuple(cvl_list))
        )
        # sort all cv lines by account / cv date
        account_info = {}
        cvl_info = {}
        auto_cv = True
        for cv in cr.fetchall():
            if cv[10] < 2:
                # CV IN VERSION 1
                account_info.setdefault(cv[1], []).append(cv)  # key = account id
            else:
                # CV STARTING FROM VERSION 2
                cvl_info.setdefault(cv[0], []).append(cv)  # key = CV line id
            if cv[9] == 'manual':
                auto_cv = False


        draft_opened = []
        cv_to_close = {}

        # deduce amount on oldest cv lines
        # NOTE: account_amount_dic is for CV in version 1 based on accounts (acc),
        #       cvl_amount_dic is for CV from version 2 based on CV lines (cvl)
        for c_type in ("acc", "cvl"):
            if c_type == "acc":
                cv_info = account_info.copy()
                amount_dic = account_amount_dic.copy()
            else:
                cv_info = cvl_info.copy()
                amount_dic = cvl_amount_dic.copy()
            for k in amount_dic.keys():  # account id or CV line id
                if k not in cv_info:
                    continue
                for cv_line in cv_info[k]:
                    if cv_line[3] == 'draft' and cv_line[2] not in draft_opened and not from_cancel:
                        draft_opened.append(cv_line[2])
                        # If Commitment voucher in draft state we change it to 'validated' without using workflow and
                        # engagement lines generation
                        # NB: This permits to avoid modification on commitment voucher when receiving some goods
                        self.pool.get('account.commitment').write(cr, uid, [cv_line[2]], {'state': 'open'}, context=context)
                    if cv_line[4] - amount_dic[k] > 0.001:
                        # update amount left on CV line
                        amount_left = cv_line[4] - amount_dic[k]
                        self.pool.get('account.commitment.line').write(cr, uid, [cv_line[0]], {'amount': amount_left}, context=context)
                        # update AAL
                        distrib_id = cv_line[5] or cv_line[6]
                        if not distrib_id:
                            raise osv.except_osv(_('Error'), _('No analytic distribution found.'))
                        # Browse distribution
                        distrib = self.pool.get('analytic.distribution').browse(cr, uid, [distrib_id], context=context)[0]
                        engagement_lines = distrib.analytic_lines
                        for distrib_lines in [distrib.cost_center_lines, distrib.funding_pool_lines,
                                              distrib.free_1_lines, distrib.free_2_lines]:
                            for distrib_line in distrib_lines:
                                vals = {
                                    'account_id': distrib_line.analytic_id.id,
                                    'general_account_id': cv_line[1],
                                }
                                if distrib_line._name == 'funding.pool.distribution.line':
                                    vals.update({'cost_center_id': distrib_line.cost_center_id and distrib_line.cost_center_id.id or False,})
                                # Browse engagement lines to found out matching elements
                                for i in range(0,len(engagement_lines)):
                                    if engagement_lines[i]:
                                        eng_line = engagement_lines[i]
                                        # restrict to the current CV line only
                                        if eng_line.commitment_line_id and eng_line.commitment_line_id.id != cv_line[0]:
                                            continue
                                        cmp_vals = {
                                            'account_id': eng_line.account_id.id,
                                            'general_account_id': eng_line.general_account_id.id,
                                        }
                                        if eng_line.cost_center_id:
                                            cmp_vals.update({'cost_center_id': eng_line.cost_center_id.id})
                                        if cmp_vals == vals:
                                            # Update analytic line with new amount
                                            anal_amount = (distrib_line.percentage * amount_left) / 100
                                            curr_date = currency_date.get_date(self, cr, eng_line.document_date, eng_line.date,
                                                                               source_date=eng_line.source_date)
                                            context.update({'currency_date': curr_date})
                                            amount = -1 * self.pool.get('res.currency').compute(cr, uid, cv_line[8], company_currency,
                                                                                                anal_amount, round=False, context=context)
                                            # write new amount to corresponding engagement line
                                            self.pool.get('account.analytic.line').write(cr, uid, [eng_line.id],
                                                                                         {'amount': amount,
                                                                                          'amount_currency': -1 * anal_amount}, context=context)
                        # check next G/L account or CV line
                        break
                    cv_to_close[cv_line[2]] = True
                    eng_ids = self.pool.get('account.analytic.line').search(cr, uid, [('commitment_line_id', '=', cv_line[0])], context=context)
                    if eng_ids:
                        self.pool.get('account.analytic.line').unlink(cr, uid, eng_ids, context=context)
                    self.pool.get('account.commitment.line').write(cr, uid, [cv_line[0]], {'amount': 0.0}, context=context)
                    if abs(cv_line[4] - amount_dic[k]) < 0.001:
                        # check next G/L account or CV line
                        break
                    amount_dic[k] -= cv_line[4]

        if auto_cv and from_cancel:
            # we cancel the last IN from PO and no draft invoice exist
            if not self.pool.get('account.invoice').search_exist(cr, uid, [('purchase_ids', 'in', po_ids), ('state', '=', 'draft')], context=context):
                dpo_ids = self.pool.get('purchase.order').search(cr, uid, [('id', 'in', po_ids), ('po_version', '!=', 1), ('order_type', '=', 'direct')], context=context)
                # for dpo we can have further IN if the first one is cancelled
                if dpo_ids:
                    po_ids = list(set(po_ids) - set(dpo_ids))
                    # can not use 0.001 because total is digits: (16, 2)
                    commit_ids = self.pool.get('account.commitment').search(cr, uid, [('purchase_id', 'in', dpo_ids), ('total', '<', 0.01)], context=context)
                    if commit_ids:
                        self.pool.get('account.commitment').action_commitment_done(cr, uid, commit_ids, context=context)
                if not self.pool.get('stock.move').search_exist(cr, uid, [('type', '=', 'in'), ('id', 'not in', from_cancel), ('state', 'not in', ['cancel', 'done']), ('picking_id.purchase_id', 'in', po_ids)], context=context):
                    self.pool.get('purchase.order')._finish_commitment(cr, uid, po_ids, context=context)
                    return True

        if cv_to_close:
            for cv in self.pool.get('account.commitment').read(cr, uid, cv_to_close.keys(), ['total'], context=context):
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
                    po_states = ['done']
                    if po.order_type == 'direct' and po.po_version == 1:
                        # DPO v1 specific use case: CV and SI are both created at DPO confirmation
                        # ==> close the CVs if the DPO is at least "Confirmed" and no SI is in Draft anymore
                        po_states = ['confirmed', 'confirmed_p', 'done']
                    if po.state in po_states and all(x.id in ids or x.state != 'draft' for x in po.invoice_ids):
                        self.pool.get('purchase.order')._finish_commitment(cr, uid, [po.id], context=context)

        # Process invoices
        self.update_commitments(cr, uid, to_process, context=context)
        return super(account_invoice, self).action_open_invoice(cr, uid, ids, context=context)

account_invoice()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
