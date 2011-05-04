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
import time
from datetime import datetime

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

    def _end_balance(self, cr, uid, ids, field_name=None, arg=None, context={}):
        """
        Calculate register's balance
        """
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

    def _get_register_id(self, cr, uid, ids, field_name=None, arg=None, context={}):
        """
        Get current register id
        """
        res = {}
        for st in self.browse(cr, uid, ids, context=context):
            res[st.id] = st.id
        return res

    _columns = {
        'balance_end': fields.function(_end_balance, method=True, store=False, string='Balance', \
            help="Closing balance based on Starting Balance and Cash Transactions"),
        'virtual_id': fields.function(_get_register_id, method=True, store=False, type='integer', string='Id', readonly="1",
            help='Virtual Field that take back the id of the Register'),
    }

    _defaults = {
        'balance_start': lambda *a: 0.0,
    }

    def balance_check(self, cr, uid, register_id, journal_type='bank', context=None):
        """
        Check the balance for Registers
        """
        if not context:
            context={}
        if journal_type == 'cash':
            if not self._equal_balance(cr, uid, register_id, context):
                raise osv.except_osv(_('Error !'), _('CashBox Balance is not matching with Calculated Balance !'))
        st = self.browse(cr, uid, register_id, context=context)
        if not (abs((st.balance_end or 0.0) - st.balance_end_real) < 0.0001):
            raise osv.except_osv(_('Error !'),
                    _('The statement balance is incorrect !\n') +
                    _('The expected balance (%.2f) is different than the computed one. (%.2f)') % (st.balance_end_real, st.balance_end))
        return True

    def write(self, cr, uid, ids, values, context={}):
        """
        Bypass disgusting default account_bank_statement write function
        """
        return super(osv.osv, self).write(cr, uid, ids, values, context=context)

    def button_open_bank(self, cr, uid, ids, context={}):
        """
        when pressing 'Open Bank' button
        """
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

            self.write(cr, uid, [st.id], {'name': st_number}, context=context)
            self.log(cr, uid, st.id, _('Statement %s is confirmed, journal items are created.') % (st_number,))
#            done.append(st.id)
        return self.write(cr, uid, ids, {'state':'confirm', 'closing_date': datetime.today()}, context=context)
        # @@@end

account_bank_statement()

class account_bank_statement_line(osv.osv):
    _name = "account.bank.statement.line"
    _inherit = "account.bank.statement.line"

    _order = 'date desc, id desc'

    def _get_state(self, cr, uid, ids, field_name=None, arg=None, context={}):
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

    def _get_amount(self, cr, uid, ids, field_name=None, arg=None, context={}):
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

    def _search_state(self, cr, uid, obj, name, args, context={}):
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
        # Non expected case
        if not filterok:
            raise osv.except_osv(_('Warning'), _('This filter is not implemented yet!'))
        return [('id', 'in', ids)]

    def _get_reconciled_state(self, cr, uid, ids, field_name=None, args=None, context={}):
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

    def _search_reconciled(self, cr, uid, obj, name, args, context={}):
        """
        Search all lines that are reconciled or not
        """
        result = []
        # Test how many arguments we have
        if not len(args):
            return res
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

    _columns = {
        'register_id': fields.many2one("account.bank.statement", "Register"),
        'employee_id': fields.many2one("hr.employee", "Employee"),
        'amount_in': fields.function(_get_amount, method=True, string="Amount In", type='float'),
        'amount_out': fields.function(_get_amount, method=True, string="Amount Out", type='float'),
        'state': fields.function(_get_state, fnct_search=_search_state, method=True, string="Status", type='selection', selection=[('draft', 'Empty'), 
            ('temp', 'Temp'), ('hard', 'Hard'), ('unknown', 'Unknown')]),
        'partner_type': fields.function(_get_third_parties, fnct_inv=_set_third_parties, type='reference', method=True, 
            string="Third Parties", selection=[('res.partner', 'Partner'), ('hr.employee', 'Employee'), ('account.bank.statement', 'Register')], 
            multi="third_parties_key"),
        'partner_type_mandatory': fields.boolean('Third Party Mandatory'),
        'reconciled': fields.function(_get_reconciled_state, fnct_search=_search_reconciled, method=True, string="Amount Reconciled", type='boolean'),
        'sequence_for_reference': fields.integer(string="Sequence", readonly=True),
        'document_date': fields.date(string="Document Date"),
        'mandatory': fields.char(string="Cheque Number", size=120),
        'from_cash_return': fields.boolean(string='Come from a cash return?'),
        'direct_invoice': fields.boolean(string='Direct invoice?'),
        'invoice_id': fields.many2one('account.invoice', "Invoice", required=False),
        'first_move_line_id': fields.many2one('account.move.line', "Register Move Line"),
        'third_parties': fields.function(_get_third_parties, type='reference', method=True, 
            string="Third Parties", selection=[('res.partner', 'Partner'), ('hr.employee', 'Employee'), ('account.bank.statement', 'Register')], 
            help="To use for python code when registering", multi="third_parties_key"),
    }

    _defaults = {
        'from_cash_return': lambda *a: 0,
        'direct_invoice': lambda *a: 0,
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
            'move_id': move_id,
            'partner_id': ((st_line.partner_id) and st_line.partner_id.id) or False,
            # Add employee_id, register_id and partner_type support
            'employee_id': ((st_line.employee_id) and st_line.employee_id.id) or False,
            'register_id': ((st_line.register_id) and st_line.register_id.id) or False,
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
            'analytic_account_id': st_line.analytic_account_id and st_line.analytic_account_id.id or False
        }

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
            'move_id': move_id,
            'partner_id': ((st_line.partner_id) and st_line.partner_id.id) or False,
            # Add employee_id and register_id support
            'employee_id': ((st_line.employee_id) and st_line.employee_id.id) or False,
            'register_id': ((st_line.register_id) and st_line.register_id.id) or False,
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

    def _verify_dates(self, cr, uid, ids, context={}):
        """
        Verify that the given parameter contains date. Then validate date with regarding register period.
        """
        # Prepare some values
        st_line = self.browse(cr, uid, ids[0], context=context)
        register = st_line.statement_id
        account_id = st_line.account_id.id
        date = st_line.date
        period_start = register.period_id.date_start
        period_stop = register.period_id.date_stop
        # Verify that the date is included between period_start and period_stop
        if date < period_start or date > period_stop:
            raise osv.except_osv(_('Error'), _('The date is outside the register period!'))
        # Verify that the date is useful with default debit or credit account activable date 
        #+ (in fact the default debit and credit account have an activation date, and the given account_id too)
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
                raise osv.except_osv(_('Error'), _('Posting date is outside the validity period of the default account for this register!'))
        if account_id:
            account = acc_obj.browse(cr, uid, account_id, context=context)
            if date < account.activation_date or (account.inactivation_date and date > account.inactivation_date):
                raise osv.except_osv(_('Error'), _('Posting date is outside the validity period of the selected account for this record!'))
        return True

    _constraints = [
        (_verify_dates, "Date is not correct. Verify that it's in the register's period. ", ['date']),
    ]

    def _update_move_from_st_line(self, cr, uid, st_line_id=None, values=None, context={}):
        """
        Update move lines from given statement lines
        """
        if not st_line_id or not values:
            return False

        # Prepare some values
        move_line_values = values.copy()
        acc_move_line_obj = self.pool.get('account.move.line')
        st_line = self.browse(cr, uid, st_line_id, context=context)
        # Get first line (from Register account)
        register_line = st_line.first_move_line_id
        if register_line:
            # Search second move line
            other_line_id = acc_move_line_obj.search(cr, uid, [('move_id', '=', st_line.move_ids[0].id), ('id', '!=', register_line.id)], context=context)[0]
            other_line = acc_move_line_obj.browse(cr, uid, other_line_id, context=context)
            other_account_id = values.get('account_id', other_line.account_id.id)
            amount = values.get('amount', st_line.amount)
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
            currency_id = False
            if st_line.statement_id.currency.id != st_line.statement_id.company_id.currency_id.id:
                # Prepare value
                res_currency_obj = self.pool.get('res.currency')
                # Get date for having a good change rate
                context.update({'date': values.get('date', st_line.date)})
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
            values.update({'account_id': register_account_id, 'debit': register_debit, 'credit': register_credit, 'amount_currency': register_amount_currency, 
                'currency_id': currency_id})
            # Write move line object for register line
            acc_move_line_obj.write(cr, uid, [register_line.id], values, context=context)
            # Update values for other line
            values.update({'account_id': other_account_id, 'debit': other_debit, 'credit': other_credit, 'amount_currency': other_amount_currency, 
                'currency_id': currency_id})
            # Write move line object for other line
            acc_move_line_obj.write(cr, uid, [other_line.id], values, context=context)
            # Update move
            # first prepare partner_type
            partner_type = False
            if st_line.third_parties:
                partner_type = ','.join([str(st_line.third_parties._table_name), str(st_line.third_parties.id)])
            # then prepare name
            name = values.get('name', st_line.name) + '/' + str(st_line.sequence)
            # finally write move object
            self.pool.get('account.move').write(cr, uid, [register_line.move_id.id], {'partner_type': partner_type, 'name': name}, context=context)
        return True

    def do_direct_expense(self, cr, uid, ids, context={}):
        """
        Do a direct expense when the line is hard posted and content a supplier
        """
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
                    'date': st_line.document_date or st_line.date or curr_date,
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

    def do_direct_invoice(self, cr, uid, ids, context={}):
        """
        Make an invoice from the statement line that have a supplier and take back :
        - amount for invoice
        - supplier
        - journal from register
        - currency from register
        - document_date (from invoice date), ifelse, we retrieve date
        Then it give some values:
        - type : in_invoice
        """
        for st_line in self.browse(cr, uid, ids, context=context):
            # Do treatments only if supplier and direct_invoice are filled in
            if st_line.direct_invoice:
                # Case where user don't filled in Third Parties for a direct invoice
                if not st_line.partner_id or not st_line.partner_id.supplier:
                    raise osv.except_osv(_('Warning'), _('Please update Third Parties field with a Supplier in order to do a direct invoice.'))
                # Prepare some values
                date = st_line.document_date or st_line.date or False
                inv_obj = self.pool.get('account.invoice')
                st_line_obj = self.pool.get('account.bank.statement.line')
                # on an invoice, amount is reversed
                amount = -st_line.amount
                vals = {
                    'type': 'in_invoice',
                    'state': 'draft',
                    'date_invoice': date,
                    'partner_id': st_line.partner_id.id,
                    'period_id': st_line.statement_id.period_id.id,
                    'currency_id': st_line.statement_id.currency.id,
                    'journal_id': st_line.statement_id.journal_id.id,
                    'check_total': amount,
                    'register_line_ids': [(4, st_line.id)],
                }
                # Update val with some fields : address_contact_id, address_invoice_id, account_id, payment_term and fiscal_position
                vals.update(inv_obj.onchange_partner_id(cr, uid, ids, 'in_invoice', st_line.partner_id.id, date).get('value', {}))
                # Create an invoice
                inv_id = inv_obj.create(cr, uid, vals, context=context)
                # Verify that the invoice creation success
                if not inv_id:
                    raise osv.except_osv(_('Error'), _('The invoice creation failed!'))
                # Link this invoice to the statement line. NB: from_cash_return is permits "Cash Return" button to be hidden
                res = st_line_obj.write(cr, uid, [st_line.id], {'invoice_id': inv_id, 'from_cash_return': True}, context=context)
                if not res:
                    raise osv.except_osv(_('Error'), _('Link to invoice failed!'))
        return True

    def create(self, cr, uid, values, context={}):
        """
        Create a new account bank statement line with values
        """
        # First update amount
        values = self._update_amount(values=values)
        # Then create a new bank statement line
        return super(account_bank_statement_line, self).create(cr, uid, values, context=context)

    def write(self, cr, uid, ids, values, context={}):
        """
        Write some existing account bank statement lines with 'values'.
        """
        # Prepare some values
        state = self._get_state(cr, uid, ids, context=context).values()[0]
        # Verify that the statement line isn't in hard state
        if state  == 'hard':
            if values == {'from_cash_return': True} or (values.get('invoice_id', False) and len(values.keys()) == 2 and values.get('from_cash_return')):
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
        return super(account_bank_statement_line, self).write(cr, uid, ids, values, context=context)

    def posting(self, cr, uid, ids, postype, context={}):
        """
        Write some statement line into some account move lines with a state that depends on postype.
        """
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
                self.create_move_from_st_line(cr, uid, absl.id, absl.statement_id.journal_id.company_id.currency_id.id, 
                    absl.name+ '/' + str(absl.sequence), context=context)

            if postype == "hard":
                seq = self.pool.get('ir.sequence').get(cr, uid, 'all.registers')
                self.write(cr, uid, [absl.id], {'sequence_for_reference': seq}, context=context)
                acc_move_obj.post(cr, uid, [x.id for x in absl.move_ids], context=context)
                # do a move that enable a complete supplier follow-up
                self.do_direct_expense(cr, uid, [absl.id], context=context)
                # do a direct expense if necessary
                if absl.direct_invoice:
                    self.do_direct_invoice(cr, uid, [absl.id], context=context)
        return True

    def button_hard_posting(self, cr, uid, ids, context={}):
        """
        Write some statement line into some account move lines in posted state.
        """
        return self.posting(cr, uid, ids, 'hard', context=context)

    def button_temp_posting(self, cr, uid, ids, context={}):
        """
        Write some statement lines into some account move lines in draft state.
        """
        return self.posting(cr, uid, ids, 'temp', context=context)

    def unlink(self, cr, uid, ids, context={}):
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
                    self.pool.get('account.move').unlink(cr, uid, [x.id for x in st_line.move_ids])
        return super(account_bank_statement_line, self).unlink(cr, uid, ids)

    def button_advance(self, cr, uid, ids, context={}):
        """
        Launch a wizard when you press "Advance return" button on a bank statement line in a Cash Register
        """
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
        # then print the wizard with an active_id = cash_register_id, and giving in the context a number of the bank statement line
        st_obj = self.pool.get('account.bank.statement.line')
        st = st_obj.browse(cr, uid, ids[0]).statement_id
        if st and st.state != 'open':
            raise osv.except_osv(_('Error'), _('You cannot do a cash return in Register which is in another state that "open"!'))
        statement_id = st.id
        amount = self.read(cr, uid, ids[0], ['amount']).get('amount', 0.0)
        if amount >= 0:
            raise osv.except_osv(_('Warning'), _('Please select a line with a filled out "amount out"!'))
        wiz_obj = self.pool.get('wizard.cash.return')
        wiz_id = wiz_obj.create(cr, uid, {'returned_amount': 0.0, 'initial_amount': abs(amount), 'advance_st_line_id': ids[0], \
            'currency_id': st_line.statement_id.currency.id}, context=context)
        if statement_id:
            return {
                'name' : "Advance Return",
                'type' : 'ir.actions.act_window',
                'res_model' :"wizard.cash.return",
                'target': 'new',
                'view_mode': 'form',
                'view_type': 'form',
                'res_id': [wiz_id],
                'context': 
                {
                    'active_id': ids[0],
                    'active_ids': ids,
                    'statement_line_id': ids[0],
                    'statement_id': statement_id,
                    'amount': amount
                }
            }
        else:
            return False

    def button_open_invoice(self, cr, uid, ids, context={}):
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

    def onchange_account(self, cr, uid, ids, account_id=None, statement_id=None, context={}):
        """
        Update Third Party type regarding account type_for_register field.
        """
        # Prepare some values
        acc_obj = self.pool.get('account.account')
        third_type = [('res.partner', 'Partner')]
        third_required = False
        third_selection = 'res.partner,0'
        domain = {'partner_type': []}
        # if an account is given, then attempting to change third_type and information about the third required
        if account_id:
            account = acc_obj.browse(cr, uid, [account_id], context=context)[0]
            acc_type = account.type_for_register
            # if the account is a payable account, then we change the domain
            if acc_type == 'partner':
                if account.type == "payable":
                    domain = {'partner_type': [('property_account_payable', '=', account_id)]}
                elif account.type == "receivable":
                    domain = {'partner_type': [('property_account_receivable', '=', account_id)]}

            if acc_type == 'transfer':
                third_type = [('account.bank.statement', 'Register')]
                third_required = True
                third_selection = 'account.bank.statement,0'
                domain = {'partner_type': [('state', '=', 'open')]}
                if statement_id:
                    domain = {'partner_type': [('state', '=', 'open'), ('id', '!=', statement_id)]}
            elif acc_type == 'advance':
                third_type = [('hr.employee', 'Employee')]
                third_required = True
                third_selection = 'hr.employee,0'
        return {'value': {'partner_type_mandatory': third_required, 'partner_type': {'options': third_type, 'selection': third_selection}}, 'domain': domain}

    def onchange_partner_type(self, cr, uid, ids, partner_type=None, amount_in=None, amount_out=None, context={}):
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
