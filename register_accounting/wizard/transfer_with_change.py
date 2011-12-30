#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
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

class wizard_transfer_with_change(osv.osv_memory):
    _name = 'wizard.transfer.with.change'
    _description = 'Transfer with Change Wizard'

    _columns = {
        'absl_id': fields.many2one('account.bank.statement.line', string='Register Line', required=True),
        'amount': fields.float(string='Amount', readonly=True, states={'draft': [('readonly', False), ('required', True)]}),
        'currency_id': fields.many2one('res.currency', string="Currency", readonly=True),
        'state': fields.selection([('draft', 'Draft'), ('closed', 'Closed')], string="State", required=True),
    }

    _defaults = {
        'state': lambda *a: 'draft',
    }

    def create(self, cr, uid, vals, context={}):
        """
        Compute amount from register line currency to journal currency
        """
        # Some verifications
        if not context:
            context = {}
        if 'amount' not in vals or vals.get('amount', 0.0) == 0.0:
            if 'absl_id' in vals:
                absl = self.pool.get('account.bank.statement.line').browse(cr, uid, vals.get('absl_id'), context=context)
                if absl and absl.transfer_journal_id and absl.currency_id:
                    context.update({'date': absl.date})
                    amount = self.pool.get('res.currency').compute(cr, uid, absl.currency_id.id, absl.transfer_journal_id.currency.id, abs(absl.amount), context=context)
                    vals.update({'amount': amount or 0.0})
        # Default behaviour
        return super(wizard_transfer_with_change, self).create(cr, uid, vals, context=context)

    def button_validate(self, cr, uid, ids, context={}):
        """
        Write on register line some values:
         - amount
         - currency
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Browse elements
        for wiz in self.browse(cr, uid, ids, context=context):
            vals = {}
            if wiz.amount:
                vals.update({'transfer_amount': wiz.amount})
            # Take currency from account_bank_statement_line transfer_journal_id field
            if wiz.absl_id and wiz.absl_id.transfer_journal_id:
                vals.update({'transfer_currency': wiz.absl_id.transfer_journal_id.currency.id})
            if vals and wiz.absl_id:
                self.pool.get('account.bank.statement.line').write(cr, uid, [wiz.absl_id.id], vals, context=context)
        # Close wizard
        return {'type' : 'ir.actions.act_window_close'}

wizard_transfer_with_change()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
