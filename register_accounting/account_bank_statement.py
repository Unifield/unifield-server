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

class account_bank_statement(osv.osv):
    _name = "account.bank.statement"
    _inherit = "account.bank.statement"

    _sql_constraints = [
        ('period_journal_uniq', 'unique (period_id, journal_id)', 'You cannot have a register on the same period and the same journal!')
    ]

    def _end_balance(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Calculate register's balance
        """
        st_line_obj = self.pool.get("account.bank.statement.line")
        res = {}

        statements = self.browse(cr, uid, ids, context=context)
        for statement in statements:
            res[statement.id] = statement.balance_start
            st_line_ids = st_line_obj.search(cr, uid, [('statement_id', '=', statement.id)], context=context)
            for st_line_id in st_line_ids:
                st_line_data = st_line_obj.read(cr, uid, [st_line_id], ['amount'], context=context)[0]
                if 'amount' in st_line_data:
                    res[statement.id] += st_line_data.get('amount')
        for r in res:
            res[r] = round(res[r], 2)
        return res

    _columns = {
        'balance_end': fields.function(_end_balance, method=True, store=True, string='Balance', \
            help="Closing balance based on Starting Balance and Cash Transactions"),
    }

    def button_open_bank(self, cr, uid, ids, context={}):
        """
        when pressing 'Open Bank' button
        """
        return self.write(cr, uid, ids, {'state': 'open'})

    def button_confirm_bank(self, cr, uid, ids, context={}):
        """
        When using 'Confirm' button in a bank register
        """
        st_line_obj = self.pool.get('account.bank.statement.line')
        for st_line_id in st_line_obj.search(cr, uid, [('statement_id', '=', ids[0])]):
            reconciled_state = st_line_obj.read(cr, uid, st_line_id, ['reconciled']).get('reconciled', False)
            if not reconciled_state:
                raise osv.except_osv(_('Warning'), _('Some lines are not reconciled! Please reconcile all lines before confirm this Register.'))
        return super(account_bank_statement, self).button_confirm_bank(cr, uid, ids, context=context)

account_bank_statement()

class account_bank_statement_line(osv.osv):
    _name = "account.bank.statement.line"
    _inherit = "account.bank.statement.line"

    _order = 'date desc'

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
            if absl.move_ids:
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
        sql_posted_moves = """
            SELECT st.id FROM account_bank_statement_line st
            LEFT JOIN account_bank_statement_line_move_rel rel ON rel.move_id = st.id
            LEFT JOIN account_move move ON rel.statement_id = move.id
            WHERE rel.move_id is not null AND move.state = 'posted'
        """
        cr.execute(sql_posted_moves)
        res = cr.fetchall()
        st_line_obj = self.pool.get('account.bank.statement.line')
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        reconciled = []
        for id in res:
            moves = st_line_obj.read(cr, uid, id[0], ['move_ids'], context=context).get('move_ids')
            # Search in this moves all move lines that have a reconciliable account
            move_ids = "(%s)" % ','.join(map(str, moves))
            sql_reconciliable_moves = """
                SELECT line.id FROM account_move_line line, account_move move, account_account ac
                WHERE move.id in """ + move_ids + """
                AND line.account_id = ac.id AND ac.reconcile = 't'
            """
            cr.execute(sql_reconciliable_moves)
            lines = cr.fetchall()
            # Retrive number of lines that have a reconciliable account
            nb_lines = len(lines)
            # Now we remember the number of lines that have a reconcile_id (this imply they are reconciled)
            count = 0
            for line_id in lines:
                reconcile_id = move_line_obj.read(cr, uid, line_id[0], ['reconcile_id'], context=context).get('reconcile_id', False)
                if reconcile_id:
                    count += 1
            # If all browsed lines are reconciled we add the st_line_id (id) in the result
            if count == nb_lines:
                reconciled.append(id)
        # Give result regarding args[0][2] (True or False)
        if args[0][2] == True:
            result = reconciled
        elif args[0][2] == False:
            # Search all statement lines
            sql = """
                SELECT st.id FROM account_bank_statement_line st
                """
            cr.execute(sql)
            statement_line_ids = cr.fetchall()
            # Make a difference between
            result = list(set(statement_line_ids) - set(reconciled))
        # Return a list of tuple (id,) that correspond to the search
        return [('id', 'in', [x[0] for x in result])]

    _columns = {
        'register_id': fields.many2one("account.bank.statement", "Register"),
        'employee_id': fields.many2one("hr.employee", "Employee"),
        'amount_in': fields.function(_get_amount, method=True, string="Amount In", type='float'),
        'amount_out': fields.function(_get_amount, method=True, string="Amount Out", type='float'),
        'state': fields.function(_get_state, fnct_search=_search_state, method=True, string="Status", type='selection', selection=[('draft', 'Empty'), 
            ('temp', 'Temp'), ('hard', 'Hard'), ('unknown', 'Unknown')]),
        'partner_type': fields.function(_get_third_parties, fnct_inv=_set_third_parties, type='reference', method=True, 
            string="Third Parties", selection=[('res.partner', 'Partner'), ('hr.employee', 'Employee'), ('account.bank.statement', 'Register')]),
        'partner_type_mandatory': fields.boolean('Third Party Mandatory'),
        'reconciled': fields.function(_get_reconciled_state, fnct_search=_search_reconciled, method=True, string="Amount Reconciled", type='boolean'),
        'sequence_for_reference': fields.integer(string="Sequence", readonly=True),
        'document_date': fields.date(string="Document Date"),
        'mandatory': fields.char(string="Mandatory", size=120),
        'from_cash_return': fields.boolean(string='Come from a cash return?'),
        'direct_invoice': fields.boolean(string='Direct invoice?'),
        'invoice_id': fields.many2one('account.invoice', "Invoice", required=False),
    }

    _defaults = {
        'from_cash_return': lambda *a: 0,
        'direct_invoice': lambda *a: 0,
    }
    
    def create_move_from_st_line(self, cr, uid, st_line_id, company_currency_id, st_line_number, context=None):
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
        if st_line.partner_type:
            partner_type = ','.join([str(st_line.partner_type._table_name), str(st_line.partner_type.id)])
        # end of add

        move_id = account_move_obj.create(cr, uid, {
            'journal_id': st.journal_id.id,
            'period_id': st.period_id.id,
            'date': st_line.date,
            'name': st_line_number,
            ## Add partner_type
            'partner_type': partner_type or False,
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
            'ref': st_line.ref,
            'move_id': move_id,
            'partner_id': ((st_line.partner_id) and st_line.partner_id.id) or False,
            # Add employee_id, register_id and partner_type support
            'employee_id': ((st_line.employee_id) and st_line.employee_id.id) or False,
            'register_id': ((st_line.register_id) and st_line.register_id.id) or False,
            'partner_type': partner_type or False,
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
            #amount_cur = res_currency_obj.compute(cr, uid, company_currency_id,
            #            st.currency.id, amount, context=context)
            val['amount_currency'] = st_line.amount

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
        account_move_line_obj.create(cr, uid, {
            'name': st_line.name,
            'date': st_line.date,
            'ref': st_line.ref,
            'move_id': move_id,
            'partner_id': ((st_line.partner_id) and st_line.partner_id.id) or False,
            # Add employee_id and register_id support
            'employee_id': ((st_line.employee_id) and st_line.employee_id.id) or False,
            'register_id': ((st_line.register_id) and st_line.register_id.id) or False,
            'partner_type': partner_type or False,
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
        return move_id

    def _updating_amount(self, values):
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
                val.update({'debit': amount, 'credit': 0.0})
                move_line_debit_id = move_line_obj.create(cr, uid, val, context=context)
                val.update({'debit': 0.0, 'credit': amount})
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
        # Verify that no supplementary field is not required
        if 'partner_type_mandatory' in values:
            if values.get('partner_type_mandatory') is True and values.get('partner_type') is False:
                raise osv.except_osv(_('Warning'), _('You should fill in Third Parties field!'))
        # First update amount
        values = self._updating_amount(values=values)
        # Then create a new bank statement line
        return super(account_bank_statement_line, self).create(cr, uid, values, context=context)

    def write(self, cr, uid, ids, values, context={}):
        """
        Write some existing account bank statement lines with 'values'.
        """
        # Prepare some values
        state = self._get_state(cr, uid, ids, context=context).values()[0]
        # Verify that no supplementary field is not required
        if 'partner_type_mandatory' in values:
            if values.get('partner_type_mandatory') is True and values.get('partner_type') is False:
                raise osv.except_osv(_('Warning'), _('You should fill in Third Parties field!'))
        # Verify that the statement line isn't in hard state
        if state  == 'hard':
            if 'from_cash_return' in values or 'invoice_id' in values:
                return super(account_bank_statement_line, self).write(cr, uid, ids, values, context=context)
            raise osv.except_osv(_('Warning'), _('You cannot write a hard posted entry.'))
        # First update amount
        values = self._updating_amount(values=values)
        # Case where _updating_amount return False ! => this imply there is a problem with amount columns
        if not values:
            return False
        # In case of Temp Posting, we also update attached account move lines
        if state == 'temp':
            move_line_values = values.copy()
            acc_move_line_obj = self.pool.get('account.move.line')
            for st_line in self.browse(cr, uid, ids, context=context):
                for move_line_id in acc_move_line_obj.search(cr, uid, [('move_id', '=', st_line.move_ids[0].id)]):
                    move_line = acc_move_line_obj.read(cr, uid, [move_line_id], context=context)[0]
                    # Update values
                    # Let's have a look to the amount
                    # first retrieve some values
                    # Because of sequence problems and multiple writing on lines, we have to see if variables are given
                    default_st_account = None
                    if 'amount' in values and 'credit' in move_line and 'debit' in move_line:
                        amount = values.get('amount', False)
                        credit = move_line.get('credit', False)
                        debit = move_line.get('debit', False)
                        # then choose where to place amount
                        new_debit = debit
                        new_credit = credit
                        if amount and credit or debit:
                            line_is_debit = False
                            line_is_credit = False
                            # then choose where take it
                            if debit > credit:
                                new_debit = abs(amount)
                                new_credit = 0.0
                                default_st_account = st_line.statement_id.journal_id.default_debit_account_id.id
                                line_is_debit = True
                            elif debit < credit:
                                new_debit = 0.0
                                new_credit = abs(amount)
                                default_st_account = st_line.statement_id.journal_id.default_credit_account_id.id
                                line_is_credit = True
                            #+ - if no different currency that OC currency, then update debit and credit
                            #+ - else update amount_currency
                            currency_id =  st_line.statement_id.journal_id.currency.id or None
                            # If a currency exist, we do some computation before sending amount
                            if currency_id:
                                res_currency_obj = self.pool.get('res.currency')
                                #TODO : change this when we have debate on "instance" definition
                                # Note: the first currency_id must be those of the journal of the cash statement
                                context.update({'date': move_line.get('date', False)}) # this permit to make the change with currency at the good date
                                line_accounting_value = res_currency_obj.compute(cr, uid, \
                                    st_line.statement_id.journal_id.currency.id, st_line.company_id.currency_id.id, amount, context=context)
                                if line_is_debit:
                                    new_debit = abs(line_accounting_value)
                                    new_credit = 0.0
                                    new_amount = amount
                                else:
                                    new_debit = 0.0
                                    new_credit = abs(line_accounting_value)
                                    new_amount = -amount
                                if currency_id == st_line.company_id.currency_id.id:
                                    new_amount = 0.0
                                # update amount_currency for the move line
                                move_line_values.update({'amount_currency': new_amount})
                            # Nonetheless the result, we have to update debit and credit
                            move_line_values.update({'debit': new_debit, 'credit': new_credit})

                    # Then we try to search account_id in order to produce 'account_id' value for the account move line.
                    #+ But for that, search if we are in a debit line or a credit line
                    if default_st_account:
                        st_line_account = st_line.account_id.id
                        move_line_account = move_line.get('account_id')[0]
                        if st_line_account == move_line_account:
                            new_account = values.get('account_id')
                        else:
                            new_account = default_st_account
                        move_line_values.update({'account_id': new_account})
                    # write of new values
                    acc_move_line_obj.write(cr, uid, [move_line_id], move_line_values, context=context)
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
        statement_id = self.read(cr, uid, ids[0], ['statement_id']).get('statement_id', False)[0]
        amount = self.read(cr, uid, ids[0], ['amount']).get('amount', 0.0)
        if amount >= 0:
            raise osv.except_osv(_('Warning'), _('Please select a line with a filled out "amount out"!'))
        wiz_obj = self.pool.get('wizard.cash.return')
        wiz_id = wiz_obj.create(cr, uid, {'returned_amount': 0.0, 'initial_amount': abs(amount), 'advance_st_line_id': ids[0], \
            'currency_id': st_line.statement_id.journal_id.currency.id}, context={})
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

    def onchange_account(self, cr, uid, ids, account_id, context={}):
        """
        Update Third Party type regarding account type_for_register field.
        """
        # Prepare some values
        acc_obj = self.pool.get('account.account')
        third_type = [('res.partner', 'Partner')]
        third_required = False
        third_selection = 'res.partner,0'
        domain = {}
        # if an account is given, then attempting to change third_type and information about the third required
        if account_id:
            account = acc_obj.browse(cr, uid, [account_id], context=context)[0]
            acc_type = account.type_for_register
            # if the account is a payable account, then we change the domain
            if account.type == "payable":
                domain = {'partner_type': [('property_account_payable', '=', account_id), ('supplier', '=', 1)]}

            if acc_type == 'transfer':
                third_type = [('account.bank.statement', 'Register')]
                third_required = True
                third_selection = 'account.bank.statement,0'
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
            # Case where the partner_type is account.bank.statement
            if obj == 'account.bank.statement':
                # if amount is inferior to 0, then we give the debit account
                register = self.pool.get('account.bank.statement').browse(cr, uid, [id], context=context)
                if register and amount < 0:
                    account_id = register[0].journal_id.default_debit_account_id.id
                elif register and amount > 0:
                    account_id = register[0].journal_id.default_credit_account_id.id
                if account_id:
                    res['value'] = {'account_id': account_id}
        return res

account_bank_statement_line()
