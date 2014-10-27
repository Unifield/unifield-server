#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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
import decimal_precision as dp
from tools.translate import _
import netsvc
import traceback
import time

class account_move_line_compute_currency(osv.osv):
    _inherit = "account.move.line"

    def _get_reconcile_total_partial_id(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Informs for each move line if a reconciliation or a partial reconciliation have been made. Else return False.
        """
        if isinstance(ids, (long, int)):
            ids = [ids]
        ret = {}
        for line in self.read(cr, uid, ids, ['reconcile_id','reconcile_partial_id']):
            if line['reconcile_id']:
                ret[line['id']] = line['reconcile_id']
            elif line['reconcile_partial_id']:
                ret[line['id']] = line['reconcile_partial_id']
            else:
                ret[line['id']] = False
        return ret

    _columns = {
        'debit_currency': fields.float('Booking Out', digits_compute=dp.get_precision('Account')),
        'credit_currency': fields.float('Booking In', digits_compute=dp.get_precision('Account')),
        'functional_currency_id': fields.related('account_id', 'company_id', 'currency_id', type="many2one", relation="res.currency", string="Functional Currency", store=False),
        # Those fields are for UF-173: Accounting Journals.
        # Since they are used in the move line view, they are added in Multi-Currency.
        'reconcile_total_partial_id': fields.function(_get_reconcile_total_partial_id, type="many2one", relation="account.move.reconcile", method=True, string="Reconcile"),
    }

    _defaults = {
        'debit_currency': 0.0,
        'credit_currency': 0.0,
    }

    def create_addendum_line(self, cr, uid, lines, total, context=None):
        """
        Create an addendum line.
        posting_date and document_date should be the oldiest date from all lines!
        """
        if context is None:
            context = {}

        current_instance = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id
        current_instance_level = current_instance.level
        current_instance_id = current_instance.id
        all_line_equal_to_current = True
        to_create = False
        previous = None
        has_section_line = False
        for line in self.browse(cr, uid, lines):
            if not previous:
                previous = line.instance_id.id

            if line.instance_id.level == 'section':
                has_section_line = True

            if not has_section_line and current_instance_level == 'section' and line.instance_id.level == 'project':
                to_create = False
                all_line_equal_to_current = False
                break

            if previous != line.instance_id.id:
                all_line_equal_to_current = False
                to_create = True
                if current_instance_level != 'section':
                    break
            elif line.instance_id.id != current_instance_id:
                all_line_equal_to_current = False
                to_create = False

            previous = line.instance_id.id

        if all_line_equal_to_current:
            to_create = True

        if not to_create:
            return False

        current_date = time.strftime('%Y-%m-%d')
        j_obj = self.pool.get('account.journal')
        company_currency_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        # Search Miscellaneous Transactions journal
        j_ids = j_obj.search(cr, uid, [('type', '=', 'cur_adj'),
                                       ('is_current_instance', '=', True)], order='id', context=context)
        if not j_ids:
            raise osv.except_osv(_('Error'), _('No Currency Adjustement journal found!'))
        journal_id = j_ids[0]
        # Get default debit and credit account for addendum_line (given by default credit/debit on journal)
        journal = j_obj.browse(cr, uid, journal_id)
        if not journal.default_debit_account_id or not journal.default_credit_account_id:
            raise osv.except_osv(_('Error'), _('Default debit/credit for journal %s is not set correctly.') % journal.name)
        addendum_line_debit_account_id = journal.default_debit_account_id.id
        addendum_line_credit_account_id = journal.default_credit_account_id.id
        addendum_line_debit_account_default_destination_id = journal.default_debit_account_id.default_destination_id.id
        addendum_line_credit_account_default_destination_id = journal.default_credit_account_id.default_destination_id.id
        # Create analytic distribution if this account is an analytic-a-holic account
        distrib_id = False
        different_currency = False
        prev_curr = False
        if journal.default_debit_account_id.is_analytic_addicted:
            ## Browse all lines to fetch some values
            partner_id = employee_id = transfer_journal_id = False
            oldiest_date = False
            for rline in self.browse(cr, uid, lines):
                account_id = (rline.account_id and rline.account_id.id) or False
                partner_id = (rline.partner_id and rline.partner_id.id) or False
                employee_id = (rline.employee_id and rline.employee_id.id) or False
                transfer_journal_id = (rline.transfer_journal_id and rline.transfer_journal_id.id) or False
                currency_id = (rline.currency_id and rline.currency_id.id) or False
                # Check if lines are in different currencies
                if not prev_curr:
                    prev_curr = rline.currency_id.id
                if rline.currency_id.id != prev_curr:
                    different_currency = True
                prev_curr = rline.currency_id.id
                if not oldiest_date:
                    oldiest_date = rline.date or False
                if rline.date > oldiest_date:
                    oldiest_date = rline.date
#                break

            # Search attached period
            period_id = None
            for tested_date in [oldiest_date, current_date]:
                period_ids = self.pool.get('account.period').search(cr, uid, [('date_start', '<=', tested_date), ('date_stop', '>=', tested_date)], context=context, limit=1, order='date_start, name')
                if not period_ids:
                    raise osv.except_osv(_('Error'), _('No attached period found!'))
                if self.pool.get('account.period').browse(cr, uid, period_ids[0]).state == 'draft':
                    period_id = period_ids[0]
                    break

            if not period_id:
                raise osv.except_osv(_('Warning'), _('No open period found for this date: %s') % current_date)

            # verify that a fx gain/loss account exists
            search_ids = self.pool.get('account.analytic.account').search(cr, uid, [('for_fx_gain_loss', '=', True)], context=context)
            if not search_ids:
                raise osv.except_osv(_('Warning'), _('Please activate an analytic account with "For FX gain/loss" to allow reconciliation!'))
            # Prepare some values
            partner_db = partner_cr = addendum_db = addendum_cr = None
            if total < 0.0:
                # data for partner line
                partner_db = addendum_cr = abs(total)
                addendum_line_account_id = addendum_line_credit_account_id
                addendum_line_account_default_destination_id = addendum_line_credit_account_default_destination_id
            # Conversely some amount is missing @credit for partner
            else:
                partner_cr = addendum_db = abs(total)
                addendum_line_account_id = addendum_line_debit_account_id
                addendum_line_account_default_destination_id = addendum_line_debit_account_default_destination_id
            # create an analytic distribution if addendum_line_account_id is an analytic-a-holic account
            account = self.pool.get('account.account').browse(cr, uid, addendum_line_account_id)
            if account and account.is_analytic_addicted:
                distrib_id = self.pool.get('analytic.distribution').create(cr, uid, {}, context={})
                # add a cost center for analytic distribution
                distrib_line_vals = {
                    'distribution_id': distrib_id,
                    'currency_id': company_currency_id,
                    'analytic_id': search_ids[0],
                    'percentage': 100.0,
                    'date': oldiest_date or current_date,
                    'source_date': oldiest_date or current_date,
                    'destination_id': addendum_line_account_default_destination_id,
                }
                cc_id = self.pool.get('cost.center.distribution.line').create(cr, uid, distrib_line_vals, context=context)
                # add a funding pool line for analytic distribution
                try:
                    fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
                except ValueError:
                    fp_id = 0
                if not fp_id:
                    raise osv.except_osv(_('Error'), _('No "MSF Private Fund" found!'))
                distrib_line_vals.update({'analytic_id': fp_id, 'cost_center_id': search_ids[0],})
                self.pool.get('funding.pool.distribution.line').create(cr, uid, distrib_line_vals, context=context)

            move_id = self.pool.get('account.move').create(cr, uid,{'journal_id': journal_id, 'period_id': period_id, 'date': oldiest_date or current_date}, context=context)
            # Create default vals for the new two move lines
            vals = {
                'move_id': move_id,
                'date': oldiest_date or current_date,
                'source_date': oldiest_date or current_date,
                'document_date': oldiest_date or current_date,
                'journal_id': journal_id,
                'period_id': period_id,
                'partner_id': partner_id,
                'employee_id': employee_id,
                'transfer_journal_id': transfer_journal_id,
                'credit': 0.0,
                'debit': 0.0,
                'name': 'Realised loss/gain',
                'is_addendum_line': True,
                'currency_id': currency_id,
                #'functional_currency_id': functional_currency_id,
            }
            # UTP-494: use functional currency as currency for addendum line
            if different_currency:
                functional_currency_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
                vals.update({'currency_id': functional_currency_id})
            # Create partner line
            vals.update({'account_id': account_id, 'debit': partner_db or 0.0, 'credit': partner_cr or 0.0,})
            # UTP-1022: Allow account.move.line creation when we come from "create_addendum_line" because of currencies rate redefinition
            context.update({'addendum_line_creation': True})
            partner_line_id = self.create(cr, uid, vals, context=context)
            # Create addendum_line
            if distrib_id:
                vals.update({'analytic_distribution_id': distrib_id})
            vals.update({'account_id': addendum_line_account_id, 'debit': addendum_db or 0.0, 'credit': addendum_cr or 0.0,})
            addendum_line_id = self.create(cr, uid, vals, context=context)
            # Validate move
            self.pool.get('account.move').post(cr, uid, [move_id], context=context)

            # Update analytic line with right amount (instead of "0.0")
            analytic_line_ids = self.pool.get('account.analytic.line').search(cr, uid, [('move_id', '=', addendum_line_id)], context=context)
            addendum_line_amount_curr = -1*total or 0.0
            self.pool.get('account.analytic.line').write(cr, uid, analytic_line_ids, {'currency_id': company_currency_id, 'amount': addendum_line_amount_curr, 'amount_currency': addendum_line_amount_curr})

            return partner_line_id

    def reconciliation_update(self, cr, uid, ids, context=None):
        """
        Update addendum line for reconciled lines
        """
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        reconciled_obj = self.pool.get('account.move.reconcile')
        al_obj = self.pool.get('account.analytic.line')
        # Search Miscellaneous Transactions journal
        j_obj = self.pool.get('account.journal')
        j_ids = j_obj.search(cr, uid, [('type', '=', 'cur_adj'),
                                       ('is_current_instance', '=', True)], order='id', context=context)
        if not j_ids:
            raise osv.except_osv(_('Error'), _('No Currency Adjustement journal found!'))
        journal_id = j_ids[0]
        # Get default debit and credit account for addendum_line (given by default credit/debit on journal)
        journal = j_obj.browse(cr, uid, journal_id)
        if not journal.default_debit_account_id or not journal.default_credit_account_id:
            raise osv.except_osv(_('Error'), _('Default debit/credit for journal %s is not set correctly.') % journal.name)
        addendum_line_debit_account_id = journal.default_debit_account_id.id
        addendum_line_credit_account_id = journal.default_credit_account_id.id
        addendum_line_debit_account_default_destination_id = journal.default_debit_account_id.default_destination_id.id
        addendum_line_credit_account_default_destination_id = journal.default_credit_account_id.default_destination_id.id
        # Check line state
        for reconciled in reconciled_obj.browse(cr, uid, ids, context=context):
            # Search addendum line
            addendum_line_ids = self.search(cr, uid, [('reconcile_id', '=', reconciled.id), ('is_addendum_line', '=', True)], context=context)
            # If addendum_line_ids, update it (if needed)
            if addendum_line_ids:
                # Search all lines that have same reconcile_id but that are not addendum_lines !
                reconciled_line_ids = self.search(cr, uid, [('reconcile_id', '=', reconciled.id), ('is_addendum_line', '=', False)], context=context)
                if not reconciled_line_ids:
                    continue
                total = self._accounting_balance(cr, uid, reconciled_line_ids, context=context)[0]
                # update addendum line if needed
                partner_db = partner_cr = addendum_db = addendum_cr = None
                if total < 0.0:
                    partner_cr = addendum_db = abs(total)
                    addendum_line_account_id = addendum_line_credit_account_id
                    addendum_line_account_default_destination_id = addendum_line_credit_account_default_destination_id
                else:
                    partner_db = addendum_cr = abs(total)
                    addendum_line_account_id = addendum_line_debit_account_id
                    addendum_line_account_default_destination_id = addendum_line_debit_account_default_destination_id
                for al in self.browse(cr, uid, addendum_line_ids, context=context):
                    # search other line from same move in order to update its amount
                    other_line_ids = self.search(cr, uid, [('move_id', '=', al.move_id.id), ('id', '!=', al.id)], context=context)
                    # Update addendum line
                    sql = """
                        UPDATE account_move_line
                        SET debit_currency=%s, credit_currency=%s, amount_currency=%s, debit=%s, credit=%s
                        WHERE id=%s
                    """
                    cr.execute(sql, [0.0, 0.0, 0.0, addendum_db or 0.0, addendum_cr or 0.0, tuple([al.id])])
                    # Update partner line
                    if isinstance(other_line_ids, (int, long)):
                        other_line_ids = [other_line_ids]
                    for o in self.pool.get('account.move.line').browse(cr, uid, other_line_ids):
                        cr.execute(sql, [0.0, 0.0, 0.0, partner_db or 0.0, partner_cr or 0.0, tuple([o.id])])
                    # Update analytic lines
                    analytic_line_ids = al_obj.search(cr, uid, [('move_id', 'in', other_line_ids)], context=context)
                    al_obj.write(cr, uid, analytic_line_ids, {'amount': -1*total, 'amount_currency': -1*total,}, context=context)
                    # Update Addendum line that's not reconciled
                    addendum_counterpart_ids = self.search(cr, uid, [('move_id', '=', al.move_id.id), ('id', '!=', al.id), ('is_addendum_line', '=', True)])
                    if not addendum_counterpart_ids:
                        continue
                    counterpart_sql = """
                        UPDATE account_move_line
                        SET account_id=%s
                        WHERE id=%s
                    """
                    cr.execute(counterpart_sql, [addendum_line_account_id, tuple(addendum_counterpart_ids)])
                    # then update their analytic lines with default destination
                    analytic_line_ids = al_obj.search(cr, uid, [('move_id', 'in', addendum_counterpart_ids)])
                    al_obj.write(cr, uid, analytic_line_ids, {'general_account_id': addendum_line_account_id, 'destination_id': addendum_line_account_default_destination_id,})
            else:
                # Search all lines that have same reconcile_id
                reconciled_line_ids = self.search(cr, uid, [('reconcile_id', '=', reconciled.id)], context=context)
                if not reconciled_line_ids:
                    continue
                total = self._accounting_balance(cr, uid, reconciled_line_ids, context=context)[0]
                if total != 0.0:
                    # UTP-752: Do not make FX Adjustement line (addendum line) if the reconciliation comes from a multi instance and that we are in synchronization
                    multi_instance = reconciled.is_multi_instance
                    current_instance = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
                    current_instance_id = current_instance.id
                    current_instance_level = current_instance.level
                    # UF-2501: when proj + coor are reconciled from HQ adj line should be created at coordo only
                    if not multi_instance and reconciled.multi_instance_level_creation:
                        multi_instance = reconciled.multi_instance_level_creation != current_instance_level

                    from_sync = context.get('sync_update_execution', False) and context.get('sync_update_execution') is True or False
                    from_another_instance = False
                    reconciliation_instance = reconciled.instance_id and reconciled.instance_id.id or False
                    if reconciliation_instance and reconciliation_instance != current_instance_id:
                        from_another_instance = True
                    if multi_instance and (from_sync or from_another_instance):
                        continue
                    # If no exception, do main process about new addendum lines
                    partner_line_id = self.create_addendum_line(cr, uid, reconciled_line_ids, total)
                    if partner_line_id:
                        # Add it to reconciliation (same that other lines)
                        reconcile_txt = ''
                        data = self.pool.get('account.move.reconcile').name_get(cr, uid, [reconciled.id])
                        if data and data[0] and data[0][1]:
                            reconcile_txt = data[0][1]
                        cr.execute('update account_move_line set reconcile_id=%s, reconcile_txt=%s where id=%s',(reconciled.id, reconcile_txt or '', partner_line_id))
        return True

    def update_amounts(self, cr, uid, ids):
        """
        - Update debit/credit and debit_currency/credit_currency regarding date and currency rate
        - Update analytic lines
        - Update reconciled lines
        """
        # Prepare some values
        cur_obj = self.pool.get('res.currency')
        analytic_obj = self.pool.get('account.analytic.line')
        reconciled_move = {}
        for move_line in self.browse(cr, uid, ids):
            if move_line.is_addendum_line:
                # addendum line will be reevaluated after the reevaluation of the reconlied lines
                # (at the end of this method)
                continue
            # amount currency is not set; it is computed from the 2 other fields
            ctx = {}
            # WARNING: since SP2, source_date have priority to date if exists. That's why it should be used for computing amounts
            if move_line.date:
                ctx['date'] = move_line.date
            # source_date is more important than date
            if move_line.source_date:
                ctx['date'] = move_line.source_date

            if move_line.period_id.state != 'done':
                if move_line.debit_currency != 0.0 or move_line.credit_currency != 0.0:
                    # amount currency is not set; it is computed from the 2 other fields
                    amount_currency = move_line.debit_currency - move_line.credit_currency
                    debit_computed = cur_obj.compute(cr, uid, move_line.currency_id.id,
                        move_line.functional_currency_id.id, move_line.debit_currency, round=True, context=ctx)
                    credit_computed = cur_obj.compute(cr, uid, move_line.currency_id.id,
                        move_line.functional_currency_id.id, move_line.credit_currency, round=True, context=ctx)
                    cr.execute('update account_move_line set debit=%s, \
                                                             credit=%s, \
                                                             amount_currency=%s where id=%s',
                              (debit_computed, credit_computed, amount_currency, move_line.id))
                elif move_line.debit_currency == 0.0 and \
                     move_line.credit_currency == 0.0 and \
                     move_line.amount_currency == 0.0 and \
                     (move_line.debit != 0.0 or move_line.debit != 0.0):
                    # only the debit/credit in functional currency are set;
                    # the amounts in booking currency are computed
                    debit_currency_computed = cur_obj.compute(cr, uid, move_line.functional_currency_id.id,
                        move_line.currency_id.id, move_line.debit, round=True, context=ctx)
                    credit_currency_computed = cur_obj.compute(cr, uid, move_line.functional_currency_id.id,
                        move_line.currency_id.id, move_line.credit, round=True, context=ctx)
                    amount_currency = debit_currency_computed - credit_currency_computed
                    cr.execute('update account_move_line set debit_currency=%s, \
                                                             credit_currency=%s, \
                                                             amount_currency=%s where id=%s',
                              (debit_currency_computed, credit_currency_computed, amount_currency, move_line.id))
                elif move_line.debit_currency == 0.0 and \
                     move_line.credit_currency == 0.0 and \
                     move_line.amount_currency != 0.0:
                    # debit/credit currency are not set; it is computed from the amount currency
                    debit_currency = 0.0
                    credit_currency = 0.0
                    if move_line.amount_currency < 0:
                        credit_currency = -move_line.amount_currency
                    else:
                        debit_currency = move_line.amount_currency
                    cr.execute('update account_move_line set debit_currency=%s, \
                                                             credit_currency=%s where id=%s',
                              (debit_currency, credit_currency, move_line.id))
                # Refresh the associated analytic lines
                analytic_line_ids = []
                for analytic_line in move_line.analytic_lines:
                    analytic_line_ids.append(analytic_line.id)
                analytic_obj.update_amounts(cr, uid, analytic_line_ids)
            # Reconciliation verification
            if move_line.reconcile_id:
                reconciled_move[move_line.reconcile_id.id] = True
#                self.reconciliation_update(cr, uid, [move_line.id])
        if reconciled_move:
            self.reconciliation_update(cr, uid, reconciled_move.keys())
        return True

    def check_date(self, cr, uid, vals):
        # check that date is in period
        if 'period_id' in vals and 'date' in vals:
            period = self.pool.get('account.period').read(cr, uid, vals['period_id'], ['name', 'date_start', 'date_stop'])
            if vals['date'] < period.get('date_start') or vals['date'] > period.get('date_stop'):
                raise osv.except_osv(_('Warning !'), _('Posting date (%s) is outside of defined period: %s!') % (vals.get('date'), period.get('name') or '',))

    def _update_amount_bis(self, cr, uid, vals, currency_id, curr_fun, date=False, source_date=False, debit_currency=False, credit_currency=False):
        newvals = {}
        ctxcurr = {}
        cur_obj = self.pool.get('res.currency')

        # WARNING: source_date field have priority to date field. This is because of SP2 Specifications
        if vals.get('date', date):
            ctxcurr['date'] = vals.get('date', date)
        if vals.get('source_date', source_date):
            ctxcurr['date'] = vals.get('source_date', source_date)

#        if ctxcurr.get('date', False):
#            newvals['date'] = ctxcurr['date']

        if vals.get('credit_currency') or vals.get('debit_currency'):
            newvals['amount_currency'] = vals.get('debit_currency') or 0.0 - vals.get('credit_currency') or 0.0
            newvals['debit'] = cur_obj.compute(cr, uid, currency_id, curr_fun, vals.get('debit_currency') or 0.0, round=True, context=ctxcurr)
            newvals['credit'] = cur_obj.compute(cr, uid, currency_id, curr_fun, vals.get('credit_currency') or 0.0, round=True, context=ctxcurr)
        elif (vals.get('debit') or vals.get('credit')) and not vals.get('amount_currency'):
            newvals['credit_currency'] = cur_obj.compute(cr, uid, curr_fun, currency_id, vals.get('credit') or 0.0, round=True, context=ctxcurr)
            newvals['debit_currency'] = cur_obj.compute(cr, uid, curr_fun, currency_id, vals.get('debit') or 0.0, round=True, context=ctxcurr)
            newvals['amount_currency'] = newvals['debit_currency'] - newvals['credit_currency']
        elif vals.get('amount_currency'):
            if vals['amount_currency'] < 0:
                newvals['credit_currency'] = -vals['amount_currency']
                newvals['debit_currency'] = 0
            else:
                newvals['debit_currency'] = vals['amount_currency']
                newvals['credit_currency'] = 0
            newvals['debit'] = cur_obj.compute(cr, uid, currency_id, curr_fun, newvals.get('debit_currency') or 0.0, round=True, context=ctxcurr)
            newvals['credit'] = cur_obj.compute(cr, uid, currency_id, curr_fun, newvals.get('credit_currency') or 0.0, round=True, context=ctxcurr)
        elif (vals.get('date') or vals.get('source_date')) and (credit_currency or debit_currency):
            newvals['debit'] = cur_obj.compute(cr, uid, currency_id, curr_fun, debit_currency or 0.0, round=True, context=ctxcurr)
            newvals['credit'] = cur_obj.compute(cr, uid, currency_id, curr_fun, credit_currency or 0.0, round=True, context=ctxcurr)
            newvals['amount_currency'] = debit_currency - credit_currency
        # Set booking values to 0 if line come from a reconciliation that have generated an addendum line (so this line have 'is_addendum_line' to True
        if vals.get('is_addendum_line', False):
            newvals.update({'debit_currency': 0.0, 'credit_currency': 0.0})
        return newvals

    def create(self, cr, uid, vals, context=None, check=True):
        """
        Account move line creation that update debit/credit values for booking and functional currency.
        """
        # Some verifications
        self.check_date(cr, uid, vals)
        date_to_compute = False

        if 'period_id' in vals:
            period = self.pool.get('account.period').browse(cr, uid, vals.get('period_id'), context)
            if period and period.state == 'created':
                raise osv.except_osv(_('Error !'), _('Period \'%s\' is not open! No Journal Item is created') % (period.name,))

        if not 'date' in vals:
            if vals.get('move_id'):
                date_to_compute = self.pool.get('account.move').read(cr, uid, vals['move_id'], ['date'])['date']
            else:
                logger = netsvc.Logger()
                logger.notifyChannel("warning", netsvc.LOG_WARNING, "No date for new account_move_line!")
                traceback.print_stack()
                # UTP-1194: Raise exception if the move is not in vals when creating move line
                raise osv.except_osv(_('Error !'), _('Cannot create Journal Item due to missing the parent Journal Entry or Date'))

        if not context:
            context = {}

        ctx = context.copy()
        data = {}
        if 'journal_id' in vals:
            ctx['journal_id'] = vals['journal_id']
        if ('journal_id' not in ctx) and vals.get('move_id'):
            m = self.pool.get('account.move').read(cr, uid, vals['move_id'], ['journal_id'])
            ctx['journal_id'] = m.get('journal_id', False) and m.get('journal_id')[0] or False

        # Add currency on line
        if context.get('from_web_menu', False):
            if 'move_id' in vals:
                m_currency = self.pool.get('account.move').read(cr, uid, vals.get('move_id'), ['manual_currency_id'])
                if m_currency and m_currency.get('manual_currency_id'):
                    vals.update({'currency_id': m_currency.get('manual_currency_id')[0]})

        account = self.pool.get('account.account').browse(cr, uid, vals['account_id'], context=context)
        curr_fun = account.company_id.currency_id.id

        newvals = vals.copy()
        if not newvals.get('currency_id'):
            if account.currency_id:
                newvals['currency_id'] = account.currency_id and account.currency_id.id or False
            else:
                newvals['currency_id'] = curr_fun
        # Don't update values for addendum lines that come from a reconciliation
        if not newvals.get('is_addendum_line', False):
            newvals.update(self._update_amount_bis(cr, uid, vals, newvals['currency_id'], curr_fun, date=date_to_compute))
        return super(account_move_line_compute_currency, self).create(cr, uid, newvals, context, check=check)

    def write(self, cr, uid, ids, vals, context=None, check=True, update_check=True):
        """
        Update line values regarding date, source_date and currency rate
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (long, int)):
            ids = [ids]
        self.check_date(cr, uid, vals)
        # Prepare some values
        res = True
        reconciled_move = {}
        # Browse lines
        for line in self.browse(cr, uid, ids):
            newvals = vals.copy()
            date = vals.get('date', line.date)
            source_date = vals.get('source_date', line.source_date)
            # Add currency on line
            if context.get('from_web_menu', False):
                vals.update({'currency_id': line.move_id and line.move_id.manual_currency_id and line.move_id.manual_currency_id.id or False})
            currency_id = vals.get('currency_id') or line.currency_id.id
            func_currency = line.account_id.company_id.currency_id.id
            newvals.update(self._update_amount_bis(cr, uid, newvals, currency_id, func_currency, date, source_date, line.debit_currency, line.credit_currency))
            res = res and super(account_move_line_compute_currency, self).write(cr, uid, [line.id], newvals, context, check=check, update_check=update_check)
            # Update addendum line for reconciliation entries if this line is reconciled
            if line.reconcile_id:
                reconciled_move[line.reconcile_id.id] = True
        if reconciled_move:
            self.reconciliation_update(cr, uid, reconciled_move.keys(), context=context)
        return res

    def _get_journal_move_line(self, cr, uid, ids, context=None):
        return self.pool.get('account.move.line').search(cr, uid, [('journal_id', 'in', ids)])

    def _get_line_account_type(self, cr, uid, ids, field_name=None, arg=None, context=None):
        if isinstance(ids, (long, int)):
            ids = [ids]
        ret = {}
        for line in self.browse(cr, uid, ids):
            ret[line.id] = line.account_id and line.account_id.user_type and line.account_id.user_type.name or False
        return ret

    def _store_journal_account(self, cr, uid, ids, context=None):
        return self.pool.get('account.move.line').search(cr, uid, [('account_id', 'in', ids)])

    def _store_journal_account_type(self, cr, uid, ids, context=None):
        return self.pool.get('account.move.line').search(cr, uid, [('account_id.user_type', 'in', ids)])

    def _search_reconcile_total_partial(self, cr, uid, ids, field_names, args, context=None):
        """
        Search either total reconciliation name or partial reconciliation name
        """
        if context is None:
            context = {}
        arg = []
        for x in args:
            if x[0] == 'reconcile_total_partial_id' and x[1] in ['=','ilike','like'] and x[2]:
                arg.append('|')
                arg.append(('reconcile_id', x[1], x[2]))
                arg.append(('reconcile_partial_id', x[1], x[2]))
            elif x[0] == 'reconcile_total_partial_id':
                raise osv.except_osv(_('Error'), _('Operator not supported!'))
            else:
                arg.append(x)
        return arg

    _columns = {
        'debit_currency': fields.float('Book. Debit', digits_compute=dp.get_precision('Account')),
        'credit_currency': fields.float('Book. Credit', digits_compute=dp.get_precision('Account')),
        'functional_currency_id': fields.related('account_id', 'company_id', 'currency_id', type="many2one", relation="res.currency", string="Func. Currency", store=False),
        # Those fields are for UF-173: Accounting Journals.
        # Since they are used in the move line view, they are added in Multi-Currency.
        'account_type': fields.function(_get_line_account_type, type='char', size=64, method=True, string="Account Type",
                store = {
                    'account.move.line': (lambda self, cr, uid, ids, c=None: ids, ['account_id'], 10),
                    'account.account': (_store_journal_account, ['user_type'], 10),
                    'account.account.type': (_store_journal_account_type, ['name'], 10),
                }
            ),
        'reconcile_total_partial_id': fields.function(_get_reconcile_total_partial_id, fnct_search=_search_reconcile_total_partial, type="many2one", relation="account.move.reconcile", method=True, string="Reconcile"),
    }

    _defaults = {
        'debit_currency': 0.0,
        'credit_currency': 0.0,
    }

account_move_line_compute_currency()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
