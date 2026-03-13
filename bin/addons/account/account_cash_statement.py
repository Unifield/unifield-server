# encoding: utf-8
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2008 PC Solutions (<http://pcsol.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import time

from osv import osv, fields
from tools.translate import _
import decimal_precision as dp
import ast

class account_cashbox_line(osv.osv):

    """ Cash Box Details """

    _name = 'account.cashbox.line'
    _description = 'CashBox Line'
    _rec_name = 'number'

    _max_amount = 10 ** 10
    _max_msg = _("The Values or the Total amount of the line is more than 10 digits."
                 "Please check that the Values and Number are correct to avoid loss of exact information")

    def _sub_total(self, cr, uid, ids, name, arg, context=None):

        """ Calculates Sub total
        @param name: Names of fields.
        @param arg: User defined arguments
        @return: Dictionary of values.
        """
        res = {}
        for obj in self.browse(cr, uid, ids, context=context):
            res[obj.id] = obj.pieces * obj.number
        return res

    def on_change_sub(self, cr, uid, ids, pieces, number, *a):

        """ Calculates Sub total on change of number
        @param pieces: Names of fields.
        @param number:
        """
        return {'value': {'subtotal': pieces * number or 0.0}}

    def _check_number_size(self, cr, uid, vals, context=None):
        if vals.get('number') and abs(vals['number']) > self._max_amount:
            raise osv.except_osv(_('Warning'), _(self._max_msg))

    def create(self, cr, uid, vals, context=None):
        context = context or {}
        self._check_number_size(cr, uid, vals, context=context)
        return super(account_cashbox_line, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        context = context or {}
        self._check_number_size(cr, uid, vals, context=context)
        return super(account_cashbox_line, self).write(cr, uid, ids, vals, context=context)

    def unlink(self, cr, uid, ids, context=None):
        return super(account_cashbox_line, self).unlink(cr, uid, ids, context=context)

    def _get_sdref(self, cr, uid, res_id, context=None):
        context = context or {}
        model_data_obj = self.pool.get('ir.model.data')
        data_ids = model_data_obj.search(cr, uid,
                                         [('model', '=', 'account.cashbox.line'),
                                          ('res_id', '=', res_id)],
                                         context=context)
        if not data_ids:
            return None
        data = model_data_obj.browse(cr, uid, data_ids[0], context=context)
        return f"{data.module}.{data.name}"

    def _get_register_lines(self, cr, uid, ids, name, args, context=None):
        context = context or {}
        res = {}
        lines_pool = self.pool.get('account.cashbox.line')

        for line in self.browse(cr, uid, ids, context=context):
            values = []
            if line.ending_id:
                line_ids = lines_pool.search(
                    cr, uid,
                    [('ending_id', '=', line.ending_id.id)],
                    context=context
                )
                for l in lines_pool.browse(cr, uid, line_ids, context=context):
                    sdref = self._get_sdref(cr, uid, l.id, context=context)
                    if sdref:
                        values.append((sdref, l.number, l.pieces))
            res[line.id] = str(values)
        return res

    def _set_register_lines(self, cr, uid, id, name, value, args, context=None):
        context = context or {}

        if not value:
            return

        if isinstance(value, str):
            value = ast.literal_eval(value)

        lines_pool = self.pool.get('account.cashbox.line')

        cr.execute("""
                   SELECT ending_id
                   FROM account_cashbox_line
                   WHERE id = %s
                   """, (id,))
        row = cr.fetchone()

        if not row or not row[0]:
            return

        statement_id = row[0]

        existing_ids = lines_pool.search(
            cr, uid,
            [('ending_id', '=', statement_id)],
            context=context
        )
        existing_lines = lines_pool.browse(cr, uid, existing_ids, context=context)
        existing_map = {}

        for l in existing_lines:
            sdref = self._get_sdref(cr, uid, l.id, context=context)
            if sdref:
                existing_map[sdref] = l
            else:
                fallback = "account_cashbox_line/%s" % l.id
                existing_map[fallback] = l

        incoming_keys = []

        for sdref, number, pieces in value:
            key = sdref
            if key not in existing_map:
                key = "account_cashbox_line/%s" % sdref.split("/")[-1]
            existing_line = existing_map.get(key)
            if not existing_line:
                for k, l in existing_map.items():
                    if l.pieces == pieces:
                        existing_line = l
                        key = k
                        break
            if existing_line:
                incoming_keys.append(key)
                if existing_line.number != number or existing_line.pieces != pieces:
                    lines_pool.write(
                        cr,
                        uid,
                        [existing_line.id],
                        {
                            'number': number,
                            'pieces': pieces
                        },
                        context=context
                    )
            else:
                new_id = lines_pool.create(
                    cr,
                    uid,
                    {
                        'ending_id': statement_id,
                        'pieces': pieces,
                        'number': number
                    },
                    context=context
                )
                new_key = "account_cashbox_line/%s" % new_id
                incoming_keys.append(new_key)

        for key, l in existing_map.items():
            if l.id == id:
                continue
            if key not in incoming_keys:
                lines_pool.unlink(
                    cr,
                    uid,
                    [l.id],
                    context=context
                )

    _columns = {
        'pieces': fields.float('Values', digits_compute=dp.get_precision('Account')),
        'number': fields.integer('Number'),
        'subtotal': fields.function(_sub_total, method=True, string='Sub Total', type='float', digits_compute=dp.get_precision('Account')),
        'starting_id': fields.many2one('account.bank.statement', ondelete='cascade'),
        'ending_id': fields.many2one('account.bank.statement', ondelete='cascade'),
        'register_lines': fields.function(_get_register_lines, fnct_inv=_set_register_lines, type='text', string="Register Lines", store=False, method=True,),
    }

    def _check_cashbox_closing_duplicates(self, cr, uid, ids):
        """
        Blocks duplicated values in the Cashbox Closing Balance
        Note that the check is only done in opened registers where the closing balance lines can be changed manually.
        """
        for line in self.browse(cr, uid, ids, fields_to_fetch=['ending_id', 'pieces']):
            if line.ending_id and line.ending_id.state == 'open':
                dom = [('ending_id', '=', line.ending_id.id), ('pieces', '=', line.pieces), ('id', '!=', line.id)]
                if self.search_exist(cr, uid, dom):
                    return False
        return True
    def _check_subtotal(self, cr, uid, ids):
        """
        Blocks the creation/edition of Cashbox line if the integer part of (value * number) is more than 10 digits.
        """
        for line in self.browse(cr, uid, ids, fields_to_fetch=['number', 'pieces']):
            if line.pieces and abs(line.pieces) >= self._max_amount or line.number and abs(line.number) >= self._max_amount or abs(line.pieces * line.number) >= self._max_amount:
                return False
        return True

    _constraints = [
        (_check_cashbox_closing_duplicates, 'The values of the Closing Balance lines must be unique per register.', ['ending_id', 'pieces']),
        (_check_subtotal, 'The Values or the Total amount of the line is more than 10 digits. '
                          'Please check that the Values and Number are correct to avoid loss of exact information', ['number', 'pieces']),
    ]


account_cashbox_line()


class account_cash_statement(osv.osv):

    _inherit = 'account.bank.statement'

    def _get_starting_balance(self, cr, uid, ids, context=None):
        """ Find starting balance
        @param name: Names of fields.
        @param arg: User defined arguments
        @return: Dictionary of values.
        """
        res = {}
        for statement in self.browse(cr, uid, ids, context=context):
            amount_total = 0.0

            if statement.journal_id.type not in('cash'):
                continue

            if not statement.prev_reg_id:
                for line in statement.starting_details_ids:
                    amount_total+= line.pieces * line.number
            else:
                amount_total = statement.prev_reg_id.msf_calculated_balance

            res[statement.id] = {
                'balance_start': amount_total
            }
        return res


    def _balance_end_cash(self, cr, uid, ids, name, arg, context=None):
        """ Find ending balance  "
        @param name: Names of fields.
        @param arg: User defined arguments
        @return: Dictionary of values.
        """
        res = {}
        for statement in self.browse(cr, uid, ids, context=context):
            amount_total = 0.0
            for line in statement.ending_details_ids:
                amount_total += line.pieces * line.number
            res[statement.id] = amount_total
        return res

    def _get_sum_entry_encoding(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Sum of given register's transactions
        """
        res = {}
        if not ids:
            return res
        # Complete those that have no result
        for i in ids:
            res[i] = 0.0
        # COMPUTE amounts
        cr.execute("""
        SELECT statement_id, SUM(amount)
        FROM account_bank_statement_line
        WHERE statement_id in %s
        GROUP BY statement_id""", (tuple(ids,),))
        sql_res = cr.fetchall()
        if sql_res:
            res.update(dict(sql_res))
        return res

    def _get_company(self, cr, uid, context=None):
        user_pool = self.pool.get('res.users')
        company_pool = self.pool.get('res.company')
        user = user_pool.browse(cr, uid, uid, context=context)
        company_id = user.company_id
        if not company_id:
            company_id = company_pool.search(cr, uid, [])
        return company_id and company_id[0] or False

    def _get_cash_open_box_lines(self, cr, uid, context=None):
        res = []
        curr = [1, 2, 5, 10, 20, 50, 100, 500]
        for rs in curr:
            dct = {
                'pieces': rs,
                'number': 0
            }
            res.append(dct)
        journal_ids = self.pool.get('account.journal').search(cr, uid, [('type', '=', 'cash')], context=context)
        if journal_ids:
            results = self.search(cr, uid, [('journal_id', 'in', journal_ids),('state', '=', 'confirm')], context=context)
            if results:
                cash_st = self.browse(cr, uid, results, context=context)[0]
                for cash_line in cash_st.ending_details_ids:
                    for r in res:
                        if cash_line.pieces == r['pieces']:
                            r['number'] = cash_line.number
        return res

    def _get_default_cash_close_box_lines(self, cr, uid, context=None):
        res = []
        curr = [1, 2, 5, 10, 20, 50, 100, 500]
        for rs in curr:
            dct = {
                'pieces': rs,
                'number': 0
            }
            res.append(dct)
        return res

    def _get_cash_open_close_box_lines(self, cr, uid, context=None):
        res = {}
        start_l = []
        end_l = []
        starting_details = self._get_cash_open_box_lines(cr, uid, context=context)
        ending_details = self._get_default_cash_close_box_lines(cr, uid, context)
        for start in starting_details:
            start_l.append((0, 0, start))
        for end in ending_details:
            end_l.append((0, 0, end))
        res['start'] = start_l
        res['end'] = end_l
        return res

    _columns = {
        'total_entry_encoding': fields.function(_get_sum_entry_encoding, method=True, store=False, string="Cash Transaction", help="Total cash transactions"),
        'balance_end_cash': fields.function(_balance_end_cash, method=True, store=False, string='Balance', help="Closing balance based on cashBox"),
        'starting_details_ids': fields.one2many('account.cashbox.line', 'starting_id', string='Opening Cashbox'),
        'ending_details_ids': fields.one2many('account.cashbox.line', 'ending_id', string='Closing Cashbox'),
        'user_id': fields.many2one('res.users', 'Responsible', required=False),
    }
    _defaults = {
        'date': lambda *a: time.strftime("%Y-%m-%d %H:%M:%S"),
        'user_id': lambda self, cr, uid, context=None: uid,
        'starting_details_ids': _get_cash_open_box_lines,
        'ending_details_ids': _get_default_cash_close_box_lines
    }

    def onchange_journal_id(self, cr, uid, statement_id, journal_id, context=None):
        """ Changes balance start and starting details if journal_id changes"
        @param statement_id: Changed statement_id
        @param journal_id: Changed journal_id
        @return:  Dictionary of changed values
        """
        res = {}
        balance_start = 0.0
        if not journal_id:
            res.update({
                'balance_start': balance_start
            })
            return res
        return super(account_cash_statement, self).onchange_journal_id(cr, uid, statement_id, journal_id, context=context)

    def _equal_balance(self, cr, uid, cash_id, context=None):
        if context is None:
            context = {}
        statement = self.browse(cr, uid, cash_id, context=context)
        context.update({'from_cash_statement_equal_balance': True})
        self.write(cr, uid, [cash_id], {'balance_end_real': statement.balance_end}, context=context)
        statement.balance_end_real = statement.balance_end
        balance_end = round(statement.balance_end or 0.0, 2)
        balance_end_cash = round(statement.balance_end_cash or 0.0, 2)
        if abs(balance_end - balance_end_cash) > 10**-3:
            return False
        return True

    def _user_allow(self, cr, uid, statement_id, context=None):
        return True

    def button_open(self, cr, uid, ids, context=None):
        """ Changes statement state to Running.
        @return: True
        """
        if context is None:
            context = {}
        statement_pool = self.pool.get('account.bank.statement')
        for statement in statement_pool.browse(cr, uid, ids, context=context):
            vals = {}
            if not self._user_allow(cr, uid, statement.id, context=context):
                raise osv.except_osv(_('Error !'), (_('User %s does not have rights to access %s journal !') % (statement.user_id.name, statement.journal_id.name)))

            if statement.name and statement.name == '/':
                number = self.pool.get('ir.sequence').get(cr, uid, 'account.cash.statement')
                vals.update({
                    'name': number
                })

            vals.update({
                'date': time.strftime("%Y-%m-%d %H:%M:%S"),
                'state': 'open',

            })
            self.write(cr, uid, [statement.id], vals, context=context)
        return True

    def statement_close(self, cr, uid, ids, journal_type='bank', context=None):
        if journal_type == 'bank':
            return super(account_cash_statement, self).statement_close(cr, uid, ids, journal_type, context)
        vals = {
            'state':'confirm',
            'closing_date': time.strftime("%Y-%m-%d %H:%M:%S")
        }
        return self.write(cr, uid, ids, vals, context=context)

    def button_cancel(self, cr, uid, ids, context=None):
        cash_box_line_pool = self.pool.get('account.cashbox.line')
        super(account_cash_statement, self).button_cancel(cr, uid, ids, context=context)
        for st in self.browse(cr, uid, ids, context):
            for end in st.ending_details_ids:
                cash_box_line_pool.write(cr, uid, [end.id], {'number': 0})
        return True

account_cash_statement()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
