# -*- coding: utf-8 -*-
##############################################################################
#
#    Author: Yannick Vaucher, Guewen Baconnier
#    Copyright 2012 Camptocamp SA
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

from osv import osv, fields
from tools.translate import _


class account_move_line(osv.osv):

    _inherit = 'account.move.line'
    _columns = {
        # [account_unrealized_currency_gain_loss module]
        #  By convention added columns stats with gl_.
        'gl_foreign_balance': fields.float('Aggregated Amount curency'),
        'gl_balance': fields.float('Aggregated Amount'),
        'gl_revaluated_balance': fields.float('Revaluated Amount'),
        'gl_currency_rate': fields.float('Currency rate'),
        # [/account_unrealized_currency_gain_loss module]
        'is_revaluated_ok': fields.boolean(
            _("Revaluation line"), readonly=True),
    }

    _defaults = {
        'is_revaluated_ok': False,
    }

account_move_line()


class account_account(osv.osv):

    _inherit = 'account.account'

    _columns = {
        'currency_revaluation': fields.boolean(
            string=_("Included in revaluation?")),
        'user_type_code': fields.related(
            'user_type', 'code',
            type='char', string=_(u"Type (code)")),
        'instance_level': fields.related(
            'company_id', 'instance_id', 'level',
            type='char', string=_(u"Instance level")),
    }

    _defaults = {'currency_revaluation': False}

    _sql_mapping = {
            'balance': "COALESCE(SUM(l.debit),0) - COALESCE(SUM(l.credit), 0) as balance",
            'debit': "COALESCE(SUM(l.debit), 0) as debit",
            'credit': "COALESCE(SUM(l.credit), 0) as credit",
            'foreign_balance': "COALESCE(SUM(l.amount_currency), 0) as foreign_balance"}

    def _revaluation_query(self, cr, uid, ids, revaluation_date, context=None,
        initial_bal_before_period_id=False):
        if initial_bal_before_period_id:
            lines_where_clause = "l.state <> 'draft'"

            # get all periods SINCE beginning BEFORE given one
            period_obj = self.pool.get('account.period')
            period_r = period_obj.read(cr, uid, [initial_bal_before_period_id],
                ['date_start'], context=context)[0]
            domain = [
                ('date_start', '<', period_r['date_start']),
            ]
            period_ids = period_obj.search(cr, uid, domain, order='date_start',
                context=context)
            if period_ids:
                lines_where_clause += " AND l.period_id IN (%s)" % (
                    ','.join(map(lambda x: str(x), period_ids)), )
        else:
            lines_where_clause = self.pool.get('account.move.line')._query_get(
                cr, uid, context=context)
        query = ("SELECT l.account_id as id, l.currency_id, " +
                   ', '.join(self._sql_mapping.values()) +
                   " FROM account_move_line l "
                   " WHERE l.account_id IN %(account_ids)s AND "
                   " l.date <= %(revaluation_date)s AND "
                   " l.currency_id IS NOT NULL AND "
                   " l.reconcile_id IS NULL AND "
                        + lines_where_clause +
                   " GROUP BY l.account_id, l.currency_id")
        params = {'revaluation_date': revaluation_date,
                  'account_ids': tuple(ids)}
        return query, params

    def compute_revaluations(
            self, cr, uid, ids, period_ids, fiscalyear_id,
            revaluation_date, revaluation_method, context=None):
        if context is None:
            context = {}
        accounts = {}

        # Compute for each account the balance/debit/credit from the move lines
        ctx_query = context.copy()
        ctx_query['periods'] = period_ids
        ctx_query['fiscalyear'] = fiscalyear_id
        query, params = self._revaluation_query(
            cr, uid, ids,
            revaluation_date,
            context=ctx_query)
        cr.execute(query, params)
        lines = cr.dictfetchall()
        for line in lines:
            # generate a tree
            # - account_id
            # -- currency_id
            # ----- balances
            account_id, currency_id = line['id'], line['currency_id']
            accounts.setdefault(account_id, {})
            accounts[account_id].setdefault(currency_id, {})
            accounts[account_id][currency_id] = line

        # Compute for each account the initial balance/debit/credit from the
        # move lines and add it to the previous result
        if revaluation_method == 'liquidity_month':
            ctx_query = context.copy()
            query, params = self._revaluation_query(
                cr, uid, ids,
                revaluation_date,
                context=ctx_query,
                # UFTP-385: we do not use 'initial_bal' context anymore and
                # 'periods' context as it forces a FY in where criteria
                # and we want initial balance from the start of the accounting
                # example: l.period_id IN (SELECT id FROM account_period WHERE
                # fiscalyear_id IN (1) AND id IN (1,2,3,4,5,6,7,8,9)
                initial_bal_before_period_id=period_ids[0]
            )
            cr.execute(query, params)
            lines = cr.dictfetchall()
            for line in lines:
                # generate a tree
                # - account_id
                # -- currency_id
                # ----- balances
                account_id, currency_id = line['id'], line['currency_id']
                accounts.setdefault(account_id, {})
                accounts[account_id].setdefault(
                    currency_id,
                    {'balance': 0, 'foreign_balance': 0, 'credit': 0, 'debit': 0})
                accounts[account_id][currency_id]['balance'] += line['balance']
                accounts[account_id][currency_id]['foreign_balance'] += line['foreign_balance']
                accounts[account_id][currency_id]['credit'] += line['credit']
                accounts[account_id][currency_id]['debit'] += line['debit']

        return accounts

account_account()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
