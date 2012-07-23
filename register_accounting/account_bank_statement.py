#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    All Rigts Reserved
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
from register_tools import _get_third_parties
from register_tools import _set_third_parties
from register_tools import previous_register_is_closed
from register_tools import create_cashbox_lines
from register_tools import totally_or_partial_reconciled
import time
from datetime import datetime
import decimal_precision as dp
from tools.misc import flatten

def _get_fake(cr, table, ids, *a, **kw):
    ret = {}
    for id in ids:
        ret[id] = False
    return ret

def _search_fake(*a, **kw):
    return []

class hr_employee(osv.osv):
    _name = 'hr.employee'
    _inherit = 'hr.employee'
    _columns = {
        'filter_for_third_party': fields.function(_get_fake, type='char', string="Internal Field", fnct_search=_search_fake, method=False),
    }
hr_employee()

class res_partner(osv.osv):
    _name = 'res.partner'
    _inherit = 'res.partner'
    def _get_fake(self, cr, table, ids, field_name, arg, context):
        ret = {}
        for id in ids:
            ret[id] = False
        return ret

    def _search_filter_third(self, cr, uid, obj, name, args, context):
        if not context:
            context = {}
        if not args:
            return []
        if args[0][2]:
           t = self.pool.get('account.account').read(cr, uid, args[0][2], ['type', 'type_for_register'])
           if t['type'] == 'payable' and t['type_for_register'] != 'down_payment':
               return [('property_account_payable', '=', args[0][2])]
           if t['type'] == 'receivable' and t['type_for_register'] != 'down_payment':
                return [('property_account_receivable', '=', args[0][2])]
        return []

    _columns = {
        'filter_for_third_party': fields.function(_get_fake, type='char', string="Internal Field", fnct_search=_search_filter_third, method=True),
    }
res_partner()

class account_journal(osv.osv):
    _name = 'account.journal'
    _inherit = 'account.journal'

    def _get_fake(self, cr, table, ids, field_name, arg, context):
        ret = {}
        for id in ids:
            ret[id] = False
        return ret

    def _search_filter_third(self, cr, uid, obj, name, args, context):
        if not context:
            context = {}
        dom = [('type', 'in', ['cash', 'bank', 'cheque'])]
        if not args or not context.get('curr'):
            return dom
        if args[0][2]:
           t = self.pool.get('account.account').read(cr, uid, args[0][2], ['type_for_register'])
           if t['type_for_register'] == 'transfer_same':
               return dom+[('currency', 'in', [context['curr']])]
        return dom

    _columns = {
        'filter_for_third_party': fields.function(_get_fake, type='char', string="Internal Field", fnct_search=_search_filter_third, method=True),
    }
account_journal()

class account_bank_statement(osv.osv):
    _name = "account.bank.statement"
    _inherit = "account.bank.statement"

    _sql_constraints = [
        ('period_journal_uniq', 'unique (period_id, journal_id)', 'You cannot have a register on the same period and the same journal!')
    ]

    def __init__(self, pool, cr):
        super(account_bank_statement, self).__init__(pool, cr)
        if self.pool._store_function.get(self._name, []):
            newstore = []
            for fct in self.pool._store_function[self._name]:
                if fct[1] != 'balance_end':
                    newstore.append(fct)
            self.pool._store_function[self._name] = newstore

    def _end_balance(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Calculate register's balance
        """
        if context is None:
            context = {}
        st_line_obj = self.pool.get("account.bank.statement.line")
        res = {}

        # Add this context in order to escape cheque register filter
        ctx = context.copy()
        ctx.update({'from_end_balance': True})
        for statement in self.browse(cr, uid, ids, context=ctx):
            res[statement.id] = statement.balance_start
            for st_line in statement.line_ids:
                res[statement.id] += st_line.amount or 0.0
        return res

    def _get_register_id(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Get current register id
        """
        res = {}
        for st in self.browse(cr, uid, ids, context=context):
            res[st.id] = st.id
        return res

    def _balance_gap_compute(self, cr, uid, ids, name, attr, context=None):
        """
        Calculate Gap between bank register balance (balance_end_real) and calculated balance (balance_end)
        """
        res = {}
        for statement in self.browse(cr, uid, ids):
            res[statement.id] = ((statement.balance_end_real or 0.0) - (statement.balance_end or 0.0)) or 0.0
        return res

    _columns = {
        'balance_end': fields.function(_end_balance, method=True, store=False, string='Calculated Balance', \
            help="Calculated balance"),
        'virtual_id': fields.function(_get_register_id, method=True, store=False, type='integer', string='Id', readonly="1",
            help='Virtual Field that take back the id of the Register'),
        'balance_end_real': fields.float('Closing Balance', digits_compute=dp.get_precision('Account'), states={'confirm':[('readonly', True)]}, 
            help="Please enter manually the end-of-month balance, as per the printed bank statement received. Before confirming closing balance & closing the register, you must make sure that the calculated balance of the bank register is equal to that amount."),
        'closing_balance_frozen': fields.boolean(string="Closing balance freezed?", readonly="1"),
        'name': fields.char('Register Name', size=64, required=True, states={'confirm': [('readonly', True)]},
            help='If you give the Name other then /, its created Accounting Entries Move will be with same name as statement name. This allows the statement entries to have the same references than the statement itself'),
        'journal_id': fields.many2one('account.journal', 'Journal Name', required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'filter_for_third_party': fields.function(_get_fake, type='char', string="Internal Field", fnct_search=_search_fake, method=False),
        'balance_gap': fields.function(_balance_gap_compute, method=True, string='Gap', readonly=True),
        'notes': fields.text('Comments'),
    }

    _defaults = {
        'balance_start': lambda *a: 0.0,
    }

    def balance_check(self, cr, uid, register_id, journal_type='bank', context=None):
        """
        Check the balance for Registers
        """
        if not context:
            context = {}
        # Disrupt cheque verification
        if journal_type == 'cheque':
            return True
        # Add other verification for cash register
        if journal_type == 'cash':
            if not self._equal_balance(cr, uid, register_id, context):
                raise osv.except_osv(_('Error !'), _('CashBox Balance is not matching with Calculated Balance !'))
        st = self.browse(cr, uid, register_id, context=context)
        if not (abs((st.balance_end or 0.0) - st.balance_end_real) < 0.0001):
            raise osv.except_osv(_('Error !'),
                    _('The statement balance is incorrect !\n') +
                    _('The expected balance (%.2f) is different than the computed one. (%.2f)') % (st.balance_end_real, st.balance_end))
        return True

    def write(self, cr, uid, ids, values, context=None):
        """
        Bypass disgusting default account_bank_statement write function
        """
        return osv.osv.write(self, cr, uid, ids, values, context=context)

    def unlink(self, cr, uid, ids, context=None):
        """
        Delete a bank statement is forbidden!
        """
        if context and context.get('from', False) and context.get('from') == "journal_deletion":
            return super(account_bank_statement, self).unlink(cr, uid, ids)
        raise osv.except_osv(_('Warning'), _('Delete a Register is totally forbidden!'))
        return True

    def button_open_bank(self, cr, uid, ids, context=None):
        """
        when pressing 'Open Bank' button
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Verify that previous register is open, unless this register is the first register
        return self.write(cr, uid, ids, {'state': 'open'})

    def check_status_condition(self, cr, uid, state, journal_type='bank'):
        """
        Check Status of Register
        """
        return state =='draft' or state == 'open'


    def button_confirm_bank(self, cr, uid, ids, context=None):
        """
        Confirm Bank Register
        """
        # First verify that all lines are in hard state
        for register in self.browse(cr, uid, ids, context=context):
            for line in register.line_ids:
                if line.state != 'hard':
                    raise osv.except_osv(_('Warning'), _('All entries must be hard posted before closing this Register!'))
        # @@@override@account.account_bank_statement.button_confirm_bank()
#        done = []
        obj_seq = self.pool.get('ir.sequence')
        if context is None:
            context = {}


        for st in self.browse(cr, uid, ids, context=context):
            j_type = st.journal_id.type
            company_currency_id = st.journal_id.company_id.currency_id.id
            if not self.check_status_condition(cr, uid, st.state, journal_type=j_type):
                continue

            # modification of balance_check for cheque registers
            if st.journal_id.type in ['bank', 'cash']:
                self.balance_check(cr, uid, st.id, journal_type=j_type, context=context)
            if (not st.journal_id.default_credit_account_id) \
                    or (not st.journal_id.default_debit_account_id):
                raise osv.except_osv(_('Configuration Error !'),
                        _('Please verify that an account is defined in the journal.'))

            if not st.name == '/':
                st_number = st.name
            else:
                if st.journal_id.sequence_id:
                    c = {'fiscalyear_id': st.period_id.fiscalyear_id.id}
                    st_number = obj_seq.get_id(cr, uid, st.journal_id.sequence_id.id, context=c)
                else:
                    st_number = obj_seq.get(cr, uid, 'account.bank.statement')

            for line in st.move_line_ids:
                if line.state <> 'valid':
                    raise osv.except_osv(_('Error !'),
                            _('The account entries lines are not in valid state.'))
            for st_line in st.line_ids:
                if st_line.analytic_account_id:
                    if not st.journal_id.analytic_journal_id:
                        raise osv.except_osv(_('No Analytic Journal !'),_("You have to define an analytic journal on the '%s' journal!") % (st.journal_id.name,))
                if not st_line.amount:
                    continue
#                st_line_number = self.get_next_st_line_number(cr, uid, st_number, st_line, context)
                # Lines are hard posted. That's why create move lines is useless
#                self.create_move_from_st_line(cr, uid, st_line.id, company_currency_id, st_line_number, context)

            # Verify lines reconciliation status
            #if not totally_or_partial_reconciled(self, cr, uid, [x.id for x in st.line_ids], context=context):
            #    raise osv.except_osv(_('Warning'), _("Some lines are not reconciled. Please verify that all lines are reconciled totally or partially."))
            self.write(cr, uid, [st.id], {'name': st_number}, context=context)
            # Verify that the closing balance is freezed
            if not st.closing_balance_frozen and st.journal_id.type in ['bank', 'cash']:
                raise osv.except_osv(_('Error'), _("Please confirm closing balance before closing register named '%s'") % st.name or '')
#            done.append(st.id)
        # Display the bank confirmation wizard
        title = "Bank"
        if context.get('confirm_from', False) and context.get('confirm_from') == 'cheque':
            title = "Cheque"
        title += " confirmation wizard"
        return {
            'name': title,
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.confirm.bank',
            'target': 'new',
            'view_mode': 'form',
            'view_type': 'form',
            'context':
            {
                'active_id': ids[0],
                'active_ids': ids,
                'statement_id': st.id,
            }
        }
        # @@@end

    def button_create_invoice(self, cr, uid, ids, context=None):
        """
        Create a direct invoice
        """
        if context is None:
            context = {}

        # Search the customized view we made for Supplier Invoice (for * Register's users)
        currency =  self.read(cr, uid, ids, ['currency'])[0]['currency']
        if isinstance(currency, tuple):
            currency =currency[0]
        id = self.pool.get('wizard.account.invoice').search(cr, uid, [('currency_id','=',currency), ('register_id', '=', ids[0])])
        if not id:
            id = self.pool.get('wizard.account.invoice').create(cr, uid, {'currency_id': currency, 'register_id': ids[0], 'type': 'in_invoice'}, 
                context={'journal_type': 'purchase', 'type': 'in_invoice'})
        return {
            'name': "Supplier Invoice",
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.account.invoice',
            'target': 'new',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': id,
            'context':
            {
                'active_id': ids[0],
                'type': 'in_invoice',
                'journal_type': 'purchase',
                'active_ids': ids,
            }
        }

    def button_wiz_import_invoices(self, cr, uid, ids, context=None):
        """
        When pressing 'Import Invoices' button then opening a wizard to select some invoices and add them into the register by changing their states to 'paid'.
        """
        # statement_id is useful for making some line's registration.
        # currency_id is useful to filter invoices in the same currency
        st = self.browse(cr, uid, ids[0], context=context)
        id = self.pool.get('wizard.import.invoice').create(cr, uid, {'statement_id': ids[0] or None, 'currency_id': st.currency.id or None}, context=context)
        # Remember if we come from a cheque register (for adding some fields)
        from_cheque = False
        if st.journal_id.type == 'cheque':
            from_cheque = True
        return {
            'name': "Import Invoice",
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.import.invoice',
            'target': 'new',
            'view_mode': 'form,tree',
            'view_type': 'form',
            'res_id': [id],
            'context':
            {
                'active_id': ids[0],
                'active_ids': ids,
                'from_cheque': from_cheque,
            }
        }

    def button_wiz_import_cheques(self, cr, uid, ids, context=None):
        """
        When pressing 'Import Cheques' button then opening a wizard to select some cheques from a register and add them into the present register 
        in a temp post state.
        """
        # statement_id is useful for making some line's registration.
        # currency_id is useful to filter cheques in the same currency
        # period_id is useful to filter cheques drawn in the same period
        st = self.browse(cr, uid, ids[0], context=context)
        id = self.pool.get('wizard.import.cheque').create(cr, uid, {'statement_id': ids[0] or None, 'currency_id': st.currency.id or None, 
            'period_id': st.period_id.id}, context=context)
        return {
            'name': "Import Cheque",
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.import.cheque',
            'target': 'new',
            'view_mode': 'form,tree',
            'view_type': 'form',
            'res_id': [id],
            'context':
            {
                'active_id': ids[0],
                'active_ids': ids,
            }
        }

    def button_confirm_closing_balance(self, cr, uid, ids, context=None):
        """
        Confirm that the closing balance could not be editable.
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = []
        for reg in self.browse(cr, uid, ids, context=context):
            # Validate register only if this one is open
            if reg.state == 'open':
                res_id = self.write(cr, uid, [reg.id], {'closing_balance_frozen': True}, context=context)
                res.append(res_id)
            # Create next starting balance for cash registers
            if reg.journal_id.type == 'cash':
                create_cashbox_lines(self, cr, uid, reg.id, context=context)
            # For bank register, give balance_end
            elif reg.journal_id.type == 'bank':
                # Verify that another bank statement exists
                st_prev_ids = self.search(cr, uid, [('prev_reg_id', '=', reg.id)], context=context)
                if len(st_prev_ids) > 1:
                    raise osv.except_osv(_('Error'), _('A problem occured: More than one register have this one as previous register!'))
                if st_prev_ids:
                    self.write(cr, uid, st_prev_ids, {'balance_start': reg.balance_end_real}, context=context)
        return res

    def button_confirm_closing_bank_balance(self, cr, uid, ids, context=None):
        """
        Verify bank register balance before closing it.
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for reg in self.browse(cr, uid, ids):
            # Verify that the closing balance (balance_end_real) correspond to the calculated balance (balance_end)
            if reg.balance_end_real != reg.balance_end:
                raise osv.except_osv(_('Warning'), _('Bank register balance is not equal to Calculated balance.'))
        return self.button_confirm_closing_balance(cr, uid, ids, context=context)

    def button_open_advances(self, cr, uid, ids, context=None):
        """
        Open a list of open advances
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        domain = []
        date = time.strftime('%Y-%m-%d')
        registers = self.browse(cr, uid, ids, context=context)
        register = registers and registers[0] or False
        if not register:
            raise osv.except_osv(_('Error'), _('Please select a register first.'))
        domain = [('account_id.type_for_register', '=', 'advance'), ('state', '=', 'hard'), ('reconciled', '=', False), ('amount', '<=', 0.0), ('date', '<=', date)]
        name = _('Open Advances')
        if register.journal_id and register.journal_id.currency:
            # prepare some values
            name += ' - ' + register.journal_id.currency.name
            domain.append(('statement_id.journal_id.currency', '=', register.journal_id.currency.id))
        # Prepare view
        view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'register_accounting', 'view_account_bank_statement_line_tree')
        view_id = view and view[1] or False
        # Prepare search view
        search_view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'register_accounting', 'view_account_bank_statement_line_filter')
        search_view_id = search_view and search_view[1] or False
        context.update({'open_advance': register.id})
        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'res_model': 'account.bank.statement.line',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'view_id': [view_id],
            'search_view_id': search_view_id,
            'domain': domain,
            'context': context,
            'target': 'current',
        }

    def get_register_lines(self, cr, uid, ids, context=None):
        """
        Return all register lines from first given register
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        domain = [('statement_id', '=', ids[0])]
        # Search valid ids
        reg = self.browse(cr, uid, ids[0])
        return {
            'name': reg and reg.name or 'Register Lines',
            'type': 'ir.actions.act_window',
            'res_model': 'account.bank.statement.line',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'context': context,
            'domain': domain,
            'target': 'current',
        }

    def get_analytic_register_lines(self, cr, uid, ids, context=None):
        """
        Return all analytic lines attached to register lines from first given register
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        valid_ids = []
        # Search valid ids
        reg = self.browse(cr, uid, ids[0])
        domain = [('account_id.category', '=', 'FUNDING'), ('move_id.statement_id', 'in', [ids[0]])]
        context.update({'display_fp': True})
        return {
            'name': reg and 'Analytic Entries from ' + reg.name or 'Analytic Entries',
            'type': 'ir.actions.act_window',
            'res_model': 'account.analytic.line',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'context': context,
            'domain': domain,
            'target': 'current',
        }

account_bank_statement()

class account_bank_statement_line(osv.osv):
    _name = "account.bank.statement.line"
    _inherit = "account.bank.statement.line"

    _order = 'date desc, id desc'

    def _get_state(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Return account_bank_statement_line state in order to know if the bank statement line is in :
        - draft
        - temp posting
        - hard posting
        - unknown if an error occured or anything else (for an example the move have a new state)
        """
        # Prepare some variables
        res = {}
        for absl in self.browse(cr, uid, ids, context=context):
            # Verify move existence
            if not absl.move_ids:
                res[absl.id] = 'draft'
                continue
            # If exists, check move state
            state = absl.move_ids[0].state
            if state == 'draft':
                res[absl.id] = 'temp'
            elif state == 'posted':
                res[absl.id] = 'hard'
            else:
                res[absl.id] = 'unknown'
        return res

    def _get_amount(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Get the amount from amount_in and amount_on
        """
        # Variable initialisation
        default_amount = 0.0
        res = {}
        # Browse account bank statement lines
        for absl in self.browse(cr, uid, ids, context=context):
            # amount is positive so he should be in amount_in
            if absl.amount > 0 and field_name == "amount_in":
                res[absl.id] = abs(absl.amount)
            # amount is negative, it should be in amount_out
            elif absl.amount < 0 and field_name == "amount_out":
                res[absl.id] = abs(absl.amount)
            # if no resultat, we display 0.0 (default amount)
            else:
                res[absl.id] = default_amount
        return res

    def _search_state(self, cr, uid, obj, name, args, context=None):
        """
        Search elements by state :
        - draft
        - temp
        """
        # Test how many arguments we have
        if not len(args):
            return []

        # We just support = and in operators
        if args[0][1] not in ['=', 'in']:
            raise osv.except_osv(_('Warning'), _('This filter is not implemented yet!'))
        # Case where we search draft lines
        sql_draft = """
            SELECT st.id FROM account_bank_statement_line st 
            LEFT JOIN account_bank_statement_line_move_rel rel ON rel.move_id = st.id 
            WHERE rel.move_id is null
            """
        sql_temp = """SELECT st.id FROM account_bank_statement_line st 
            LEFT JOIN account_bank_statement_line_move_rel rel ON rel.move_id = st.id 
            LEFT JOIN account_move m ON m.id = rel.statement_id 
            WHERE m.state = 'draft'
            """
        sql_hard = """SELECT st.id FROM account_bank_statement_line st 
            LEFT JOIN account_bank_statement_line_move_rel rel ON rel.move_id = st.id 
            LEFT JOIN account_move m ON m.id = rel.statement_id 
            WHERE m.state = 'posted'
            """
        ids = []
        filterok = False
        if args[0][1] == '=' and args[0][2] == 'draft' or 'draft' in args[0][2]:
            sql = sql_draft
            cr.execute(sql)
            ids += [x[0] for x in cr.fetchall()]
            filterok = True
        # Case where we search temp lines
        if args[0][1] == '=' and args[0][2] == 'temp' or 'temp' in args[0][2]:
            sql = sql_temp
            cr.execute(sql)
            ids += [x[0] for x in cr.fetchall()]
            filterok = True
        if args[0][1] == '=' and args[0][2] == 'hard' or 'hard' in args[0][2]:
            sql = sql_hard
            cr.execute(sql)
            ids += [x[0] for x in cr.fetchall()]
            filterok = True
        # Non expected case
        if not filterok:
            raise osv.except_osv(_('Warning'), _('This filter is not implemented yet!'))
        return [('id', 'in', ids)]

    def _get_reconciled_state(self, cr, uid, ids, field_name=None, args=None, context=None):
        """
        Give the state of reconciliation for the account bank statement line
        """
        # Prepare some values
        res = {}
        # browse account bank statement lines
        for absl in self.browse(cr, uid, ids):
            # browse each move and move lines
            if absl.move_ids and absl.state == 'hard':
                res[absl.id] = True
                for move in absl.move_ids:
                    for move_line in move.line_id:
                        # Result is false if the account is reconciliable but no reconcile id exists
                        if move_line.account_id.reconcile and not move_line.reconcile_id:
                            res[absl.id] = False
                            break
            else:
                res[absl.id] = False
        return res

    def _search_reconciled(self, cr, uid, obj, name, args, context=None):
        """
        Search all lines that are reconciled or not
        """
        result = []
        # Test how many arguments we have
        if not len(args):
            return []
        # We just support "=" case
        if args[0][1] not in ['=', 'in']:
            raise osv.except_osv(_('Warning'), _('This filter is not implemented yet!'))
        # Search statement lines that have move lines and which moves are posted
        if args[0][2] == True:
            sql_posted_moves = """
                SELECT st.id FROM account_bank_statement_line st
                    LEFT JOIN account_bank_statement_line_move_rel rel ON rel.move_id = st.id
                    LEFT JOIN account_move move ON rel.statement_id = move.id
                    LEFT JOIN account_move_line line ON line.move_id = move.id
                    LEFT JOIN account_account ac ON ac.id = line.account_id
                WHERE rel.move_id is not null AND move.state = 'posted'
                GROUP BY st.id HAVING COUNT(reconcile_id IS NULL AND ac.reconcile='t' OR NULL)=0
            """
        else:
            sql_posted_moves = """
                SELECT st.id FROM account_bank_statement_line st
                    LEFT JOIN account_bank_statement_line_move_rel rel ON rel.move_id = st.id
                    LEFT JOIN account_move move ON rel.statement_id = move.id
                    LEFT JOIN account_move_line line ON line.move_id = move.id
                    LEFT JOIN account_account ac ON ac.id = line.account_id
                WHERE 
                    rel.move_id is null OR move.state != 'posted' OR (line.reconcile_id IS NULL AND ac.reconcile='t')
            """
        cr.execute(sql_posted_moves)
        return [('id', 'in', [x[0] for x in cr.fetchall()])]
    
    def _get_number_imported_invoice(self, cr, uid, ids, field_name=None, args=None, context=None):
        ret = {}
        for i in self.read(cr, uid, ids, ['imported_invoice_line_ids']):
            ret[i['id']] = len(i['imported_invoice_line_ids'])
        return ret

    def _get_down_payment_state(self, cr, uid, ids, field_name=None, args=None, context=None):
        """
        Verify down payment eligibility:
         - account should be a down_payment type for register
         - amount should be negative
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        # Browse elements
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = False
            if line.account_id and line.account_id.user_type and line.account_id.type_for_register == 'down_payment' and line.amount < 0.0:
                res[line.id] = True
        return res

    def _get_transfer_with_change_state(self, cr, uid, ids, field_name=None, args=None, context=None):
        """
        If account is a transfer with change, then True. Otherwise False.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        # Browse elements
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = False
            if line.account_id and line.account_id.type_for_register and line.account_id.type_for_register == 'transfer':
                res[line.id] = True
        return res

    _columns = {
        'register_id': fields.many2one("account.bank.statement", "Register"),
        'transfer_journal_id': fields.many2one("account.journal", "Journal"),
        'employee_id': fields.many2one("hr.employee", "Employee"),
        'amount_in': fields.function(_get_amount, method=True, string="Amount In", type='float'),
        'amount_out': fields.function(_get_amount, method=True, string="Amount Out", type='float'),
        'state': fields.function(_get_state, fnct_search=_search_state, method=True, string="Status", type='selection', selection=[
            ('draft', 'Draft'), ('temp', 'Temp'), ('hard', 'Hard'), ('unknown', 'Unknown')]),
        'partner_type': fields.function(_get_third_parties, fnct_inv=_set_third_parties, type='reference', method=True, 
            string="Third Parties", selection=[('res.partner', 'Partner'), ('account.journal', 'Journal'), ('hr.employee', 'Employee'), 
            ('account.bank.statement', 'Register')], multi="third_parties_key"),
        'partner_type_mandatory': fields.boolean('Third Party Mandatory'),
        'reconciled': fields.function(_get_reconciled_state, fnct_search=_search_reconciled, method=True, string="Amount Reconciled", 
            type='boolean', store=False),
        'sequence_for_reference': fields.integer(string="Sequence", readonly=True),
        'document_date': fields.date(string="Document Date", required=True),
        'cheque_number': fields.char(string="Cheque Number", size=120),
        'from_cash_return': fields.boolean(string='Come from a cash return?'),
        'direct_invoice': fields.boolean(string='Direct invoice?'),
        'invoice_id': fields.many2one('account.invoice', "Invoice", required=False),
        'first_move_line_id': fields.many2one('account.move.line', "Register Move Line"),
        'third_parties': fields.function(_get_third_parties, type='reference', method=True, 
            string="Third Parties", selection=[('res.partner', 'Partner'), ('account.journal', 'Journal'), ('hr.employee', 'Employee'), 
            ('account.bank.statement', 'Register')], help="To use for python code when registering", multi="third_parties_key"),
        'imported_invoice_line_ids': fields.many2many('account.move.line', 'imported_invoice', 'st_line_id', 'move_line_id', 
            string="Imported Invoices", required=False, readonly=True),
        'number_imported_invoice': fields.function(_get_number_imported_invoice, method=True, string='Number Invoices', type='integer'),
        'is_down_payment': fields.function(_get_down_payment_state, method=True, string="Is a down payment line?", 
            type='boolean', store=False),
        'from_import_cheque_id': fields.many2one('account.move.line', "Cheque Line", 
            help="This move line has been taken for create an Import Cheque in a bank register."),
        'is_transfer_with_change': fields.function(_get_transfer_with_change_state, method=True, string="Is a transfer with change line?", 
            type='boolean', store=False),
        'down_payment_id': fields.many2one('purchase.order', "Down payment", readonly=True),
        'transfer_amount': fields.float(string="Amount", help="Amount used for Transfers"),
    }

    _defaults = {
        'from_cash_return': lambda *a: 0,
        'direct_invoice': lambda *a: 0,
        'transfer_amount': lambda *a: 0,
    }

    def create_move_from_st_line(self, cr, uid, st_line_id, company_currency_id, st_line_number, context=None):
        """
        Create move from the register line
        """
        # @@@override@ account.account_bank_statement.create_move_from_st_line()
        if context is None:
            context = {}
        res_currency_obj = self.pool.get('res.currency')
        account_move_obj = self.pool.get('account.move')
        account_move_line_obj = self.pool.get('account.move.line')
        st_line = self.browse(cr, uid, st_line_id, context=context)
        st = st_line.statement_id

        context.update({'date': st_line.date})

        # Prepare partner_type
        partner_type = False
        if st_line.third_parties:
            partner_type = ','.join([str(st_line.third_parties._table_name), str(st_line.third_parties.id)])
        # end of add

        move_id = account_move_obj.create(cr, uid, {
            'journal_id': st.journal_id.id,
            'period_id': st.period_id.id,
            'date': st_line.date,
            'name': st_line_number,
            'ref': st_line.ref or False,
            ## Add partner_type
#            'partner_type': partner_type or False,
            # end of add
        }, context=context)
        self.write(cr, uid, [st_line.id], {
            'move_ids': [(4, move_id, False)]
        })

        torec = []
        if st_line.amount >= 0:
            account_id = st.journal_id.default_credit_account_id.id
        else:
            account_id = st.journal_id.default_debit_account_id.id

        acc_cur = ((st_line.amount<=0) and st.journal_id.default_debit_account_id) or st_line.account_id
        context.update({
                'res.currency.compute.account': acc_cur,
            })
        amount = res_currency_obj.compute(cr, uid, st.currency.id,
                company_currency_id, st_line.amount, context=context)

        val = {
            'name': st_line.name,
            'date': st_line.date,
            'document_date': st_line.document_date,
            'move_id': move_id,
            'partner_id': ((st_line.partner_id) and st_line.partner_id.id) or False,
            # Add employee_id, register_id and partner_type support
            'employee_id': ((st_line.employee_id) and st_line.employee_id.id) or False,
            'register_id': ((st_line.register_id) and st_line.register_id.id) or False,
            'transfer_journal_id': ((st_line.transfer_journal_id) and st_line.transfer_journal_id.id) or False,
#            'partner_type': partner_type or False,
            'partner_type_mandatory': st_line.partner_type_mandatory or False,
            # end of add
            'account_id': (st_line.account_id) and st_line.account_id.id,
            'credit': ((amount>0) and amount) or 0.0,
            'debit': ((amount<0) and -amount) or 0.0,
            'statement_id': st.id,
            'journal_id': st.journal_id.id,
            'period_id': st.period_id.id,
            'currency_id': st.currency.id,
            'analytic_account_id': st_line.analytic_account_id and st_line.analytic_account_id.id or False,
            'transfer_amount': st_line.transfer_amount or 0.0,
        }

        if st_line.analytic_distribution_id:
            val.update({'analytic_distribution_id': self.pool.get('analytic.distribution').copy(cr, uid, 
                st_line.analytic_distribution_id.id, {}, context=context) or False})

        if st.currency.id <> company_currency_id:
            amount_cur = res_currency_obj.compute(cr, uid, company_currency_id,
                        st.currency.id, amount, context=context)
            val['amount_currency'] = -st_line.amount

        if st_line.account_id and st_line.account_id.currency_id and st_line.account_id.currency_id.id <> company_currency_id:
            val['currency_id'] = st_line.account_id.currency_id.id
            amount_cur = res_currency_obj.compute(cr, uid, company_currency_id,
                    st_line.account_id.currency_id.id, amount, context=context)
            val['amount_currency'] = -amount_cur

        move_line_id = account_move_line_obj.create(cr, uid, val, context=context)
        torec.append(move_line_id)

        # Fill the secondary amount/currency
        # if currency is not the same than the company
        amount_currency = False
        currency_id = False
        if st.currency.id <> company_currency_id:
            amount_currency = st_line.amount
            currency_id = st.currency.id
        # Add register_line_id variable
        first_move_line_id = account_move_line_obj.create(cr, uid, {
            'name': st_line.name,
            'date': st_line.date,
            'document_date': st_line.document_date,
            'move_id': move_id,
            'partner_id': ((st_line.partner_id) and st_line.partner_id.id) or False,
            # Add employee_id and register_id support
            'employee_id': ((st_line.employee_id) and st_line.employee_id.id) or False,
            'register_id': ((st_line.register_id) and st_line.register_id.id) or False,
            'transfer_journal_id': ((st_line.transfer_journal_id) and st_line.transfer_journal_id.id) or False,
#            'partner_type': partner_type or False,
            'partner_type_mandatory': st_line.partner_type_mandatory or False,
            # end of add
            'account_id': account_id,
            'credit': ((amount < 0) and -amount) or 0.0,
            'debit': ((amount > 0) and amount) or 0.0,
            'statement_id': st.id,
            'journal_id': st.journal_id.id,
            'period_id': st.period_id.id,
            'amount_currency': amount_currency,
            'currency_id': currency_id,
            }, context=context)

        for line in account_move_line_obj.browse(cr, uid, [x.id for x in
                account_move_obj.browse(cr, uid, move_id,
                    context=context).line_id],
                context=context):
            if line.state <> 'valid':
                raise osv.except_osv(_('Error !'),
                        _('Journal Item "%s" is not valid') % line.name)
        # @@@end

        # Removed post from original method

        self.write(cr, uid, [st_line_id], {'first_move_line_id': first_move_line_id}, context=context)
        return move_id

    def _update_amount(self, values):
        """
        Update amount in 'values' with the difference between amount_in and amount_out.
        """
        res = values.copy()
        amount = None
        if 'amount_in' not in values and 'amount_out' not in values:
            return res
        if values:
            amount_in = values.get('amount_in', 0.0)
            amount_out = values.get('amount_out', 0.0)
            if amount_in > 0 and amount_out == 0:
                amount = amount_in
            elif amount_in == 0 and amount_out > 0:
                amount = - amount_out
            else:
                raise osv.except_osv(_('Error'), _('Please correct amount fields!'))
        if amount:
            res.update({'amount': amount})
        return res

    def _verify_dates(self, cr, uid, ids, context=None):
        """
        Verify that the given parameter contains date. Then validate date with regarding register period.
        """
        for st_line in self.browse(cr, uid, ids, context=context):
            # Prepare some values
            register = st_line.statement_id
            account_id = st_line.account_id.id
            date = st_line.date
            period_start = register.period_id.date_start
            period_stop = register.period_id.date_stop
            # Verify that the date is included between period_start and period_stop
            if date < period_start or date > period_stop:
                raise osv.except_osv(_('Error'), _('The date for "%s" is outside the register period!') % (st_line.name,))
            # Verify that the date is useful with default debit or credit account activable date 
            #+ (in fact the default debit and credit account have an activation date, and the given account_id too)
            #+ That means default debit and credit account are required for registers !
            register_debit_account_id = register.journal_id.default_debit_account_id.id
            register_credit_account_id = register.journal_id.default_credit_account_id.id
            amount = st_line.amount
            acc_obj = self.pool.get('account.account')
            register_account = None
            if amount > 0:
                register_account = acc_obj.browse(cr, uid, register_debit_account_id, context=context)
            elif amount < 0:
                register_account = acc_obj.browse(cr, uid, register_credit_account_id, context=context)
            if register_account:
                if date < register_account.activation_date or (register_account.inactivation_date and date > register_account.inactivation_date):
                    raise osv.except_osv(_('Error'), 
                        _('Posting date for "%s" is outside the validity period of the default account for this register!') % (st_line.name,))
            if account_id:
                account = acc_obj.browse(cr, uid, account_id, context=context)
                if date < account.activation_date or (account.inactivation_date and date > account.inactivation_date):
                    raise osv.except_osv(_('Error'), 
                        _('Posting date for "%s" is outside the validity period of the selected account for this record!') % (st_line.name,))
        return True

    _constraints = [
        (_verify_dates, "Date is not correct. Verify that it's in the register's period. ", ['date']),
    ]

    def _update_move_from_st_line(self, cr, uid, st_line_id=None, values=None, context=None):
        """
        Update move lines from given statement lines
        """
        if not st_line_id or not values:
            return False

        if context is None:
            context = {}

        # Prepare some values
        move_line_values = dict(values)
        acc_move_line_obj = self.pool.get('account.move.line')
        st_line = self.browse(cr, uid, st_line_id, context=context)
        # Get first line (from Register account)
        register_line = st_line.first_move_line_id
        # Delete 'from_import_cheque_id' field not to break the account move line write
        if 'from_import_cheque_id' in move_line_values:
            del(move_line_values['from_import_cheque_id'])
        # Delete down_payment value not to be given to account_move_line
        if 'down_payment_id' in move_line_values:
            del(move_line_values['down_payment_id'])
        if register_line:
            # Search second move line
            other_line_id = acc_move_line_obj.search(cr, uid, [('move_id', '=', st_line.move_ids[0].id), ('id', '!=', register_line.id)], context=context)[0]
            other_line = acc_move_line_obj.browse(cr, uid, other_line_id, context=context)
            other_account_id = move_line_values.get('account_id', other_line.account_id.id)
            amount = move_line_values.get('amount', st_line.amount)
            # Search all data for move lines
            register_account_id = st_line.statement_id.journal_id.default_debit_account_id.id
            if amount < 0:
                register_account_id = st_line.statement_id.journal_id.default_credit_account_id.id
                register_debit = 0.0
                register_credit = abs(amount)
                other_debit = abs(amount)
                other_credit = 0.0
            else:
                register_debit = amount
                register_credit = 0.0
                other_debit = 0.0
                other_credit = amount
            # What's about register currency ?
            register_amount_currency = False
            other_amount_currency = False
            currency_id = st_line.statement_id.currency.id
            if st_line.statement_id.currency.id != st_line.statement_id.company_id.currency_id.id:
                # Prepare value
                res_currency_obj = self.pool.get('res.currency')
                # Get date for having a good change rate
                context.update({'date': move_line_values.get('date', st_line.date)})
                # Change amount
                new_amount = res_currency_obj.compute(cr, uid, \
                    st_line.statement_id.journal_id.currency.id, st_line.company_id.currency_id.id, abs(amount), round=False, context=context)
                # Take currency for the move lines
                currency_id = st_line.statement_id.journal_id.currency.id
                # Default amount currency
                register_amount_currency = False
                if amount < 0:
                    register_amount_currency = -abs(amount)
                    register_debit = 0.0
                    register_credit = new_amount
                    other_debit = new_amount
                    other_credit = 0.0
                else:
                    register_amount_currency = abs(amount)
                    register_debit = new_amount
                    register_credit = 0.0
                    other_debit = 0.0
                    other_credit = new_amount
                # Amount currency for "other line" is the opposite of "register line"
                other_amount_currency = -register_amount_currency
            # Update values for register line
            for el in ['is_transfer_with_change', 'transfer_amount']:
                if el in move_line_values:
                    del(move_line_values[el])
            move_line_values.update({'account_id': register_account_id, 'debit': register_debit, 'credit': register_credit, 
                'amount_currency': register_amount_currency, 'currency_id': currency_id,})
            # Write move line object for register line
            acc_move_line_obj.write(cr, uid, [register_line.id], move_line_values, context=context)
            # Update values for other line
            move_line_values.update({'account_id': other_account_id, 'debit': other_debit, 'credit': other_credit, 'amount_currency': other_amount_currency, 
                'currency_id': currency_id,})
            if st_line.is_transfer_with_change:
                move_line_values.update({'is_transfer_with_change': True})
                if st_line.transfer_amount:
                    move_line_values.update({'transfer_amount': st_line.transfer_amount or 0.0})
            # Write move line object for other line
            acc_move_line_obj.write(cr, uid, [other_line.id], move_line_values, context=context)
            # Update analytic distribution lines
            analytic_amount = acc_move_line_obj.read(cr, uid, [other_line.id], ['amount_currency'], context=context)[0].get('amount_currency', False)
            if analytic_amount:
                self.pool.get('analytic.distribution').update_distribution_line_amount(cr, uid, [st_line.analytic_distribution_id.id], 
                amount=analytic_amount, context=context)
            # Update move
            # first prepare partner_type
            partner_type = False
            if st_line.third_parties:
                partner_type = ','.join([str(st_line.third_parties._table_name), str(st_line.third_parties.id)])
            # then prepare name
            name = '/'
            # finally write move object
            self.pool.get('account.move').write(cr, uid, [register_line.move_id.id], {'partner_type': partner_type, 'name': name}, context=context)
        return True

    def do_direct_expense(self, cr, uid, ids, context=None):
        """
        Do a direct expense when the line is hard posted and content a supplier
        """
        if context is None:
            context = {}
        for st_line in self.browse(cr, uid, ids, context=context):
            # Do the treatment only if the line is hard posted and have a partner who is a supplier
            if st_line.state == "hard" and st_line.partner_id and st_line.account_id.user_type.code in ('expense', 'income') and \
                st_line.direct_invoice is False:
                # Prepare some elements
                move_obj = self.pool.get('account.move')
                move_line_obj = self.pool.get('account.move.line')
                curr_date = time.strftime('%Y-%m-%d')
                # Create a move
                move_vals= {
                    'journal_id': st_line.statement_id.journal_id.id,
                    'period_id': st_line.statement_id.period_id.id,
                    'date': st_line.document_date or st_line.date or curr_date,
                    'name': 'DirectExpense/' + st_line.name,
                    'partner_id': st_line.partner_id.id,
                }
                move_id = move_obj.create(cr, uid, move_vals, context=context)
                # Create move lines
                account_id = False
                if st_line.account_id.user_type.code == 'expense':
                    account_id = st_line.partner_id.property_account_payable.id or False
                elif st_line.account_id.user_type.code == 'income':
                    account_id = st_line.partner_id.property_account_receivable.id or False
                if not account_id:
                    raise osv.except_osv(_('Warning'), _('The supplier seems not to have a correct account. \
                            Please contact an accountant administrator to resolve this problem.'))
                val = {
                    'name': st_line.name,
                    'date': st_line.date or curr_date,
                    'document_date': st_line.document_date or curr_date,
                    'ref': st_line.ref,
                    'move_id': move_id,
                    'partner_id': st_line.partner_id.id or False,
                    'partner_type_mandatory': True,
                    'account_id': account_id,
                    'credit': 0.0,
                    'debit': 0.0,
                    'statement_id': st_line.statement_id.id,
                    'journal_id': st_line.statement_id.journal_id.id,
                    'period_id': st_line.statement_id.period_id.id,
                    'currency_id': st_line.statement_id.currency.id,
                    'analytic_account_id': st_line.analytic_account_id and st_line.analytic_account_id.id or False
                }
                amount = abs(st_line.amount)
                # update values if we have a different currency that company currency
                if st_line.statement_id.currency.id != st_line.statement_id.company_id.currency_id.id:
                    context['date'] = st_line.document_date or st_line.date or curr_date
                    amount = self.pool.get('res.currency').compute(cr, uid, st_line.statement_id.currency.id, 
                        st_line.statement_id.company_id.currency_id.id, amount, round=False, context=context)
                val.update({'debit': amount, 'credit': 0.0, 'amount_currency': abs(st_line.amount)})
                move_line_debit_id = move_line_obj.create(cr, uid, val, context=context)
                val.update({'debit': 0.0, 'credit': amount, 'amount_currency': -abs(st_line.amount)})
                move_line_credit_id = move_line_obj.create(cr, uid, val, context=context)
                # Post the move
                move_res_id = move_obj.post(cr, uid, [move_id], context=context)
                # Do reconciliation
                move_line_res_id = move_line_obj.reconcile_partial(cr, uid, [move_line_debit_id, move_line_credit_id])
                # Disable the cash return button on this line
                self.write(cr, uid, [st_line.id], {'from_cash_return': True}, context=context)
        return True

    def do_import_invoices_reconciliation(self, cr, uid, st_lines=None, context=None):
        """
        Reconcile line that come from an import invoices wizard in 3 steps :
         - split line into the move
         - post move
         - reconcile lines from the move
        """
        # Some verifications
        if not context:
            context = {}
        if not st_lines or isinstance(st_lines, (int, long)):
            st_lines = []

        # Prepare some values
        absl_obj = self.pool.get('account.bank.statement.line')
        move_line_obj = self.pool.get('account.move.line')
        move_obj = self.pool.get('account.move')

        # Parse register lines
        for st_line in absl_obj.browse(cr, uid, st_lines, context=context):
            # Verification if st_line have some imported invoice lines
            if not st_line.imported_invoice_line_ids:
                continue
           
            total_amount = 0
            for invoice_move_line in st_line.imported_invoice_line_ids:
                total_amount += invoice_move_line.amount_currency

            ## STEP 1 : Split lines
            # Prepate some values
            move_ids = [x.id for x in st_line.move_ids]
            # Search move lines that are attached to move_ids
            move_lines = move_line_obj.search(cr, uid, [('move_id', 'in', move_ids), 
                ('id', '!=', st_line.first_move_line_id.id)]) # move lines that have been created AFTER import invoice wizard
            # Add new lines
            amount = abs(st_line.first_move_line_id.amount_currency)
            sign = 1
            if st_line.first_move_line_id.amount_currency > 0:
                sign = -1
            res_ml_ids = []
            process_invoice_move_line_ids = []
            total_payment = True
            if st_line.first_move_line_id.amount_currency != total_amount:
                # multi unpartial payment
                total_payment = False
                # Delete them
                move_line_obj.unlink(cr, uid, move_lines, context=context)
                for invoice_move_line in sorted(st_line.imported_invoice_line_ids, key=lambda x: abs(x.amount_currency)):
                    if abs(invoice_move_line.amount_currency) <= amount:
                        amount_to_write = sign * abs(invoice_move_line.amount_currency)
                    else:
                        amount_to_write = sign * amount
                    # create a new move_line corresponding to this invoice move line
                    aml_vals = {
                        'name': invoice_move_line.invoice.number,
                        'move_id': move_ids[0],
                        'partner_id': invoice_move_line.partner_id.id,
                        'account_id': st_line.account_id.id,
                        'amount_currency': amount_to_write,
                        'statement_id': st_line.statement_id.id,
                        'currency_id': st_line.statement_id.currency.id,
                        'from_import_invoice_ml_id': invoice_move_line.id, # FIXME: add this ONLY IF total amount was paid
                        'date': st_line.date,
                        'document_date': st_line.document_date,
                    }
                    process_invoice_move_line_ids.append(invoice_move_line.id)
                    move_line_id = move_line_obj.create(cr, uid, aml_vals, context=context)
                    res_ml_ids.append(move_line_id)
                    
                    amount -= abs(amount_to_write)
                    if not amount:
                        todo = [x.id for x in st_line.imported_invoice_line_ids if x.id not in process_invoice_move_line_ids]
                        # remove remaining invoice lines
                        if todo:
                            absl_obj.write(cr, uid, [st_line.id], {'imported_invoice_line_ids': [(3, x) for x in todo]}, context=context)
                        break
            # STEP 2 : Post moves
            move_obj.post(cr, uid, move_ids, context=context)
            
            # STEP 3 : Reconcile
            if total_payment:
                move_line_obj.reconcile_partial(cr, uid, move_lines+[x.id for x in st_line.imported_invoice_line_ids], context=context)
            else:
                for ml in move_line_obj.browse(cr, uid, res_ml_ids, context=context):
                    # reconcile lines
                    move_line_obj.reconcile_partial(cr, uid, [ml.id, ml.from_import_invoice_ml_id.id], context=context)
        return True

    def do_import_cheque_reconciliation(self, cr, uid, st_lines=None, context=None):
        """
        Do a reconciliation of an imported cheque and the current register line
        """
        # Some verifications
        if not context:
            context = {}
        if not st_lines or isinstance(st_lines, (int, long)):
            st_lines = []
        # Prepare some values
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        # Parse register lines
        for st_line in self.browse(cr, uid, st_lines, context=context):
            # Verification if st_line have some imported invoice lines
            if not st_line.from_import_cheque_id:
                continue
            move_obj.post(cr, uid, [st_line.move_ids[0].id], context=context)
            # Search the line that would be reconcile after hard post
            move_line_id = move_line_obj.search(cr, uid, [('move_id', '=', st_line.move_ids[0].id), ('id', '!=', st_line.first_move_line_id.id)], 
                context=context)
            # Do reconciliation
            move_line_obj.reconcile_partial(cr, uid, [st_line.from_import_cheque_id.id, move_line_id[0]], context=context)
        return True

    def analytic_distribution_is_mandatory(self, cr, uid, id, context=None):
        """
        Verify that no analytic distribution is mandatory. It's not until one of test is true
        """
        # Some verifications
        if isinstance(id, (list)):
            id = id[0]
        if not context:
            context = {}
        # Tests
        absl = self.browse(cr, uid, id, context=context)
        if absl.account_id.user_type.code in ['expense'] and not absl.analytic_distribution_id:
            return True
        elif absl.account_id.user_type.code in ['expense'] and not absl.analytic_distribution_id.funding_pool_lines:
            return True
        return False

    def create_down_payment_link(self, cr, uid, ids, context=None):
        """
        Copy down_payment link to right move line
        """
        # some verifications
        if isinstance(ids, (int, long)):
            ids = [ids]
        # browse all bank statement line
        for absl in self.browse(cr, uid, ids):
            if not absl.is_down_payment:
                continue
            move_ids = [x.id or None for x in absl.move_ids]
            # Search line that have same account for given register line
            line_ids = self.pool.get('account.move.line').search(cr, uid, [('account_id', '=', absl.account_id.id), ('move_id', 'in', move_ids)])
            # Add down_payment link
            for line_id in line_ids:
                self.pool.get('account.move.line').write(cr, uid, [line_id], {'down_payment_id': absl.down_payment_id.id})
        return True

    def create(self, cr, uid, values, context=None):
        """
        Create a new account bank statement line with values
        """
        # First update amount
        values = self._update_amount(values=values)
        # Then create a new bank statement line
        return super(account_bank_statement_line, self).create(cr, uid, values, context=context)

    def write(self, cr, uid, ids, values, context=None):
        """
        Write some existing account bank statement lines with 'values'.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        # Prepare some values
        state = self._get_state(cr, uid, ids, context=context).values()[0]
        # Verify that the statement line isn't in hard state
        if state  == 'hard':
            if values == {'from_cash_return': True} or values.get('analytic_distribution_id', False) or (values.get('invoice_id', False) and len(values.keys()) == 2 and values.get('from_cash_return')) or 'from_correction' in context:
                return super(account_bank_statement_line, self).write(cr, uid, ids, values, context=context)
            raise osv.except_osv(_('Warning'), _('You cannot write a hard posted entry.'))
        # First update amount
        values = self._update_amount(values=values)
        # Case where _update_amount return False ! => this imply there is a problem with amount columns
        if not values:
            return False
        # In case of Temp Posting, we also update attached account move lines
        if state == 'temp':
            # method write removes date in value: save it, then restore it
            saveddate = False
            if values.get('date'):
                saveddate = values['date']
            for id in ids:
                self._update_move_from_st_line(cr, uid, id, values, context=context)
            if saveddate:
                values['date'] = saveddate
        # Update the bank statement lines with 'values'
        res = super(account_bank_statement_line, self).write(cr, uid, ids, values, context=context)
        # Amount verification regarding Down payments
        for line in self.browse(cr, uid, ids):
            if line.is_down_payment and line.down_payment_id:
                if not self.pool.get('wizard.down.payment').check_register_line_and_po(cr, uid, line.id, line.down_payment_id.id, context=context):
                    raise osv.except_osv(_('Warning'), _('An error occured on down_payment check. Please contact an administrator to resolve this problem.'))
        return res

    def copy(self, cr, uid, id, default=None, context=None):
        """
        Create a copy of given line
        """
        # Some verifications
        if not context:
            context = {}
        if not default:
            default = {}
        # Update vals
        default.update({
            'analytic_account_id': False,
            'analytic_distribution_id': False,
            'direct_invoice': False,
            'first_move_line_id': False,
            'from_cash_return': False,
            'from_import_cheque_id': False,
            'imported_invoice_line_ids': False,
            'invoice_id': False,
            'move_ids': False,
            'reconciled': False,
            'sequence': False,
            'sequence_for_reference': False,
            'state': 'draft',
            'transfer_amount': False,
            'transfer_currency': False,
            'down_payment_id': False,
        })
        return super(osv.osv, self).copy(cr, uid, id, default, context=context)

    def posting(self, cr, uid, ids, postype, context=None):
        """
        Write some statement line into some account move lines with a state that depends on postype.
        """
        if not context:
            context = {}
        if postype not in ('hard', 'temp'):
            raise osv.except_osv(_('Warning'), _('Post type has to be hard or temp'))
        if not len(ids):
            raise osv.except_osv(_('Warning'), _('There is no active_id. Please contact an administrator to resolve the problem.'))
        acc_move_obj = self.pool.get("account.move")
        # browse all statement lines for creating move lines
        for absl in self.browse(cr, uid, ids, context=context):
            if absl.state == "hard":
                raise osv.except_osv(_('Warning'), _('You can\'t re-post a hard posted entry !'))
            elif absl.state == "temp" and postype == "temp":
                    raise osv.except_osv(_('Warning'), _('You can\'t temp re-post a temp posted entry !'))

            if absl.state == "draft":
                self.create_move_from_st_line(cr, uid, absl.id, absl.statement_id.journal_id.company_id.currency_id.id, '/', context=context)
                # reset absl browse_record cache, because move_ids have been created by create_move_from_st_line
                absl = self.browse(cr, uid, absl.id, context=context)

            if postype == "hard":
                # some verifications
                if self.analytic_distribution_is_mandatory(cr, uid, absl.id, context=context) and not context.get('from_yml'):
                    raise osv.except_osv(_('Error'), _('No analytic distribution found!'))

                if absl.is_transfer_with_change:
                    if not absl.transfer_journal_id:
                        raise osv.except_osv(_('Warning'), _('Third party is required in order to hard post a transfer with change register line!'))

                if absl.is_down_payment and not absl.down_payment_id:
                    raise osv.except_osv(_('Error'), _('Link with a PO for Down Payment is missing!'))
                elif absl.is_down_payment:
                    self.pool.get('wizard.down.payment').check_register_line_and_po(cr, uid, absl.id, absl.down_payment_id.id, context=context)
                    self.create_down_payment_link(cr, uid, absl.id, context=context)

                seq = self.pool.get('ir.sequence').get(cr, uid, 'all.registers')
                self.write(cr, uid, [absl.id], {'sequence_for_reference': seq}, context=context)
                # Case where this line come from an "Import Invoices" Wizard
                if absl.imported_invoice_line_ids:
                    self.do_import_invoices_reconciliation(cr, uid, [absl.id], context=context)
                elif absl.from_import_cheque_id:
                    self.do_import_cheque_reconciliation(cr, uid, [absl.id], context=context)
                else:
                    acc_move_obj.post(cr, uid, [x.id for x in absl.move_ids], context=context)
                    # do a move that enable a complete supplier follow-up
                    self.do_direct_expense(cr, uid, [absl.id], context=context)
        return True

    def button_hard_posting(self, cr, uid, ids, context=None):
        """
        Write some statement line into some account move lines in posted state.
        """
        return self.posting(cr, uid, ids, 'hard', context=context)

    def button_temp_posting(self, cr, uid, ids, context=None):
        """
        Write some statement lines into some account move lines in draft state.
        """
        return self.posting(cr, uid, ids, 'temp', context=context)

    def unlink(self, cr, uid, ids, context=None):
        """
        Permit to delete some account_bank_statement_line. But do some treatments on temp posting lines and do nothing for hard posting lines.
        """
        # We browse all ids
        for st_line in self.browse(cr, uid, ids):
            # if the line have a link to a move we have to make some treatments
            if st_line.move_ids:
                # in case of hard posting line : do nothing (because not allowed to change an entry which was posted!
                if st_line.state == "hard":
                    raise osv.except_osv(_('Error'), _('You are not allowed to delete hard posting lines!'))
                else:
                    # In case of line that content some move_line that come from imported invoices
                    # delete link between account_move_line and register_line that will be unlinked
                    #if st_line.imported_invoice_line_ids:
                    #    self.pool.get('account.move.line').write(cr, uid, [x['id'] for x in st_line.imported_invoice_line_ids], 
                    #        {'imported_invoice_line_ids': (3, st_line.id, False)}, context=context)
                    self.pool.get('account.move').unlink(cr, uid, [x.id for x in st_line.move_ids])
        return super(account_bank_statement_line, self).unlink(cr, uid, ids)

    def button_advance(self, cr, uid, ids, context=None):
        """
        Launch a wizard when you press "Advance return" button on a bank statement line in a Cash Register
        """
        if context is None:
            context = {}
        # Some verifications
        if len(ids) > 1:
            raise osv.except_osv(_('Error'), _('This wizard only accept ONE advance line.'))
        # others verifications
        for st_line in self.browse(cr, uid, ids, context=context):
            # verify that the journal id is a cash journal
            if not st_line.statement_id or not st_line.statement_id.journal_id or not st_line.statement_id.journal_id.type \
                or st_line.statement_id.journal_id.type != 'cash':
                raise osv.except_osv(_('Error'), _("The attached journal is not a Cash Journal"))
            # verify that there is a third party, particularly an employee_id in order to do something
            if not st_line.employee_id:
                raise osv.except_osv(_('Error'), _("The staff field is not filled in. Please complete the third parties field with an employee/staff."))
        # then display the wizard with an active_id = cash_register_id, and giving in the context a number of the bank statement line
        st_obj = self.pool.get('account.bank.statement.line')
        st = st_obj.browse(cr, uid, ids[0]).statement_id
        if 'open_advance' in context:
            st = self.pool.get('account.bank.statement').browse(cr, uid, context.get('open_advance'), context=context)
        if st and st.state != 'open':
            raise osv.except_osv(_('Error'), _('You cannot do a cash return in Register which is in another state that "open"!'))
        statement_id = st.id
        amount = self.read(cr, uid, ids[0], ['amount']).get('amount', 0.0)
        if amount >= 0:
            raise osv.except_osv(_('Warning'), _('Please select a line with a filled out "amount out"!'))
        wiz_obj = self.pool.get('wizard.cash.return')
        wiz_id = wiz_obj.create(cr, uid, {'returned_amount': 0.0, 'initial_amount': abs(amount), 'advance_st_line_id': ids[0], \
            'currency_id': st_line.statement_id.currency.id}, context=context)
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
            'statement_line_id': ids[0],
            'statement_id': statement_id,
            'amount': amount
        })
        if statement_id:
            return {
                'name' : "Advance Return",
                'type' : 'ir.actions.act_window',
                'res_model' :"wizard.cash.return",
                'target': 'new',
                'view_mode': 'form',
                'view_type': 'form',
                'res_id': [wiz_id],
                'context': context,
            }
        else:
            return False

    def button_open_invoices(self, cr, uid, ids, context=None):
        l = self.read(cr, uid, ids, ['imported_invoice_line_ids'])[0]
        if not l['imported_invoice_line_ids']:
            raise osv.except_osv(_('Error'), _("No related invoice line"))
        return {
            'name': "Invoice Lines",
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'target': 'new',
            'view_mode': 'tree,form',
            'view_type': 'form',
            'domain': [('id', 'in', l['imported_invoice_line_ids'])]
        }
        

    def button_open_invoice(self, cr, uid, ids, context=None):
        """
        Open the attached invoice
        """
        for st_line in self.browse(cr, uid, ids, context=context):
            if not st_line.direct_invoice or not st_line.invoice_id:
                raise osv.except_osv(_('Warning'), _('No invoice founded.'))
        # Search the customized view we made for Supplier Invoice (for * Register's users)
        irmd_obj = self.pool.get('ir.model.data')
        view_ids = irmd_obj.search(cr, uid, [('name', '=', 'wizard_supplier_invoice_form_view'), ('model', '=', 'ir.ui.view')])
        # Préparation de l'élément permettant de trouver la vue à  afficher
        if view_ids:
            view = irmd_obj.read(cr, uid, view_ids[0])
            view_id = (view.get('res_id'), view.get('name'))
        else:
            raise osv.except_osv(_('Error'), _("View not found."))
        return {
            'name': "Supplier Invoice",
            'type': 'ir.actions.act_window',
            'res_model': 'account.invoice',
            'target': 'new',
            'view_mode': 'form',
            'view_type': 'form',
            'view_id': view_id,
            'res_id': self.browse(cr, uid, ids[0], context=context).invoice_id.id,
            'context':
            {
                'active_id': ids[0],
                'type': 'in_invoice',
                'active_ids': ids,
            }
        }

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
            if line.statement_id and line.statement_id.state != 'open':
                raise osv.except_osv(_('Warning'), _("Register not open, you can't duplicate lines."))

            default_vals = ({
                'name': '(copy) ' + line.name,
            })
            self.copy(cr, uid, line.id, default_vals, context=context)
        return True

    def button_down_payment(self, cr, uid, ids, context=None):
        """
        Open Down Payment wizard
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        vals = {}
        register_line = self.browse(cr, uid, ids[0], context=context)
        vals.update({'register_line_id': register_line.id})
        if register_line and register_line.down_payment_id:
            vals.update({'purchase_id': register_line.down_payment_id.id})
        if register_line and register_line.state and register_line.state != 'hard':
            vals.update({'state': 'draft'})
        if register_line and register_line.currency_id:
            vals.update({'currency_id': register_line.currency_id.id})
        if register_line and register_line.partner_id:
            vals.update({'partner_id': register_line.partner_id.id})
        wiz_id = self.pool.get('wizard.down.payment').create(cr, uid, vals, context=context)
        # Return view with register_line id
        context.update({
            'active_id': wiz_id,
            'active_ids': [wiz_id],
            'register_line_id': ids[0],
        })
        return {
            'name': _("Down Payment"),
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.down.payment',
            'target': 'new',
            'res_id': [wiz_id],
            'view_mode': 'form',
            'view_type': 'form',
            'context': context,
        }

    def button_transfer(self, cr, uid, ids, context=None):
        """
        Open Transfer with change wizard
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        vals = {}
        absl = self.browse(cr, uid, ids[0], context=context)
        if absl.account_id and absl.account_id.type_for_register and absl.account_id.type_for_register != 'transfer':
            raise osv.except_osv(_('Error'), _('Open transfer with change wizard is only possible with transfer account in other currency!'))
        # Create wizard
        vals = {'absl_id': ids[0],}
        transfer_type = 'to'
        amount_field = 'amount_to'
        curr_field = 'currency_to'
        if absl and absl.amount:
            if absl.amount >= 0:
                transfer_type = 'from'
                amount_field = 'amount_from'
                curr_field = 'currency_from'
        if absl and absl.transfer_amount:
            vals.update({amount_field: absl.transfer_amount,})
        elif absl and absl.transfer_journal_id:
            vals.update({'currency_id': absl.transfer_journal_id.currency.id, curr_field: absl.transfer_journal_id.currency.id})
        if absl and absl.state == 'hard':
            vals.update({'state': 'closed',})
        vals.update({'type': transfer_type,})
        wiz_id = self.pool.get('wizard.transfer.with.change').create(cr, uid, vals, context=context)
        # Return view with register_line id
        context.update({
            'active_id': wiz_id,
            'active_ids': [wiz_id],
            'register_line_id': ids[0],
        })
        return {
            'name': _("Transfer with change"),
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.transfer.with.change',
            'target': 'new',
            'res_id': [wiz_id],
            'view_mode': 'form',
            'view_type': 'form',
            'context': context,
        }

    def onchange_account(self, cr, uid, ids, account_id=None, statement_id=None, context=None):
        """
        Update Third Party type regarding account type_for_register field.
        """
        # Prepare some values
        acc_obj = self.pool.get('account.account')
        third_type = [('res.partner', 'Partner'), ('hr.employee', 'Employee')]
        third_required = False
        third_selection = 'res.partner,0'
        # if an account is given, then attempting to change third_type and information about the third required
        if account_id:
            a = acc_obj.read(cr, uid, account_id, ['type_for_register'])
            if a['type_for_register'] in ['transfer', 'transfer_same']:
                # UF-428: transfer type shows only Journals instead of Registers as before
                third_type = [('account.journal', 'Journal')]
                third_required = True
                third_selection = 'account.journal,0'
            elif a['type_for_register'] == 'advance':
                third_type = [('hr.employee', 'Employee')]
                third_required = True
                third_selection = 'hr.employee,0'
            elif a['type_for_register'] == 'down_payment':
                third_type = [('res.partner', 'Partner')]
                third_required = True
                third_selection = 'res.partner,0'
        return {'value': {'partner_type_mandatory': third_required, 'partner_type': {'options': third_type, 'selection': third_selection}}}

    def onchange_partner_type(self, cr, uid, ids, partner_type=None, amount_in=None, amount_out=None, context=None):
        """
        Update account_id field if partner_type change
        NB:
         - amount_out = debit
         - amount_in = credit
        """
        res = {}
        amount = (amount_in or 0.0) - (amount_out or 0.0)
        if not partner_type and not amount:
            return res
        if partner_type:
            partner_data = partner_type.split(",")
            if partner_data:
                obj = partner_data[0]
                id = int(partner_data[1])
            # Case where the partner_type is res.partner
            if obj == 'res.partner':
                # if amount is inferior to 0, then we give the account_payable
                res_account = None
                if amount < 0:
                    res_account = self.pool.get('res.partner').read(cr, uid, [id], 
                        ['property_account_payable'], context=context)[0].get('property_account_payable', False)
                elif amount > 0:
                    res_account = self.pool.get('res.partner').read(cr, uid, [id], 
                        ['property_account_receivable'], context=context)[0].get('property_account_receivable', False)
                if res_account:
                    res['value'] = {'account_id': res_account[0]}
#            # Case where the partner_type is account.bank.statement
#            if obj == 'account.bank.statement':
#                # if amount is inferior to 0, then we give the debit account
#                register = self.pool.get('account.bank.statement').browse(cr, uid, [id], context=context)
#                account_id = False
#                if register and amount < 0:
#                    account_id = register[0].journal_id.default_debit_account_id.id
#                elif register and amount > 0:
#                    account_id = register[0].journal_id.default_credit_account_id.id
#                if account_id:
#                    res['value'] = {'account_id': account_id}
        return res

account_bank_statement_line()

class ir_values(osv.osv):
    _name = 'ir.values'
    _inherit = 'ir.values'

    def get(self, cr, uid, key, key2, models, meta=False, context=None, res_id_req=False, without_user=True, key2_req=True):
        if context is None:
            context = {}
        values = super(ir_values, self).get(cr, uid, key, key2, models, meta, context, res_id_req, without_user, key2_req)
        if context.get('type_posting') and key == 'action' and key2 == 'client_action_multi' and 'account.bank.statement.line' in [x[0] for x in models]:
            new_act = []
            for v in values:
                if v[1] != 'act_wizard_temp_posting' and context['type_posting'] == 'hard' or v[1] != 'act_wizard_hard_posting' and context['type_posting'] == 'temp':
                    new_act.append(v)
            values = new_act
        elif context.get('journal_type') and key == 'action' and key2 == 'client_print_multi' and 'account.bank.statement' in [x[0] for x in models]:
            new_act = []
            for v in values:
                if v[1] == 'Bank Reconciliation' and context['journal_type'] == 'bank' \
                or v[1] == 'Cash Inventory' and context['journal_type'] == 'cash' \
                or v[1] == 'Open Advances' and context['journal_type'] == 'cash' \
                or v[1] == 'Cheque Inventory' and context['journal_type'] == 'cheque' \
                or v[1] == 'Liquidity Position' and context['journal_type'] != 'cheque':
                    new_act.append(v)
            values = new_act
        return values

ir_values()
