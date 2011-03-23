#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution    
#    Copyright (C) 2011 TeMPO Consulting, MSF.
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

class account_bank_statement(osv.osv):
    _name = "account.bank.statement"
    _inherit = "account.bank.statement"

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
                raise osv.except_osv(_('Warning'), _('Some lines are not reconciled! Please reconcile all lines before confirm Bank.'))
        return super(account_bank_statement, self).button_confirm_bank(cr, uid, ids, context=context)

account_bank_statement()


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

    _columns = {
        'register_id': fields.many2one("account.account", "Register"),
        'employee_id': fields.many2one("account.account", "Employee"),
        'amount_in': fields.function(_get_amount, method=True, string="Amount In", type='float'),
        'amount_out': fields.function(_get_amount, method=True, string="Amount Out", type='float'),
        'state': fields.function(_get_state, fnct_search=_search_state, method=True, string="Status", type='selection', selection=[('draft', 'Empty'), \
            ('temp', 'Temp'), ('hard', 'Hard'), ('unknown', 'Unknown')]),
        'partner_type': fields.reference("Third Parties", [('res.partner', 'Partners'), ('hr.employee', 'Employee'), \
            ('account.bank.statement', 'Register')], 128),
        'reconciled': fields.function(_get_reconciled_state, method=True, string="Amount Reconciled", type='boolean'),
        'sequence_for_reference': fields.integer(string="Sequence", readonly=True),
        'document_date': fields.date(string="Document Date"),
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

        move_id = account_move_obj.create(cr, uid, {
            'journal_id': st.journal_id.id,
            'period_id': st.period_id.id,
            'date': st_line.date,
            'name': st_line_number,
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
            val['amount_currency'] = -amount_cur

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

    def create(self, cr, uid, values, context={}):
        """
        Create a new account bank statement line with values
        """
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
        # Verify that the statement line isn't in hard state
        if state  == 'hard':
            return False
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
                                line_accounting_value = res_currency_obj.compute(cr, uid, st_line.statement_id.journal_id.currency.id, st_line.company_id.currency_id.id, amount, context=context)
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
        return True

    def button_hard_posting(self, cr, uid, ids, context={}):
        return self.posting(cr, uid, ids, 'hard', context=context)

    def button_temp_posting(self, cr, uid, ids, context={}):
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

account_bank_statement_line()
