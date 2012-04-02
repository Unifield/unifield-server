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

class account_move_line_compute_currency(osv.osv):
    _inherit = "account.move.line"

    def _get_reconcile_total_partial_id(self, cr, uid, ids, field_name=None, arg=None, context={}):
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
        'instance': fields.related('journal_id', 'instance_id', type="char", string="Proprietary instance", store=False),
        'reconcile_total_partial_id': fields.function(_get_reconcile_total_partial_id, type="many2one", relation="account.move.reconcile", method=True, string="Reconcile"),
    }

    _defaults = {
        'debit_currency': 0.0,
        'credit_currency': 0.0,
    }

    def reconciliation_update(self, cr, uid, ids, context={}):
        """
        Update addendum line for reconciled lines
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Check line state
        for line in self.browse(cr, uid, ids, context=context):
            if not line.reconcile_id:
                continue
            # Search addendum line
            addendum_line_ids = self.search(cr, uid, [('reconcile_id', '=', line.reconcile_id.id), ('is_addendum_line', '=', True)], context=context)
            # If no addendum_line_ids, do nothing
            if addendum_line_ids:
                # Search all lines that have same reconcile_id but that are not addendum_lines !
                reconciled_line_ids = self.search(cr, uid, [('reconcile_id', '=', line.reconcile_id.id), ('is_addendum_line', '=', False)], context=context)
                total = self._accounting_balance(cr, uid, reconciled_line_ids, context=context)[0]
                # update addendum line if needed
                if total != 0.0:
                    partner_db = partner_cr = addendum_db = addendum_cr = None
                    if total < 0.0:
                        partner_cr = addendum_db = abs(total)
                    else:
                        partner_db = addendum_cr = abs(total)
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
                        cr.execute(sql, [0.0, 0.0, 0.0, partner_db or 0.0, partner_cr or 0.0, tuple(other_line_ids)])
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
        for move_line in self.browse(cr, uid, ids):
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
                self.reconciliation_update(cr, uid, [move_line.id])
        return True

    def check_date(self, cr, uid, vals):
        # check that date is in period
        if 'period_id' in vals and 'date' in vals:
            period = self.pool.get('account.period').browse(cr, uid, vals['period_id'])
            if vals['date'] < period.date_start or vals['date'] > period.date_stop:
                raise osv.except_osv(_('Warning !'), _('Posting date is outside of defined period!'))

    def _update_amount_bis(self, cr, uid, vals, currency_id, curr_fun, date=False, source_date=False, debit_currency=False, credit_currency=False):
        newvals = {}
        ctxcurr = {}
        cur_obj = self.pool.get('res.currency')
        
        # WARNING: source_date field have priority to date field. This is because of SP2 Specifications
        if vals.get('date', date):
            ctxcurr['date'] = vals.get('date', date)
        if vals.get('source_date', source_date):
            ctxcurr['date'] = vals.get('source_date', source_date)
        
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
        if not 'date' in vals:
            logger = netsvc.Logger()
            logger.notifyChannel("warning", netsvc.LOG_WARNING, "No date for new account_move_line!")
            traceback.print_stack()
        if not context:
            context = {}
        # Prepare some values
        move_obj = self.pool.get('account.move')
        journal_obj = self.pool.get('account.journal')
        account_obj = self.pool.get('account.account')
        
        ctx = context.copy()
        data = {}
        if 'journal_id' in vals:
            ctx['journal_id'] = vals['journal_id']
        if ('journal_id' not in ctx) and vals.get('move_id'):
            m = move_obj.browse(cr, uid, vals['move_id'])
            ctx['journal_id'] = m.journal_id.id
        journal = journal_obj.browse(cr, uid, ctx['journal_id'])
        
        account = account_obj.browse(cr, uid, vals['account_id'], context=context)
        curr_fun = account.company_id.currency_id.id
        
        newvals = vals.copy()
        if not newvals.get('currency_id'):
            if account.currency_id:
                newvals['currency_id'] = account.currency_id.id
            else:
                newvals['currency_id'] = curr_fun
        # Don't update values for addendum lines that come from a reconciliation
        if not newvals.get('is_addendum_line', False):
            newvals.update(self._update_amount_bis(cr, uid, vals, newvals['currency_id'], curr_fun))
        return super(account_move_line_compute_currency, self).create(cr, uid, newvals, context, check=check)

    def write(self, cr, uid, ids, vals, context={}, check=True, update_check=True):
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
        # Browse lines
        for line in self.browse(cr, uid, ids):
            newvals = vals.copy()
            date = vals.get('date', line.date)
            source_date = vals.get('source_date', line.source_date)
            currency_id = vals.get('currency_id') or line.currency_id.id
            func_currency = line.account_id.company_id.currency_id.id
            newvals.update(self._update_amount_bis(cr, uid, newvals, currency_id, func_currency, date, source_date, line.debit_currency, line.credit_currency))
            res = res and super(account_move_line_compute_currency, self).write(cr, uid, [line.id], newvals, context, check=check, update_check=update_check)
            # Update addendum line for reconciliation entries if this line is reconciled
            if line.reconcile_id:
                self.reconciliation_update(cr, uid, [line.id], context=context)
        return res

    def _get_reconcile_total_partial_id(self, cr, uid, ids, field_name=None, arg=None, context={}):
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

    def _get_instance_type(self, cr, uid, ids, field_name=None, arg=None, context={}):
        if isinstance(ids, (long, int)):
            ids = [ids]
        ret = {}
        for line in self.browse(cr, uid, ids):
            ret[line.id] = line.journal_id and line.journal_id.instance_id or False
        return ret

    def _get_journal_move_line(self, cr, uid, ids, context=None):
        return self.pool.get('account.move.line').search(cr, uid, [('journal_id', 'in', ids)])
    
    def _get_line_account_type(self, cr, uid, ids, field_name=None, arg=None, context={}):
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


    _columns = {
        'debit_currency': fields.float('Booking Debit', digits_compute=dp.get_precision('Account')),
        'credit_currency': fields.float('Booking Credit', digits_compute=dp.get_precision('Account')),
        'functional_currency_id': fields.related('account_id', 'company_id', 'currency_id', type="many2one", relation="res.currency", string="Functional Currency", store=False),
        # Those fields are for UF-173: Accounting Journals.
        # Since they are used in the move line view, they are added in Multi-Currency.
        'instance': fields.function(_get_instance_type, type='char', string='Proprietary instance', size=64, method=True,
                store = {
                    'account.move.line': (lambda self, cr, uid, ids, c={}: ids, ['journal_id'], 10),
                    'account.journal': (_get_journal_move_line, ['instance_id'], 10),
                }
            ),
        'account_type': fields.function(_get_line_account_type, type='char', size=64, method=True, string="Account Type",
                store = {
                    'account.move.line': (lambda self, cr, uid, ids, c={}: ids, ['account_id'], 10),
                    'account.account': (_store_journal_account, ['user_type'], 10),
                    'account.account.type': (_store_journal_account_type, ['name'], 10),
                }
            ),
        'reconcile_total_partial_id': fields.function(_get_reconcile_total_partial_id, type="many2one", relation="account.move.reconcile", method=True, string="Reconcile"),
    }

    _defaults = {
        'debit_currency': 0.0,
        'credit_currency': 0.0,
    }

account_move_line_compute_currency()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
