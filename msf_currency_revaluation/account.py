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

    def _revaluation_query(self, cr, uid, ids, revaluation_date, context=None):
        lines_where_clause = self.pool.get('account.move.line').\
            _query_get(cr, uid, context=context)
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
            ctx_query['periods'] = period_ids
            ctx_query['fiscalyear'] = fiscalyear_id
            ctx_query['initial_bal'] = True
            query, params = self._revaluation_query(
                cr, uid, ids,
                revaluation_date,
                context=ctx_query)
            cr.execute(query, params)
            lines = cr.dictfetchall()
            # search previous period for reval search
            previous_period_ids = []
            for p in self.pool.get('account.period').read(cr, uid, period_ids, ['number']):
                previous_period_ids += self.pool.get('account.period').search(cr, uid, [('number', '<', p.get('number')), ('fiscalyear_id', '=', fiscalyear_id)])
            for line in lines:
                # generate a tree
                # - account_id
                # -- currency_id
                # ----- balances
                account_id, currency_id = line['id'], line['currency_id']
                accounts.setdefault(account_id, {})
                accounts[account_id].setdefault(
                    currency_id,
                    {'balance': 0, 'foreign_balance': 0, 'credit': 0, 'debit': 0, 'reval_balance': 0})
                accounts[account_id][currency_id]['balance'] += line['balance']
                accounts[account_id][currency_id]['foreign_balance'] += line['foreign_balance']
                accounts[account_id][currency_id]['credit'] += line['credit']
                accounts[account_id][currency_id]['debit'] += line['debit']
                # search old revaluation lines for this account and this currency for the given period
                reval_sql = """
                SELECT SUM(COALESCE(aml.debit, 0.0) - COALESCE(aml.credit, 0.0)) AS balance
                FROM account_move_line AS aml
                WHERE is_revaluated_ok = 't'
                AND period_id in %s
                AND account_id = %s
                AND currency_id = %s;"""
                cr.execute(reval_sql, (tuple(previous_period_ids), account_id, currency_id))
                reval_res = cr.dictfetchall()
                if reval_res and reval_res[0] and reval_res[0].get('balance', 0.0):
                    accounts[account_id][currency_id]['reval_balance'] += reval_res[0].get('balance', 0.0)

        return accounts

account_account()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
