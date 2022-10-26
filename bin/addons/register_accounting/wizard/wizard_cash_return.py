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
from base import currency_date
import time
from lxml import etree


class account_bank_statement_line(osv.osv):
    _name = "account.bank.statement.line"
    _inherit = "account.bank.statement.line"

    _columns = {
        'cash_return_move_line_id': fields.many2one('account.move.line',
                                                    'Advance Return JI', required=False, readonly=True),  # BKLG-60
    }

account_bank_statement_line()


class wizard_invoice_line(osv.osv_memory):
    """
    A register line simulation containing some invoices.
    """
    _name = "wizard.invoice.line"

    _columns = {
        'document_date': fields.date(string='Document Date'),
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
    A register line simulation.
    """
    _name = 'wizard.advance.line'

    def _get_distribution_state(self, cr, uid, ids, name, args, context=None):
        """
        Get state of distribution:
         - if compatible with the line, then "valid"
         - if no distribution on line, then "none"
         - all other case are "invalid"
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        # Browse all given lines
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = 'none'
            cash_return_distrib_id = line.wizard_id.analytic_distribution_id and line.wizard_id.analytic_distribution_id.id or False
            line_distrib_id = line.analytic_distribution_id and line.analytic_distribution_id.id or False
            account_id = line.account_id and line.account_id.id or False
            res[line.id] = self.pool.get('analytic.distribution')._get_distribution_state(
                cr, uid, line_distrib_id, cash_return_distrib_id, account_id, amount=line.amount or 0.0)
        return res

    def _get_distribution_state_recap(self, cr, uid, ids, name, arg, context=None):
        """
        Get a recap from analytic distribution state and if it come from header or not.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = ''
            if not line.display_analytic_button:
                continue
            from_header = ''
            if line.have_analytic_distribution_from_header:
                from_header = _(' (from header)')
            res[line.id] = '%s%s' % (self.pool.get('ir.model.fields').get_browse_selection(cr, uid, line, 'analytic_distribution_state', context), from_header)
        return res

    def _have_analytic_distribution_from_header(self, cr, uid, ids, name, arg, context=None):
        """
        If invoice have an analytic distribution, return False, else return True
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = True
            if line.analytic_distribution_id:
                res[line.id] = False
        return res

    def _display_analytic_button(self, cr, uid, ids, name, args, context=None):
        """
        Return True for all element that correspond to some criteria:
         - The entry state is draft
         - The account is analytic-a-holic
        """
        res = {}
        for absl in self.browse(cr, uid, ids, context=context):
            res[absl.id] = True
            # False if account not an analytic-a-holic account
            if not absl.account_id.is_analytic_addicted:
                res[absl.id] = False
        return res

    def onchange_account(self, cr, uid, ids, account_id=None, context=None):
        """
        Update Third Party type regarding account type_for_register field.
        """
        return self.pool.get('account.bank.statement.line').onchange_account(cr, uid, ids, account_id=account_id, context=context)

    _columns = {
        'document_date': fields.date(string='Document Date', required=True),
        'description': fields.char(string='Description', size=64, required=True),
        'account_id': fields.many2one('account.account', string='Account', required=True, domain=[('type', '!=', 'view')]),
        'partner_id': fields.many2one('res.partner', string='Partner', required=False),
        'employee_id': fields.many2one('hr.employee', string="Employee", required=False),
        'partner_type': fields.reference("3RD party", selection=[('res.partner', 'Partner'), ('hr.employee', 'Employee')], size=128),
        'amount': fields.float(string="Amount", size=(16,2), required=True),
        'wizard_id': fields.many2one('wizard.cash.return', string='wizard'),
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
        'analytic_distribution_state': fields.function(
            _get_distribution_state, method=True, type='selection',
            selection=[('none', 'None'), ('valid', 'Valid'), ('invalid', 'Invalid'), ('invalid_small_amount', 'Invalid')],
            string="Distribution state",
            help="Informs from distribution state among 'none', 'valid', 'invalid."),
        'analytic_distribution_state_recap': fields.function(
            _get_distribution_state_recap, method=True, type='char', size=30,
            string="Distribution",
            help="Informs you about analaytic distribution state among 'none', 'valid', 'invalid', from header or not, or no analytic distribution"),
        'have_analytic_distribution_from_header': fields.function(
            _have_analytic_distribution_from_header, method=True, type='boolean',
            string='Header Distrib.?'),
        'display_analytic_button': fields.function(_display_analytic_button, method=True, string='Display analytic button?', type='boolean', readonly=True,
                                                   help="This informs system that we can display or not an analytic button", store=False),
    }

    _defaults = {
        'display_analytic_button': lambda *a: True,
        'analytic_distribution_state_recap': lambda *a: '',
        'have_analytic_distribution_from_header': lambda *a: True,
    }

    def check_employee_distribution(self, cr, uid, vals, context=None):
        """
        Check vals. If employee_id given, add new analytic distribution
        """
        if context is None:
            context = {}
        if vals.get('partner_type', False):
            partner_string = vals.get('partner_type')
            partner_data = partner_string.split(',')
            if partner_data and len(partner_data) >= 2:
                partner_obj = partner_data[0]
                partner_id = partner_data[1]
                if partner_obj == 'hr.employee':
                    account_id = vals.get('account_id', False)
                    wizard_id = vals.get('wizard_id', False)
                    wizard = self.pool.get('wizard.cash.return').browse(cr, uid, [wizard_id], context=context)[0]
                    vals_4_distrib = {
                        'employee_id': partner_id,
                        'account_id': account_id,
                        'statement_id': wizard.advance_st_line_id.statement_id.id,
                    }
                    new_distrib = self.pool.get('account.bank.statement.line').update_employee_analytic_distribution(cr, uid, vals_4_distrib)
                    if new_distrib and new_distrib.get('analytic_distribution_id', False):
                        vals.update({'analytic_distribution_id': new_distrib.get('analytic_distribution_id')})
        return vals

    def create(self, cr, uid, vals, context=None):
        """
        Check vals. If employee_id given, add new analytic distribution
        """
        if context is None:
            context = {}
        new_vals = vals.copy()
        new_vals = self.check_employee_distribution(cr, uid, new_vals)
        return super(wizard_advance_line, self).create(cr, uid, new_vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        Check vals. If employee_id given, add new analytic distribution
        """
        if not ids:
            return True
        # Some checks
        if context is None:
            context = {}
        # Prepare some values
        res = []
        # Need to process each line
        for line in self.read(cr, uid, ids, ['wizard_id'], context=context):
            new_vals = vals.copy()
            new_vals.update({'wizard_id': line.get('wizard_id', False)}) # Add wizard_id so that we can check statement_id
            new_vals = self.check_employee_distribution(cr, uid, new_vals)
            tmp_res = super(wizard_advance_line, self).write(cr, uid, [line.get('id', False)], new_vals, context=context)
            res.append(tmp_res)
        return res

    def button_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Launch analytic distribution wizard from a statement line
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        absl = self.browse(cr, uid, ids[0], context=context)
        amount = absl.amount * -1 or 0.0
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = absl.wizard_id.currency_id and absl.wizard_id.currency_id.id or company_currency
        # Get analytic distribution id from this line
        distrib_id = absl.analytic_distribution_id and absl.analytic_distribution_id.id or False
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'cash_return_line_id': absl.id,
            #'register_line_id': absl.id,
            'currency_id': currency or False,
            'state': 'dispatch',
            'account_id': absl.account_id and absl.account_id.id or False,
        }
        if distrib_id:
            vals.update({'distribution_id': distrib_id,})

        # set some values to the context to indicate the caller of the distr. wizard
        context['cash_return_id'] = False
        context.update({'from_cash_return_analytic_dist': True,
                        'from': 'wizard.cash.return',
                        'wiz_id': absl.wizard_id.id or False,
                        'cash_return_line_id': ids[0]})

        # Create the wizard
        wiz_obj = self.pool.get('analytic.distribution.wizard')
        wiz_id = wiz_obj.create(cr, uid, vals, context=context)
        # Update some context values
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
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
            'keep_open': 1,
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

    def changeline(self, cr, uid, ids, lines, returned_amount, invoices, date, reference, additional_amount, context=None):
        total_amount = returned_amount or 0.0
        # add the amount of invoice lines
        for invoice in invoices:
            if len(invoice) > 2:
                total_amount += invoice[2].get('amount', 0.0)
        for line in lines:
            if line[0] == 1:
                total_amount += line[2].get('amount',0)

        # write the modifiable values to the cash return wizard, because the opening of the distribution analytic wizard could
        # reset all entered values!
        self.write(cr, uid, ids, {'returned_amount': returned_amount, 'total_amount': total_amount, 'date': date, 'reference': reference, 'additional_amount': additional_amount}, context=context)
        return {'value': {'total_amount': total_amount}}

    def _get_ok_with_confirm(self, cr, uid, ids, fieldname, args, context=None):
        """UFTP-24 display confirm message at wizard validation when linked
        to a PO and no invoices selected"""
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long)):
            ids = [ids]
        fields = ['advance_linked_po_auto_invoice', 'invoice_line_ids', 'advance_line_ids']
        for r in self.read(cr, uid, ids, fields, context=context):
            res[r['id']] = r['advance_linked_po_auto_invoice'] and not r['invoice_line_ids']
        return res

    _columns = {
        'initial_amount': fields.float(string="Initial Advance amount", digits=(16,2), readonly=True),
        'returned_amount': fields.float(string="Advance return amount", digits=(16,2), required=True),
        'additional_amount': fields.float(string="Additional Advance amount", digits=(16,2)),
        'invoice_line_ids': fields.one2many('wizard.invoice.line', 'wizard_id', string="Invoice Lines", \
                                            help="Add the invoices you want to link to the Cash Advance Return", required=False, readonly=True),
        'advance_line_ids': fields.one2many('wizard.advance.line', 'wizard_id', string="Advance Lines"),
        'total_amount': fields.float(string="Justified Amount", digits=(16,2), readonly=True),
        'invoice_ids': fields.many2many('account.invoice', 'wizard_cash_return_invoice_rel', 'wizard_id', 'invoice_id', "Invoices"),
        'advance_st_line_id': fields.many2one('account.bank.statement.line', string='Advance Statement Line', required=True),
        'currency_id': fields.many2one('res.currency', string='Currency'),
        'journal_id': fields.many2one('account.journal', string="Journal", readonly=True),
        'date': fields.date(string='Date for advance return', required=True),
        'reference': fields.char(string='Advance Return Reference', size=50),
        'advance_linked_po_auto_invoice': fields.boolean(string="Operational advance linked po invoices"),
        'comment': fields.text(string='Note'),
        'analytic_distribution_id': fields.many2one(
            'analytic.distribution', 'Analytic Distribution', readonly=True),
        'ok_with_confirm': fields.function(_get_ok_with_confirm, type='boolean', string='Ok button with confirm', method=True),
    }

    _defaults = {
        'initial_amount': lambda self, cr, uid, c=None: c.get('amount', False),
        'date': lambda *a: time.strftime('%Y-%m-%d'),
        'advance_linked_po_auto_invoice': False,
    }

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        """
        Give the initial amount to the wizard. If no amount is given to the wizard, raise an error.
        It also keep the bank statement line origin (the advance line) for many treatments.
        """
        if context is None:
            context = {}
        res = super(wizard_cash_return, self).default_get(cr, uid, fields, context=context, from_web=from_web)
        if 'statement_line_id' in context:
            amount = self.pool.get('account.bank.statement.line').read(cr, uid, context.get('statement_line_id'), \
                                                                       ['amount'], context=context).get('amount', False)
            if amount >= 0:
                raise osv.except_osv(_('Error'), _('A wrong amount was selected. Please select an advance with a positive amount.'))
            else:
                st_line = self.pool.get('account.bank.statement.line').browse(cr, uid, context.get('statement_line_id'), context=context)
                currency_id = st_line.statement_id.currency.id # currency is a mandatory field on statement/register
                journal_id = st_line.statement_id.journal_id.id
                res.update({'initial_amount': abs(amount), 'advance_st_line_id': context.get('statement_line_id'), 'currency_id': currency_id, 'journal_id': journal_id})
        return res

    def create(self, cr, uid, values, context=None):
        w_id = super(wizard_cash_return, self).create(cr, uid, values, context=context)
        if context is None:
            context = {}

        if 'statement_line_id' in context:
            """"
            UTP-482 if statment line of Operational Advance,
            is linked to a PO, automatically adding PO invoices
            (force user to use invoices for this cash return)
            """
            st_line_obj = self.pool.get('account.bank.statement.line')
            st_line = st_line_obj.browse(cr, uid, context['statement_line_id'], context)
            if st_line:
                if st_line.type_for_register == 'advance' \
                        and st_line.cash_register_op_advance_po_id \
                        and st_line.cash_register_op_advance_po_id.order_type \
                        and st_line.cash_register_op_advance_po_id.order_type in ('regular', 'purchase_list', 'direct'):
                    values = {'advance_linked_po_auto_invoice': True}  # flagged linked to an op advance
                    invoice_numbers = []
                    for invoice in st_line.cash_register_op_advance_po_id.invoice_ids:
                        if invoice.state and invoice.state == 'open' \
                                and invoice.number:
                            invoice_numbers.append(invoice.number)
                            context['po_op_advance_auto_add_invoice_id'] = invoice.id
                            self.action_add_invoice(cr, uid, [w_id], context=context)
                    msg = "This operational advance is linked to PO %s." % (st_line.cash_register_op_advance_po_id.name,)
                    if invoice_numbers:
                        msg += " Corresponding invoice lines have automatically been added:"
                        msg += "\nInvoice(s) number: " + ", ".join(invoice_numbers) + "."
                        msg += "\nYou can change selection by clicking on 'Clean invoices' then selecting invoice manually." \
                            " Entering a 100% cash return (advance return amount = initial advance amount) you will be able to close this advance without linking it to an invoice."
                        values['comment'] = msg
                    self.write(cr, uid, [w_id], values, context=context)

        context['from_wizard'] = {
            'model': 'wizard.cash.return',
            'res_id': w_id,
        }
        return w_id

    def onchange_addl_amount(self, cr, uid, returned_amount, context=None):
        if returned_amount <> 0:
            return {'value': {'returned_amount': 0}}
        return {}

    def onchange_returned_amount(self, cr, uid, ids, amount=0.0, invoices=None, advances=None, initial_amount=0.0, advance_linked_po_auto_invoice=False, additional_amount=0.0, context=None):
        """
        When the returned amount change, it update the "Justified amount" (total_amount)
        """
        values = {}
        if advance_linked_po_auto_invoice and amount and initial_amount \
                and amount >= initial_amount:
            """
            UTP-482 operational advance linked to a PO
                exception: if amount > initial_amount
                    then add invoice(s) is not mandatory
                => total_amount does not count invoices amount
            '1 exception: if advance is settled through 100% cash return,
            no need to link the advance return with an invoice'
            """
            values.update({'total_amount': amount})
            return {'value': values}
        if amount:
            total_amount = amount + 0.0
            for invoice in invoices:
                total_amount += invoice[2].get('amount', 0.0)
            for advance in advances:
                total_amount += advance[2].get('amount', 0.0)
            values.update({'total_amount': total_amount})
        # clear the additional amount if returned amount is updated
        if additional_amount <> 0:
            values.update({'additional_amount': 0})
        return {'value': values}

    def create_move_line(self, cr, uid, ids, date=None, document_date=None, description='/', journal=False, register=False, partner_id=False, employee_id=False, account_id=None, \
                         debit=0.0, credit=0.0, reference=None, move_id=None, analytic_distribution_id=None, partner_mandatory=False, context=None):
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

        if context is None:
            context = {}

        # We need journal, register, account_id and the move id
        if not journal or not register or not account_id or not move_id:
            return False

        # Fetch object
        move_line_obj = self.pool.get('account.move.line')

        # Prepare values
        journal_id = journal.id
        period_id = register.period_id.id
        current_date = time.strftime('%Y-%m-%d')
        if not document_date:
            document_date = date
        curr_date = currency_date.get_date(self, cr, document_date, date)
        currency_id = register.currency.id
        register_id = register.id
        amount_currency = 0.0
        new_debit = debit
        new_credit = credit
        new_reference = reference

        # Case where currency is different from company currency
        if currency_id != register.company_id.currency_id.id:
            currency_obj = self.pool.get('res.currency')
            context['currency_date'] = curr_date or current_date
            new_amount = 0.0
            if debit > 0:
                amount_currency = debit
                new_amount = currency_obj.compute(cr, uid, currency_id, register.company_id.currency_id.id, debit, round=False, context=context)
                new_debit = abs(new_amount)
            else:
                amount_currency = -credit
                new_amount = currency_obj.compute(cr, uid, currency_id, register.company_id.currency_id.id, credit, round=False, context=context)
                new_credit = abs(new_amount)

        if analytic_distribution_id:
            # UF-2440
            # copy AD to isolate it from wizard global or line AD
            # to prevent delete of all AJIs linked to global AD...
            ad_obj = self.pool.get('analytic.distribution')
            new_analytic_distribution_id = ad_obj.copy(cr, uid,
                                                       analytic_distribution_id, context=context)
        else:
            new_analytic_distribution_id = False

        # Create an account move line
        move_line_vals = {
            'name': description,
            'date': date or current_date,
            'document_date': document_date,
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
            'analytic_distribution_id': new_analytic_distribution_id,
            'partner_type_mandatory': partner_mandatory or False,
            'reference': new_reference or False,
        }
        move_line_id = move_line_obj.create(cr, uid, move_line_vals, context=context)
        return move_line_id

    def create_st_line_from_move_line(self, cr, uid, ids, register_id=None, move_id=None, move_line_id=None, invoice_id=None, do_move_line_id_link=True, context=None):
        """
        Create a statement line from a move line and then link it to the move line
        """
        # We need the register_id, the move id and the move line id
        if not register_id or not move_id or not move_line_id:
            return False

        # Fetch objects
        move_line_obj = self.pool.get('account.move.line')
        absl_obj = self.pool.get('account.bank.statement.line')
        inv_obj = self.pool.get('account.invoice')
        move_line = move_line_obj.browse(cr, uid, move_line_id, context=context)

        # Prepare some values
        date = move_line.date
        document_date = move_line.document_date
        name = move_line.name
        amount = (move_line.credit - move_line.debit) or 0.0
        account_id = move_line.account_id.id
        partner_id = move_line.partner_id.id or False
        employee_id = move_line.employee_id.id or False
        seq = self.pool.get('ir.sequence').get(cr, uid, 'all.registers')
        reference = move_line.ref or False
        # BKLG-44: we keep the link with AD of the move line
        # (no need to copy it, just link it (register line already hard posted))
        # => as a temp/posted reg line copied will copy (new) AD, this gives a
        #    consistent mechanism of AD copy: for reg lines generated from
        #    advance cash return wizard
        analytic_distribution_id = move_line.analytic_distribution_id and \
            move_line.analytic_distribution_id.id or False

        # Verify that the currency is the same as those of the Register
        register = self.pool.get('account.bank.statement').browse(cr, uid, register_id, context=context)
        new_amount = amount

        if register.journal_id.currency and (register.journal_id.currency.id == move_line.currency_id.id) \
                and (register.journal_id.currency.id != register.company_id.currency_id.id):
            new_amount = -move_line.amount_currency

        vals = {
            'date': date,
            'document_date': document_date,
            'name': name,
            'amount': new_amount,
            'account_id': account_id,
            'partner_id': partner_id,
            'employee_id': employee_id,
            'statement_id': register_id,
            'from_cash_return': True, # this permits to disable the return function on the statement line
            'sequence_for_reference': seq,
            'ref': reference,
            'analytic_distribution_id': analytic_distribution_id,
            # BKLG-60 reg line: cash return reg line link with JI (for debit adv regline - not for the close adv one)
            'cash_return_move_line_id': do_move_line_id_link and move_line_id or False,
        }
        # Add invoice link if exists
        if invoice_id:
            vals.update({'invoice_id': invoice_id,})
            # also store the invoice JE
            inv = inv_obj.browse(cr, uid, invoice_id, fields_to_fetch=['move_id'], context=context)
            vals.update({'advance_invoice_move_id': inv and inv.move_id and inv.move_id.id or False})

        # Create the statement line with vals
        st_line_id = absl_obj.create(cr, uid, vals, context=context)
        # Make a link between the statement line and the move line
        absl_obj.write(cr, uid, [st_line_id], {'move_ids': [(4, move_id, False)]}, context=context)

        # hard post for this account line
#        if move_line.account_id.is_analytic_addicted:
#            absl_obj.posting(cr, uid, [move_line.id], 'hard', context=context)

        return True

    def action_add_invoice(self, cr, uid, ids, context=None):
        """
        Add some invoice elements in the invoice_line_ids field
        """
        wizard = self.browse(cr, uid, ids[0], context=context)
        if context and 'po_op_advance_auto_add_invoice_id' in context:
            """"
            UTP-482 if statment line of Operational Advance,
            is linked to a PO, automatically adding PO invoices
            (force user to use invoices for this cash return)
            """
            invoice_obj = self.pool.get('account.invoice')
            invoice_rec = invoice_obj.browse(cr, uid,
                                             context['po_op_advance_auto_add_invoice_id'], context)
            del context['po_op_advance_auto_add_invoice_id']
            if not invoice_rec:
                return
            auto_add = True
            invoices = [invoice_rec]
        else:
            # default behaviour
            if not wizard.invoice_ids:
                return False
            auto_add = False
            invoices = wizard.invoice_ids

        new_lines = []
        total = wizard.returned_amount or 0.  # reuse current amount when adding new line
        # add the amount of advance lines
        for adv_line in wizard.advance_line_ids:
            total += adv_line.amount or 0.0
        added_invoice_ids = [
            wil.invoice_id.id for wil in wizard.invoice_line_ids ]
        for invoice in invoices:
            # Verify that the invoice is in the same currency as those of the register
            inv_currency = invoice.currency_id.id
            if wizard.advance_st_line_id and wizard.advance_st_line_id.statement_id \
                    and wizard.advance_st_line_id.statement_id.currency:
                st_currency = wizard.advance_st_line_id.statement_id.currency.id
            else:
                st_currency = False
            if st_currency and st_currency != inv_currency:
                raise osv.except_osv(_('Error'), _('The choosen invoice is not in the same currency as those of the register.'))

            # Do operations only if our invoice is not in our list
            if invoice.id not in added_invoice_ids:
                # recompute the total_amount
                if wizard.invoice_line_ids:
                    for line in wizard.invoice_line_ids:
                        total += line.amount
                reference = invoice.internal_number or False
                communication = invoice.name or False
                partner_id = invoice.partner_id.id or False
                account_id = invoice.account_id.id or False
                date = invoice.document_date or False
                line_vals = {
                    'document_date': date,
                    'reference': reference,
                    'communication': communication,
                    'partner_id': partner_id,
                    'account_id': account_id,
                    'amount': invoice.residual,
                    'invoice_id': invoice.id,
                }
                new_lines.append((0, 0, line_vals))
                # Add amount to total_amount
                total += invoice.residual
            else:
                raise osv.except_osv(_('Warning'), _('This invoice: %s %s has already been added. Please choose another invoice.')%(invoice.internal_number or '', invoice.residual))

        if new_lines:
            vals = {
                'invoice_line_ids': new_lines,
                'total_amount': total,
                'invoice_ids': [(6, 0, [])],  # reset invoices picker
            }
            self.write(cr, uid, ids, vals, context=context)

        if not auto_add:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'wizard.cash.return',
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': ids[0],
                'context': context,
                'target': 'new',
            }

    def clean_invoices(self, cr, uid, ids, context=None):
        """
        Clean content of invoice list and refresh view.

        above UTP-482 code desactivated in UFTP-24
        point 3)4° of ticket
        user can create expense lines in the advance
        but we show a confirm message at wizard validation
        """

        vals = {
            'invoice_ids': [(6, 0, [])] ,  # reset invoices picker
            'invoice_line_ids': [(5, )],  # reset to import invoices
        }
        self.write(cr, uid, ids, vals, context=context)

        # Update total amount
        self.compute_total_amount(cr, uid, ids, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.cash.return',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': ids[0],
            'context': context,
            'target': 'new',
        }

    def verify_date(self, cr, uid, ids, context=None):
        """
        Verify that date is superior than advance_line date.
        """
        wizard = self.browse(cr, uid, ids[0], context=context)
        if wizard.date < wizard.advance_st_line_id.document_date:
            raise osv.except_osv(_('Warning'), _('The entered date must be greater than or equal to advance posting date.'))
        return True

    def compute_total_amount(self, cr, uid, ids, context=None):
        """
        Compute the total of amount given by the invoices (if exists) or by the advance lines (if exists)
        """
        res = {}
        wizard = self.browse(cr, uid, ids[0], context=context)
        total = 0.0
        total += wizard.returned_amount
        advance_settled_100_cash_return = self._is_advance_settled_100_cash_return(wizard)
        if not advance_settled_100_cash_return:
            """
            UTP-482 operational advance linked to a PO
            exception: if amount > initial_amount
            then add invoice(s) is not mandatory
            => total_amount does not count invoices amount
            '1 exception: if advance is settled through 100% cash return,
            no need to link the advance return with an invoice'
            """
            # add the amount of invoice lines to the total
            for move_line in wizard.invoice_line_ids:
                total += move_line.amount
            # add the amount of advance lines to the total
            for st_line in wizard.advance_line_ids:
                total += st_line.amount
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

    def _create_move(self, cr, uid, vals, move_ids=None, context=None):
        """
        Creates a new JE using the vals in param., adds it to the move_ids list ONLY IF it is passed in param., and returns its id.
        """
        if context is None:
            context = {}
        move_obj = self.pool.get('account.move')
        # make sure to reset the Entry Sequence so a new one is generated each time this method is called
        if 'name' in vals:
            del vals['name']
        move_id = move_obj.create(cr, uid, vals, context=context)
        if isinstance(move_ids, list):
            move_ids.append(move_id)
        return move_id

    def action_confirm_cash_return(self, cr, uid, ids, context=None):
        """
        Make a cash return either the given invoices or given statement lines.
        """
        if context is None:
            context = {}
        account_obj = self.pool.get('account.account')
        absl_obj = self.pool.get('account.bank.statement.line')
        inv_obj = self.pool.get('account.invoice')
        wizard = self.browse(cr, uid, ids[0], context=context)
        wiz_date = wizard.date
        move_ids = []
        error_post_impossible = _('An error has occurred: The journal entries cannot be posted.')
        error_negative_amount = _('%s: negative amounts are forbidden.')

        # US-672/2
        inv_obj.check_accounts_for_partner(cr, uid, ids, context=context, header_obj=self,
                                           lines_field='advance_line_ids', line_level_partner_type=True)

        advance_settled_100_cash_return = self._is_advance_settled_100_cash_return(wizard)
        if advance_settled_100_cash_return:
            """
            UTP-482 operational advance linked to a PO
                exception: if amount > initial_amount
                    then add invoice(s) is not mandatory
                '1 exception: if advance is settled through 100% cash return,
                no need to link the advance return with an invoice'
            => deactivate auto invoice lines
            """
            values = {
                'total_amount': wizard.returned_amount,
                'invoice_line_ids': [(5,)],
            }
            self.write(cr, uid, ids, values, context=context)
            wizard = self.browse(cr, uid, ids[0], context=context)

        # check if any line with an analytic-a-holic account missing the distribution_id value
        for st_line in wizard.advance_line_ids:
            if st_line.account_id.is_analytic_addicted and st_line.analytic_distribution_state != 'valid':
                raise osv.except_osv(_('Warning'),
                                     _('All advance lines with an account depending on an analytic distribution '
                                       'must have a valid allocation.'))

        # Do computation of total_amount of advance return lines
        self.compute_total_amount(cr, uid, ids, context=context)

        # Verify dates
        self.verify_date(cr, uid, ids, context=context)
        # retrieve some values
        if abs(wizard.initial_amount + wizard.additional_amount -  wizard.total_amount) > 10**-3:
            adv_amount = (wizard.initial_amount or 0.0) + (wizard.additional_amount or 0.0)
            raise osv.except_osv(_('Warning'), _('Advance amount (%s) does not match the amount you justified (%s). First correct. Then press Compute button.') % (adv_amount, wizard.total_amount or 0.0))

        # determine the advance return reference (for the advance closing entry and advance expense lines/SI lines)
        adv_return_ref = wizard.reference

        # prepare some values
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        register = wizard.advance_st_line_id.statement_id
        if 'open_advance' in context:
            register = self.pool.get('account.bank.statement').browse(cr, uid, context.get('open_advance'), context=context)
        journal = register.journal_id
        period_id = register.period_id.id
        # move name have been deleted by UTP-330 to be consistent with other register lines ' sequence
        #move_name = "Advance return" + "/" + wizard.advance_st_line_id.statement_id.journal_id.code
        # prepare a move
        move_vals = {
            'journal_id': journal.id,
            'period_id': period_id,
            'date': wizard.date,
            'ref': adv_return_ref,
        }

        # Prepare the closing advance name
        adv_closing_name = "closing" + "-" + wizard.advance_st_line_id.name

        addl_dr_move_line_id = False
        # create new balanced entries if an additional amount has been added
        if wizard.additional_amount < 0.0:
            raise osv.except_osv(_('Error'), error_negative_amount % _('Additional Advance amount'))
        elif wizard.additional_amount > 0.0:  # if equal to zero, this amount is simply ignored
            # credit journal credit account
            journal_acc_id = register.journal_id.default_credit_account_id.id
            additional_amount_move = self._create_move(cr, uid, move_vals, context=context)
            self.create_move_line(cr, uid, ids, wizard.date, wizard.date, adv_closing_name, journal, register, False, wizard.advance_st_line_id.employee_id.id, journal_acc_id, \
                                  0.0, wizard.additional_amount, adv_return_ref, additional_amount_move, False, context=context)
            # debit account 13000 adv returns
            adv_acc_id = wizard.advance_st_line_id.account_id.id
            addl_dr_move_line_id = self.create_move_line(cr, uid, ids, wizard.date, wizard.date, adv_closing_name, journal,
                                                         register, False, wizard.advance_st_line_id.employee_id.id, adv_acc_id,
                                                         wizard.additional_amount, 0.0, adv_return_ref, additional_amount_move,
                                                         False, context=context)
            # post the move
            if not move_obj.post(cr, uid, [additional_amount_move], context=context):
                raise osv.except_osv(_('Error'), error_post_impossible)
            self.create_st_line_from_move_line(cr, uid, ids, register.id, additional_amount_move, addl_dr_move_line_id, context=context)

        # create a cash return move line ONLY IF this return is superior to 0
        if wizard.returned_amount < 0.0:
            raise osv.except_osv(_('Error'), error_negative_amount % _('Advance return amount'))
        elif wizard.returned_amount > 0.0:  # if equal to zero, this amount is simply ignored
            return_acc_id = register.journal_id.default_credit_account_id.id
            cash_return_move = self._create_move(cr, uid, move_vals, move_ids, context=context)
            self.create_move_line(cr, uid, ids, wizard.date, wizard.date, adv_closing_name, journal, register, False,
                                  wizard.advance_st_line_id.employee_id.id, return_acc_id, wizard.returned_amount, 0.0, adv_return_ref,
                                  cash_return_move, False, context=context)

        # make treatment for invoice lines
        # create invoice lines
        inv_ml_data = []
        for invoice in wizard.invoice_line_ids:
            inv_name = "Invoice" + " " + invoice.invoice_id.internal_number
            inv_doc_date = invoice.invoice_id.document_date
            partner_id = invoice.partner_id.id
            if invoice.amount < 0.0:
                raise osv.except_osv(_('Error'), error_negative_amount % invoice.reference or '')
            debit = invoice.amount
            credit = 0.0
            account_id = invoice.account_id.id
            move_vals.update({'document_date': inv_doc_date})
            inv_move = self._create_move(cr, uid, move_vals, move_ids, context=context)
            inv_ml_id = self.create_move_line(cr, uid, ids, wizard.date, inv_doc_date, inv_name, journal, register, partner_id, False,
                                              account_id, debit, credit, adv_return_ref, inv_move, False, context=context)
            inv_ml_data.append((inv_move, inv_ml_id, invoice.invoice_id.id))
        # make treatment for advance lines
        # Prepare a list of advances that have a supplier and then demand generating some moves
        advances_with_supplier = {}
        # create move line from advance line
        adv_move_data = []
        for advance in wizard.advance_line_ids:
            # Case where line equals 0
            if advance.amount == 0.0:
                continue
            elif advance.amount < 0.0:
                raise osv.except_osv(_('Error'), error_negative_amount % advance.description)
            adv_date = advance.document_date
            adv_name = advance.description
            # create a move that will be used for the advance line AND for the related trade payable automatic entries
            move_vals.update({'document_date': adv_date})
            adv_move = self._create_move(cr, uid, move_vals, move_ids, context=context)
            partner_id = False
            line_employee_id = False
            partner = advance.partner_type
            if partner:
                if partner._name == 'res.partner':
                    partner_id = partner.id
                    if partner.partner_type not in ('intermission', 'section'):
                        advances_with_supplier.setdefault(adv_move, []).append(advance)
                elif partner._name == 'hr.employee':
                    line_employee_id = partner.id
            debit = abs(advance.amount)
            credit = 0.0
            account_id = advance.account_id.id

            # check the compatibility between Third Party and Account "Type for specific treatment"
            account_obj.check_type_for_specific_treatment(cr, uid, [account_id], partner_id=partner_id, journal_id=journal.id,
                                                          employee_id=line_employee_id, context=context)

            # Analytic distribution for this line
            distrib_id = (advance.analytic_distribution_id and advance.analytic_distribution_id.id) or \
                (advance.wizard_id.analytic_distribution_id and advance.wizard_id.analytic_distribution_id.id) or False
            # other infos
            adv_id = self.create_move_line(cr, uid, ids, wizard.date, adv_date, adv_name, journal, register, partner_id, line_employee_id,
                                           account_id, debit, credit, adv_return_ref, adv_move, distrib_id, context=context)
            adv_move_data.append((adv_move, adv_id))

        # if advance lines have a Partner Third Party being neither Intermission nor Intersection:
        # create Payable Entries and add them to the advance closing JE
        to_reconcile = {}  # per advance line
        payable_lines = []
        for adv_move in advances_with_supplier:
            for adv_supp_line in advances_with_supplier[adv_move]:
                adv_supp_line_amount = adv_supp_line.amount or 0.0
                # create both move lines related to the advance line
                if adv_supp_line_amount > 0:
                    supp_move_name = adv_supp_line.description or "/"
                    supp_move_date = adv_supp_line.document_date or wiz_date
                    supplier_id = adv_supp_line.partner_type.id  # don't use partner_id which is a browse_null in that case
                    # search account_id of the supplier
                    account_id = self.pool.get('res.partner').read(cr, uid, supplier_id, ['property_account_payable'], context=context)
                    if 'property_account_payable' in account_id and account_id.get('property_account_payable', False):
                        account_id = account_id.get('property_account_payable')[0]
                    else:
                        raise osv.except_osv(_('Warning'), _('One supplier seems not to have a payable account. \
                                                             Please contact an accountant administrator to resolve this problem.'))
                    # create move_lines and add them to the advance move
                    move_vals.update({'document_date': supp_move_date})
                    supp_move_line_debit_id = self.create_move_line(cr, uid, ids, wizard.date, supp_move_date, supp_move_name, journal,
                                                                    register, supplier_id, False, account_id, adv_supp_line_amount, 0.0,
                                                                    adv_return_ref, adv_move, False, context=context)
                    supp_move_line_credit_id = self.create_move_line(cr, uid, ids, wizard.date, supp_move_date, supp_move_name, journal,
                                                                     register, supplier_id, False, account_id, 0.0, adv_supp_line_amount,
                                                                     adv_return_ref, adv_move, False, context=context)
                    # mark the lines as to be reconciled, for each advance line
                    to_reconcile[adv_supp_line.id] = [supp_move_line_debit_id, supp_move_line_credit_id]
                    # store all payable lines created
                    payable_lines.append(supp_move_line_debit_id)
                    payable_lines.append(supp_move_line_credit_id)

        # add the counterpart "closing advance line" in each move and post them
        adv_closing_data = []
        adv_closing_acc_id = wizard.advance_st_line_id.account_id.id
        employee_id = wizard.advance_st_line_id.employee_id.id
        st_currency = wizard.advance_st_line_id.statement_id.journal_id.currency.id
        for move_id in move_ids:
            created_move = move_obj.browse(cr, uid, move_id, fields_to_fetch=['line_id', 'date', 'document_date'], context=context)
            ml_amount = 0.0
            for ml in created_move.line_id:
                if ml.id not in payable_lines:  # exclude amounts of the Trade payable automatic entries
                    # /!\ NOTE: ml.credit_currency should always be zero as negative amounts are forbidden
                    ml_amount += (ml.debit_currency or 0.0) + (ml.credit_currency or 0.0)
            adv_closing_ml_id = self.create_move_line(cr, uid, ids, created_move.date, created_move.document_date, adv_closing_name,
                                                      journal, register, False, employee_id, adv_closing_acc_id, 0.0, ml_amount,
                                                      adv_return_ref, move_id, False, partner_mandatory=True, context=context)
            adv_closing_data.append((move_id, adv_closing_ml_id))

            # Verify that the balance of the move is null
            if st_currency != wizard.advance_st_line_id.statement_id.company_id.currency_id.id:
                # reverse the booking of the advance closing line (not done in create_move_line function)
                move_line_obj.write(cr, uid, [adv_closing_ml_id], {'amount_currency': -ml_amount}, context=context)

            # don't go further if one of the moves couldn't be posted
            if not move_obj.post(cr, uid, [move_id], context=context):
                raise osv.except_osv(_('Error'), error_post_impossible)

        # reconcile partner Payable Entries together if any
        for adv_line_id in to_reconcile:
            move_line_obj.reconcile_partial(cr, uid, to_reconcile[adv_line_id], context=context)

        # Update the statement line with the partner_move_line_ids ("Automated entries")
        if payable_lines and 'statement_line_id' in context:
            absl_obj.write(cr, uid, context['statement_line_id'], {'partner_move_line_ids': [(6, 0, payable_lines)]},
                           context=context)

        # Create statement lines for invoices and advance closing
        # handle invoice lines
        for inv_move_line_data in inv_ml_data:
            inv_move_id, inv_move_line_id, inv_id = inv_move_line_data
            self.create_st_line_from_move_line(cr, uid, ids, register.id, inv_move_id, inv_move_line_id, inv_id, context=context)

            # search the invoice move line that comes from the invoice
            invoice_move_id = inv_obj.read(cr, uid, inv_id, ['move_id'], context=context).get('move_id', None)
            inv_move_line_account_id = move_line_obj.read(cr, uid, inv_move_line_id, ['account_id'], context=context).get('account_id', None)
            if invoice_move_id and inv_move_line_account_id:
                ml_ids = move_line_obj.search(cr, uid, [('move_id', '=', invoice_move_id[0]), ('account_id', '=', inv_move_line_account_id[0])], context=context)
            if not ml_ids or len(ml_ids) > 1:
                raise osv.except_osv(_('Error'), _('An error occurred on invoice reconciliation: Invoice line not found.'))
            # reconcile invoice line (from cash return) with specified invoice line (from invoice)
            move_line_obj.reconcile_partial(cr, uid, [ml_ids[0], inv_move_line_id])
        # handle advance lines
        for adv_move_id, adv_move_line_id in adv_move_data:
            self.create_st_line_from_move_line(cr, uid, ids, register.id, adv_move_id, adv_move_line_id, context=context)

        # reconcile advance and advance return lines
        original_move_id = wizard.advance_st_line_id.move_ids[0]
        criteria = [('statement_id', '=', wizard.advance_st_line_id.statement_id.id), ('account_id', '=', adv_closing_acc_id), ('move_id', '=', original_move_id.id)]
        ml_ids = move_line_obj.search(cr, uid, criteria, context=context)
        if not ml_ids or len(ml_ids) > 1:
            raise osv.except_osv(_('Error'), _('An error occurred on the automatic reconciliation in advance return.'))

        rec_targets = [ml_ids[0]] + [adv_cl[1] for adv_cl in adv_closing_data]
        if addl_dr_move_line_id:
            rec_targets.append(addl_dr_move_line_id)

        move_line_obj.reconcile_partial(cr, uid, rec_targets)
        # create the statement lines for the advance closing
        for adv_closing in adv_closing_data:
            self.create_st_line_from_move_line(cr, uid, ids, register.id, move_id=adv_closing[0], move_line_id=adv_closing[1],
                                               do_move_line_id_link=False, context=context)

        # Disable the return function on the statement line origin (on which we launch the wizard)
        absl_obj.write(cr, uid, [wizard.advance_st_line_id.id], {'from_cash_return': True}, context=context)

        # Close Wizard
        return { 'type': 'ir.actions.act_window_close', }

    def action_confirm_cash_return2(self, cr, uid, ids, context=None):
        """UFTP-24 same action handler as action_confirm_cash_return
        for a button with a confirm attribute"""
        return self.action_confirm_cash_return(cr, uid, ids, context=context)

    def _is_advance_settled_100_cash_return(self, wizard):
        if wizard and wizard.advance_linked_po_auto_invoice \
                and wizard.initial_amount and wizard.returned_amount \
                and (wizard.returned_amount + wizard.additional_amount) >= wizard.initial_amount:
            # advance settled 100% with cash return in returned_amount
            return True
        return False

    def button_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Launch analytic distribution wizard on a Cash Return
        """
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        cash_return = self.browse(cr, uid, ids[0], context=context)
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(
            cr, uid, uid, context=context).company_id.currency_id.id
        currency = cash_return.currency_id and cash_return.currency_id.id \
            or company_currency
        # Compute amount for this Cash Return
        amount = cash_return.initial_amount - cash_return.returned_amount
        # Get analytic_distribution_id
        distrib_id = cash_return.analytic_distribution_id \
            and cash_return.analytic_distribution_id.id
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'cash_return_id': cash_return.id,
            'currency_id': currency or False,
            'state': 'dispatch',
            'account_id': False,
            'date': cash_return.date,
            'posting_date': cash_return.date,
            'document_date': cash_return.date,
            'distribution_id': distrib_id,
        }
        # Create the wizard
        wiz_obj = self.pool.get('analytic.distribution.wizard')
        wiz_id = wiz_obj.create(cr, uid, vals, context=context)
        # Update some context values
        context['cash_return_line_id'] = False
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        context.update({
            'from_cash_return_analytic_dist': True,
            'from': 'wizard.cash.return',
            'wiz_id': ids[0],
            'cash_return_id': ids[0]})
        # Open it!
        return {
            'name': _('Global analytic distribution'),
            'type': 'ir.actions.act_window',
            'res_model': 'analytic.distribution.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': [wiz_id],
            'context': context,
            'keep_open': 1,
        }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        res = super(wizard_cash_return, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
        if 'cash_register_op_advance_po_id' in context:
            doc = etree.XML(res['arch'])

            # UFTP-24
            # if cash return linked to a PO dynamically define confirm message
            # of the 'ok button with confirm' variant
            po = self.pool.get('purchase.order').browse(cr, uid, context['cash_register_op_advance_po_id'], context=context)
            if po:
                msg_base = _("No invoice selected in the advance return wizard. The corresponding advance return has been linked with PO %s - Please confirm you wish to proceed.")
                msg = msg_base % (po.name,)
                nodes = doc.xpath("//button[@name='action_confirm_cash_return2']")
                for node in nodes:
                    node.set('confirm', msg)

            res['arch'] = etree.tostring(doc)
        return res

wizard_cash_return()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
