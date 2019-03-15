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

class msf_accrual_line(osv.osv):
    _name = 'msf.accrual.line'
    _rec_name = 'date'

    def onchange_period(self, cr, uid, ids, period_id, context=None):
        if period_id is False:
            return {'value': {'date': False}}
        else:
            period = self.pool.get('account.period').browse(cr, uid, period_id, context=context)
            return {'value': {'date': period.date_stop, 'document_date': period.date_stop}}

    def _get_functional_amount(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for accrual_line in self.browse(cr, uid, ids, context=context):
            date_context = {'date': accrual_line.document_date}
            res[accrual_line.id] =  self.pool.get('res.currency').compute(cr,
                                                                          uid,
                                                                          accrual_line.currency_id.id,
                                                                          accrual_line.functional_currency_id.id, 
                                                                          accrual_line.accrual_amount or 0.0,
                                                                          round=True,
                                                                          context=date_context)
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

    _columns = {
        'date': fields.date("Date"),
        'document_date': fields.date("Document Date", required=True),
        'period_id': fields.many2one('account.period', 'Period', required=True, domain=[('state', '=', 'draft'), ('is_system', '=', False)]),
        'description': fields.char('Description', size=64, required=True),
        'reference': fields.char('Reference', size=64),
        'expense_account_id': fields.many2one('account.account', 'Expense Account', required=True, domain=[('type', '!=', 'view'), ('user_type_code', '=', 'expense')]),
        'accrual_account_id': fields.many2one('account.account', 'Accrual Account', required=True, domain=[('type', '!=', 'view'), ('user_type_code', 'in', ['receivables', 'payables', 'debt'])]),
        'accrual_amount': fields.float('Accrual Amount', required=True),
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
        'functional_amount': fields.function(_get_functional_amount, method=True, store=False, string="Functional Amount", type="float", readonly="True"),
        'functional_currency_id': fields.many2one('res.currency', 'Functional Currency', required=True, readonly=True),
        'move_line_id': fields.many2one('account.move.line', 'Account Move Line', readonly=True),
        'rev_move_id': fields.many2one('account.move', 'Rev Journal Entry', readonly=True),
        'accrual_type': fields.selection([
            ('reversing_accrual', 'Reversing accrual'),
            ('one_time_accrual', 'One Time accrual'),
        ], 'Accrual type', required=True),
        'state': fields.selection([('draft', 'Draft'),
                                   ('posted', 'Posted'),
                                   ('partially_posted', 'Partially posted'),
                                   ('cancel', 'Cancelled')], 'Status', required=True),
        # Field to store the third party's name for list view
        'third_party_name': fields.char('Third Party', size=64),
        'entry_sequence': fields.function(_get_entry_sequence, method=True,
                                          store=False, string="Number", type="char", readonly="True"),
    }

    _defaults = {
        'third_party_type': 'res.partner',
        'journal_id': lambda self,cr,uid,c: self.pool.get('account.journal').search(cr, uid, [('type', '=', 'accrual'),
                                                                                              ('is_current_instance', '=', True)])[0],
        'functional_currency_id': lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
        'state': 'draft',
        'accrual_type' : 'reversing_accrual',
    }

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
            if accrual_line.state != 'posted':
                raise osv.except_osv(_('Warning !'), _("The line '%s' is already posted!") % accrual_line.description)

            # US-770/1
            if accrual_line.period_id.state not in ('draft', 'field-closed'):
                raise osv.except_osv(_('Warning !'), _("The period '%s' is not open!" % accrual_line.period_id.name))

            move_date = accrual_line.period_id.date_stop
            if accrual_line.accrual_type == 'reversing_accrual':
                reversal_move_posting_date = (datetime.datetime.strptime(move_date, '%Y-%m-%d') + relativedelta(days=1)).strftime('%Y-%m-%d')
                reversal_move_document_date = (datetime.datetime.strptime(move_date, '%Y-%m-%d') + relativedelta(days=1)).strftime('%Y-%m-%d')
                reversal_period_ids = period_obj.find(cr, uid, reversal_move_posting_date, context=context)
                reversal_period_id = reversal_period_ids[0]
            else:
                reversal_move_posting_date = accrual_line.rev_move_id.date
                reversal_move_document_date = accrual_line.rev_move_id.document_date
                reversal_period_id = accrual_line.rev_move_id.period_id.id

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
                'source_date': move_date,
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
                'source_date': move_date,
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

    def button_duplicate(self, cr, uid, ids, context=None):
        """
        Copy given lines and delete all links
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Browse lines
        for line in self.browse(cr, uid, ids, context=context):
            default_vals = ({
                'description': '(copy) ' + line.description,
            })
            if line.analytic_distribution_id:
                # the distribution must be copied, not just the id
                new_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, line.analytic_distribution_id.id, {}, context=context)
                if new_distrib_id:
                    default_vals.update({'analytic_distribution_id': new_distrib_id})
            self.copy(cr, uid, line.id, default_vals, context=context)
        return True

    def button_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Launch analytic distribution wizard on an invoice line
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        accrual_line = self.browse(cr, uid, ids[0], context=context)
        # Search elements for currency
        currency = accrual_line.currency_id and accrual_line.currency_id.id
        # Get analytic distribution id from this line
        distrib_id = accrual_line and accrual_line.analytic_distribution_id and accrual_line.analytic_distribution_id.id or False
        # Prepare values for wizard
        vals = {
            'total_amount': accrual_line.accrual_amount or 0.0,
            'accrual_line_id': accrual_line.id,
            'currency_id': currency or False,
            'state': 'dispatch',
            'account_id': accrual_line.expense_account_id and accrual_line.expense_account_id.id or False,
            'posting_date': accrual_line.date,
            'document_date': accrual_line.document_date,
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
            'from_accrual_line': True
        })
        # Open it!
        return {
            'name': _('Analytic distribution'),
            'type': 'ir.actions.act_window',
            'res_model': 'analytic.distribution.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': [wiz_id],
            'context': context,
        }

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
                    status = 'partially_posted'
                else:
                    status = 'posted'
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

                reversal_period_ids = period_obj.find(cr, uid, posting_date, context=context)
                reversal_period_id = reversal_period_ids[0]

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
                    'source_date': move_date,
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
                    'source_date': move_date,
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

                # Change the status to "Posted"
                self.write(cr, uid, [accrual_line.id], {'state': 'posted', 'rev_move_id': reversal_move_id}, context=context)

msf_accrual_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
