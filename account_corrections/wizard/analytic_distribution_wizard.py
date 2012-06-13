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
import time
from collections import defaultdict
from tools.misc import flatten

class analytic_distribution_wizard(osv.osv_memory):
    _inherit = 'analytic.distribution.wizard'

    _columns = {
        'date': fields.date(string="Date", help="This date is taken from analytic distribution corrections"),
        'state': fields.selection([('draft', 'Draft'), ('cc', 'Cost Center only'), ('dispatch', 'All other elements'), ('done', 'Done'), 
            ('correction', 'Correction')], string="State", required=True, readonly=True),
        'old_account_id': fields.many2one('account.account', "New account given by correction wizard", readonly=True),
    }

    _defaults = {
        'state': lambda *a: 'draft',
        'date': lambda *a: time.strftime('%Y-%m-%d'),
    }

    def _check_lines(self, cr, uid, distribution_line_id, wiz_line_id, type):
        """
        Check components compatibility
        """
        # Prepare some values
        wiz_line_types = {'cost.center': '', 'funding.pool': 'fp', 'free.1': 'f1', 'free.2': 'f2',}
        obj = '.'.join([type, 'distribution', 'line'])
        oline = self.pool.get(obj).browse(cr, uid, distribution_line_id)
        nline_type = '.'.join([wiz_line_types.get(type), 'lines'])
        nline_obj = '.'.join(['analytic.distribution.wizard', nline_type])
        nline = self.pool.get(nline_obj).browse(cr, uid, wiz_line_id)
        to_reverse = []
        to_override = defaultdict(list)
        period = nline.wizard_id and nline.wizard_id.move_line_id and nline.wizard_id.move_line_id.period_id or False
        if not period:
            raise osv.except_osv(_('Error'), _('No attached period to the correction wizard. Do you come from a correction wizard attached to a journal item?'))
        # Some cases
        if type == 'funding.pool':
            old_component = [oline.destination_id.id, oline.analytic_id.id, oline.cost_center_id.id, oline.percentage]
            new_component = [nline.destination_id.id, nline.analytic_id.id, nline.cost_center_id.id, nline.percentage]
            if old_component != new_component:
                # Don't do anything if the old FP account is on a soft/hard closed contract!
                if oline.analytic_id.id != nline.analytic_id.id:
                    check_fp = self.pool.get('account.analytic.account').is_blocked_by_a_contract(cr, uid, [oline.analytic_id.id])
                    if check_fp and oline.analytic_id.id in check_fp:
                        return False, _("Old funding pool is on a soft/hard closed contract: %s") % (oline.analytic_id.code,), to_reverse, to_override
                    to_override[oline.id].append(('account_id', nline.analytic_id.id))
                # Override CC on open period, otherwise reverse line
                if oline.cost_center_id.id != nline.cost_center_id.id:
                    # if period is open, do an override, except if FP needs to reverse the line
                    if period.state != 'done' and oline.id not in to_reverse:
                        to_override[oline.id].append(('cost_center_id', nline.cost_center_id.id))
                    elif period.state == 'done':
                        to_reverse.append(oline.id)
                # Only reverse line if destination have changed
                if oline.destination_id.id != nline.destination_id.id:
                    if period.state != 'done' and oline.id not in to_reverse:
                        to_override[oline.id].append(('destination_id', nline.destination_id.id))
                    elif period.state == 'done':
                        to_reverse.append(oline.id)
                # Override line if percentage have changed
                if oline.percentage != nline.percentage and oline.id not in to_reverse:
                    to_override[oline.id].append(('percentage', nline.percentage))
                # Check that if old_component and new_component have changed we should find oline.id in to_reverse OR to_override
                if oline.id not in to_override and oline.id not in to_reverse:
                    raise osv.except_osv(_('Error'), _('Code error: A case have not been taken.'))
        else:
            old_component = [oline.analytic_id.id, oline.percentage]
            new_component = [nline.analytic_id.id, nline.percentage]
            if old_component != new_component:
                field_name = ''
                value = None
                if oline.analytic_id.id != nline.analytic_id.id:
                    field_name = 'account_id'
                    value = nline.analytic_id.id
                if oline.percentage != nline.percentage:
                    field_name = 'percentage'
                    value = nline.percentage
                if not value:
                    raise osv.except_osv(_('Error'), _('A value is missing.'))
                to_override[oline.id].append((field_name, value))
        # Delete lines that are in override if they are in to_reverse
        if oline.id in to_override and oline.id in to_reverse:
            del to_override[oline.id]
        return True, _("All is OK."), to_reverse, to_override

    def do_analytic_distribution_changes(self, cr, uid, wizard_id, distrib_id):
        """
        For each given wizard compare old (distrib_id) and new analytic distribution. Then adapt analytic lines.
        """
        # Prepare some values
        wiz_line_types = {'cost.center': '', 'funding.pool': 'fp', 'free.1': 'f1', 'free.2': 'f2',}
        wizard = self.browse(cr, uid, wizard_id)
        to_update  = [] # NEEDED for analytic lines to be updated with new analytic distribution after its creation
        # Fetch funding pool lines, free 1 lines and free 2 lines
        for line_type in ['funding.pool', 'free.1', 'free.2']:
            # Prepare some values
            line_obj = '.'.join([line_type, 'distribution', 'line'])
            company_currency_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id
            current_date = time.strftime('%Y-%m-%d')
            ml = wizard.move_line_id
            ml_id = ml.id
            # Search old line and new lines
            old_line_ids = self.pool.get(line_obj).search(cr, uid, [('distribution_id', '=', distrib_id)])
            wiz_line_type = '.'.join([wiz_line_types.get(line_type), 'lines'])
            wiz_line_obj = '.'.join(['analytic.distribution.wizard', wiz_line_type])
            wiz_line_ids = self.pool.get(wiz_line_obj).search(cr, uid, [('wizard_id', '=', wizard_id), ('type', '=', line_type)])
            # Compare database lines with wizard lines
            old_line_checked = []
            for wiz_line in self.pool.get(wiz_line_obj).browse(cr, uid, wiz_line_ids):
                if wiz_line.distribution_line_id.id not in old_line_ids:
                    amount = (ml.debit_currency - ml.credit_currency) * wiz_line.percentage / 100
                    context = {'date': current_date}
                    func_amount = self.pool.get('res.currency').compute(cr, uid, ml.currency_id.id, company_currency_id, amount, round=False, context=context)
                    # Create new lines
                    vals = {
                        'account_id': wiz_line.analytic_id and wiz_line.analytic_id.id or False,
                        'amount_currency': amount or 0.0,
                        'general_account_id': ml.account_id and ml.account_id.id or False,
                        'source_date': current_date,
                        'date': current_date,
                        'move_id': ml_id,
                        'name': ml.name,
                        'journal_id': ml.journal_id and ml.journal_id.analytic_journal_id and ml.journal_id.analytic_journal_id.id or False,
                        'currency_id': ml.currency_id and ml.currency_id.id or False,
                        'amount': func_amount,
                    }
                    if line_type == 'funding.pool':
                        vals.update({
                            'cost_center_id': wiz_line.cost_center_id and wiz_line.cost_center_id.id or False,
                            'destination_id': wiz_line.destination_id and wiz_line.destination_id.id or False,
                        })
                    self.pool.get('account.analytic.line').create(cr, uid, vals)
                    continue
                # compare components (Destination | CC | FP | percentage)
                res_cmp, msg, to_reverse, to_override = self._check_lines(cr, uid, wiz_line.distribution_line_id.id, wiz_line.id, line_type)
                old_line_checked.append(wiz_line.distribution_line_id.id)
                if not res_cmp:
                    raise osv.except_osv(_('Warning'), msg)
                # Override process
                if to_override:
                    for old_line_id in to_override:
                        distrib_line = self.pool.get(line_obj).browse(cr, uid, old_line_id)
                        amount = (ml.debit_currency - ml.credit_currency) * distrib_line.percentage / 100
                        # search analytic lines
                        args = [
                            ('move_id', '=', ml_id),
                            ('distribution_id', '=', distrib_line.distribution_id.id),
                            ('account_id', '=', distrib_line.analytic_id.id),
                            ('amount_currency', '=', -1 * amount),
                        ]
                        if line_type == "funding.pool":
                            args.append(('cost_center_id', '=', distrib_line.cost_center_id.id))
                            args.append(('destination_id', '=', distrib_line.destination_id.id))
                        too_ana_ids = self.pool.get('account.analytic.line').search(cr, uid, args)
                        if too_ana_ids:
                            to_update.append(too_ana_ids)
                        # fetch all modifications
                        vals = {}
                        for couple in to_override[old_line_id]:
                            # Compute all lines amount
                            if couple[0] == 'percentage':
                                for ana_line in self.pool.get('account.analytic.line').browse(cr, uid, too_ana_ids):
                                    context = {'date': ana_line.source_date or ana_line.date}
                                    func_amount = self.pool.get('res.currency').compute(cr, uid, ana_line.currency_id.id, company_currency_id, amount, round=False, context=context)
                                    new_amount = (ml.debit_currency - ml.credit_currency) * wiz_line.percentage / 100
                                    self.pool.get('account.analytic.line').write(cr, uid, too_ana_ids, {'amount_currency': new_amount, 'amount': func_amount,})
                            else:
                                vals.update({couple[0]: couple[1]})
                        # Write changes
                        self.pool.get('account.analytic.line').write(cr, uid, too_ana_ids, vals)
                # Reverse process
                if to_reverse:
                    for rev in to_reverse:
                        distrib_line = self.pool.get(line_obj).browse(cr, uid, rev)
                        amount = (ml.debit_currency - ml.credit_currency) * distrib_line.percentage / 100
                        # Search lines
                        args = [
                            ('move_id', '=', ml_id),
                            ('distribution_id', '=', distrib_line.distribution_id.id),
                            ('account_id', '=', distrib_line.analytic_id.id),
                            ('amount_currency', '=', -1 * amount),
                        ]
                        if line_type == 'funding.pool':
                            args.append(('cost_center_id', '=', distrib_line.cost_center_id.id))
                            args.append(('destination_id', '=', distrib_line.destination_id.id))
                        tor_ana_ids = self.pool.get('account.analytic.line').search(cr, uid, args)
                        # Reverse lines
                        self.pool.get('account.analytic.line').reverse(cr, uid, tor_ana_ids)
                        # Mark old lines as non reallocatable (ana_ids)
                        self.pool.get('account.analytic.line').write(cr, uid, tor_ana_ids, {'is_reallocated': True,})
                        # Write new lines
                        for ana_line in self.pool.get('account.analytic.line').browse(cr, uid, tor_ana_ids):
                            context = {'date': ana_line.source_date or ana_line.date}
                            func_amount = self.pool.get('res.currency').compute(cr, uid, ana_line.currency_id.id, company_currency_id, amount, round=False, context=context)
                            # Create new lines
                            vals = {
                                'account_id': wiz_line.analytic_id and wiz_line.analytic_id.id or False,
                                'amount_currency': amount or 0.0,
                                'general_account_id': ml.account_id and ml.account_id.id or False,
                                'source_date': ana_line.source_date or ana_line.date,
                                'date': time.strftime('%Y-%m-%d'),
                                'move_id': ml_id,
                                'name': ana_line.name,
                                'journal_id': ana_line.journal_id and ana_line.journal_id.id or False,
                                'currency_id': ana_line.currency_id and ana_line.currency_id.id or False,
                                'amount': func_amount,
                            }
                            if line_type == 'funding.pool':
                                vals.update({
                                    'cost_center_id': wiz_line.cost_center_id and wiz_line.cost_center_id.id or False,
                                    'destination_id': wiz_line.destination_id and wiz_line.destination_id.id or False,
                                })
                            self.pool.get('account.analytic.line').create(cr, uid, vals)
            # Check which old line have not been processed
            have_disappear = set(old_line_ids) - set(old_line_checked)
            if have_disappear:
                for hd_line in self.pool.get(line_obj).browse(cr, uid, list(have_disappear)):
                    amount = (ml.debit_currency - ml.credit_currency) * hd_line.percentage / 100
                    args = [
                            ('move_id', '=', ml_id),
                            ('distribution_id', '=', hd_line.distribution_id.id),
                            ('account_id', '=', hd_line.analytic_id.id),
                            ('amount_currency', '=', amount),
                    ]
                    if line_type == 'funding.pool':
                        args.append(('cost_center_id', '=', hd_line.cost_center_id.id))
                        args.append(('destination_id', '=', hd_line.destination_id.id))
                    # search lines to reverse
                    hd_ana_ids = self.pool.get('account.analytic.line').search(cr, uid, args)
                    # reverse lines
                    self.pool.get('account.analytic.line').reverse(cr, uid, hd_ana_ids)
        if to_update:
            to_update = flatten(to_update)
        return True, to_update

    def button_cancel(self, cr, uid, ids, context=None):
        """
        Close wizard and return on another wizard if 'from' and 'wiz_id' are in context
        """
        # Some verifications
        if not context:
            context = {}
        if 'from' in context and 'wiz_id' in context:
            wizard_name = context.get('from')
            wizard_id = context.get('wiz_id')
            return {
                'type': 'ir.actions.act_window',
                'res_model': wizard_name,
                'target': 'new',
                'view_mode': 'form,tree',
                'view_type': 'form',
                'res_id': wizard_id,
                'context': context,
            }
        return super(analytic_distribution_wizard, self).button_cancel(cr, uid, ids, context=context)

    def button_confirm(self, cr, uid, ids, context=None):
        """
        Change wizard state in order to use normal method
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Change wizard state if current is 'correction'
        for wiz in self.browse(cr, uid, ids, context=context):
            if wiz.state == 'correction':
                self.write(cr, uid, ids, {'state': 'dispatch'}, context=context)
            if 'from' in context and 'wiz_id' in context:
                # Update cost center lines
                if not self.update_cost_center_lines(cr, uid, wiz.id, context=context):
                    raise osv.except_osv(_('Error'), _('Cost center update failure.'))
                # Do some verifications before writing elements
                self.wizard_verifications(cr, uid, wiz.id, context=context)
                # Verify old account and new account
                account_changed = False
                new_account_id = wiz.account_id and wiz.account_id.id or False
                old_account_id = wiz.old_account_id and wiz.old_account_id.id or False
                if old_account_id != new_account_id:
                    account_changed = True
                # Compare new distribution with old one
                distrib_changed = False
                distrib_id = wiz.distribution_id and wiz.distribution_id.id or False
                for line_type in ['funding.pool', 'free.1', 'free.2']:
                    dbl = self.distrib_lines_to_list(cr, uid, distrib_id, line_type)
                    wizl = self.wizard_lines_to_list(cr, uid, wiz.id, line_type)
                    if not dbl == wizl:
                        distrib_changed = True
                        break
                # After checks, 3 CASES:
                ## 1/ Account AND Distribution have changed
                ## 2/ JUST account have changed
                ## 3/ JUST distribution have changed
                # So:
                ## 1 => Reverse G/L Account as expected and do a COR line. Do changes on analytic distribution and create new distribution then 
                #- linked it to new corrected line.
                ## 2 => Normal correction for G/L Account
                ## 3 => Verify analytic distribution and do changes regarding periods and contracts
                
                # Account AND Distribution have changed
                if account_changed and distrib_changed:
                    # Create new distribution
                    new_distrib_id = self.pool.get('analytic.distribution').create(cr, uid, {})
                    self.write(cr, uid, [wiz.id], {'distribution_id': new_distrib_id})
                    for line_type in ['funding.pool', 'free.1', 'free.2']:
                        # Compare and write modifications done on analytic lines
                        type_res = self.compare_and_write_modifications(cr, uid, wiz.id, line_type, context=context)
                    # return account change behaviour with a new analytic distribution
                    self.pool.get('wizard.journal.items.corrections').write(cr, uid, [context.get('wiz_id')], {'date': wiz.date})
                    return self.pool.get('wizard.journal.items.corrections').action_confirm(cr, uid, context.get('wiz_id'), new_distrib_id)
                # JUST Account have changed
                elif account_changed and not distrib_changed:
                    # return normal behaviour with account change
                    self.pool.get('wizard.journal.items.corrections').write(cr, uid, [context.get('wiz_id')], {'date': wiz.date})
                    return self.pool.get('wizard.journal.items.corrections').action_confirm(cr, uid, context.get('wiz_id'))
                # JUST Distribution have changed
                else:
                    # Check all lines to proceed to changes
                    to_update = []
                    res_changes, to_update = self.do_analytic_distribution_changes(cr, uid, wiz.id, distrib_id)
                    # Create new distribution
                    new_distrib_id = self.pool.get('analytic.distribution').create(cr, uid, {})
                    self.write(cr, uid, [wiz.id], {'distribution_id': new_distrib_id})
                    for line_type in ['funding.pool', 'free.1', 'free.2']:
                        # Compare and write modifications done on analytic lines
                        type_res = self.compare_and_write_modifications(cr, uid, wiz.id, line_type, context=context)
                    # Check new distribution state
                    if self.pool.get('analytic.distribution')._get_distribution_state(cr, uid, new_distrib_id, False, wiz.account_id.id) != 'valid':
                        raise osv.except_osv(_('Warning'), _('New analytic distribution is not compatible. Please check your distribution!'))
                    # Link new distribtion to analytic lines that have been overriden
                    ana_line_ids = self.pool.get('account.analytic.line').search(cr, uid, [('distribution_id', '=', distrib_id), ('move_id', "=", wiz.move_line_id.id), ('is_reversal', '=', False), ('is_reallocated', '=', False)])
                    if to_update:
                        for id in to_update:
                            if id not in ana_line_ids:
                                ana_line_ids.append(id)
                    res_ana = self.pool.get('account.analytic.line').write(cr, uid, ana_line_ids, {'distribution_id': new_distrib_id})
                    # Link new distribution to the move line
                    # WARNING CHECK=FALSE IS NEEDED in order NOT to delete OLD ANALYTIC LINES (and so permits reverse)
                    self.pool.get('account.move.line').write(cr, uid, wiz.move_line_id.id, {'analytic_distribution_id': new_distrib_id}, check=False, update_check=False)
                    return {'type': 'ir.actions.act_window_close'}
        # Get default method
        return super(analytic_distribution_wizard, self).button_confirm(cr, uid, ids, context=context)

analytic_distribution_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
