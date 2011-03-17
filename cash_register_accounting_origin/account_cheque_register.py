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

class one2many_register(fields.one2many):
    def get(self, cr, obj, ids, name, user=None, offset=0, context=None, values=None):
        if context is None:
            context = {}

        if 'journal_type' not in context or context.get('journal_type') != 'cheque':
            return super(one2many_register, self).get(cr, obj, ids, name, user=None, offset=0, context=None, values=None)

        if values is None:
            values = {}

        res5 = obj.read(cr, user, ids, ['display_type'], context=context)
        res6 = {}
        for r in res5:
            res6[r['id']] = r['display_type']

        ids2 = []
        for id in ids:
            dom = []
            if id in res6:
                if res6[id] == 'reconciled':
                    dom = [('reconciled', '=', True)]
                else:
                    dom = [('reconciled', '=', False)]
            ids2.extend(obj.pool.get(self._obj).search(cr, user,
                dom, limit=self._limit))
        res = {}
        for i in ids:
            res[i] = []
        for r in obj.pool.get(self._obj)._read_flat(cr, user, ids2,
                [self._fields_id], context=context, load='_classic_write'):
            if r[self._fields_id]:
                res[r[self._fields_id]].append(r['id'])
        return res

class account_cheque_register(osv.osv):
    _name = "account.bank.statement"
    _inherit = "account.bank.statement"

    _columns = {
        'display_type': fields.selection([('reconciled', 'Reconciled'), ('not_reconciled', 'Not Reconciled')], string="Display type"),
        'line_ids': one2many_register('account.bank.statement.line', 'statement_id', 'Statement lines', \
                states={'partial_close':[('readonly', True)], 'confirm':[('readonly', True)]}),
    }

    def button_open_cheque(self, cr, uid, ids, context={}):
        """
        When you click on "Open Cheque Register"
        """
        return self.write(cr, uid, ids, {'state': 'open'}, context=context)

    def button_confirm_cheque(self, cr, uid, ids, context={}):
        """
        When you press "Confirm" on a Cheque Register.
        You have to verify that all lines are in hard posting, then that they are reconciled.
        """
        # @ this moment, the button_confirm_bank verify that all lines are hard posted and reconciled
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
