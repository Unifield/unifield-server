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
            for st in st_obj.read(cr, uid, st_ids, ['statement_id', 'reconciled'], context=context):
                res[st['statement_id'][0]].append(st['id'])

            if display_type[st['statement_id'][0]] == 'not_reconciled':
                for statement_id in ids:
                    if not res[statement_id]:
                        continue
                    # UFTP-348: We take all register lines IDs and we delete those that are hard-posted, imported in another register and hard posted
                    # List of hard posted linked register lines
                    # We omit to search on bank registers as the import cheque wizard is only available on bank register
                    #+ and this is the only wizard that add "from_import_cheque_id". So if a register line have
                    #+ this field filled in, so it comes from a cheque import.
                    # Note that account_bank_statement_line_move_rel invert columns. move_id = register line and
                    #+ statement_id = journal entry (OpenERP bug)
                    sql = """
                        SELECT move_rel.move_id
                        FROM account_bank_statement_line_move_rel as move_rel
                        WHERE move_rel.statement_id IN (
                            SELECT move_id
                            FROM account_move_line
                            WHERE id IN (
                                SELECT absl.from_import_cheque_id
                                FROM account_bank_statement_line as absl, account_bank_statement_line_move_rel as abslmr, account_move as m
                                WHERE absl.from_import_cheque_id is not NULL
                                AND abslmr.move_id = absl.id
                                AND abslmr.statement_id = m.id
                                AND m.state = 'posted'
                            )
                        )
                        AND move_rel.move_id IN %s
                    """
                    cr.execute(sql, (tuple(res[statement_id]),))
                    tmp_res = cr.fetchall()
                    excluded_line_ids = [x and x[0] for x in tmp_res]
                    current_ids = res[statement_id]
                    res[statement_id] = [stl_id for stl_id in current_ids if stl_id not in excluded_line_ids]
        return res

class account_cheque_register(osv.osv):
    _name = "account.bank.statement"
    _inherit = "account.bank.statement"

    _columns = {
        'display_type': fields.selection([('not_reconciled', 'Outstanding cheques only'), ('all', 'All cheques')], \
                                         string="Display type", required=True, states={'draft': [('readonly', True)]}),
        'line_ids': one2many_register('account.bank.statement.line', 'statement_id', 'Statement lines', \
                                      states={'partial_close':[('readonly', True)], 'confirm':[('readonly', True)], 'draft': [('readonly', True)]}),
    }

    _defaults = {
        'display_type': 'all',
    }

    _order = 'state, period_id, instance_id, journal_id'

    def button_confirm_cheque(self, cr, uid, ids, context=None):
        """
        When you press "Confirm" on a Cheque Register.
        You have to verify that all lines are in hard posting.
        """
        if context is None:
            context = {}
        context.update({'confirm_from': 'cheque'})
        return self.button_confirm_bank(cr, uid, ids, context=context)

    def button_display_type(self, cr, uid, ids, context=None):
        """
        Filter on display_type in order to just show lines that are reconciled or not
        """
        for register in self.browse(cr, uid, ids, context=context):
            self.write(cr, uid, [register.id], {'display_type': register.display_type},context=context)
        return True

account_cheque_register()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
