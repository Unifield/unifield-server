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
        'absl_amount': fields.float(string="Transfer amount", readonly=True),
        'converted_amount': fields.float(string="Transfer amount valuation at system rate (automatic)", readonly=True,
            help="Register line converted amount at standard rate (based on third party journal currency)"),
        'absl_currency': fields.many2one('res.currency', string="Register line currency", readonly=True, help="Register line currency"),
        'amount_from': fields.float(string='Transfer amount converted at real rate', readonly=True, states={'draft': [('readonly', False)]}),
        'amount_to': fields.float(string='Transfer amount converted at real rate', readonly=True, states={'draft': [('readonly', False)]}),
        'currency_id': fields.many2one('res.currency', string="Currency", readonly=True, help="This currency is those from given third party journal."),
        'currency_from': fields.many2one('res.currency', string="Currency", readonly=True),
        'currency_to': fields.many2one('res.currency', string="Currency", readonly=True),
        'state': fields.selection([('draft', 'Draft'), ('closed', 'Closed')], string="State", required=True),
        'type': fields.selection([('from', 'From'), ('to', 'To')], string="Type", readonly=True),
    }

    _defaults = {
        'state': lambda *a: 'draft',
    }

    def create(self, cr, uid, vals, context=None):
        """
        Compute amount from register line currency to journal currency
        """
        # Some verifications
        if not context:
            context = {}
#         transfer_type = 'to'
        if 'absl_id' in vals:
            absl = self.pool.get('account.bank.statement.line').browse(cr, uid, vals.get('absl_id'), context=context)
            if absl and absl.amount:
#                 if absl.amount >= 0:
#                     transfer_type = 'from'
                vals.update({'absl_amount': abs(absl.amount)})
                if absl.transfer_journal_id and absl.currency_id:
                    context.update({'currency_date': absl.date})
                    converted_amount = self.pool.get('res.currency').compute(cr, uid, absl.currency_id.id, absl.transfer_journal_id.currency.id,
                        abs(absl.amount), round=False, context=context)
                    if converted_amount:
                        vals.update({'converted_amount': converted_amount or 0.0})
            if absl and absl.currency_id:
                vals.update({'absl_currency': absl.currency_id.id or False})
#        # Fill in 'amount_from' if transfer type is 'from'
#        if 'amount_from' not in vals and transfer_type == 'from':
#            if absl and absl.transfer_amount:
#                vals.update({'amount_from': absl.transfer_amount})
#            elif 'converted_amount' in vals:
#                vals.update({'amount_from': vals.get('converted_amount')})
#        # Fill in 'amount_to' if transfer type is 'to'
#        if 'amount_to' not in vals and transfer_type == 'to':
#            if absl and absl.transfer_amount:
#                vals.update({'amount_to': absl.transfer_amount})
#            elif 'converted_amount' in vals:
#                vals.update({'amount_to': vals.get('converted_amount')})
        # Default behaviour
        return super(wizard_transfer_with_change, self).create(cr, uid, vals, context=context)

    def button_validate(self, cr, uid, ids, context=None):
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
            vals = {'transfer_amount': False} # Default value for users that delete the previous amount
            # Fetch transfer amount
            if (wiz.amount_to or wiz.amount_from) and wiz.type:
                amount = 0.0
                if wiz.type == 'to':
                    amount = wiz.amount_to
                elif wiz.type == 'from':
                    amount = wiz.amount_from
                vals.update({'transfer_amount': amount})
            if vals and wiz.absl_id:
                self.pool.get('account.bank.statement.line').write(cr, uid, [wiz.absl_id.id], vals, context=context)
        # Close wizard
        return {'type' : 'ir.actions.act_window_close'}

wizard_transfer_with_change()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
