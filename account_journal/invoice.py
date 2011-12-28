#!/usr/bin/env python
#-*- encoding:utf-8 -*-
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
from datetime import datetime

class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    def action_cancel(self, cr, uid, ids, context={}, *args):
        """
        Delete engagement journal lines if exists
        """
        # Some verifications
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        analytic_line_obj = self.pool.get('account.analytic.line')
        # Unlink all engagement journal lines
        for inv in self.browse(cr, uid, ids, context=context):
            for invl_line in inv.invoice_line:
                if invl_line.analytic_line_ids:
                    analytic_line_obj.unlink(cr, uid, [x.id for x in invl_line.analytic_line_ids], context=context)
        res = super(account_invoice, self).action_cancel(cr, uid, ids, context, args)
        return True

    def action_cancel_draft(self, cr, uid, ids, context={}, *args):
        """
        Recreate engagement journal lines when resetting invoice to draft state
        """
        # Some verifications
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = super(account_invoice, self).action_cancel_draft(cr, uid, ids, args)
        # Recreate engagement journal lines
        for inv in self.browse(cr, uid, ids, context=context):
            self.pool.get('account.invoice.line').create_engagement_lines(cr, uid, [x.id for x in inv.invoice_line], context=context)
        return res

    def action_reverse_engagement_lines(self, cr, uid, ids, context, *args):
        """
        Reverse an engagement lines with an opposite amount
        """
        if not context:
            context = {}
        eng_obj = self.pool.get('account.analytic.line')
        # Browse invoice
        for inv in self.browse(cr, uid, ids, context=context):
            # Search engagement journal line ids
            invl_ids = [x.id for x in inv.invoice_line]
            eng_ids = eng_obj.search(cr, uid, [('invoice_line_id', 'in', invl_ids)])
            # Browse engagement journal line ids
            for eng in eng_obj.browse(cr, uid, eng_ids, context=context):
                # Create new line and change some fields:
                # - name with REV
                # - amount * -1
                # - date with invoice_date
                # Copy this line for reverse
                new_line_id = eng_obj.copy(cr, uid, eng.id, context=context)
                # Prepare reverse values
                vals = {
                    'name': eng_obj.join_without_redundancy(eng.name, 'REV'),
                    'amount': eng.amount * -1,
                    'date': inv.date_invoice,
                    'reversal_origin': eng.id,
                    'amount_currency': eng.amount_currency * -1,
                    'currency_id': eng.currency_id.id,
                }
                # Write changes
                eng_obj.write(cr, uid, [new_line_id], vals, context=context)
        return True

    def action_open_invoice(self, cr, uid, ids, context={}, *args):
        """
        Reverse engagement lines before opening invoice
        """
        res = super(account_invoice, self).action_open_invoice(cr, uid, ids, context, args)
        if not self.action_reverse_engagement_lines(cr, uid, ids, context, args):
            return False
        return res

account_invoice()

class account_invoice_line(osv.osv):
    _name = 'account.invoice.line'
    _inherit = 'account.invoice.line'

    _columns = {
        'analytic_line_ids': fields.one2many('account.analytic.line', 'invoice_line_id', string="Analytic line", 
            help="An analytic line linked with this invoice from an engagement journal (theorically)"),
    }

    def create_engagement_lines(self, cr, uid, ids, context={}):
        """
        Create engagement journal lines from given invoice lines (ids)
        """
        # Some verifications
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        analytic_line_obj = self.pool.get('account.analytic.line')
        j_obj = self.pool.get('account.analytic.journal')
        journals = j_obj.search(cr, uid, [('type', '=', 'engagement')])
        analytic_acc_obj = self.pool.get('account.analytic.account')
        plan_line_obj = self.pool.get('account.analytic.plan.instance.line')
        journal = journals and journals[0] or False
        if not journal:
            raise osv.except_osv(_('Error'), _('No engagement journal found!'))
        engagement_line_ids = []
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        for inv_line in self.browse(cr, uid, ids, context=context):
            # Don't create engagement journal line if the invoice come from a purchase list
            if inv_line.invoice_id.purchase_list or inv_line.invoice_id.state!='draft':
                continue
            # Search old engagement journal lines to be deleted (to not have split invoice problem that delete not engagement journal lines)
            analytic_line_ids = analytic_line_obj.search(cr, uid, [('invoice_line_id', '=', inv_line.id)], context=context)
            analytic_line_obj.unlink(cr, uid, analytic_line_ids, context=context)
            if inv_line.analytic_distribution_id:
                # Search distribution lines
                distrib_obj = self.pool.get('analytic.distribution').browse(cr, uid, inv_line.analytic_distribution_id.id, context=context)
                for distrib_lines in [distrib_obj.cost_center_lines, distrib_obj.funding_pool_lines, distrib_obj.free_1_lines, distrib_obj.free_2_lines]:
                    for distrib_line in distrib_lines:
                        date = inv_line.invoice_id.date_invoice
                        if not date:
                            perm = self.perm_read(cr, uid, [inv_line.id], context=context)
                            if perm and 'create_date' in perm[0]:
                                date = datetime.strptime(perm[0].get('create_date').split('.')[0], '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
                        # Prepare some values
                        invoice_currency = inv_line.invoice_id.currency_id.id
                        amount = round(distrib_line.percentage * 
                            self._amount_line(cr, uid, [inv_line.id], None, None, {})[inv_line.id]) / 100.0
                        if inv_line.invoice_id.type in ['in_invoice', 'out_refund']:
                            amount = -1 * amount
                        context.update({'date': date})
                        al_vals = {
                            'name': inv_line.name,
                            'date': date,
                            'account_id': distrib_line.analytic_id and distrib_line.analytic_id.id or False,
                            'unit_amount': inv_line.quantity,
                            'product_id': inv_line.product_id and inv_line.product_id.id or False,
                            'product_uom_id': inv_line.uos_id and inv_line.uos_id.id or False,
                            'amount': self.pool.get('res.currency').compute(cr, uid, invoice_currency, company_currency, amount or 0.0, round=False, context=context),
                            'amount_currency': amount or 0.0,
                            'currency_id': invoice_currency,
                            'general_account_id': inv_line.account_id.id,
                            'journal_id': journal,
                            'source_date': date,
                            'invoice_line_id': inv_line.id,
                        }
                        # Update values if we come from a funding pool
                        if distrib_line._name == 'funding.pool.distribution.line':
                            al_vals.update({'cost_center_id': distrib_line.cost_center_id and distrib_line.cost_center_id.id or False,})
                        res = analytic_line_obj.create(cr, uid, al_vals, context=context)
                        engagement_line_ids.append(res)
        return engagement_line_ids or False

    def create(self, cr, uid, vals, context={}):
        """
        Add engagement journal lines creation when creating a new invoice line
        """
        if not context:
            context={}
        # Default behaviour
        res = super(account_invoice_line, self).create(cr, uid, vals, context=context)
        # FIXME / TODO: Verify that this invoice line don't come from a standard donation or purchase list
        # Verify that the invoice is in draft state
        if res and vals.get('invoice_id'):
            invoice_id = vals.get('invoice_id')
            objname = self._name == 'wizard.account.invoice.line' and 'wizard.account.invoice' or 'account.invoice'
            state = self.pool.get(objname).read(cr, uid, [invoice_id], ['state'])[0].get('state', False)
            # if invoice in draft state, do engagement journal lines
            if state and state == 'draft':
                self.create_engagement_lines(cr, uid, [res], context=context)
        return res

    def write(self, cr, uid, ids, vals, context={}):
        """
        Update engagement journal lines
        """
        # Some verifications
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        analytic_line_obj = self.pool.get('account.analytic.line')
        # Write object
        res = super(account_invoice_line, self).write(cr, uid, ids, vals, context=context)
        # No update if we come from a direct invoice
        if self._name == 'wizard.account.invoice' or self._name == 'wizard.account.invoice.line':
            return res
        # Search analytic lines to remove
        to_remove = analytic_line_obj.search(cr, uid, [('invoice_line_id', 'in', ids)], context=context)
        # Search analytic line to create
        to_create = []
        for inv_line in self.browse(cr, uid, ids, context=context):
            # Don't create any line if state not draft
            if inv_line.invoice_id.state != 'draft':
                continue
            if inv_line.analytic_distribution_id:
                to_create.append(inv_line.id)
        if to_create:
            # Create new analytic lines
            self.create_engagement_lines(cr, uid, to_create, context=context)
        return res

account_invoice_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
