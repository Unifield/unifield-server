# -*- coding: utf-8 -*-
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
from tools.translate import _
import datetime
from dateutil.relativedelta import relativedelta
from base import currency_date


class msf_accrual_line(osv.osv):
    # this object actually corresponds to the "Accruals" and not to their lines...
    _name = 'msf.accrual.line'
    _rec_name = 'date'

    def onchange_period(self, cr, uid, ids, period_id, context=None):
        if period_id is False:
            return {'value': {'date': False}}
        else:
            period = self.pool.get('account.period').browse(cr, uid, period_id, context=context)
            return {'value': {'date': period.date_stop, 'document_date': period.date_stop}}

    def _get_accrual_amounts(self, cr, uid, ids, fields, arg, context=None):
        """
        Computes the values for fields.function fields, retrieving the sum of the Accrual amounts of all lines:
        - in booking curr. => total_accrual_amount
        - in functional curr. => total_functional_amount
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for accrual_line in self.browse(cr, uid, ids, fields_to_fetch=['expense_line_ids'], context=context):
            booking_amount = 0
            func_amount = 0
            for expense_line in accrual_line.expense_line_ids:
                booking_amount += expense_line.accrual_amount or 0.0
                func_amount += expense_line.functional_amount or 0.0
            res[accrual_line.id] = {
                'total_accrual_amount': booking_amount,
                'total_functional_amount': func_amount,
            }
        return res

    def _get_entry_sequence(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        if not ids:
            return res
        for rec in self.browse(cr, uid, ids, context=context):
            es = ''
            if rec.state != 'draft' and rec.analytic_distribution_id \
                    and rec.analytic_distribution_id.move_line_ids:
                # get the NOT REV entry
                # (same period as REV posting date is M+1)
                move_line_br = False
                for mv in rec.analytic_distribution_id.move_line_ids:
                    if mv.period_id.id == rec.period_id.id:
                        move_line_br = mv
                        break
                if move_line_br:
                    es = move_line_br.move_id \
                        and move_line_br.move_id.name or ''
            res[rec.id] = es
        return res

    def _get_distribution_state(self, cr, uid, ids, name, args, context=None):
        """
        The AD state of an Accrual depends on the AD state of its expense lines (which all require an AD):
        - if no line has an AD => none
        - else if all lines are "valid" => valid
        - else if one line is "invalid_small_amount" and no line is "invalid" => invalid_small_amount
        - other cases => invalid
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for accrual_line in self.browse(cr, uid, ids, fields_to_fetch=['expense_line_ids'], context=context):
            line_ad_states = [exp_l.analytic_distribution_state for exp_l in accrual_line.expense_line_ids]
            if not line_ad_states or all(state == 'none' for state in line_ad_states):
                ad_state = 'none'
            elif all(state == 'valid' for state in line_ad_states):
                ad_state = 'valid'
            elif any([state == 'invalid_small_amount' for state in line_ad_states]) and not any([state == 'invalid'
                                                                                                 for state in line_ad_states]):
                ad_state = 'invalid_small_amount'
            else:
                ad_state = 'invalid'
            res[accrual_line.id] = ad_state
        return res

    def _get_accrual_journal(self, cr, uid, context=None):
        """
        Returns the Accrual journal of the current instance
        """
        if context is None:
            context = {}
        acc_journal_ids = self.pool.get('account.journal').search(cr, uid,
                                                                  [('type', '=', 'accrual'),
                                                                   ('is_current_instance', '=', True),
                                                                   ('is_active', '=', True)],
                                                                  order='id', limit=1, context=context)
        if not acc_journal_ids:
            raise osv.except_osv(_('Warning !'), _("No active journal of type Accrual has been found for the current instance."))
        return acc_journal_ids[0]

    _columns = {
        'date': fields.date("Date"),
        'document_date': fields.date("Document Date", required=True),
        'period_id': fields.many2one('account.period', 'Period', required=True, domain=[('state', '=', 'draft'), ('is_system', '=', False)]),
        'description': fields.char('Description', size=64, required=True),
        'reference': fields.char('Reference', size=64),
        'expense_account_id': fields.many2one('account.account', 'Expense Account (deprecated)', required=True,
                                              domain=[('type', '!=', 'view'), ('user_type_code', '=', 'expense')]),
        'accrual_account_id': fields.many2one('account.account', 'Accrual Account', required=True, domain=[('type', '!=', 'view'), ('user_type_code', 'in', ['receivables', 'payables', 'debt'])]),
        'accrual_amount': fields.float('Accrual Amount (deprecated)', required=True),
        'total_accrual_amount': fields.function(_get_accrual_amounts, method=True, store=False, readonly=True,
                                                string="Accrual Amount", type="float", multi="acc_amount"),
        'total_functional_amount': fields.function(_get_accrual_amounts, method=True, store=False, readonly=True,
                                                   string="Functional Amount", type="float", multi="acc_amount"),
        'currency_id': fields.many2one('res.currency', 'Currency', required=True),
        'journal_id': fields.many2one('account.journal', 'Journal', required=True),
        'third_party_type': fields.selection([
            ('', ''),
            ('res.partner', 'Partner'),
            ('hr.employee', 'Employee'),
        ], 'Third Party', required=False),
        'partner_id': fields.many2one('res.partner', 'Third Party Partner', ondelete="restrict"),
        'employee_id': fields.many2one('hr.employee', 'Third Party Employee', ondelete="restrict"),
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
        'analytic_distribution_state': fields.function(_get_distribution_state, method=True, store=False, type='selection',
                                                       selection=[('none', 'None'), ('valid', 'Valid'),
                                                                  ('invalid', 'Invalid'), ('invalid_small_amount', 'Invalid')],
                                                       string="Distribution state"),
        'functional_currency_id': fields.many2one('res.currency', 'Functional Currency', required=True, readonly=True),
        'move_line_id': fields.many2one('account.move.line', 'Account Move Line', readonly=True),
        'rev_move_id': fields.many2one('account.move', 'Rev Journal Entry', readonly=True),
        'accrual_type': fields.selection([
            ('reversing_accrual', 'Reversing accrual'),
            ('one_time_accrual', 'One Time accrual'),
        ], 'Accrual type', required=True),
        'state': fields.selection([('draft', 'Draft'),
                                   ('done', 'Done'),
                                   ('running', 'Running'),
                                   ('cancel', 'Cancelled')], 'Status', required=True),
        # Field to store the third party's name for list view
        'third_party_name': fields.char('Third Party', size=64),
        'entry_sequence': fields.function(_get_entry_sequence, method=True,
                                          store=False, string="Number", type="char", readonly="True"),
        'expense_line_ids': fields.one2many('msf.accrual.line.expense', 'accrual_line_id', string="Accrual Expense Lines"),
        'sequence_id': fields.many2one('ir.sequence', string='Sequence of the lines', ondelete='cascade'),
    }

    _defaults = {
        'third_party_type': 'res.partner',
        'journal_id': _get_accrual_journal,
        'functional_currency_id': lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
        'state': 'draft',
        'accrual_type' : 'reversing_accrual',
    }

    _order = 'id desc'

    def _create_write_set_vals(self, cr, uid, vals, context=None):
        if context is None:
            context = {}

        employee_id = partner_id = False
        if 'third_party_type' in vals:
            if vals['third_party_type'] == 'hr.employee' and 'employee_id' in vals:
                employee_id = vals['employee_id']
                employee = self.pool.get('hr.employee').browse(cr, uid, employee_id, context=context)
                vals['third_party_name'] = employee.name
            elif vals['third_party_type'] == 'res.partner' and 'partner_id' in vals:
                partner_id = vals['partner_id']
                partner = self.pool.get('res.partner').browse(cr, uid, partner_id, context=context)
                vals['third_party_name'] = partner.name
            elif not vals['third_party_type']:
                vals['partner_id'] = False

        account_ids = []
        if vals.get('expense_account_id', False):
            account_ids.append(vals.get('expense_account_id'))
        if vals.get('accrual_account_id', False):
            account_ids.append(vals.get('accrual_account_id'))

        if 'period_id' in vals:
            period = self.pool.get('account.period').browse(cr, uid, vals['period_id'], context=context)
            vals['date'] = period.date_stop

        if 'currency_id' in vals and 'date' in vals:
            cr.execute("SELECT currency_id, name, rate FROM res_currency_rate WHERE currency_id = %s AND name <= %s ORDER BY name desc LIMIT 1" ,(vals['currency_id'], vals['date']))
            if not cr.rowcount:
                currency_name = self.pool.get('res.currency').browse(cr, uid, vals['currency_id'], context=context).name
                formatted_date = datetime.datetime.strptime(vals['date'], '%Y-%m-%d').strftime('%d/%b/%Y')
                raise osv.except_osv(_('Warning !'), _("The currency '%s' does not have any rate set for date '%s'!") % (currency_name, formatted_date))

        # US-672/2
        if not context.get('sync_update_execution', False) and account_ids:
            self.pool.get('account.account').is_allowed_for_thirdparty(cr, uid,
                                                                       account_ids, employee_id=employee_id, partner_id=partner_id,
                                                                       raise_it=True,  context=context)

    def create_sequence(self, cr, uid):
        """
        Initializes a new sequence for each Accrual (for the line number)
        """
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')
        name = 'Accrual Expense L'  # For Accrual Expense Lines
        code = 'msf.accrual.line'
        types = {
            'name': name,
            'code': code
        }
        seq_typ_pool.create(cr, uid, types)
        seq = {
            'name': name,
            'code': code,
            'prefix': '',
            'padding': 0,
        }
        return seq_pool.create(cr, uid, seq)

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}

        if 'document_date' in vals and vals.get('period_id', False):
            # US-192 check doc date regarding post date
            # => read (as date readonly in form) to get posting date:
            # is end of period
            posting_date = self.pool.get('account.period').read(cr, uid,
                                                                vals['period_id'], ['date_stop', ],
                                                                context=context)['date_stop']
            self.pool.get('finance.tools').check_document_date(cr, uid,
                                                               vals['document_date'], posting_date, context=context)

        # create a sequence for this new accrual
        seq_id = self.create_sequence(cr, uid)
        vals.update({'sequence_id': seq_id, })

        self._create_write_set_vals(cr, uid, vals, context=context)
        return super(msf_accrual_line, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if context is None:
            context = {}
        if isinstance(ids, (int, long, )):
            ids = [ids]
        self._create_write_set_vals(cr, uid, vals, context=context)
        # US-192 check doc date regarding post date
        current_values = self.read(cr, uid, ids, ['document_date', 'date'], context=context)[0]
        document_date = 'document_date' in vals and vals['document_date'] or current_values['document_date']
        posting_date = 'date' in vals and vals['date'] or current_values['date']
        self.pool.get('finance.tools').check_document_date(cr, uid, document_date, posting_date, context=context)

        return super(msf_accrual_line, self).write(cr, uid, ids, vals, context=context)

    def _check_period_state(self, cr, uid, period_id, context=None):
        """
        Raises an error in case the period is either not opened yet or already Mission-Closed or HQ-Closed.
        """
        if context is None:
            context = {}
        period = self.pool.get('account.period').browse(cr, uid, period_id, fields_to_fetch=['state', 'name'], context=context)
        if period.state not in ('draft', 'field-closed'):
            raise osv.except_osv(_('Warning !'), _("The period \"%s\" is not Open!" % (period.name,)))
        return True

    def button_cancel(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        period_obj = self.pool.get('account.period')
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        for accrual_line in self.browse(cr, uid, ids, context=context):
            # check for periods, distribution, etc.
            if accrual_line.state != 'done':
                raise osv.except_osv(_('Warning !'), _("The line \"%s\" is not Done!") % accrual_line.description)

            self._check_period_state(cr, uid, accrual_line.period_id.id, context=context)

            move_date = accrual_line.period_id.date_stop
            curr_date = currency_date.get_date(self, cr, accrual_line.document_date, move_date)
            if accrual_line.accrual_type == 'reversing_accrual':
                reversal_move_posting_date = (datetime.datetime.strptime(move_date, '%Y-%m-%d') + relativedelta(days=1)).strftime('%Y-%m-%d')
                reversal_move_document_date = (datetime.datetime.strptime(move_date, '%Y-%m-%d') + relativedelta(days=1)).strftime('%Y-%m-%d')
                reversal_period_ids = period_obj.find(cr, uid, reversal_move_posting_date, context=context)
                reversal_period_id = reversal_period_ids[0]
            else:
                reversal_move_posting_date = accrual_line.rev_move_id.date
                reversal_move_document_date = accrual_line.rev_move_id.document_date
                reversal_period_id = accrual_line.rev_move_id.period_id.id

            self._check_period_state(cr, uid, reversal_period_id, context=context)

            # Create moves
            move_vals = {
                'ref': accrual_line.reference,
                'period_id': accrual_line.period_id.id,
                'journal_id': accrual_line.journal_id.id,
                'date': move_date,
                'document_date': accrual_line.document_date,
            }
            reversal_move_vals = {
                'ref': accrual_line.reference,
                'period_id': reversal_period_id,
                'journal_id': accrual_line.journal_id.id,
                'date': reversal_move_posting_date,
                'document_date': reversal_move_document_date,
            }
            move_id = move_obj.create(cr, uid, move_vals, context=context)
            reversal_move_id = move_obj.create(cr, uid, reversal_move_vals, context=context)

            cancel_description = "CANCEL - " + accrual_line.description
            reverse_cancel_description = "CANCEL - REV - " + accrual_line.description

            # Create move lines
            booking_field = accrual_line.accrual_amount > 0 and 'debit_currency' or 'credit_currency'  # reverse of initial entry
            accrual_move_line_vals = {
                'accrual': True,
                'move_id': move_id,
                'date': move_date,
                'document_date': accrual_line.document_date,
                'journal_id': accrual_line.journal_id.id,
                'period_id': accrual_line.period_id.id,
                'reference': accrual_line.reference,
                'name': cancel_description,
                'account_id': accrual_line.accrual_account_id.id,
                'partner_id': ((accrual_line.partner_id) and accrual_line.partner_id.id) or False,
                'employee_id': ((accrual_line.employee_id) and accrual_line.employee_id.id) or False,
                booking_field: abs(accrual_line.accrual_amount),
                'currency_id': accrual_line.currency_id.id,
            }
            booking_field = accrual_line.accrual_amount > 0 and 'credit_currency' or 'debit_currency'
            expense_move_line_vals = {
                'accrual': True,
                'move_id': move_id,
                'date': move_date,
                'document_date': accrual_line.document_date,
                'journal_id': accrual_line.journal_id.id,
                'period_id': accrual_line.period_id.id,
                'reference': accrual_line.reference,
                'name': cancel_description,
                'account_id': accrual_line.expense_account_id.id,
                'partner_id': ((accrual_line.partner_id) and accrual_line.partner_id.id) or False,
                'employee_id': ((accrual_line.employee_id) and accrual_line.employee_id.id) or False,
                booking_field: abs(accrual_line.accrual_amount),
                'currency_id': accrual_line.currency_id.id,
                'analytic_distribution_id': accrual_line.analytic_distribution_id.id,
            }

            # and their reversal (source_date to keep the old change rate)
            booking_field = accrual_line.accrual_amount > 0 and 'credit_currency' or 'debit_currency'
            reversal_accrual_move_line_vals = {
                'accrual': True,
                'move_id': reversal_move_id,
                'date': reversal_move_posting_date,
                'document_date': reversal_move_document_date,
                'source_date': curr_date,  # date from the original accrual line
                'journal_id': accrual_line.journal_id.id,
                'period_id': reversal_period_id,
                'reference': accrual_line.reference,
                'name': reverse_cancel_description,
                'account_id': accrual_line.accrual_account_id.id,
                'partner_id': ((accrual_line.partner_id) and accrual_line.partner_id.id) or False,
                'employee_id': ((accrual_line.employee_id) and accrual_line.employee_id.id) or False,
                booking_field: abs(accrual_line.accrual_amount),
                'currency_id': accrual_line.currency_id.id,
            }
            booking_field = accrual_line.accrual_amount > 0 and 'debit_currency' or 'credit_currency'
            reversal_expense_move_line_vals = {
                'accrual': True,
                'move_id': reversal_move_id,
                'date': reversal_move_posting_date,
                'document_date': reversal_move_document_date,
                'source_date': curr_date,  # date from the original accrual line
                'journal_id': accrual_line.journal_id.id,
                'period_id': reversal_period_id,
                'reference': accrual_line.reference,
                'name': reverse_cancel_description,
                'account_id': accrual_line.expense_account_id.id,
                'partner_id': ((accrual_line.partner_id) and accrual_line.partner_id.id) or False,
                'employee_id': ((accrual_line.employee_id) and accrual_line.employee_id.id) or False,
                booking_field: abs(accrual_line.accrual_amount),
                'currency_id': accrual_line.currency_id.id,
                'analytic_distribution_id': accrual_line.analytic_distribution_id.id,
            }

            accrual_move_line_id = move_line_obj.create(cr, uid, accrual_move_line_vals, context=context)
            move_line_obj.create(cr, uid, expense_move_line_vals, context=context)
            reversal_accrual_move_line_id = move_line_obj.create(cr, uid, reversal_accrual_move_line_vals, context=context)
            move_line_obj.create(cr, uid, reversal_expense_move_line_vals, context=context)

            # Post the moves
            move_obj.post(cr, uid, [move_id, reversal_move_id], context=context)
            # Reconcile the accrual move line with its reversal
            move_line_obj.reconcile_partial(cr, uid, [accrual_move_line_id, reversal_accrual_move_line_id], context=context)
            # validate the accrual line
            self.write(cr, uid, [accrual_line.id], {'state': 'cancel'}, context=context)
        return True

    def copy(self, cr, uid, acc_line_id, default=None, context=None):
        """
        Duplicates the msf_accrual_line:
        - adds "(copy) " before the description
        - links the new record to a COPY of the AD from the initial record
        """
        if context is None:
            context = {}
        if default is None:
            default = {}
        acc_line_copied = self.browse(cr, uid, acc_line_id, fields_to_fetch=['description', 'analytic_distribution_id'], context=context)
        suffix = ' (copy)'  # "copy" should remain in English i.e. not translated
        description = '%s%s' % (acc_line_copied.description[:64 - len(suffix)], suffix)
        default.update({
            'description': description,
        })
        if acc_line_copied.analytic_distribution_id:
            new_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, acc_line_copied.analytic_distribution_id.id, {},
                                                                         context=context)
            if new_distrib_id:
                default.update({'analytic_distribution_id': new_distrib_id})
        return super(msf_accrual_line, self).copy(cr, uid, acc_line_id, default=default, context=context)

    def button_duplicate(self, cr, uid, ids, context=None):
        """
        Calls the copy() method so that both buttons have the same behavior
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for acc_line_id in ids:
            self.copy(cr, uid, acc_line_id, context=context)
        return True

    def button_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Opens the analytic distribution wizard on an Accrual
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        accrual_line = self.browse(cr, uid, ids[0],
                                   fields_to_fetch=['currency_id', 'expense_line_ids', 'analytic_distribution_id', 'date', 'document_date'],
                                   context=context)
        # the total amount in the AD wizard is the sum of all lines (they are all on expense accounts)
        amount = 0.0
        for line in accrual_line.expense_line_ids:
            amount += line.accrual_amount or 0.0
        # get the current AD of the header if any
        distrib_id = accrual_line.analytic_distribution_id and accrual_line.analytic_distribution_id.id or False
        vals = {
            'total_amount': amount,
            'accrual_line_id': accrual_line.id,
            'currency_id': accrual_line.currency_id.id,
            'state': 'dispatch',
            'posting_date': accrual_line.date,
            'document_date': accrual_line.document_date,
        }
        if distrib_id:
            vals.update({'distribution_id': distrib_id,})
        # create and open the wizard
        wiz_obj = self.pool.get('analytic.distribution.wizard')
        wiz_id = wiz_obj.create(cr, uid, vals, context=context)
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        return {
            'name': _('Global analytic distribution'),
            'type': 'ir.actions.act_window',
            'res_model': 'analytic.distribution.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': [wiz_id],
            'context': context,
        }

    def button_analytic_distribution_2(self, cr, uid, ids, context=None):
        """
        Alias for button_analytic_distribution (used to avoid having 2 buttons with the same name within the same view)
        """
        return self.button_analytic_distribution(cr, uid, ids, context=context)

    def button_reset_distribution(self, cr, uid, ids, context=None):
        """
        Resets the AD at line level.
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        expense_line_obj = self.pool.get('msf.accrual.line.expense')
        to_reset = expense_line_obj.search(cr, uid, [('accrual_line_id', 'in', ids)], order='NO_ORDER', context=context)
        if to_reset:
            expense_line_obj.write(cr, uid, to_reset, {'analytic_distribution_id': False}, context=context)
        return True

    def button_delete(self, cr, uid, ids, context=None):
        return self.unlink(cr, uid, ids, context=context)

    def unlink(self, cr, uid, ids, context=None):
        if not ids:
            return
        for rec in self.browse(cr, uid, ids, context=context):
            if rec.state != 'draft':
                raise osv.except_osv(_('Warning'),
                                     _('You can only delete draft accruals'))
        return super(msf_accrual_line, self).unlink(cr, uid, ids,
                                                    context=context)

    def accrual_post(self, cr, uid, ids, context=None):
        """
        Post the accrual entries without their reversal
        """
        if context is None:
            context = {}
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        if ids:
            for accrual_line in self.browse(cr, uid, ids, context=context):
                move_date = accrual_line.period_id.date_stop
                # Create moves
                move_vals = {
                    'ref': accrual_line.reference,
                    'period_id': accrual_line.period_id.id,
                    'journal_id': accrual_line.journal_id.id,
                    'document_date': accrual_line.document_date,
                    'date': move_date,
                }

                move_id = move_obj.create(cr, uid, move_vals, context=context)

                # Create move lines
                booking_field = accrual_line.accrual_amount > 0 and 'credit_currency' or 'debit_currency'
                accrual_move_line_vals = {
                    'accrual': True,
                    'move_id': move_id,
                    'date': move_date,
                    'document_date': accrual_line.document_date,
                    'journal_id': accrual_line.journal_id.id,
                    'period_id': accrual_line.period_id.id,
                    'reference': accrual_line.reference,
                    'name': accrual_line.description,
                    'account_id': accrual_line.accrual_account_id.id,
                    'partner_id': ((accrual_line.partner_id) and accrual_line.partner_id.id) or False,
                    'employee_id': ((accrual_line.employee_id) and accrual_line.employee_id.id) or False,
                    booking_field: abs(accrual_line.accrual_amount),
                    'currency_id': accrual_line.currency_id.id,
                }
                # negative amount for expense would result in an opposite
                # behavior, expense in credit and a accrual in debit for the
                # initial entry
                booking_field = accrual_line.accrual_amount > 0 and 'debit_currency' or 'credit_currency'
                expense_move_line_vals = {
                    'accrual': True,
                    'move_id': move_id,
                    'date': move_date,
                    'document_date': accrual_line.document_date,
                    'journal_id': accrual_line.journal_id.id,
                    'period_id': accrual_line.period_id.id,
                    'reference': accrual_line.reference,
                    'name': accrual_line.description,
                    'account_id': accrual_line.expense_account_id.id,
                    'partner_id': ((accrual_line.partner_id) and accrual_line.partner_id.id) or False,
                    'employee_id': ((accrual_line.employee_id) and accrual_line.employee_id.id) or False,
                    booking_field: abs(accrual_line.accrual_amount),
                    'currency_id': accrual_line.currency_id.id,
                    'analytic_distribution_id': accrual_line.analytic_distribution_id.id,
                }

                accrual_move_line_id = move_line_obj.create(cr, uid, accrual_move_line_vals, context=context)
                move_line_obj.create(cr, uid, expense_move_line_vals, context=context)

                # Post the moves
                move_obj.post(cr, uid, move_id, context=context)

                # validate the accrual line
                if accrual_line.accrual_type == 'one_time_accrual':
                    status = 'running'
                else:
                    status = 'done'
                self.write(cr, uid, [accrual_line.id], {'state': status, 'move_line_id': accrual_move_line_id}, context=context)

    def accrual_reversal_post(self, cr, uid, ids, document_date, posting_date, context=None):
        """
        Reverse the selected accruals
        """
        if context is None:
            context = {}
        period_obj = self.pool.get('account.period')
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')

        if ids:
            for accrual_line in self.browse(cr, uid, ids, context=context):
                move_date = accrual_line.period_id.date_stop
                curr_date = currency_date.get_date(self, cr, accrual_line.document_date, move_date)

                reversal_period_ids = period_obj.find(cr, uid, posting_date, context=context)
                reversal_period_id = reversal_period_ids[0]

                self._check_period_state(cr, uid, reversal_period_id, context=context)

                reversal_move_vals = {
                    'ref': accrual_line.reference,
                    'period_id': reversal_period_id,
                    'journal_id': accrual_line.journal_id.id,
                    'date': posting_date,
                    'document_date': document_date,
                }

                reversal_move_id = move_obj.create(cr, uid, reversal_move_vals, context=context)

                reversal_description = "REV - " + accrual_line.description

                # Create move lines / reversal entry (source_date to keep the old change rate):
                booking_field = accrual_line.accrual_amount > 0 and 'debit_currency' or 'credit_currency'
                reversal_accrual_move_line_vals = {
                    'accrual': True,
                    'move_id': reversal_move_id,
                    'date': posting_date,
                    'document_date': document_date,
                    'source_date': curr_date,  # date from the original accrual line
                    'journal_id': accrual_line.journal_id.id,
                    'period_id': reversal_period_id,
                    'reference': accrual_line.reference,
                    'name': reversal_description,
                    'account_id': accrual_line.accrual_account_id.id,
                    'partner_id': ((accrual_line.partner_id) and accrual_line.partner_id.id) or False,
                    'employee_id': ((accrual_line.employee_id) and accrual_line.employee_id.id) or False,
                    booking_field: abs(accrual_line.accrual_amount),
                    'currency_id': accrual_line.currency_id.id,
                }
                booking_field = accrual_line.accrual_amount > 0 and 'credit_currency' or 'debit_currency'
                reversal_expense_move_line_vals = {
                    'accrual': True,
                    'move_id': reversal_move_id,
                    'date': posting_date,
                    'document_date': document_date,
                    'source_date': curr_date,
                    'journal_id': accrual_line.journal_id.id,
                    'period_id': reversal_period_id,
                    'reference': accrual_line.reference,
                    'name': reversal_description,
                    'account_id': accrual_line.expense_account_id.id,
                    'partner_id': ((accrual_line.partner_id) and accrual_line.partner_id.id) or False,
                    'employee_id': ((accrual_line.employee_id) and accrual_line.employee_id.id) or False,
                    booking_field: abs(accrual_line.accrual_amount),
                    'currency_id': accrual_line.currency_id.id,
                    'analytic_distribution_id': accrual_line.analytic_distribution_id.id,
                }

                reversal_accrual_move_line_id = move_line_obj.create(cr, uid, reversal_accrual_move_line_vals, context=context)
                move_line_obj.create(cr, uid, reversal_expense_move_line_vals, context=context)

                # Post the moves
                move_obj.post(cr, uid, reversal_move_id, context=context)

                # Reconcile the accrual move line with its reversal
                move_line_obj.reconcile_partial(cr, uid, [accrual_line.move_line_id.id, reversal_accrual_move_line_id], context=context)

                # Change the status to "Done"
                self.write(cr, uid, [accrual_line.id], {'state': 'done', 'rev_move_id': reversal_move_id}, context=context)

msf_accrual_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
