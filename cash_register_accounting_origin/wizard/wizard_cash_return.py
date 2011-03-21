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
        'invoice_line_ids': fields.many2many('account.move.line', 'account_move_line_cash_return_rel', 'line_id', 'invoice_id', string="Invoice Lines", \
            help="Just add the invoices you want to link to the Cash Advance Return", required=False, readonly=True),
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

    def onchange_returned_amount(self, cr, uid, ids, amount=0.0, context={}):
        """
        When the returned amount change, it update the "Justified amount" (total_amount)
        """
        res = {}
        if amount:
            # FIXME: Make an addition with the total off all lines given in the "advance_line_ids"
            total_amount = amount + 0.0 # FIXME: Add here the total off all advance line_ids
            res.update({'total_amount': total_amount})
        return {'value': res}

    def action_add_invoice(self, cr, uid, ids, context={}):
        """
        Add an invoice in the invoice_line_ids field
        """
        wizard = self.browse(cr, uid, ids[0], context=context)
        if wizard.invoice_id:
            if wizard.invoice_id.id not in wizard.invoice_line_ids:
                move_line_ids = self.pool.get('account.move.line').search(cr, uid, [('move_id', '=', wizard.invoice_id.move_id.id)], context=context)
                return self.write(cr, uid, ids, {'invoice_line_ids': [(6, 0, move_line_ids)]}, context=context)
        return False

    def action_compute(self, cr, uid, ids, context={}):
        """
        Compute the total of amount given by the invoices (if exists) or by the advance lines (if exists)
        """
        res = {}
        wizard = self.browse(cr, uid, ids[0], context=context)
        total = 0.0
        total += wizard.returned_amount
        for move_line in wizard.invoice_line_ids:
            print move_line.balance
        for st_line in wizard.advance_line_ids:
            total+= st_line.amount
        res.update({'total_amount': total})
        return self.write(cr, uid, ids, res, context=context)

    def action_confirm_cash_return(self, cr, uid, ids, context={}):
        """
        Make a cash return with the given invoices or by registering some given statement lines.
        """
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
