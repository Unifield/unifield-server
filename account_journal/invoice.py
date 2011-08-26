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

    def unlink(self, cr, uid, ids, context={}):
        """
        Delete engagement journal lines before deleting invoice
        """
        # Some verifications
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        analytic_line_obj = self.pool.get('account.analytic.line')
        # Delete engagement journal lines
        for inv in self.browse(cr, uid, ids, context=context):
            analytic_line_ids = analytic_line_obj.search(cr, uid, [('invoice_line_id', 'in', [x.id for x in inv.invoice_line])], context=context)
            analytic_line_obj.unlink(cr, uid, analytic_line_ids, context=context)
        res = super(account_invoice, self).unlink(cr, uid, ids, context=context)
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
        for inv_line in self.browse(cr, uid, ids, context=context):
            # Search old engagement journal lines to be deleted (to not have split invoice problem that delete not engagement journal lines)
            analytic_line_ids = analytic_line_obj.search(cr, uid, [('invoice_line_id', '=', inv_line.id)], context=context)
            analytic_line_obj.unlink(cr, uid, analytic_line_ids, context=context)
            if inv_line.analytics_id:
                # inv_line.analytics_id.id --> account.analytic.plan.instance
                # Search analytic plan line
                plan_ids = plan_line_obj.search(cr, uid, [('plan_id', '=', inv_line.analytics_id.id)], context=context)
                for plan in plan_line_obj.browse(cr, uid, plan_ids, context=context):
                    val = inv_line.price_subtotal # (credit or  0.0) - (debit or 0.0)
                    amt = val * (plan.rate/100)
                    date = inv_line.invoice_id.date_invoice
                    if not date:
                        perm = self.perm_read(cr, uid, [inv_line.id], context=context)
                        if perm and 'create_date' in perm[0]:
                            date = datetime.strptime(perm[0].get('create_date').split('.')[0], '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
                    al_vals = {
                        'name': inv_line.name,
                        'date': date,
                        'account_id': plan.id,
                        'unit_amount': inv_line.quantity,
                        'product_id': inv_line.product_id and inv_line.product_id.id or False,
                        'product_uom_id': inv_line.uos_id and inv_line.uos_id.id or False,
                        'amount': amt,
                        'general_account_id': inv_line.account_id.id,
                        'journal_id': journal,
                        'source_date': date,
                        'invoice_line_id': inv_line.id,
                    }
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
        if res and 'invoice_id' in vals:
            invoice_id = vals.get('invoice_id')
            state = self.pool.get('account.invoice').read(cr, uid, [invoice_id], ['state'])[0].get('state', False)
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
        # Search analytic lines to remove
        to_remove = analytic_line_obj.search(cr, uid, [('invoice_line_id', 'in', ids)], context=context)
        # Search analytic line to create
        to_create = []
        for inv_line in self.pool.get('account.invoice.line').browse(cr, uid, ids, context=context):
            # Don't create any line if state not draft
            if inv_line.invoice_id.state != 'draft':
                continue
            if inv_line.analytics_id:
                to_create.append(inv_line.id)
        if to_create:
            # Delete existing anaytic lines
            analytic_line_obj.unlink(cr, uid, to_remove, context=context)
            # Create new analytic lines
            self.create_engagement_lines(cr, uid, to_create, context=context)
        return res

    def unlink(self, cr, uid, ids, context={}):
        """
        Delete engagement journal lines before deleting invoice line
        """
        # Some verifications
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        analytic_line_obj = self.pool.get('account.analytic.line')
        # Delete engagement journal lines
        for inv_line in self.browse(cr, uid, ids, context=context):
            analytic_line_ids = analytic_line_obj.search(cr, uid, [('invoice_line_id', 'in', ids)], context=context)
            analytic_line_obj.unlink(cr, uid, analytic_line_ids, context=context)
        res = super(account_invoice_line, self).unlink(cr, uid, ids, context=context)
        return res

account_invoice_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
