#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
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
from osv import fields
from osv import osv
from datetime import datetime


class account_board_liquidity(osv.osv):
    _name = 'account.bank.statement'
    _inherit = 'account.bank.statement'

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        if context is not None and "board_view" in context and context['board_view'] is True:
            sql = 'SELECT id, name FROM account_bank_statement ' \
                  'WHERE date <= \'' + str(datetime.now().strftime("%Y-%m-%d")) + \
                  '\' ORDER BY date DESC'
            cr.execute(sql)
            account_lines = cr.dictfetchall()
            res = []
            account_names = []
            for line in account_lines:
                if not line['name'] in account_names:
                    account_names.append(line['name'])
                    res.append(line['id'])
        else:
            res = super(account_board_liquidity, self)\
                .search(cr, uid, args, offset=offset, limit=limit, order=order, context=context, count=count)
        return res

    def _get_current_balance(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for account_id in ids:
            accounts = self.browse(cr, uid, [account_id], context=context)
            for account in accounts:
                if 'cheque' in account['journal_id']['type']:
                    amount = 0
                    for line in account['line_ids']:
                        if not line['direct_invoice_move_id'] and not line['direct_invoice']:
                            amount += line['amount_out']
                    res[account_id] = amount
                else:
                    res[account_id] = account['balance_end']
        return res

    def _get_current_board_balance_func(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        ccy = self.pool.get('res.users').browse(cr, uid, [uid], context=context)[0].company_id.currency_id
        for account_id in ids:
            accounts = self.browse(cr, uid, [account_id], context=context)
            for account in accounts:
                amount = float(self.pool.get('res.currency').compute(cr, uid,
                                                                     account.currency.id,
                                                                     ccy.id,
                                                                     account.current_board_balance))
                res[account_id] = amount
        return res

    def _get_current_board_currency_func(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        ccy = self.pool.get('res.users').browse(cr, uid, [uid], context=context)[0].company_id.currency_id
        for account_id in ids:
            res[account_id] = ccy.name
        return res

    def _get_balance_negative_board(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for account_id in ids:
            res[account_id] = 'False'
            accounts = self.browse(cr, uid, [account_id], context=context)
            for account in accounts:
                if account.current_board_balance < 0:
                    res[account_id] = 'True'
        return res

    _columns = {
        'balance_negative_board': fields.function(_get_balance_negative_board,
                                                 method=True, type='string', string='Is negative balance', readonly=True),
        'current_board_balance': fields.function(_get_current_balance,
                                                 method=True, type='float', string='Balance / Outstanding cheque amount', readonly=True),
        'current_board_balance_func': fields.function(_get_current_board_balance_func,
                                                      method=True, type='float',
                                                      string='Balance / Outstanding cheque amount in func. ccy', readonly=True),
        'current_board_currency_func': fields.function(_get_current_board_currency_func,
                                                       method=True, type='string',
                                                       string='Functional currency', readonly=True),
    }




account_board_liquidity()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
