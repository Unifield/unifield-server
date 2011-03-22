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

    def create(self, cr, uid, vals, context={}):
        # TODO: Change here the global variable in order to display (or not) the advance line
        res = super(wizard_advance_line, self).create(cr, uid, vals, context=context)
        return res

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
    }

    _defaults = {
        'initial_amount': lambda self, cr, uid, c={}: c.get('amount', False),
    }

    def default_get(self, cr, uid, fields, context={}):
        """
        Give the initial amount to the wizard. If no amount is given to the wizard, raise an error.
        """
        res = super(wizard_cash_return, self).default_get(cr, uid, fields, context=context)
        if 'active_id' in context:
            amount = self.pool.get('account.bank.statement.line').read(cr, uid, context.get('active_id'), \
                ['amount'], context=context).get('amount', False)
            if amount <= 0:
                raise osv.except_osv(_('Error'), _('A wrong amount was selected. Please select an advance with a positive amount.'))
            else:
                res.update({'initial_amount': amount})
        return res

    def read(self, cr, uid, ids, fields=None, context={}, load='_classic_read'):
        """
        Update the total_amount field when the wizard is reloaded
        """
        res = super(wizard_cash_return, self).read(cr, uid, ids, fields, context=context, load=load)
        if 'initial_amount' in res[0] and 'returned_amount' in res[0]:
            initial_amount = res[0].get('initial_amount')
            returned_amount = res[0].get('returned_amount')
            invoice_line_ids = res[0].get('invoice_line_ids', False)
            advance_line_ids = res[0].get('advance_line_ids', False)
            total_amount = returned_amount + 0.0
            if invoice_line_ids:
                for invoice_id in invoice_line_ids:
                    inv_amount = self.pool.get('wizard.invoice.line').read(cr, uid, invoice_id, ['amount']).get('amount', 0.0)
                    total_amount += inv_amount
            if advance_line_ids:
                for advance_id in advance_line_ids:
                    adv_amount = self.pool.get('wizard.advance.line').read(cr, uid, advance_id, ['amount']).get('amount', 0.0)
                    total_amount += adv_amount
            res[0].update({'total_amount': total_amount})
        return res

    def onchange_returned_amount(self, cr, uid, ids, amount=0.0, invoices=None, advances=None, context={}):
        """
        When the returned amount change, it update the "Justified amount" (total_amount)
        """
        res = {}
        if amount:
            total_amount = amount + 0.0
            for invoice in invoices:
                total_amount += invoice[2].get('amount', 0.0)
            for advance in advances:
                total_amount += advance[2].get('amount', 0.0)
            res.update({'total_amount': total_amount})
        return {'value': res}

    def action_add_invoice(self, cr, uid, ids, context={}):
        """
        Add some invoice elements in the invoice_line_ids field
        """
        # TODO: Change a global variable in order to display (or not) the invoice_line_ids
        wizard = self.browse(cr, uid, ids[0], context=context)
        new_lines = []
        if wizard.invoice_id:
            # Make a list of invoices that have already been added in this wizard
            added_invoices = [x['invoice_id']['id'] for x in wizard.invoice_line_ids]
            # Do operations only if our invoice is not in our list
            if wizard.invoice_id.id not in added_invoices:
                # Retrive some variables
                move_line_obj = self.pool.get('account.move.line')
                account_id = wizard.invoice_id.account_id.id
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
                    amount = abs(move_line.balance) or False 
                    # Add this line to 
                    new_lines.append((0, 0, {'date': date, 'reference': reference, 'communication': communication, 'partner_id': partner_id, \
                        'account_id': account_id, 'amount': amount, 'wizard_id': wizard.id, 'invoice_id': wizard.invoice_id.id}))
        return self.write(cr, uid, ids, {'invoice_line_ids': new_lines}, context=context)

    def action_compute(self, cr, uid, ids, context={}):
        """
        Compute the total of amount given by the invoices (if exists) or by the advance lines (if exists)
        """
        res = {}
        wizard = self.browse(cr, uid, ids[0], context=context)
        total = 0.0
        total += wizard.returned_amount
        # Do computation for invoice lines, then for advance lines
        for move_line in wizard.invoice_line_ids:
            total += move_line.amount
        for st_line in wizard.advance_line_ids:
            total+= st_line.amount
        res.update({'total_amount': total})
        return self.write(cr, uid, ids, res, context=context)

    def action_confirm_cash_return(self, cr, uid, ids, context={}):
        """
        Make a cash return with the given invoices or by registering some given statement lines.
        """
        # TODO: verify the global variable and take invoices or advance lines
        initial_mnt = self.read(cr, uid, ids, ['initial_amount'])[0].get('initial_amount', False)
        total_mnt = self.read(cr, uid, ids, ['total_amount'])[0].get('total_amount', False)
        print initial_mnt, total_mnt
        if initial_mnt != total_mnt:
            raise osv.except_osv(_('Error'), _("The initial amount don't correspond to the Justified amount. \
                Please correct this an press the 'Compute' button. Then click on 'Ok'."))
        # TODO: return an ir.action.close window if all elements are validated
        return True

wizard_cash_return()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
