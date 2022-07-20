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
            type='char', string=_(u"Type (code)"),
            write_relate=False),
        'instance_level': fields.related(
            'company_id', 'instance_id', 'level',
            type='char', string=_(u"Instance level"),
            write_relate=False),
    }

    _defaults = {'currency_revaluation': False}

    _sql_mapping = {
        'balance': "COALESCE(l.debit, 0) - COALESCE(l.credit, 0) as balance",
        'debit': "COALESCE(l.debit, 0) as debit",
        'credit': "COALESCE(l.credit, 0) as credit",
        # US-1251: booking balance mapping: use directly booking balance vs JI amount_currency as we have discrepancies
        'foreign_balance': "COALESCE(l.debit_currency, 0) - COALESCE(l.credit_currency, 0) as foreign_balance"
    }

    def _revaluation_query(self, cr, uid, ids, revaluation_date, context=None):
        query = ("SELECT l.account_id as id, l.currency_id, l.reconcile_id, "
                 " l.id AS aml_id, " +
                 ', '.join(self._sql_mapping.values()) +
                 " FROM account_move_line l"
                 " inner join account_period p on p.id = l.period_id"
                 " WHERE l.account_id IN %(account_ids)s AND"
                 " l.date <= %(revaluation_date)s AND"
                 " l.currency_id IS NOT NULL AND"
                 " l.state <> 'draft' AND"
                 " p.number != 0;")  # US-1251 exclude IB entries period 0 for monthly and yearly
        params = {'revaluation_date': revaluation_date,
                  'account_ids': tuple(ids)}
        return query, params

    def compute_revaluations(
            self, cr, uid, ids, period_ids, fiscalyear_id,
            revaluation_date, revaluation_method, context=None):
        if context is None:
            context = {}
        accounts = {}
        entries_included = {}
        reconciliations = {}
        aml_obj = self.pool.get('account.move.line')

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
        for l in lines:
            '''
            US-2382 Include the line in the revaluation if at least one of the following conditions is met:
            - month-end reval
            - year-end reval and entry being either partially reconciled or not reconciled
            - year-end reval and entry reconciled with at least one leg of the rec. having a posting date later than the FY
            '''
            line_to_keep = False
            if len(period_ids) == 1 or not l['reconcile_id']:
                line_to_keep = True
            elif l['reconcile_id']:
                if l['reconcile_id'] in reconciliations:
                    line_to_keep = reconciliations[l['reconcile_id']]
                else:
                    # get the JIs with the same reconcile_id
                    aml_list = aml_obj.search(cr, uid, [('reconcile_id', '=', l['reconcile_id'])], order='NO_ORDER', context=context)
                    # check that at least one of them has a posting date later than the FY
                    if aml_obj.search_exist(cr, uid, [('id', 'in', aml_list), ('date', '>', revaluation_date)], context=context):
                        line_to_keep = True
                    # store the result for this rec. to avoid re-doing the same computation several times
                    reconciliations.update({l['reconcile_id']: line_to_keep})
            if line_to_keep:
                # store by account and currency all the entries included in the reval
                if l['id'] not in entries_included:  # l['id'] is the id of the account
                    entries_included[l['id']] = {}
                if l['currency_id'] not in entries_included[l['id']]:
                    entries_included[l['id']][l['currency_id']] = []
                entries_included[l['id']][l['currency_id']].append(l['aml_id'])
                # generate a tree
                # - account_id
                # -- currency_id
                # ----- balances
                if l['id'] not in accounts:
                    accounts[l['id']] = {}
                if l['currency_id'] not in accounts[l['id']]:
                    accounts[l['id']][l['currency_id']] = {
                        'foreign_balance': 0,
                        'credit': 0,
                        'debit': 0,
                        'balance': 0,
                    }
                accounts[l['id']][l['currency_id']]['foreign_balance'] += l['foreign_balance']
                accounts[l['id']][l['currency_id']]['credit'] += l['credit']
                accounts[l['id']][l['currency_id']]['debit'] += l['debit']
                accounts[l['id']][l['currency_id']]['balance'] += l['balance']

        return accounts, entries_included

account_account()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
