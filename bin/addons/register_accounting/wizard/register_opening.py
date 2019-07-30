#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2017 TeMPO Consulting, MSF. All Rights Reserved
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


class wizard_register_opening_confirmation(osv.osv_memory):

    _name = 'wizard.register.opening.confirmation'

    def _get_opening_balance(self, cr, uid, ids, name, arg, context=None):
        """
        Returns a dict with key = id of the wizard, and value = amount of the starting balance of the related register
        The Starting Balance is:
        - equal to the value of "balance_start" for Bank Registers
        - based on the Cashbox lines for Cash Registers
        - always equal to 0.00 for Cheque Registers
        """
        res = {}
        if context is None:
            context = {}
        reg_obj = self.pool.get('account.bank.statement')
        for wiz in self.browse(cr, uid, ids, fields_to_fetch=['register_id', 'register_type'], context=context):
            res[wiz.id] = 0.0
            if wiz.register_id:
                reg_id = wiz.register_id.id
                reg_type = wiz.register_type
                if reg_type == 'bank':
                    res[wiz.id] = wiz.register_id.balance_start or 0.0
                elif reg_type == 'cash':
                    computed_balance = reg_obj._get_starting_balance(cr, uid, [reg_id], context=context)
                    res[wiz.id] = computed_balance[reg_id].get('balance_start', 0.0)
        return res

    def _get_journal_type(self, cr, uid, context=None):
        """
        Returns a list of tuples containing the different Journal Types
        """
        return self.pool.get('account.journal').get_journal_type(cr, uid, context=context)

    _columns = {
        'confirm_opening_balance': fields.boolean(string='Do you want to open the register with the following starting balance?',
                                                  required=False),
        'register_id': fields.many2one('account.bank.statement', 'Register', required=True, readonly=True),
        'register_type': fields.related('register_id', 'journal_id', 'type', string='Register Type', type='selection',
                                        selection=_get_journal_type, readonly=True),
        'opening_balance': fields.function(_get_opening_balance, method=True, type='float', readonly=True,
                                           string='Starting Balance'),
        'confirm_opening_period': fields.boolean(string='Do you want to open the register on the following period?',
                                                 required=False),
        'opening_period': fields.related('register_id', 'period_id', string='Opening Period', type='many2one',
                                         relation='account.period', readonly=True),
    }

    def button_confirm_register_opening(self, cr, uid, ids, context=None):
        """
        Triggers the opening of the register if all the confirmation tick boxes have been ticked
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        reg_obj = self.pool.get('account.bank.statement')
        wiz = self.browse(cr, uid, ids[0], context=context)
        reg_id = wiz.register_id.id
        reg_type = wiz.register_type
        balance_ok = wiz.confirm_opening_balance or reg_type == 'cheque'
        period_ok = wiz.confirm_opening_period
        if not balance_ok or not period_ok:
            raise osv.except_osv(_('Warning'), _('You must tick the boxes before clicking on Yes.'))
        else:
            cash_opening_balance = 0.0
            if reg_type == 'cash':
                cash_opening_balance = wiz.opening_balance
            reg_obj.open_register(cr, uid, reg_id, cash_opening_balance=cash_opening_balance, context=context)
        return {'type': 'ir.actions.act_window_close'}


wizard_register_opening_confirmation()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
