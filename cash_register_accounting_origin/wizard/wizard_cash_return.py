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
                res.update({'initial_amount': abs(amount), 'advance_st_line_id': context.get('active_id')})
        return res

    def onchange_returned_amount(self, cr, uid, ids, amount=0.0, invoices=None, advances=None, display_invoice=None, context={}):
        """
        When the returned amount change, it update the "Justified amount" (total_amount)
        """
        res = {}
        if amount:
            total_amount = amount + 0.0
            if display_invoice:
                for invoice in invoices:
                    total_amount += invoice[2].get('amount', 0.0)
            else:
                for advance in advances:
                    total_amount += advance[2].get('amount', 0.0)
            res.update({'total_amount': total_amount})
        return {'value': res}

    def create_move_line(self, cr, uid, ids, description='/', journal=False, register=False, partner_id=False, employee_id=False, account_id=None, \
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

        # fetching object
        move_line_obj = self.pool.get('account.move.line')

        # preparing values
        journal_id = journal.id
        period_id = register.period_id.id
        curr_date = time.strftime('%Y-%m-%d')
        currency_id = register.currency.id
        register_id = register.id
        analytic_account_id = journal.analytic_journal_id.id

        # creating an account move line
        move_line_vals = {
            'name': description,
            'date': curr_date,
            'move_id': move_id,
            'partner_id': partner_id or False,
            'employee_id': employee_id or False,
            'account_id': account_id,
            'credit': credit,
            'debit': debit,
            'statement_id': register_id,
            'journal_id': journal_id,
            'period_id': period_id,
            'currency_id': currency_id,
            'analytic_account_id': analytic_account_id,
        }
        move_line_id = move_line_obj.create(cr, uid, move_line_vals, context = context)

        return move_line_id

    def action_add_invoice(self, cr, uid, ids, context={}):
        """
        Add some invoice elements in the invoice_line_ids field
        """
        wizard = self.browse(cr, uid, ids[0], context=context)
        to_write = {}
        new_lines = []
        total = 0.0
        if wizard.invoice_id:
            # Make a list of invoices that have already been added in this wizard
            added_invoices = [x['invoice_id']['id'] for x in wizard.invoice_line_ids]
            # Do operations only if our invoice is not in our list
            if wizard.invoice_id.id not in added_invoices:
                # Retrive some variables
                move_line_obj = self.pool.get('account.move.line')
                account_id = wizard.invoice_id.account_id.id
                # recompute the total_amount
                self.compute_total_amount(cr, uid, ids, context=context)
                total += self.read(cr, uid, ids[0], ['total_amount'], context=context).get('total_amount', 0.0)
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
                    # Add this line to 
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
        return self.write(cr, uid, ids, to_write, context=context)

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
        return self.write(cr, uid, ids, res, context=context)

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
        if wizard.display_invoice:
            # make treatment for invoice lines
            # prepare some values
            move_obj = self.pool.get('account.move')
            curr_date = time.strftime('%Y-%m-%d')
            register = wizard.advance_st_line_id.statement_id
            journal = register.journal_id
            period_id = register.period_id.id
            move_name = "Advance return" + "/" + wizard.advance_st_line_id.statement_id.journal_id.code
            # create a move
            move_vals = {
                'journal_id': journal.id,
                'period_id': period_id,
                'date': curr_date,
                'name': move_name,
            }
            move_id = move_obj.create(cr, uid, move_vals, context=context)
            # create a cash return move line
            return_name = "Cash return"
            return_acc_id = register.journal_id.default_credit_account_id.id
            return_id = self.create_move_line(cr, uid, ids, return_name, journal, register, False, False, return_acc_id, \
                wizard.returned_amount, 0.0, move_id, context=context)
            # create invoice lines
            inv_move_line_ids = []
            for invoice in wizard.invoice_line_ids:
                inv_name = "Invoice" + " " + invoice.invoice_id.internal_number
                partner_id = invoice.partner_id.id
                debit = invoice.amount
                credit = 0.0
                account_id = invoice.account_id.id
                inv_id = self.create_move_line(cr, uid, ids, inv_name, journal, register, partner_id, False, account_id, \
                    debit, credit, move_id, context=context)
                inv_move_line_ids.append(inv_id)
            # create the advance closing line
            adv_name = "Advance closing"
            adv_acc_id = wizard.advance_st_line_id.account_id.id
            employee_id = wizard.advance_st_line_id.employee_id.id
            adv_id = self.create_move_line(cr, uid, ids, adv_name, journal, register, False, employee_id, adv_acc_id, \
                0.0, wizard.initial_amount, move_id, context=context)
            # make the move line in posted state
            res_move_id = move_obj.write(cr, uid, [move_id], {'state': 'posted'}, context=context)
            # We create statement lines for invoices and advance closing ONLY IF the move is posted.
            # Verify that the posting has succeed
            if res_move_id == False:
                raise osv.except_osv(_('Error'), _('An error has occured: The journal entries cannot be posted.'))
            # create the statement line for the invoices
            absl_obj = self.pool.get('account.bank.statement.line')
            move_line_obj = self.pool.get('account.move.line')
            for inv_move_line_id in inv_move_line_ids:
                inv_data = move_line_obj.read(cr, uid, inv_move_line_id, ['date', 'name', 'debit', 'credit', 'account_id', 'partner_id'], \
                    context=context)
                vals = {
                    'date': inv_data.get('date', False),
                    'name': inv_data.get('name', '/'),
                    'amount': inv_data.get('credit', 0.0) - inv_data.get('debit', 0.0),
                    'account_id': inv_data.get('account_id', False)[0] or False,
                    'partner_id': inv_data.get('partner_id', False)[0] or False,
                    'statement_id': register.id,
                    'from_cash_return': True, # this permits to disable the return function on the statement line
                }
                inv_st_id = absl_obj.create(cr, uid, vals, context=context)
                # Make the link between the statement line and the move line
                absl_obj.write(cr, uid, [inv_st_id], {'move_ids': [(4, move_id, False)]}, context=context)
            # create the statement line for the advance closing
            adv_data = move_line_obj.read(cr, uid, adv_id, ['date', 'name', 'credit', 'account_id', 'employee_id'], context=context)
            adv_test = move_line_obj.browse(cr, uid, adv_id, context=context)
            vals = {
                'date': adv_data.get('date', False),
                'name': adv_data.get('name', False),
                'amount': adv_data.get('credit', 0.0),
                'account_id': adv_data.get('account_id', False)[0] or False,
                'employee_id': adv_data.get('employee_id', False)[0] or False,
                'statement_id': register.id,
                'from_cash_return': True, # this permits to disable the return function on the statement line
            }
            adv_st_id = absl_obj.create(cr, uid, vals, context=context)
            # Make the link between the statement line and the move line
            absl_obj.write(cr, uid, [adv_st_id], {'move_ids': [(4, move_id, False)]}, context=context)
            # Disable the return function on the statement line origin (on which we launch the wizard)
            absl_obj.write(cr, uid, [wizard.advance_st_line_id.id], {'from_cash_return': True}, context=context)
        else:
            # TODO:  make treatment for advance lines
            pass
        ## TODO: make something to stop displaying the icon that permit to launch the advance return.
        return { 'type': 'ir.actions.act_window_close', }

wizard_cash_return()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
