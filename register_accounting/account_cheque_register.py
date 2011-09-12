#!/usr/bin/env python
# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution    
#    Copyright (C) Tempo Consulting (<http://www.tempo-consulting.fr/>), MSF.
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
from register_tools import previous_register_is_closed

class one2many_register(fields.one2many):
    def get(self, cr, obj, ids, name, uid=None, offset=0, context=None, values=None):
        if context is None:
            context = {}

        # From end_balance is used by account_bank_statement._end_balance() in order to calculate the balance of Registers
        if 'journal_type' not in context or context.get('journal_type') != 'cheque' or context.get('from_end_balance'):
            return super(one2many_register, self).get(cr, obj, ids, name, uid, offset, context, values)

        if values is None:
            values = {}

        res = {}

        display_type = {}
        for st in obj.read(cr, uid, ids, ['display_type']):
            res[st['id']] = []
            display_type[st['id']] = st['display_type']

        st_obj = obj.pool.get('account.bank.statement.line')
        st_ids = st_obj.search(cr, uid, [('statement_id', 'in', ids)])
        if st_ids:
            for st in  st_obj.read(cr, uid, st_ids, ['statement_id', 'reconciled'], context=context):
                if display_type[st['statement_id'][0]] == 'reconciled' and st['reconciled']:
                    res[st['statement_id'][0]].append(st['id'])
                elif display_type[st['statement_id'][0]] == 'not_reconciled' and st['reconciled'] is False:
                    res[st['statement_id'][0]].append(st['id'])
                elif display_type[st['statement_id'][0]] == 'all':
                    res[st['statement_id'][0]].append(st['id'])
        return res

class account_cheque_register(osv.osv):
    _name = "account.bank.statement"
    _inherit = "account.bank.statement"

    _columns = {
        'display_type': fields.selection([('reconciled', 'Display Reconciled'), ('not_reconciled', 'Display Not Reconciled'), ('all', 'All')], \
            string="Display type", states={'draft': [('readonly', True)]}),
        'line_ids': one2many_register('account.bank.statement.line', 'statement_id', 'Statement lines', \
                states={'partial_close':[('readonly', True)], 'confirm':[('readonly', True)], 'draft': [('readonly', True)]}),
    }

    _defaults = {
        'display_type': 'not_reconciled',
    }

    def button_open_cheque(self, cr, uid, ids, context={}):
        """
        When you click on "Open Cheque Register"
        """
        return self.write(cr, uid, ids, {'state': 'open'}, context=context)

    def button_confirm_cheque(self, cr, uid, ids, context={}):
        """
        When you press "Confirm" on a Cheque Register.
        You have to verify that all lines are in hard posting.
        """
        return self.button_confirm_bank(cr, uid, ids, context=context)

    def button_display_type(self, cr, uid, ids, context={}):
        """
        Filter on display_type in order to just show lines that are reconciled or not
        """
        for register in self.browse(cr, uid, ids, context=context):
            self.write(cr, uid, [register.id], {'display_type': register.display_type},context=context)
        return True

account_cheque_register()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
