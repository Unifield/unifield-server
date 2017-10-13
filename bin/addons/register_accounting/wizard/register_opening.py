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


class wizard_register_opening_confirmation(osv.osv_memory):

    _name = 'wizard.register.opening.confirmation'

    def _get_opening_balance(self, cr, uid, ids, name, arg, context=None):
        """
        Returns a dict with key = id of the wizard, and value = amount of the opening balance of the related register
        The Opening Balance is:
        - equal to the value of "balance_start" for Bank Registers
        - based on the Cashbox lines or on the previous register balance for Cash Registers
        - always equal to 0.00 for Cheque Registers
        """
        res = {}
        if context is None:
            context = {}
        reg_obj = self.pool.get('account.bank.statement')
        for wiz in self.browse(cr, uid, ids, fields_to_fetch=['register_id'], context=context):
            res[wiz.id] = 0.0
            if wiz.register_id:
                reg_id = wiz.register_id.id
                reg_type = wiz.register_type
                if reg_type == 'bank':
                    res[wiz.id] = wiz.register_id.balance_start or 0.0
                elif reg_type == 'cash':
                    context['from_open'] = True
                    computed_balance = reg_obj._get_starting_balance(cr, uid, [reg_id], context=context)
                    del context['from_open']
                    res[wiz.id] = computed_balance[reg_id].get('balance_start', 0.0)
        return res

    def _get_journal_type(self, cr, uid, context=None):
        """
        Returns a list of tuples containing the different Journal Types
        """
        return self.pool.get('account.journal').get_journal_type(cr, uid, context=context)

    _columns = {
        'confirm_opening_balance': fields.boolean(string='Do you want to open the register with the following opening balance?',
                                                  required=False),
        'register_id': fields.many2one('account.bank.statement', 'Register', required=True, readonly=True),
        'register_type': fields.related('register_id', 'journal_id', 'type', string='Register Type', type='selection',
                                        selection=_get_journal_type, readonly=True),
        'opening_balance': fields.function(_get_opening_balance, method=True, type='float', readonly=True,
                                           string='Opening Balance'),
        'confirm_opening_period': fields.boolean(string='Do you want to open the register on the following period?',
                                                 required=False),
        'opening_period': fields.related('register_id', 'period_id', string='Opening Period', type='many2one',
                                         relation='account.period', readonly=True),
    }


wizard_register_opening_confirmation()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
