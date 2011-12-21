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
from account_tools import get_period_from_date

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
        'journal_id': fields.many2one('account.analytic.journal', string="Journal", readonly=True, required=True),
        'name': fields.char(string="Number", size=64, readonly=True, required=True),
        'currency_id': fields.many2one('res.currency', string="Currency", readonly=True, required=True),
        'partner_id': fields.many2one('res.partner', string="Supplier", readonly=True, required=True),
        'period_id': fields.many2one('account.period', string="Period", readonly=True, required=True),
        'state': fields.selection([('draft', 'Draft'), ('open', 'Validated'), ('done', 'Done')], readonly=True, string="State", required=True),
        'date': fields.date(string="Commitment Date", readonly=True, required=True, states={'draft': [('readonly', False)], 'open': [('readonly', False)]}),
        'line_ids': fields.one2many('account.commitment.line', 'commit_id', string="Commitment Voucher Lines"),
        'total': fields.function(_get_total, type='float', method=True, digits_compute=dp.get_precision('Account'), readonly=True, string="Total"),
        'analytic_distribution_id': fields.many2one('analytic.distribution', string="Analytic distribution"),
        'analytic_distribution_line_count': fields.function(_get_distribution_line_count, method=True, type='char', size=256,
            string="Analytic distribution count", readonly=True, store=False),
        'type': fields.selection([('manual', 'Manual'), ('external', 'From external supplier'), ('esc', 'From Esc supplier')], string="Type", readonly=True),
        'from_yml_test': fields.boolean('Only used to pass addons unit test', readonly=True, help='Never set this field to true !'),
    }

    _defaults = {
        'name': lambda s, cr, uid, c: s.pool.get('ir.sequence').get(cr, uid, 'account.commitment'),
        'state': lambda *a: 'draft',
        'date': lambda *a: strftime('%Y-%m-%d'),
        'type': lambda *a: 'manual',
        'from_yml_test': lambda *a: False,
        'journal_id': lambda s, cr, uid, c: s.pool.get('account.analytic.journal').search(cr, uid, [('type', '=', 'engagement')], limit=1, context=c)[0]
    }

    def create(self, cr, uid, vals, context={}):
        """
        Update period_id regarding date.
        """
        # Some verifications
        if not context:
            context = {}
        if not 'period_id' in vals:
            period_ids = get_period_from_date(self, cr, uid, vals.get('date', strftime('%Y-%m-%d')), context=context)
            vals.update({'period_id': period_ids and period_ids[0]})
        return super(account_commitment, self).create(cr, uid, vals, context=context)

    def copy(self, cr, uid, id, default={}, context={}):
        """
        Copy analytic_distribution
        """
        # Some verifications
        if not context:
            context = {}
        # Update default values
        default.update({
            'name': self.pool.get('ir.sequence').get(cr, uid, 'account.commitment'),
            'state': 'draft',
        })
        # Default method
        res = super(account_commitment, self).copy(cr, uid, id, default, context)
        # Update analytic distribution
        if res:
            c = self.browse(cr, uid, res, context=context)
        if res and c.analytic_distribution_id:
            new_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, c.analytic_distribution_id.id, {}, context=context)
            if new_distrib_id:
                self.write(cr, uid, [res], {'analytic_distribution_id': new_distrib_id}, context=context)
        return res

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

    def button_compute(self, cr, uid, ids, context={}):
        """
        Compute commitment voucher total.
        """
        # trick to refresh view and update total amount
        return self.write(cr, uid, ids, [], context=context)

    def onchange_date(self, cr, uid, ids, date, period_id=False, context={}):
        """
        Update period regarding given date
        """
        # Some verifications
        if not context:
            context = {}
        if not date:
            return False
        # Prepare some values
        vals = {}
        periods = get_period_from_date(self, cr, uid, date, context=context)
        if periods:
            vals['period_id'] = periods[0]
        return {'value': vals}

    def create_analytic_lines(self, cr, uid, ids, context={}):
        """
        Create analytic line for given commitment voucher.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Browse commitments
        for c in self.browse(cr, uid, ids, context=context):
            for cl in c.line_ids:
                # Continue if we come from yaml tests
                if c.from_yml_test or cl.from_yml_test:
                    continue
                # Verify that analytic distribution is present
                if cl.analytic_distribution_state != 'valid':
                    raise osv.except_osv(_('Error'), _('Analytic distribution is not valid for account "%s %s".' % 
                        (cl.account_id and cl.account_id.code, cl.account_id and cl.account_id.name)))
                # Take analytic distribution either from line or from commitment voucher
                distrib_id = cl.analytic_distribution_id and cl.analytic_distribution_id.id or c.analytic_distribution_id and c.analytic_distribution_id.id or False
                if not distrib_id:
                    raise osv.except_osv(_('Error'), _('No analytic distribution found!'))
                # Search if analytic lines exists for this commitment voucher line
                al_ids = self.pool.get('account.analytic.line').search(cr, uid, [('commitment_line_id', '=', cl.id)], context=context)
                if not al_ids:
                    # Create engagement journal lines
                    self.pool.get('analytic.distribution').create_analytic_lines(cr, uid, [distrib_id], 'Commitment voucher line', c.date, 
                        cl.amount, c.journal_id and c.journal_id.id, c.currency_id and c.currency_id.id, c.purchase_id and c.purchase_id.name or False, 
                        c.date, cl.account_id and cl.account_id.id or False, False, False, cl.id, context=context)
        return True

    def action_commitment_open(self, cr, uid, ids, context={}):
        """
        To do when we validate a commitment.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Browse commitments and create analytic lines
        self.create_analytic_lines(cr, uid, ids, context=context)
        # Validate commitment voucher
        return self.write(cr, uid, ids, {'state': 'open'}, context=context)

    def action_commitment_done(self, cr, uid, ids, context={}):
        """
        To do when a commitment is done.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Browse commitments
        for c in self.browse(cr, uid, ids, context=context):
            # Search analytic lines that have commitment line ids
            search_ids = self.pool.get('account.analytic.line').search(cr, uid, [('commitment_line_id', 'in', [x.id for x in c.line_ids])], context=context)
            # Delete them
            res = self.pool.get('account.analytic.line').unlink(cr,  uid, search_ids, context=context)
            # And finally update commitment voucher state and lines amount
            if res:
                self.pool.get('account.commitment.line').write(cr, uid, [x.id for x in c.line_ids], {'amount': 0}, context=context)
                self.write(cr, uid, [c.id], {'state':'done'}, context=context)
        return True

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
            if line.from_yml_test:
                res[line.id] = 'valid'
            else:
                res[line.id] = self.pool.get('analytic.distribution')._get_distribution_state(cr, uid, line.analytic_distribution_id.id, line.commit_id.analytic_distribution_id.id, line.account_id.id) 
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
        'account_id': fields.many2one('account.account', string="Account", required=True),
        'amount': fields.float(string="Amount left", digits_compute=dp.get_precision('Account'), required=True),
        'initial_amount': fields.float(string="Initial amount", digits_compute=dp.get_precision('Account'), required=False, readonly=True),
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
        'analytic_lines': fields.one2many('account.analytic.line', 'commitment_line_id', string="Analytic Lines"),
    }

    _defaults = {
        'initial_amount': lambda *a: 0.0,
        'amount': lambda *a: 0.0,
        'from_yml_test': lambda *a: False,
    }

    def update_analytic_lines(self, cr, uid, ids, amount, account_id=False, context={}):
        """
        Update analytic lines from given commitment lines with an ugly method: delete all analytic lines and recreate them…
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        for cl in self.browse(cr, uid, ids, context=context):
            # Browse distribution
            distrib_id = cl.analytic_distribution_id and cl.analytic_distribution_id.id or False
            if not distrib_id:
                distrib_id = cl.commit_id and cl.commit_id.analytic_distribution_id and cl.commit_id.analytic_distribution_id.id or False
            if distrib_id:
                analytic_line_ids = self.pool.get('account.analytic.line').search(cr, uid, [('commitment_line_id', '=', cl.id)], context=context)
                self.pool.get('account.analytic.line').unlink(cr, uid, analytic_line_ids, context=context)
                ref = cl.commit_id and cl.commit_id.purchase_id and cl.commit_id.purchase_id.name or ''
                self.pool.get('analytic.distribution').create_analytic_lines(cr, uid, [distrib_id], 'Commitment voucher line', cl.commit_id.date, amount, 
                    cl.commit_id.journal_id.id, cl.commit_id.currency_id.id, ref, cl.commit_id.date, account_id or cl.account_id.id, move_id=False, invoice_line_id=False, 
                    commitment_line_id=cl.id, context=context)
        return True

    def create(self, cr, uid, vals, context={}):
        """
        Verify that given account_id (in vals) is not 'view'.
        Update initial amount with those given by 'amount' field.
        Verify amount sign.
        """
        # Some verifications
        if not context:
            context = {}
        if 'account_id' in vals:
            account_id = vals.get('account_id')
            account = self.pool.get('account.account').browse(cr, uid, [account_id], context=context)[0]
            if account.type in ['view']:
                raise osv.except_osv(_('Error'), _("You cannot create a commitment voucher line on a 'view' account type!"))
        # Update initial amount
        if not vals.get('initial_amount', 0.0) and vals.get('amount', 0.0):
            vals.update({'initial_amount': vals.get('amount')})
        # Verify amount validity
        if 'amount' in vals and vals.get('amount', 0.0) < 0.0:
            raise osv.except_osv(_('Warning'), _('Amount should be superior to 0!'))
        res = super(account_commitment_line, self).create(cr, uid, vals, context={})
        if res:
            for cl in self.browse(cr, uid, [res], context=context):
                if 'amount' in vals and cl.commit_id and cl.commit_id.state and cl.commit_id.state == 'open':
                    self.update_analytic_lines(cr, uid, [cl.id], vals.get('amount'), context=context)
        return res

    def write(self, cr, uid, ids, vals, context={}):
        """
        Verify that given account_id is not 'view'.
        Update initial_amount if amount in vals and type is 'manual' and state is 'draft'.
        Update analytic distribution if amount in vals.
        Verify amount sign.
        """
        # Some verifications
        if not context:
            context = {}
        if 'account_id' in vals:
            account_id = vals.get('account_id')
            account = self.pool.get('account.account').browse(cr, uid, [account_id], context=context)[0]
            if account.type in ['view']:
                raise osv.except_osv(_('Error'), _("You cannot write a commitment voucher line on a 'view' account type!"))
        # Verify amount validity
        if 'amount' in vals and vals.get('amount', 0.0) < 0.0:
            raise osv.except_osv(_('Warning'), _('Amount should be superior to 0!'))
        # Update analytic distribution if needed and initial_amount
        for line in self.browse(cr, uid, ids, context=context):
            # verify analytic distribution only on 'open' commitments
            if line.commit_id and line.commit_id.state and line.commit_id.state == 'open':
                # Search distribution
                distrib_id = line.analytic_distribution_id and line.analytic_distribution_id.id or False
                if not distrib_id:
                    distrib_id = line.commit_id.analytic_distribution_id and line.commit_id.analytic_distribution_id.id or False
                # Verify amount
                if 'amount' in vals and vals.get('amount', 0.0) == '0.0':
                    # delete analytic lines that are null
                    if distrib_id:
                        distrib = self.pool.get('analytic.distribution').browse(cr, uid, [distrib_id], context=context)[0]
                        if distrib and distrib.analytic_lines:
                            self.pool.get('account.analytic.line').unlink(cr, uid, [x.id for x in distrib.analytic_lines], context=context)
                elif 'amount' in vals:
                    # Verify expense account
                    account_id = False
                    if 'account_id' in vals and vals.get('account_id', False) and line.account_id.id != vals.get('account_id'):
                        account_id = vals.get('account_id')
                    # Update analytic lines
                    if distrib_id:
                        self.update_analytic_lines(cr, uid, [line.id], vals.get('amount'), account_id, context=context)
            elif line.commit_id and line.commit_id.state and line.commit_id.state == 'draft' and vals.get('amount', 0.0):
                vals.update({'initial_amount': vals.get('amount')})
        return super(account_commitment_line, self).write(cr, uid, ids, vals, context={})

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
