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
from base import currency_date


class msf_accrual_line(osv.osv):
    # this object actually corresponds to the "Accruals" and not to their lines...
    _name = 'msf.accrual.line'
    _rec_name = 'date'
    _trace = True

    def onchange_period(self, cr, uid, ids, period_id, context=None):
        if period_id is False:
            return {'value': {'date': False}}
        else:
            period = self.pool.get('account.period').browse(cr, uid, period_id, context=context)
            return {'value': {'date': period.date_stop, 'document_date': period.date_stop}}

    def _get_accrual_amounts(self, cr, uid, ids, fields, arg, context=None):
        """
        Computes the values for "fields.function" fields, retrieving the sum of the Accrual amounts of all lines:
        - in booking curr. => total_accrual_amount
        - in functional curr. => total_functional_amount
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
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
        if isinstance(ids, int):
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

    def _get_move_line_ids(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Gets the JIs linked to the original Accrual, and the automatic REV and CANCEL entries (if any)
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        res = {}
        ml_obj = self.pool.get('account.move.line')
        for acc_id in ids:
            res[acc_id] = ml_obj.search(cr, uid, [('accrual_line_id', '=', acc_id)], order='move_id', context=context)
        return res

    def import_accrual(self, cr, uid, ids, data, context=None):
        """
        Opens the Import Accrual Lines wizard
        """
        if isinstance(ids, int):
            ids = [ids]
        wiz_id = self.pool.get('msf.accrual.import').create(cr, uid, {'accrual_id': ids[0]}, context=context)
        return {
            'name': _('Import Accrual Lines'),
            'type': 'ir.actions.act_window',
            'res_model': 'msf.accrual.import',
            'target': 'new',
            'view_mode': 'form,tree',
            'view_type': 'form',
            'res_id': [wiz_id],
        }

    _columns = {
        'date': fields.date("Date"),
        'document_date': fields.date("Document Date", required=True),
        'period_id': fields.many2one('account.period', 'Period', required=True, domain=[('state', '=', 'draft'), ('is_system', '=', False)]),
        'description': fields.char('Description', size=64, required=True),
        'reference': fields.char('Reference', size=64),
        'expense_account_id': fields.many2one('account.account', 'Expense Account (deprecated)',
                                              domain=[('type', '!=', 'view'), ('user_type_code', '=', 'expense')]),
        'accrual_account_id': fields.many2one('account.account', 'Accrual Account', required=True,
                                              domain=[('restricted_area', '=', 'accruals_accrual')]),
        'accrual_amount': fields.float('Accrual Amount (deprecated)'),
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
        'move_line_ids': fields.function(_get_move_line_ids, type='one2many', obj='account.move.line', method=True,
                                         store=False, string='Journal Items'),
        'rev_move_id': fields.many2one('account.move', 'Rev Journal Entry', readonly=True),
        'accrual_type': fields.selection([
            ('reversing_accrual', 'Reversing accrual'),
            ('one_time_accrual', 'One Time accrual'),
        ], 'Accrual type', required=True),
        'state': fields.selection([('draft', 'Draft'),
                                   ('done', 'Done'),
                                   ('running', 'Running'),
                                   ('cancel', 'Cancelled')], "State", required=True),
        # Field to store the third party's name for list view
        'third_party_name': fields.char('Third Party', size=64),
        'entry_sequence': fields.char("Number", size=64, readonly=True),
        'expense_line_ids': fields.one2many('msf.accrual.line.expense', 'accrual_line_id', string="Accrual Expense Lines"),
        'sequence_id': fields.many2one('ir.sequence', string='Sequence of the lines', ondelete='cascade'),
        'order_accrual': fields.date("Custom sort field"),  # US-9999
    }

    _defaults = {
        'third_party_type': lambda *a: 'res.partner',
        'journal_id': _get_accrual_journal,
        'functional_currency_id': lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
        'state': lambda *a: 'draft',
        'accrual_type': lambda *a: 'reversing_accrual',
        'entry_sequence': lambda *a: '',
    }

    _order = 'order_accrual desc, entry_sequence desc, id desc'

    def _create_write_set_vals(self, cr, uid, vals, context=None):
        if context is None:
            context = {}

        if 'third_party_type' in vals:
            # set the third_party_name
            if vals['third_party_type'] == 'hr.employee' and 'employee_id' in vals:
                employee_id = vals['employee_id']
                employee = self.pool.get('hr.employee').browse(cr, uid, employee_id, context=context)
                vals['third_party_name'] = employee.name
            elif vals['third_party_type'] == 'res.partner' and 'partner_id' in vals:
                partner_id = vals['partner_id']
                partner = self.pool.get('res.partner').browse(cr, uid, partner_id, context=context)
                vals['third_party_name'] = partner.name
            elif vals['third_party_type'] not in ('res.partner', 'hr.employee'):
                vals['third_party_name'] = False

        if 'period_id' in vals:
            period = self.pool.get('account.period').browse(cr, uid, vals['period_id'], context=context)
            vals['date'] = period.date_stop

        if 'currency_id' in vals and 'date' in vals:
            cr.execute("SELECT currency_id, name, rate FROM res_currency_rate WHERE currency_id = %s AND name <= %s ORDER BY name desc LIMIT 1" ,(vals['currency_id'], vals['date']))
            if not cr.rowcount:
                currency_name = self.pool.get('res.currency').browse(cr, uid, vals['currency_id'], context=context).name
                formatted_date = datetime.datetime.strptime(vals['date'], '%Y-%m-%d').strftime('%d/%b/%Y')
                raise osv.except_osv(_('Warning !'), _("The currency '%s' does not have any rate set for date '%s'!") % (currency_name, formatted_date))

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

    def _clean_third_party_fields(self, cr, uid, vals, accrual_id=None, context=None):
        """
        Removes the irrelevant third party links from the dict vals. E.g.: create an Accrual with a Third Party Employee,
        then change it to a Partner => the link to the Employee should be removed.
        """
        if context is None:
            context = {}
        if 'third_party_type' in vals:
            third_party_type = vals['third_party_type']
        elif accrual_id:
            third_party_type = self.browse(cr, uid, accrual_id, fields_to_fetch=['third_party_type'], context=context).third_party_type
        else:
            third_party_type = None
        if third_party_type is not None and not third_party_type:
            vals.update({'partner_id': False,
                         'employee_id': False,
                         })
        elif third_party_type == 'res.partner':
            vals.update({'employee_id': False, })
        elif third_party_type == 'hr.employee':
            vals.update({'partner_id': False, })
        return True

    def _check_account_compat(self, cr, uid, accrual_line_ids, context=None):
        """
        Raises an error in case the accrual account OR the expense account of one of the lines is not compatible with
        the Third Party selected (note that Accruals aren't synchronized, so no need to check the sync_update_execution value).
        Example UC: modify the Third Party after the creation of the lines, the new Third Party must be compatible with
        the already selected accounts.
        """
        if context is None:
            context = {}
        if isinstance(accrual_line_ids, int):
            accrual_line_ids = [accrual_line_ids]
        account_obj = self.pool.get('account.account')
        for accrual in self.browse(cr, uid, accrual_line_ids,
                                   fields_to_fetch=['accrual_account_id', 'expense_line_ids', 'employee_id', 'partner_id'],
                                   context=context):
            account_ids = set([accrual.accrual_account_id.id] + [expl.expense_account_id.id for expl in accrual.expense_line_ids])
            employee_id = accrual.employee_id and accrual.employee_id.id or False
            partner_id = accrual.partner_id and accrual.partner_id.id or False
            account_obj.is_allowed_for_thirdparty(cr, uid, list(account_ids), employee_id=employee_id, partner_id=partner_id,
                                                  raise_it=True, context=context)
            account_obj.check_type_for_specific_treatment(cr, uid, list(account_ids), partner_id=partner_id,
                                                          employee_id=employee_id, context=context)
        return True

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
            # US-9999: create order_accrual column for custom sort of accruals lines
            vals.update({'order_accrual': vals['document_date']})
        # create a sequence for this new accrual
        seq_id = self.create_sequence(cr, uid)
        vals.update({'sequence_id': seq_id, })

        self._create_write_set_vals(cr, uid, vals, context=context)
        self._clean_third_party_fields(cr, uid, vals, context=context)
        accrual_line_id = super(msf_accrual_line, self).create(cr, uid, vals, context=context)
        self._check_account_compat(cr, uid, accrual_line_id, context=context)
        return accrual_line_id

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        self._create_write_set_vals(cr, uid, vals, context=context)
        for accrual_id in ids:
            self._clean_third_party_fields(cr, uid, vals, accrual_id=accrual_id, context=context)
        # US-192 check doc date regarding post date
        current_values = self.read(cr, uid, ids, ['document_date', 'date', 'state'], context=context)[0]
        document_date = 'document_date' in vals and vals['document_date'] or current_values['document_date']
        posting_date = 'date' in vals and vals['date'] or current_values['date']
        changing_state = 'state' in vals and vals['state'] != 'draft' or False
        self.pool.get('finance.tools').check_document_date(cr, uid, document_date, posting_date, context=context)
        # US-9999: create order_accrual column for custom sort of accruals lines
        if document_date:
            if not changing_state and current_values['state'] == 'draft':
                vals.update({'order_accrual': document_date})
            else:
                vals.update({'order_accrual': '1901-01-01'})
        res = super(msf_accrual_line, self).write(cr, uid, ids, vals, context=context)
        self._check_account_compat(cr, uid, ids, context=context)
        return res

    def _check_period_state(self, cr, uid, period_id, context=None):
        """
        Raises an error in case the period is not Open
        """
        if context is None:
            context = {}
        period = self.pool.get('account.period').browse(cr, uid, period_id, fields_to_fetch=['state', 'name'], context=context)
        if period.state != 'draft':
            raise osv.except_osv(_('Warning'), _("The period \"%s\" is not Open!") % (period.name,))
        return True

    def button_cancel(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        ad_obj = self.pool.get('analytic.distribution')
        for accrual_line in self.browse(cr, uid, ids, context=context):
            if accrual_line.state != 'done':
                raise osv.except_osv(_('Warning'), _("The Accrual \"%s\" is not Done!") % accrual_line.description)
            if not accrual_line.rev_move_id:
                raise osv.except_osv(_('Warning'), _("Impossible to find the reversal entry to cancel: "
                                                     "please check if the lines have been reconciled manually."))
            self._check_period_state(cr, uid, accrual_line.period_id.id, context=context)

            move_date = accrual_line.period_id.date_stop
            curr_date = currency_date.get_date(self, cr, accrual_line.document_date, move_date)
            reversal_move_posting_date = accrual_line.rev_move_id.date
            reversal_move_document_date = accrual_line.rev_move_id.document_date
            reversal_period_id = accrual_line.rev_move_id.period_id.id
            self._check_period_state(cr, uid, reversal_period_id, context=context)

            # Create moves
            # the original ref is kept as is without prefix
            move_vals = {
                'ref': accrual_line.reference,
                'period_id': accrual_line.period_id.id,
                'journal_id': accrual_line.journal_id.id,
                'date': move_date,
                'document_date': accrual_line.document_date,
                'analytic_distribution_id': accrual_line.analytic_distribution_id and ad_obj.copy(cr, uid,
                                                                                                  accrual_line.analytic_distribution_id.id,
                                                                                                  {},
                                                                                                  context=context) or False,
            }
            move_id = move_obj.create(cr, uid, move_vals, context=context)

            reversal_move_vals = {
                'ref': accrual_line.reference,
                'period_id': reversal_period_id,
                'journal_id': accrual_line.journal_id.id,
                'date': reversal_move_posting_date,
                'document_date': reversal_move_document_date,
                # note: for Accruals Done before US-5722 and Cancelled after, the AD will be at line level in the
                # original entries and at header level in the cancellation entries but AJIs will still be consistent
                'analytic_distribution_id': accrual_line.analytic_distribution_id and ad_obj.copy(cr, uid,
                                                                                                  accrual_line.analytic_distribution_id.id,
                                                                                                  {},
                                                                                                  context=context) or False,
            }
            reversal_move_id = move_obj.create(cr, uid, reversal_move_vals, context=context)

            # create the move line...
            booking_field_cancel = accrual_line.total_accrual_amount > 0 and 'debit_currency' or 'credit_currency'  # reverse of initial entry
            accrual_move_line_vals = {
                'accrual': True,
                'accrual_line_id': accrual_line.id,
                'move_id': move_id,
                # same dates as the original accrual = same FX rate
                'date': move_date,
                'document_date': accrual_line.document_date,
                'journal_id': accrual_line.journal_id.id,
                'period_id': accrual_line.period_id.id,
                'reference': accrual_line.reference,
                'name': "CANCEL - %s" % accrual_line.description,
                'account_id': accrual_line.accrual_account_id.id,
                'partner_id': accrual_line.partner_id and accrual_line.partner_id.id or False,
                'employee_id': accrual_line.employee_id and accrual_line.employee_id.id or False,
                booking_field_cancel: abs(accrual_line.total_accrual_amount or 0.0),
                'currency_id': accrual_line.currency_id.id,
            }
            accrual_move_line_id = move_line_obj.create(cr, uid, accrual_move_line_vals, context=context)

            # ...and its reversal (use the source_date to keep the original FX rate)
            booking_field_rev = accrual_line.total_accrual_amount > 0 and 'credit_currency' or 'debit_currency'
            reversal_accrual_move_line_vals = {
                'accrual': True,
                'accrual_line_id': accrual_line.id,
                'move_id': reversal_move_id,
                'date': reversal_move_posting_date,
                'document_date': reversal_move_document_date,
                'source_date': curr_date,  # date from the original accrual line
                'journal_id': accrual_line.journal_id.id,
                'period_id': reversal_period_id,
                'reference': accrual_line.reference,
                'name': "CANCEL - REV - %s" % accrual_line.description,
                'account_id': accrual_line.accrual_account_id.id,
                'partner_id': accrual_line.partner_id and accrual_line.partner_id.id or False,
                'employee_id': accrual_line.employee_id and accrual_line.employee_id.id or False,
                booking_field_rev: abs(accrual_line.total_accrual_amount or 0.0),
                'currency_id': accrual_line.currency_id.id,
            }
            reversal_accrual_move_line_id = move_line_obj.create(cr, uid, reversal_accrual_move_line_vals, context=context)

            # create the expense lines
            booking_field_cancel_exp = accrual_line.total_accrual_amount > 0 and 'credit_currency' or 'debit_currency'
            booking_field_rev_exp = accrual_line.total_accrual_amount > 0 and 'debit_currency' or 'credit_currency'
            for expense_line in accrual_line.expense_line_ids:
                expense_move_line_vals = {
                    'accrual': True,
                    'accrual_line_id': accrual_line.id,
                    'move_id': move_id,
                    # same dates as the original accrual = same FX rate
                    'date': move_date,
                    'document_date': accrual_line.document_date,
                    'journal_id': accrual_line.journal_id.id,
                    'period_id': accrual_line.period_id.id,
                    'reference': expense_line.reference or '',
                    'name': "CANCEL - %s" % expense_line.description,
                    'account_id': expense_line.expense_account_id.id,
                    'partner_id': accrual_line.partner_id and accrual_line.partner_id.id or False,
                    'employee_id': accrual_line.employee_id and accrual_line.employee_id.id or False,
                    booking_field_cancel_exp: abs(expense_line.accrual_amount or 0.0),
                    'currency_id': accrual_line.currency_id.id,
                    'analytic_distribution_id': expense_line.analytic_distribution_id and
                    ad_obj.copy(cr, uid, expense_line.analytic_distribution_id.id, {},
                                context=context) or False,
                }
                move_line_obj.create(cr, uid, expense_move_line_vals, context=context)

                reversal_expense_move_line_vals = {
                    'accrual': True,
                    'accrual_line_id': accrual_line.id,
                    'move_id': reversal_move_id,
                    'date': reversal_move_posting_date,
                    'document_date': reversal_move_document_date,
                    'source_date': curr_date,  # date from the original accrual line
                    'journal_id': accrual_line.journal_id.id,
                    'period_id': reversal_period_id,
                    'reference': expense_line.reference or '',
                    'name': "CANCEL - REV - %s" % expense_line.description,
                    'account_id': expense_line.expense_account_id.id,
                    'partner_id': accrual_line.partner_id and accrual_line.partner_id.id or False,
                    'employee_id': accrual_line.employee_id and accrual_line.employee_id.id or False,
                    booking_field_rev_exp: abs(expense_line.accrual_amount or 0.0),
                    'currency_id': accrual_line.currency_id.id,
                    'analytic_distribution_id': expense_line.analytic_distribution_id and
                    ad_obj.copy(cr, uid, expense_line.analytic_distribution_id.id, {},
                                context=context) or False,
                }
                move_line_obj.create(cr, uid, reversal_expense_move_line_vals, context=context)

            # Post the moves
            move_obj.post(cr, uid, [move_id, reversal_move_id], context=context)
            # Reconcile the accrual move line with its reversal
            move_line_obj.reconcile_partial(cr, uid, [accrual_move_line_id, reversal_accrual_move_line_id], context=context)
            # set the accrual line as Cancelled
            self.write(cr, uid, [accrual_line.id], {'state': 'cancel'}, context=context)
        return True

    def copy(self, cr, uid, acc_line_id, default=None, context=None):
        """
        Duplicates the msf_accrual_line:
        - adds " (copy)" after the description
        - links the new record to a COPY of the AD from the initial record
        - resets the links to JI, JE...
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
            'move_line_id': False,
            'entry_sequence': '',
            'sequence_id': False,
            'rev_move_id': False,
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
        if isinstance(ids, int):
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
        if isinstance(ids, int):
            ids = [ids]
        accrual_line = self.browse(cr, uid, ids[0],
                                   fields_to_fetch=['currency_id', 'expense_line_ids', 'analytic_distribution_id', 'date', 'document_date'],
                                   context=context)
        # the total amount in the AD wizard is the sum of all lines (they are all on expense accounts)
        amount = 0.0
        for expense_line in accrual_line.expense_line_ids:
            amount += expense_line.accrual_amount or 0.0
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
        if isinstance(ids, int):
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
                                     _('You can only delete draft accruals.'))
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
        ad_obj = self.pool.get('analytic.distribution')
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
                    'analytic_distribution_id': accrual_line.analytic_distribution_id and ad_obj.copy(cr, uid,
                                                                                                      accrual_line.analytic_distribution_id.id,
                                                                                                      {}, context=context) or False,
                }
                move_id = move_obj.create(cr, uid, move_vals, context=context)

                # Create move lines
                booking_field = accrual_line.total_accrual_amount > 0 and 'credit_currency' or 'debit_currency'
                accrual_move_line_vals = {
                    'accrual': True,
                    'accrual_line_id': accrual_line.id,
                    'move_id': move_id,
                    'date': move_date,
                    'document_date': accrual_line.document_date,
                    'journal_id': accrual_line.journal_id.id,
                    'period_id': accrual_line.period_id.id,
                    'reference': accrual_line.reference,
                    'name': accrual_line.description,
                    'account_id': accrual_line.accrual_account_id.id,
                    'partner_id': accrual_line.partner_id and accrual_line.partner_id.id or False,
                    'employee_id': accrual_line.employee_id and accrual_line.employee_id.id or False,
                    booking_field: abs(accrual_line.total_accrual_amount or 0.0),
                    'currency_id': accrual_line.currency_id.id,
                }
                accrual_move_line_id = move_line_obj.create(cr, uid, accrual_move_line_vals, context=context)

                # negative amount for expense would result in an opposite behavior, expense in credit and
                # an accrual in debit for the initial entry
                booking_field_exp = accrual_line.total_accrual_amount > 0 and 'debit_currency' or 'credit_currency'
                for expense_line in accrual_line.expense_line_ids:
                    expense_move_line_vals = {
                        'accrual': True,
                        'accrual_line_id': accrual_line.id,
                        'move_id': move_id,
                        'date': move_date,
                        'document_date': accrual_line.document_date,
                        'journal_id': accrual_line.journal_id.id,
                        'period_id': accrual_line.period_id.id,
                        'reference': expense_line.reference or '',
                        'name': expense_line.description,
                        'account_id': expense_line.expense_account_id.id,
                        'partner_id': accrual_line.partner_id and accrual_line.partner_id.id or False,
                        'employee_id': accrual_line.employee_id and accrual_line.employee_id.id or False,
                        booking_field_exp: abs(expense_line.accrual_amount or 0.0),
                        'currency_id': accrual_line.currency_id.id,
                        'analytic_distribution_id': expense_line.analytic_distribution_id and
                        ad_obj.copy(cr, uid, expense_line.analytic_distribution_id.id, {},
                                    context=context) or False,

                    }
                    move_line_obj.create(cr, uid, expense_move_line_vals, context=context)

                # Post the moves
                move_obj.post(cr, uid, move_id, context=context)

                # validate the accrual line and set its entry_sequence
                if accrual_line.accrual_type == 'one_time_accrual':
                    status = 'running'
                else:
                    status = 'done'
                entry_seq = move_obj.read(cr, uid, move_id, ['name'], context=context)['name'] or ''
                self.write(cr, uid, [accrual_line.id],
                           {'state': status,
                            'move_line_id': accrual_move_line_id,
                            'entry_sequence': entry_seq},
                           context=context)

    def accrual_reversal_post(self, cr, uid, ids, document_date, posting_date, reversal_period_id, context=None):
        """
        Reverse the selected accruals
        """
        if context is None:
            context = {}
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        ad_obj = self.pool.get('analytic.distribution')

        if ids:
            for accrual_line in self.browse(cr, uid, ids, context=context):
                move_date = accrual_line.period_id.date_stop
                curr_date = currency_date.get_date(self, cr, accrual_line.document_date, move_date)

                reversal_move_vals = {
                    'ref': accrual_line.reference,  # the original ref is kept as is without prefix REV
                    'period_id': reversal_period_id,
                    'journal_id': accrual_line.journal_id.id,
                    'date': posting_date,
                    'document_date': document_date,
                    # note: for Accruals running before US-5722 and posted after, the AD will be at line level in the
                    # original entry and at header level in the REV entry but AJIs will still be consistent
                    'analytic_distribution_id': accrual_line.analytic_distribution_id and ad_obj.copy(cr, uid,
                                                                                                      accrual_line.analytic_distribution_id.id,
                                                                                                      {},
                                                                                                      context=context) or False,
                }

                reversal_move_id = move_obj.create(cr, uid, reversal_move_vals, context=context)

                # Create move lines for the reversal entry (use the source_date to keep the original FX rate):
                booking_field = accrual_line.total_accrual_amount > 0 and 'debit_currency' or 'credit_currency'
                reversal_accrual_move_line_vals = {
                    'accrual': True,
                    'accrual_line_id': accrual_line.id,
                    'move_id': reversal_move_id,
                    'date': posting_date,
                    'document_date': document_date,
                    'source_date': curr_date,  # date from the original accrual line
                    'journal_id': accrual_line.journal_id.id,
                    'period_id': reversal_period_id,
                    'reference': accrual_line.reference,
                    'name': "REV - %s" % accrual_line.description,
                    'account_id': accrual_line.accrual_account_id.id,
                    'partner_id': accrual_line.partner_id and accrual_line.partner_id.id or False,
                    'employee_id': accrual_line.employee_id and accrual_line.employee_id.id or False,
                    booking_field: abs(accrual_line.total_accrual_amount or 0.0),
                    'currency_id': accrual_line.currency_id.id,
                }
                reversal_accrual_move_line_id = move_line_obj.create(cr, uid, reversal_accrual_move_line_vals, context=context)

                booking_field_exp = accrual_line.total_accrual_amount > 0 and 'credit_currency' or 'debit_currency'
                for expense_line in accrual_line.expense_line_ids:
                    reversal_expense_move_line_vals = {
                        'accrual': True,
                        'accrual_line_id': accrual_line.id,
                        'move_id': reversal_move_id,
                        'date': posting_date,
                        'document_date': document_date,
                        'source_date': curr_date,
                        'journal_id': accrual_line.journal_id.id,
                        'period_id': reversal_period_id,
                        'reference': expense_line.reference or '',
                        'name': "REV - %s" % expense_line.description,
                        'account_id': expense_line.expense_account_id.id,
                        'partner_id': accrual_line.partner_id and accrual_line.partner_id.id or False,
                        'employee_id': accrual_line.employee_id and accrual_line.employee_id.id or False,
                        booking_field_exp: abs(expense_line.accrual_amount or 0.0),
                        'currency_id': accrual_line.currency_id.id,
                        'analytic_distribution_id': expense_line.analytic_distribution_id and
                        ad_obj.copy(cr, uid, expense_line.analytic_distribution_id.id, {},
                                    context=context) or False,
                    }
                    move_line_obj.create(cr, uid, reversal_expense_move_line_vals, context=context)

                # Post the moves
                move_obj.post(cr, uid, reversal_move_id, context=context)

                # Reconcile the accrual move line with its reversal
                if accrual_line.move_line_id:
                    if accrual_line.move_line_id.reconcile_id or accrual_line.move_line_id.reconcile_partial_id:
                        raise osv.except_osv(_('Warning'), _('The line %s is already included into the reconciliation %s.') %
                                             (accrual_line.entry_sequence or '', accrual_line.move_line_id.reconcile_txt or ''))
                    move_line_obj.reconcile_partial(cr, uid, [accrual_line.move_line_id.id, reversal_accrual_move_line_id], context=context)

                # Change the status to "Done"
                self.write(cr, uid, [accrual_line.id], {'state': 'done', 'rev_move_id': reversal_move_id}, context=context)


msf_accrual_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
