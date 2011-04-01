#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution    
#    Copyright (C) TeMPO Consulting (<http://www.tempo-consulting.fr/>), MSF.
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
import time

class wizard_invoice_line(osv.osv_memory):
    """
    A simulated bank statement line containing some invoices.
    """
    _name = "wizard.invoice.line"
    _columns = {
        'date': fields.date(string='Date'),
        'reference': fields.char(string='Reference', size=64, required=False), # invoice.internal_number
        'communication': fields.char(string='Communication', size=64, required=False), # name of invoice.line
        'partner_id': fields.many2one('res.partner', string="Partner", required=False), # partner of invoice
        'account_id': fields.many2one('account.account', string="Account", required=True), # account of invoice
        'amount': fields.float(string="Amount", size=(16,2), required=True), # amount of invoice.line
        'wizard_id': fields.many2one('wizard.cash.return', string="wizard", required=True),
        'invoice_id': fields.many2one('account.invoice', string='Invoice', required=True),
    }

wizard_invoice_line()

class wizard_advance_line(osv.osv_memory):
    """
    A simulated bank statement line.
    """
    _name = 'wizard.advance.line'
    _columns = {
        'date': fields.date(string='Date', required=True),
        'description': fields.char(string='Description', size=64, required=True),
        'account_id': fields.many2one('account.account', string='Account', required=True),
        'partner_id': fields.many2one('res.partner', string='Partner', required=False),
        'amount': fields.float(string="Amount", size=(16,2), required=True),
        'wizard_id': fields.many2one('wizard.cash.return', string='wizard'),
    }

wizard_advance_line()

class wizard_cash_return(osv.osv_memory):
    """
    A wizard to link some advance lines to some account_move_line according to some parameters :
     - account_move_line are from invoices
     - account_move_line are created with the cash advance
    """
    _name = "wizard.cash.return"
    _description = "A wizard that link some advance lines to some account move lines"

    def changeline(self, cr, uid, ids, lines, returned_amount, context={}):
        total_amount = returned_amount or 0.0
        for line in lines:
            if line[0] == 1:
                total_amount += line[2].get('amount',0)

        return {'value': {'total_amount': total_amount}}

    _columns = {
        'initial_amount': fields.float(string="Initial Advance amount", digits=(16,2), readonly=True),
        'returned_amount': fields.float(string="Advance return amount", digits=(16,2), required=True),
        'invoice_line_ids': fields.one2many('wizard.invoice.line', 'wizard_id', string="Invoice Lines", \
            help="Add the invoices you want to link to the Cash Advance Return", required=False, readonly=True),
        'advance_line_ids': fields.one2many('wizard.advance.line', 'wizard_id', string="Advance Lines"),
        'total_amount': fields.float(string="Justified Amount", digits=(16,2), readonly=True),
        'invoice_id': fields.many2one('account.invoice', string='Invoice', required=False),
        'display_invoice': fields.boolean(string="Display Invoice"),
        'advance_st_line_id': fields.many2one('account.bank.statement.line', string='Advance Statement Line', required=True),
        'currency_id': fields.many2one('account.currency', string='Currency'),
    }

    _defaults = {
        'initial_amount': lambda self, cr, uid, c={}: c.get('amount', False),
        'display_invoice': False, # this permits to show only advance lines tree. Then add an invoice make the invoice tree to be displayed
    }

    def default_get(self, cr, uid, fields, context={}):
        """
        Give the initial amount to the wizard. If no amount is given to the wizard, raise an error.
        It also keep the bank statement line origin (the advance line) for many treatments.
        """
        res = super(wizard_cash_return, self).default_get(cr, uid, fields, context=context)
        if 'active_id' in context:
            amount = self.pool.get('account.bank.statement.line').read(cr, uid, context.get('active_id'), \
                ['amount'], context=context).get('amount', False)
            if amount >= 0:
                raise osv.except_osv(_('Error'), _('A wrong amount was selected. Please select an advance with a positive amount.'))
            else:
                st_line = self.pool.get('account.bank.statement.line').browse(cr, uid, context.get('active_id'), context=context)
                currency_id = st_line.statement_id.company_id.currency_id.id
                if st_line.statement_id.journal_id.currency:
                    currency_id = st_line.statement_id.journal_id.currency.id
                res.update({'initial_amount': abs(amount), 'advance_st_line_id': context.get('active_id'), 'currency_id': currency_id})
        return res

    def onchange_returned_amount(self, cr, uid, ids, amount=0.0, invoices=None, advances=None, display_invoice=None, context={}):
        """
        When the returned amount change, it update the "Justified amount" (total_amount)
        """
        res = {}
        if amount:
            total_amount = amount + 0.0
            if display_invoice:
                if invoices:
                    for invoice in invoices:
                        total_amount += invoice[2].get('amount', 0.0)
            else:
                if advances:
                    for advance in advances:
                        total_amount += advance[2].get('amount', 0.0)
            res.update({'total_amount': total_amount})
        return {'value': res}

    def create_move_line(self, cr, uid, ids, date=None, description='/', journal=False, register=False, partner_id=False, employee_id=False, account_id=None, \
        debit=0.0, credit=0.0, move_id=None, context={}):
        """
        Create a move line with some params:
        - description: description of our move line
        - journal: the attached journal
        - register: the register we come from
        - partner_id: the destination partner
        - employee_id: staff that do the move line
        - account_id: account of the move line
        - debit
        - credit
        - move_id: id of the move that contain the move lines
        """

        # We need journal, register, account_id and the move id
        if not journal or not register or not account_id or not move_id:
            return False

        # Fetch object
        move_line_obj = self.pool.get('account.move.line')

        # Prepare values
        journal_id = journal.id
        period_id = register.period_id.id
        curr_date = time.strftime('%Y-%m-%d')
        if date:
            curr_date = date
        currency_id = register.currency.id
        register_id = register.id
        analytic_account_id = journal.analytic_journal_id.id
        amount_currency = 0.0
        new_debit = debit
        new_credit = credit

        # Case where currency is different from company currency
        if currency_id != register.company_id.currency_id.id:
            currency_obj = self.pool.get('res.currency')
            context['date'] = curr_date
            new_amount = 0.0
            if debit > 0:
                amount_currency = debit
                new_amount = currency_obj.compute(cr, uid, currency_id, register.company_id.currency_id.id, debit, round=False, context=context)
                new_debit = abs(new_amount)
            else:
                amount_currency = credit
                new_amount = currency_obj.compute(cr, uid, currency_id, register.company_id.currency_id.id, credit, round=False, context=context)
                new_credit = abs(new_amount)

        # Create an account move line
        move_line_vals = {
            'name': description,
            'date': curr_date,
            'move_id': move_id,
            'partner_id': partner_id or False,
            'employee_id': employee_id or False,
            'account_id': account_id,
            'credit': new_credit,
            'debit': new_debit,
            'statement_id': register_id,
            'journal_id': journal_id,
            'period_id': period_id,
            'currency_id': currency_id,
            'amount_currency': amount_currency,
            'analytic_account_id': analytic_account_id,
        }
        move_line_id = move_line_obj.create(cr, uid, move_line_vals, context=context)

        return move_line_id

    def create_st_line_from_move_line(self, cr, uid, ids, register_id=None, move_id=None, move_line_id=None, context={}):
        """
        Create a statement line from a move line and then link it to the move line
        """
        # We need the register_id, the move id and the move line id
        if not register_id or not move_id or not move_line_id:
            return False

        # Fetch objects
        move_line_obj = self.pool.get('account.move.line')
        absl_obj = self.pool.get('account.bank.statement.line')
        move_line = move_line_obj.browse(cr, uid, move_line_id, context=context)

        # Prepare some values
        date = move_line.date
        name = move_line.name
        amount = (move_line.credit - move_line.debit) or 0.0
        account_id = move_line.account_id.id
        partner_id = move_line.partner_id.id or False
        employee_id = move_line.employee_id.id or False
        statement_id = register_id
        seq = self.pool.get('ir.sequence').get(cr, uid, 'all.registers')

        # Verify that the currency is the same as those of the Register
        register = self.pool.get('account.bank.statement').browse(cr, uid, register_id, context=context)
        new_amount = amount

        if register.journal_id.currency and (register.journal_id.currency.id == move_line.currency_id.id):
            new_amount = move_line.amount_currency

        vals = {
            'date': date,
            'name': name,
            'amount': new_amount,
            'account_id': account_id,
            'partner_id': partner_id,
            'employee_id': employee_id,
            'statement_id': register_id,
            'from_cash_return': True, # this permits to disable the return function on the statement line
            'sequence_for_reference': seq,
        }

        # Create the statement line with vals
        st_line_id = absl_obj.create(cr, uid, vals, context=context)
        # Make a link between the statement line and the move line
        absl_obj.write(cr, uid, [st_line_id], {'move_ids': [(4, move_id, False)]}, context=context)
        return True

    def _round_move(self, cr, uid, move_id=None, close_move_id=None, context={}):
        """
        Round the move in case where the _compute_balance(move_id) is not null
        """
        # Presence verification of variables
        if not move_id and not close_move_id:
            return False

        # Retrieve some elements
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        balance = move_obj._compute_balance(cr, uid, move_id, context=context)
        line_ids = move_obj.read(cr, uid, move_id, ['line_id'], context=context).get('line_id', False)
        total_currency = 0.0

        # Verify that balance on currency amount is equal to 0
        for move_line in move_line_obj.browse(cr, uid, line_ids, context=context):
            total_currency += move_line.amount_currency
        if abs(total_currency) > 10 ** -4:
            raise osv.except_osv(_('Error'), _('An error occured on the currency balance.'))
        # Verify that balance is not null
        # If null, then correct the advance line
        if balance > 0 or balance < 0:
            curr_credit = move_line_obj.browse(cr, uid, [close_move_id], context=context)[0].credit
            new_credit = curr_credit + balance
            res = move_line_obj.write(cr, uid, [close_move_id], {'credit': new_credit}, context=context)
            new_balance = move_obj._compute_balance(cr, uid, move_id, context=context)
            # verify that the balance is inferior to 0.0001
            if not res or abs(new_balance) > 10 ** -4:
                raise osv.except_osv(_('Error'), _('The calculated balance is not correct.'))
        return True

    def action_add_invoice(self, cr, uid, ids, context={}):
        """
        Add some invoice elements in the invoice_line_ids field
        """
        wizard = self.browse(cr, uid, ids[0], context=context)
        to_write = {}
        new_lines = []
        total = 0.0
        if wizard.invoice_id:
            # Verify that the invoice is in the same currency as those of the register
            inv_currency = wizard.invoice_id.currency_id.id
            st_currency = wizard.advance_st_line_id.statement_id.journal_id.currency.id
            if st_currency and st_currency != inv_currency:
                raise osv.except_osv(_('Error'), _('The choosen invoice is not in the same currency as those of the register.'))
            # Make a list of invoices that have already been added in this wizard
            added_invoices = [x['invoice_id']['id'] for x in wizard.invoice_line_ids]
            # Do operations only if our invoice is not in our list
            if wizard.invoice_id.id not in added_invoices:
                # Retrieve some variables
                move_line_obj = self.pool.get('account.move.line')
                account_id = wizard.invoice_id.account_id.id
                # recompute the total_amount
                total = wizard.returned_amount or 0
                for line in wizard.invoice_line_ids:
                    total += line.amount
                # We search all move_line that results from an invoice (so they have the same move_id that the invoice)
                line_ids = move_line_obj.search(cr, uid, [('move_id', '=', wizard.invoice_id.move_id.id), \
                    ('account_id', '=', account_id)], context=context)
                for move_line in move_line_obj.browse(cr, uid, line_ids, context=context):
                    date = move_line.date or False
                    reference = move_line.invoice.internal_number or False
                    communication = move_line.invoice.name or False
                    partner_id = move_line.partner_id.id or False
                    account_id = move_line.account_id.id or False
                    # abs() should be deleted if we take care of "Credit Note".
                    #+ Otherwise abs() give an absolute amount.
                    amount = abs(move_line.balance) or 0.0
                    # Calculate the good amount seeing currency
                    if move_line.currency_id and move_line.currency_id.id == st_currency:
                        amount = abs(move_line.amount_currency) or 0.0
                    # Add this line to our wizard
                    new_lines.append((0, 0, {'date': date, 'reference': reference, 'communication': communication, 'partner_id': partner_id, \
                        'account_id': account_id, 'amount': amount, 'wizard_id': wizard.id, 'invoice_id': wizard.invoice_id.id}))
                    # Add amount to total_amount
                    total += amount
            # Change display_invoice to True in order to show invoice lines
            if new_lines:
                to_write['display_invoice'] = True
                # Add lines to elements to be written
                to_write['invoice_line_ids'] = new_lines
                # Add total_amount to elements to be written
                to_write['total_amount'] = total
                # Delete content of invoice_id field
                to_write['invoice_id'] = False
                # write changes in the wizard
                self.write(cr, uid, ids, to_write, context=context)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.cash.return',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': ids[0],
            'context': context,
            'target': 'new',
        }

    def compute_total_amount(self, cr, uid, ids, context={}):
        """
        Compute the total of amount given by the invoices (if exists) or by the advance lines (if exists)
        """
        res = {}
        wizard = self.browse(cr, uid, ids[0], context=context)
        total = 0.0
        total += wizard.returned_amount
        # Do computation for invoice lines only if display_invoice is True
        if wizard.display_invoice:
            for move_line in wizard.invoice_line_ids:
                total += move_line.amount
        # else do computation for advance lines only
        else:
            for st_line in wizard.advance_line_ids:
                total+= st_line.amount
        res.update({'total_amount': total})
        self.write(cr, uid, ids, res, context=context)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.cash.return',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': ids[0],
            'context': context,
            'target': 'new',
        }

    def action_confirm_cash_return(self, cr, uid, ids, context={}):
        """
        Make a cash return either the given invoices or given statement lines.
        """
        # Do computation of total_amount
        self.compute_total_amount(cr, uid, ids, context=context)
        # retrieve some values
        wizard = self.browse(cr, uid, ids[0], context=context)
        if wizard.initial_amount != wizard.total_amount:
            raise osv.except_osv('Warning', 'Initial amount and Justified amount are not similar. First correct. Then press Compute button')
        if not wizard.invoice_line_ids and not wizard.advance_line_ids:
            raise osv.except_osv(_('Warning'), _('Please give some data or click on Cancel.'))
        # All exceptions passed. So let's go doing treatments on data !
        # prepare some values
        move_obj = self.pool.get('account.move')
        curr_date = time.strftime('%Y-%m-%d')
        register = wizard.advance_st_line_id.statement_id
        journal = register.journal_id
        period_id = register.period_id.id
        move_name = "Advance return" + "/" + wizard.advance_st_line_id.statement_id.journal_id.code
        # prepare a move
        move_vals = {
            'journal_id': journal.id,
            'period_id': period_id,
            'date': curr_date,
            'name': move_name,
        }
        # create the move
        move_id = move_obj.create(cr, uid, move_vals, context=context)
        # create a cash return move line ONLY IF this return is superior to 0
        if wizard.returned_amount > 0:
            return_name = "Cash return"
            return_acc_id = register.journal_id.default_credit_account_id.id
            return_id = self.create_move_line(cr, uid, ids, curr_date, return_name, journal, register, False, False, return_acc_id, \
                wizard.returned_amount, 0.0, move_id, context=context)
        if wizard.display_invoice:
            # make treatment for invoice lines
            # create invoice lines
            inv_move_line_ids = []
            for invoice in wizard.invoice_line_ids:
                inv_name = "Invoice" + " " + invoice.invoice_id.internal_number
                partner_id = invoice.partner_id.id
                debit = invoice.amount
                credit = 0.0
                account_id = invoice.account_id.id
                inv_id = self.create_move_line(cr, uid, ids, curr_date, inv_name, journal, register, partner_id, False, account_id, \
                    debit, credit, move_id, context=context)
                inv_move_line_ids.append((inv_id, invoice.invoice_id.id))
        else:
            # make treatment for advance lines
            # Prepare a list of advances that have a supplier and then demand generating some moves
            advances_with_supplier = {}
            # create move line from advance line
            adv_move_line_ids = []
            for advance in wizard.advance_line_ids:
                adv_date = advance.date
                adv_name = advance.description
                partner_id = advance.partner_id.id or False
                if partner_id:
                    if partner_id in advances_with_supplier:
                        advances_with_supplier[partner_id].append(advance.id)
                    else:
                        advances_with_supplier[partner_id] = [advance.id]
                debit = abs(advance.amount)
                credit = 0.0
                account_id = advance.account_id.id
                adv_id = self.create_move_line(cr, uid, ids, curr_date, adv_name, journal, register, partner_id, False, account_id, \
                    debit, credit, move_id, context=context)
                adv_move_line_ids.append(adv_id)

        # create the advance closing line
        adv_closing_name = "Advance closing"
        adv_closing_acc_id = wizard.advance_st_line_id.account_id.id
        employee_id = wizard.advance_st_line_id.employee_id.id
        adv_closing_id = self.create_move_line(cr, uid, ids, curr_date, adv_closing_name, journal, register, False, employee_id, adv_closing_acc_id, \
            0.0, wizard.initial_amount, move_id, context=context)
        # Verify that the balance of the move is null
        st_currency = wizard.advance_st_line_id.statement_id.journal_id.currency.id
        if st_currency and st_currency != wizard.advance_st_line_id.statement_id.company_id.currency_id.id:
            # change the amount_currency of the advance closing line in order to be negative (not done in create_move_line function)
            res_adv_closing = self.pool.get('account.move.line').write(cr, uid, [adv_closing_id], {'amount_currency': -wizard.initial_amount}, context=context)
            if move_obj._compute_balance(cr, uid, move_id, context=context) <> 0:
                res_round = self._round_move(cr, uid, move_id, adv_closing_id, context=context)
                if not res_round:
                    raise osv.except_osv(_('Error'), _('Rounding the move failed.'))
        # make the move line in posted state
        res_move_id = move_obj.write(cr, uid, [move_id], {'state': 'posted'}, context=context)
        # We create statement lines for invoices and advance closing ONLY IF the move is posted.
        # Verify that the posting has succeed
        if res_move_id == False:
            raise osv.except_osv(_('Error'), _('An error has occured: The journal entries cannot be posted.'))
        # create the statement line for the invoices
        absl_obj = self.pool.get('account.bank.statement.line')
        if wizard.display_invoice:
            for inv_move_line_data in inv_move_line_ids:
                inv_st_id = self.create_st_line_from_move_line(cr, uid, ids, register.id, move_id, inv_move_line_data[0], context=context)
                # Confirm the payment for the invoice
                invoice_id = inv_move_line_data[1]
                inv_paid = self.pool.get('account.invoice').write(cr, uid, invoice_id, {'state': 'paid'}, context=context)
                if not inv_paid:
                    raise osv.except_osv(_('Error'), _('The payment confirmation of an invoice failed.'))
        else:
            for adv_move_line_id in adv_move_line_ids:
                adv_st_id = self.create_st_line_from_move_line(cr, uid, ids, register.id, move_id, adv_move_line_id, context=context)
            # Have you filled in the supplier field ? If yes let's go for creating some moves for them !
            if advances_with_supplier:
                wiz_adv_line_obj = self.pool.get('wizard.advance.line')
                # Browse suppliers
                for supplier_id in advances_with_supplier:
                    total = 0.0
                    # Calculate the total amount for the seleted supplier
                    for id in advances_with_supplier[supplier_id]:
                        data = wiz_adv_line_obj.read(cr, uid, id, ['amount'], context=context)
                        if 'amount' in data:
                            total += data.get('amount')
                    # create the move with 2 move lines for the supplier
                    if total > 0:
                        # prepare the move
                        supp_move_name = wiz_adv_line_obj.read(cr, uid, advances_with_supplier[supplier_id][0], ['description'], context=context).get('description', "/")
                        supp_move_vals = {
                            'journal_id': journal.id,
                            'period_id': period_id,
                            'date': curr_date,
                            'name': supp_move_name,
                        }
                        # search account_id of the supplier
                        account_id = self.pool.get('res.partner').read(cr, uid, supplier_id, ['property_account_payable'], context=context)
                        if 'property_account_payable' in account_id: 
                            account_id = account_id.get('property_account_payable')[0]
                        else:
                            raise osv.except_osv(_('Warning'), _('One supplier seems not to have a payable account. \
                            Please contact an accountant administrator to resolve this problem.'))
                        # Create the move
                        supp_move_id = move_obj.create(cr, uid, supp_move_vals, context=context)
                        # Create move_lines
                        supp_move_line_debit_id = self.create_move_line(cr, uid, ids, curr_date, supp_move_name, journal, register, supplier_id, False, \
                            account_id, total, 0.0, supp_move_id, context=context)
                        supp_move_line_credit_id = self.create_move_line(cr, uid, ids, curr_date, supp_move_name, journal, register, supplier_id, False, \
                            account_id, 0.0, total, supp_move_id, context=context)
                        # We hard post the move
                        supp_res_id = move_obj.write(cr, uid, [supp_move_id], {'state': 'posted'}, context=context)
                        # Verify that the posting has succeed
                        if supp_move_id == False:
                            raise osv.except_osv(_('Error'), _('An error has occured: The journal entries cannot be posted.'))
                        # Do reconciliation
                        move_line_obj = self.pool.get('account.move.line')
                        supp_reconcile_id = move_line_obj.reconcile_partial(cr, uid, [supp_move_line_debit_id, supp_move_line_credit_id])
        # create the statement line for the advance closing
        adv_closing_st_id = self.create_st_line_from_move_line(cr, uid, ids, register.id, move_id, adv_closing_id, context=context)

        # Disable the return function on the statement line origin (on which we launch the wizard)
        absl_obj.write(cr, uid, [wizard.advance_st_line_id.id], {'from_cash_return': True}, context=context)

        # Close Wizard
        return { 'type': 'ir.actions.act_window_close', }

wizard_cash_return()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
