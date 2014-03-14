#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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

class account_bank_statement_line(osv.osv):
    _inherit = "account.bank.statement.line"
    _name = "account.bank.statement.line"

    def _display_analytic_button(self, cr, uid, ids, name, args, context=None):
        """
        Return True for all element that correspond to some criteria:
         - The entry state is draft
         - The account is analytic-a-holic
        """
        res = {}
        for absl in self.browse(cr, uid, ids, context=context):
            res[absl.id] = True
            # False if st_line is hard posted
            if absl.state == 'hard':
                res[absl.id] = False
            # False if account not allocatable
            if not absl.account_id.is_analytic_addicted:
                res[absl.id] = False
        return res

    def _get_distribution_state(self, cr, uid, ids, name, args, context=None):
        """
        Get state of distribution:
         - if compatible with the line, then "valid"
         - if no distribution, then "none"
         - all other case are "invalid"
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        # Browse all given lines
        for line in self.read(cr, uid, ids, ['analytic_distribution_id', 'account_id'], context=context):
            if not line.get('analytic_distribution_id', False):
                res[line.get('id')] = 'none'
                continue
            distribution_id = line.get('analytic_distribution_id')[0]
            account_id = line.get('account_id', [False])[0]
            res[line.get('id')] = self.pool.get('analytic.distribution')._get_distribution_state(cr, uid, distribution_id, False, account_id)
        return res

    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
        'display_analytic_button': fields.function(_display_analytic_button, method=True, string='Display analytic button?', type='boolean', readonly=True,
            help="This informs system that we can display or not an analytic button", store=False),
        'analytic_distribution_state': fields.function(_get_distribution_state, method=True, type='selection',
            selection=[('none', 'None'), ('valid', 'Valid'), ('invalid', 'Invalid')],
            string="Distribution state", help="Informs from distribution state among 'none', 'valid', 'invalid."),
    }

    _defaults = {
        'display_analytic_button': lambda *a: True,
    }

    def button_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Launch analytic distribution wizard from a statement line
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        absl = self.browse(cr, uid, ids[0], context=context)
        amount = absl.amount * -1 or 0.0
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = absl.statement_id.journal_id.currency and absl.statement_id.journal_id.currency.id or company_currency
        # Get analytic distribution id from this line
        distrib_id = absl.analytic_distribution_id and absl.analytic_distribution_id.id or False
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'register_line_id': absl.id,
            'currency_id': currency or False,
            'state': 'dispatch',
            'account_id': absl.account_id and absl.account_id.id or False,
            'posting_date': absl.date,
            'document_date': absl.document_date,
        }
        if distrib_id:
            vals.update({'distribution_id': distrib_id,})
        # Create the wizard
        wiz_obj = self.pool.get('analytic.distribution.wizard')
        wiz_id = wiz_obj.create(cr, uid, vals, context=context)
        # Update some context values
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        # Open it!
        return {
                'name': 'Analytic distribution',
                'type': 'ir.actions.act_window',
                'res_model': 'analytic.distribution.wizard',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [wiz_id],
                'context': context,
        }

account_bank_statement_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
