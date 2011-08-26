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
from time import strftime

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
        for inv_line in self.browse(cr, uid, ids, context=context):
            if inv_line.analytics_id:
                # inv_line.analytics_id.id --> account.analytic.plan.instance
                # Search analytic plan line
                plan_ids = plan_line_obj.search(cr, uid, [('plan_id', '=', inv_line.analytics_id.id)], context=context)
                for plan in plan_line_obj.browse(cr, uid, plan_ids, context=context):
                    val = inv_line.price_subtotal # (credit or  0.0) - (debit or 0.0)
                    amt = val * (plan.rate/100)
                    al_vals = {
                        'name': inv_line.name,
                        'date': strftime('%Y-%m-%d'),
                        'account_id': plan.id,
                        'unit_amount': inv_line.quantity,
                        'product_id': inv_line.product_id and inv_line.product_id.id or False,
                        'product_uom_id': inv_line.uos_id and inv_line.uos_id.id or False,
                        'amount': amt,
                        'general_account_id': inv_line.account_id.id,
                        'journal_id': journal,
                        'source_date': strftime('%Y-%m-%d'),
                        'invoice_line_id': inv_line.id,
                    }
                    analytic_line_obj.create(cr, uid, al_vals, context=context)
        return True

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

account_invoice_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
