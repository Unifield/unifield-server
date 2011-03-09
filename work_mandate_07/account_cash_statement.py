#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution    
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    Author: Tempo Consulting (<http://www.tempo-consulting.fr/>), MSF.
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

# For account_bank_statement only
import decimal_precision as dp
import time

class account_bank_statement_line(osv.osv):
    _name = "account.bank.statement.line"
    _inherit = "account.bank.statement.line"

    def _get_state(self, cr, uid, ids, field_name=None, arg=None, context={}):
        """
        Return account_bank_statement_line state in order to know if the bank statement line is in :
        - draft
        - temp posting
        - hard posting
        - unknown if an error occured or anything else (for an example the move have a new state)
        """
        # Preparation of some variables
        res = {}
        acc_st_line_obj = self.pool.get("account.bank.statement.line")
        for absl in self.browse(cr, uid, ids, context=context):
            statement_id = absl.statement_id.id
            # Searching all moves linked to an account bank statement line attached
            st_line = acc_st_line_obj.browse(cr, uid, absl.id, context=context)
            # Verifying move existence
            if not st_line.move_ids:
                res[absl.id] = 'draft'
                continue
            # If exists, check move state
            state = st_line.move_ids[0].state
            if state == 'draft':
                res[absl.id] = 'temp'
            elif state == 'posted':
                res[absl.id] = 'hard'
            else:
                res[absl.id] = 'unknown'
        return res

    def _get_amount(self, cr, uid, ids, field_name=None, arg=None, context={}):
        # Variable initialisation
        default_amount = 0.0
        res = {}
        # Browsing account bank statement lines
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

    _columns = {
        'register_id': fields.many2one("account.account", "Register"),
        'employee_id': fields.many2one("account.account", "Employee"),
        'amount_in': fields.function(_get_amount, method=True, string="Amount In", type='float'),
        'amount_out': fields.function(_get_amount, method=True, string="Amount Out", type='float'),
        'state': fields.function(_get_state, method=True, string="State", type='selection', selection=[('draft', 'Empty'), \
            ('temp', 'Temp'), ('hard', 'Hard'), ('unknown', 'Unknown')]),
        'partner_type': fields.reference("Third Parties", [('res.partner', 'Partners'), ('hr.employee', 'Employee'), \
            ('account.bank.statement', 'Register')], 128),
    }

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
                #FIXME: Add an exception to the user if possible. Not possible at this moment because of multiple writings
                raise osv.except_osv(_('Error'), _('Please correct amount fields!'))
#                return False
        if amount:
            res.update({'amount': amount})
        return res

    def create(self, cr, uid, values, context={}):
        """
        Create a new account bank statement line with values
        """
        # First update amount
        values = self._updating_amount(values=values)
        # Then creating a new bank statement line
        return super(account_bank_statement_line, self).create(cr, uid, values, context=context)

    def write(self, cr, uid, ids, values, context={}):
        """
        Write some existing account bank statement lines with 'values'.
        
        """
        # Preparing some values
        state = self._get_state(cr, uid, ids, context=context).values()[0]
        # Verifying that the statement line isn't in hard state
        if state  == 'hard':
            return False
        # First update amount
        values = self._updating_amount(values=values)
        # Case where _updating_amount return False ! => this imply there is a problem with amount columns
        if not values:
            return False
        # In case of Temp Posting, we also update attached account move lines
        if state == 'temp':
            data = values.copy()
            #FIXME: update account move lines
            acc_move_line_obj = self.pool.get('account.move.line')
            for move in self.browse(cr, uid, ids, context=context):
                for line in acc_move_line_obj.search(cr, uid, [('move_id', '=', move.move_ids[0].id)]):
                    old_line = acc_move_line_obj.read(cr, uid, [line], context=context)[0]
                    # Updating values
                    # first we try to search account_id in order to produce 'account_id' value for the account move line
                    account_id = values.get('account_id', False)
                    # then we build the account value
                    if account_id:
                        account = self.pool.get('account.account').browse(cr, uid, [account_id], context=context)
                        account_value = (account_id, str(account[0].code) + ' ' + str(account[0].name))
                        data.update({'account': account_value})
                    # Let's have a look to the amount
                    # first retrieving some values
                    amount = abs(values.get('amount', False))
                    credit = old_line.get('credit', False)
                    debit = old_line.get('debit', False)
                    # then choosing where to place amount
                    if amount and credit or debit:
                        # then choosing where take it
                        if debit > credit:
                            new_debit = amount
                            new_credit = 0.0
                        else:
                            new_debit = 0.0
                            new_credit = amount
                        data.update({'debit': new_debit, 'credit': new_credit})
                    # writing of new values
                    acc_move_line_obj.write(cr, uid, [line], data, context=context)
        # Updating the bank statement lines with 'values'
        return super(account_bank_statement_line, self).write(cr, uid, ids, values, context=context)

    def button_hard_posting(self, cr, uid, ids, context={}):
        """
        Write some statement line into some account move lines in posted state.
        Warning! : this function is used by 'button_temp_posting'. Please take care of returning all account_move_ids !
        """
        # Variable initialisation
        res = []
        if context:
            statement_id = context.get('active_id', False)
        if not statement_id:
            raise osv.except_osv(_('Warning'), _('There is no active_id. Please contact an administrator to resolve the problem.'))
        cash_statement = self.browse(cr, uid, statement_id)
        cash_st_obj = self.pool.get("account.bank.statement")
        acc_move_obj = self.pool.get("account.move")
        currency_id = cash_statement.statement_id.journal_id.company_id.currency_id.id
        # browsing all statement lines for creating move lines
        for absl in self.browse(cr, uid, ids, context=context):
            # creating move lines
            if absl.state == "draft":
                #FIXME: which code could we return for the move line ?
                st_name = cash_statement.name + '/' + str(absl.sequence)
                # creating move from statement line
                res_id = cash_st_obj.create_move_from_st_line(cr, uid, absl.id, currency_id, st_name, context=context)
                res.append(res_id)
            elif absl.state == "temp":
                # Search attached move
                move = acc_move_obj.browse(cr, uid, absl.move_ids[0].id, context=context)
                # Change state of this move
                acc_move_obj.write(cr, uid, [move.id], {'state': 'posted'}, context=context)
        return res

    def button_temp_posting(self, cr, uid, ids, context={}):
        """
        Write some statement lines into some account move lines in draft state.
        Warning! : this function take advantage of 'button_hard_posting' for temp posting entries.
        Indeed you have to use account moves returned by 'button_hard_posting' to unpost them.
        """
        # Variable initialisation
        res = []
        acc_move_obj = self.pool.get("account.move")
        hard_posting_ids = self.button_hard_posting(cr, uid, ids, context=context)
        for id in hard_posting_ids:
            # changing line state in unposted
            move = acc_move_obj.browse(cr, uid, id, context=context)
            acc_move_obj.write(cr, uid, [move.id], {'state': 'draft'}, context=context)
        return res

account_bank_statement_line()

class account_cash_statement(osv.osv):
    _name = "account.bank.statement"
    _inherit = "account.bank.statement"

#TODO: Make this cash register allows multiple registers on the same journal
#    def create(self, cr, uid, values, context={}):
#        """
#        Create a Cash Register.
#        """
#        return super(account_cash_statement, self).create(cr, uid, values, context=context)

    _defaults = {
        'state': lambda *a: 'draft',
    }
    
    _sql_constraints = [
        ('name_uniq', 'UNIQUE(name)', _('The CashBox name must be unique!')),
    ]

    def button_open(self, cr, uid, ids, context={}):
        """
        when pressing 'Open CashBox' button
        """
        self.write(cr, uid, ids, {'state' : 'open'})
        return True

    def button_confirm_cash(self, cr, uid, ids, context={}):
        """
        when you're attempting to close a CashBox via 'Close CashBox'
        """
        # retrieving Calculated balance
        balcal = self.read(cr, uid, ids[0], ['balance_end']).get('balance_end')
        # retrieving CashBox Balance
        bal = self.read(cr, uid, ids[0], ['balance_end_cash']).get('balance_end_cash')
        
        # comparing the selected balances
        equivalent = balcal == bal
        if not equivalent:
            self.write(cr, uid, ids, {'state' : 'partial_close'})
            return True
        else:
            ##### pick up from openerp source #####
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
            ##### end of pickup #####
                    # If statement line is not hard posted, displaying an error
                    if st_line.state != 'hard':
                            raise osv.except_osv(_('Warning'), _('All entries must be hard posted before closing CashBox!'))
                    if not st_line.amount:
                         continue

                self.write(cr, uid, [st.id], {'name': st_number, 'state':'confirm'}, context=context)
            return {
                'name' : "Closing CashBox",
                'type' : 'ir.actions.act_window',
                'res_model' :"wizard.closing.cashbox",
                'target': 'new',
                'view_mode': 'form',
                'view_type': 'form',
                'context': {'active_id': ids[0],
                            'active_ids': ids
                }
            }

    def button_reopen(self, cr, uid, ids, context={}):
        """
        When an administrator push the 'Re-open CashBox' button
        """
        self.write(cr, uid, ids, {'state' : 'open'})
        return True

    def button_write_off(self, cr, uid, ids, context={}):
        """
        When an administrator push the 'Write-off' button
        """
        self.write(cr, uid, ids, {'state' : 'confirm'})
        return True

    _columns = {
            'state': fields.selection((('draft', 'Draft'), ('open', 'Open'), ('partial_close', 'Partial Close'), ('confirm', 'Closed')), \
            readonly="True", string='State'),
    }

    def create(self, cr, uid, vals, context=None):
        """
        Create a new CashBox Register.
        """
        ##### pick up from openerp source #####
        sql = [
                ('journal_id', '=', vals.get('journal_id', False)),
                ('state', '=', 'open')
        ]
        open_jrnl = self.search(cr, uid, sql)
        # Lines commented because of volition to have two opened (or more) cashbox registers on the same journal !
#        if open_jrnl:
#            raise osv.except_osv(_('Error'), _('You can not have two open register for the same journal'))

        if self.pool.get('account.journal').browse(cr, uid, vals['journal_id'], context=context).type == 'cash':
            open_close = self._get_cash_open_close_box_lines(cr, uid, context)
            if vals.get('starting_details_ids', False):
                for start in vals.get('starting_details_ids'):
                    dict_val = start[2]
                    for end in open_close['end']:
                       if end[2]['pieces'] == dict_val['pieces']:
                           end[2]['number'] += dict_val['number']
            vals.update({
                 'ending_details_ids': open_close['start'],
                'starting_details_ids': open_close['end']
            })
        else:
            vals.update({
                'ending_details_ids': False,
                'starting_details_ids': False
            })
        res_id = super(account_cash_statement, self).create(cr, uid, vals, context=context)
        self.write(cr, uid, [res_id], {})
        return res_id


account_cash_statement()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
