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
from time import strftime
import decimal_precision as dp

class account_commitment(osv.osv):
    _name = 'account.commitment'
    _description = "Account Commitment Voucher"
    _order = "id desc"

    def _get_total(self, cr, uid, ids, name, args, context={}):
        """
        Give total of given commitments
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        # Browse commitments
        for co in self.browse(cr, uid, ids, context=context):
            res[co.id] = 0.0
            for line in co.line_ids:
                res[co.id] += line.amount
        return res

    def _get_distribution_line_count(self, cr, uid, ids, name, args, context={}):
        """
        Return analytic distribution line count (given by analytic distribution)
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        # Browse given invoices
        for co in self.browse(cr, uid, ids, context=context):
            res[co.id] = co.analytic_distribution_id and co.analytic_distribution_id.lines_count or 'None'
        return res

    _columns = {
        'journal_id': fields.many2one('account.journal', string="Journal", readonly=True, required=True),
        'name': fields.char(string="Number", size=64),
        'currency_id': fields.many2one('res.currency', string="Currency", readonly=True, required=True),
        'partner_id': fields.many2one('res.partner', string="Supplier", readonly=True, required=True),
        'period_id': fields.many2one('account.period', string="Period", readonly=True),
        'ref': fields.char(string='Reference', size=64, readonly=True),
        'state': fields.selection([('draft', 'Draft'), ('open', 'Open'), ('done', 'Closed')], readonly=True, string="State", required=True),
        'date': fields.date(string="Commitment Date", readonly=True, required=True, states={'draft': [('readonly', False)], 'open': [('readonly', False)]}),
        'line_ids': fields.one2many('account.commitment.line', 'commit_id', string="Commitment Voucher Lines"),
        'total': fields.function(_get_total, type='float', method=True, digits_compute=dp.get_precision('Account'), readonly=True, string="Total"),
        'analytic_distribution_id': fields.many2one('analytic.distribution', string="Analytic distribution"),
        'analytic_distribution_line_count': fields.function(_get_distribution_line_count, method=True, type='char', size=256,
            string="Analytic distribution count", readonly=True, store=False),
        'type': fields.selection([('manual', 'Manual'), ('auto_ext', 'From external supplier'), ('auto_esc', 'From Esc supplier')], string="Type", readonly=True),
    }

    _defaults = {
        'name': '/',
        'state': lambda *a: 'draft',
        'date': lambda *a: strftime('%Y-%m-%d'),
        'type': lambda *a: 'manual',
    }

    def button_analytic_distribution(self, cr, uid, ids, context={}):
        """
        Launch analytic distribution wizard on a commitment
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        commitment = self.browse(cr, uid, ids[0], context=context)
        amount = commitment.total or 0.0
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = commitment.currency_id and commitment.currency_id.id or company_currency
        # Get analytic_distribution_id
        distrib_id = commitment.analytic_distribution_id and commitment.analytic_distribution_id.id
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'commitment_id': commitment.id,
            'currency_id': currency or False,
            'state': 'dispatch',
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
                'type': 'ir.actions.act_window',
                'res_model': 'analytic.distribution.wizard',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [wiz_id],
                'context': context,
        }

account_commitment()

class account_commitment_line(osv.osv):
    _name = 'account.commitment.line'
    _description = "Account Commitment Voucher Line"
    _order = "id desc"

    def _get_distribution_state(self, cr, uid, ids, name, args, context={}):
        """
        Get state of distribution:
         - if compatible with the commitment voucher line, then "valid"
         - if no distribution, take a tour of commitment voucher distribution, if compatible, then "valid"
         - if no distribution on commitment voucher line and commitment voucher, then "none"
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
        for line in self.browse(cr, uid, ids, context=context):
            # Default value is invalid
            res[line.id] = 'invalid'
            # Search MSF Private Fund element, because it's valid with all accounts
            try:
                fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 
                'analytic_account_msf_private_funds')[1]
            except ValueError:
                fp_id = 0
            # Verify that the distribution is compatible with line account
            if line.analytic_distribution_id:
                total = 0.0
                for fp_line in line.analytic_distribution_id.funding_pool_lines:
                    # If fp_line is MSF Private Fund, all is ok
                    if fp_line.analytic_id.id == fp_id:
                        total += 1
                        continue
                    # If account don't be on ONLY ONE funding_pool, then continue
                    if line.account_id.id not in [x.id for x in fp_line.analytic_id.account_ids]:
                        continue
                    else:
                        total += 1
                if total and total == len(line.analytic_distribution_id.funding_pool_lines):
                    res[line.id] = 'valid'
            # If no analytic_distribution on commitment voucher line, check with commitment voucher distribution
            elif line.commit_id.analytic_distribution_id:
                total = 0.0
                for fp_line in line.commit_id.analytic_distribution_id.funding_pool_lines:
                    # If fp_line is MSF Private Fund, all is ok
                    if fp_line.analytic_id.id == fp_id:
                        total += 1
                        continue
                    # If account don't be on ONLY ONE funding_pool, then continue
                    if line.account_id.id not in [x.id for x in fp_line.analytic_id.account_ids]:
                        continue
                    else:
                        total += 1
                if total and total == len(line.commit_id.analytic_distribution_id.funding_pool_lines):
                    res[line.id] = 'valid'
            # If no analytic distribution on commitment voucher line, but come from a yaml test, then set to 'valid'
            elif line.from_yml_test:
                res[line.id] = 'valid'
            # If no analytic distribution on commitment voucher line and on commitment voucher, then give 'none' state
            else:
                # no analytic distribution on commitment voucher line or commitment voucher => 'none'
                res[line.id] = 'none'
        return res

    def _get_distribution_line_count(self, cr, uid, ids, name, args, context={}):
        """
        Return analytic distribution line count (given by analytic distribution)
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        # Browse given invoices
        for col in self.browse(cr, uid, ids, context=context):
            res[col.id] = col.analytic_distribution_id and col.analytic_distribution_id.lines_count or ''
        return res

    def _have_analytic_distribution_from_header(self, cr, uid, ids, name, arg, context={}):
        """
        If Commitment have an analytic distribution, return False, else return True
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for co in self.browse(cr, uid, ids, context=context):
            res[co.id] = True
            if co.analytic_distribution_id:
                res[co.id] = False
        return res

    _columns = {
        'account_id': fields.many2one('account.account', string="Account"),
        'amount': fields.float(string="Amount", digits_compute=dp.get_precision('Account')),
        'commit_id': fields.many2one('account.commitment', string="Commitment Voucher"),
        'analytic_distribution_id': fields.many2one('analytic.distribution', string="Analytic distribution"),
        'analytic_distribution_line_count': fields.function(_get_distribution_line_count, method=True, type='char', size=256,
            string="Analytic distribution count", readonly=True, store=False),
        'analytic_distribution_state': fields.function(_get_distribution_state, method=True, type='selection', 
            selection=[('none', 'None'), ('valid', 'Valid'), ('invalid', 'Invalid')], 
            string="Distribution state", help="Informs from distribution state among 'none', 'valid', 'invalid."),
        'have_analytic_distribution_from_header': fields.function(_have_analytic_distribution_from_header, method=True, type='boolean', 
            string='Header Distrib.?'),
        'from_yml_test': fields.boolean('Only used to pass addons unit test', readonly=True, help='Never set this field to true !'),
    }

    _defaults = {
        'amount': lambda *a: 0.0,
        'from_yml_test': lambda *a: False,
    }

    def button_analytic_distribution(self, cr, uid, ids, context={}):
        """
        Launch analytic distribution wizard on a commitment voucher line
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not ids:
            raise osv.except_osv(_('Error'), _('No invoice line given. Please save your commitment voucher line before.'))
        # Prepare some values
        commitment_voucher_line = self.browse(cr, uid, ids[0], context=context)
        distrib_id = False
        amount = commitment_voucher_line.amount or 0.0
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = commitment_voucher_line.commit_id.currency_id and commitment_voucher_line.commit_id.currency_id.id or company_currency
        # Get analytic distribution id from this line
        distrib_id = commitment_voucher_line and commitment_voucher_line.analytic_distribution_id and commitment_voucher_line.analytic_distribution_id.id or False
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'commitment_line_id': commitment_voucher_line.id,
            'currency_id': currency or False,
            'state': 'dispatch',
            'account_id': commitment_voucher_line.account_id and commitment_voucher_line.account_id.id or False,
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
                'type': 'ir.actions.act_window',
                'res_model': 'analytic.distribution.wizard',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [wiz_id],
                'context': context,
        }

account_commitment_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
