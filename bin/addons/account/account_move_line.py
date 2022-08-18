# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

import time
from datetime import datetime

from osv import fields, osv
from tools.translate import _
import decimal_precision as dp
import tools
import netsvc
from base import currency_date


class account_move_line(osv.osv):
    _name = "account.move.line"
    _description = "Journal Items"

    def _query_get(self, cr, uid, obj='l', context=None):
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        fiscalperiod_obj = self.pool.get('account.period')
        account_obj = self.pool.get('account.account')
        fiscalyear_ids = []
        if context is None:
            context = {}
        initial_bal = context.get('initial_bal', False)
        company_clause = " "
        if context.get('company_id', False):
            company_clause = " AND " +obj+".company_id = %s" % context.get('company_id', False)
        if context.get('report_cross_fy', False):
            context['all_fiscalyear'] = True
            context['fiscalyear'] = False
        if not context.get('fiscalyear', False):
            if context.get('all_fiscalyear', False):
                #this option is needed by the aged balance report because otherwise, if we search only the draft ones, an open invoice of a closed fiscalyear won't be displayed
                fiscalyear_ids = fiscalyear_obj.search(cr, uid, [])
            else:
                fiscalyear_ids = fiscalyear_obj.search(cr, uid, [('state', '=', 'draft')])
        else:
            #for initial balance as well as for normal query, we check only the selected FY because the best practice is to generate the FY opening entries
            fiscalyear_ids = [context['fiscalyear']]

        # get period 0 ids
        period0_domain = [('number', '=', 0)]
        if fiscalyear_ids:
            period0_domain += [('fiscalyear_id', 'in', fiscalyear_ids)]
        period0_ids = fiscalperiod_obj.search(cr, uid, period0_domain,
                                              context={'show_period_0': 1})

        fiscalyear_clause = (','.join([str(x) for x in fiscalyear_ids])) or '0'
        state = context.get('state', False)
        where_move_state = ''
        where_move_lines_by_date = ''

        if context.get('report_cross_fy', False):
            # US-926 cross FY reporting
            if context.get('date_from', False) or context.get('date_to', False):
                field = 'document_date' \
                    if context.get('date_fromto_docdate', False) else 'date'
                from_to_contexts = [ ('date_from', '>='), ('date_to', '<='), ]
                date_where = ''
                for ft in from_to_contexts:
                    if context.get(ft[0], False):
                        date_where += "%s%s %s '%s'" % (
                            ' AND ' if date_where else '',
                            field, ft[1], context[ft[0]])
                if date_where:
                    where_move_lines_by_date = " AND " +obj+".move_id IN (SELECT id FROM account_move WHERE " + date_where + ")"
        else:
            # default behaviour (except US-926 cross FY reporting)
            if context.get('date_from', False) and context.get('date_to', False):
                if context.get('date_fromto_docdate', False):
                    if initial_bal:
                        where_move_lines_by_date = " AND " +obj+".move_id IN (SELECT id FROM account_move WHERE document_date < '" +context['date_from']+"')"
                    else:
                        where_move_lines_by_date = " AND " +obj+".move_id IN (SELECT id FROM account_move WHERE document_date >= '" +context['date_from']+"' AND document_date <= '"+context['date_to']+"')"
                else:
                    if initial_bal:
                        where_move_lines_by_date = " AND " +obj+".move_id IN (SELECT id FROM account_move WHERE date < '" +context['date_from']+"')"
                    else:
                        where_move_lines_by_date = " AND " +obj+".move_id IN (SELECT id FROM account_move WHERE date >= '" +context['date_from']+"' AND date <= '"+context['date_to']+"')"

        if state:
            if state.lower() not in ['all']:
                where_move_state= " AND "+obj+".move_id IN (SELECT id FROM account_move WHERE account_move.state = '"+state+"')"

        ctx_period_from = context.get('period_from', False)
        ctx_period_to = context.get('period_to', False)
        if (ctx_period_from or ctx_period_to) and not context.get('periods', False):
            if initial_bal:
                if ctx_period_from:
                    period_company_id = fiscalperiod_obj.browse(cr, uid, ctx_period_from, context=context).company_id.id
                    first_period = fiscalperiod_obj.search(cr, uid, [('company_id', '=', period_company_id)], order='date_start', limit=1)[0]
                    context['periods'] = fiscalperiod_obj.build_ctx_periods(cr, uid, first_period, ctx_period_from)
            else:
                context['periods'] = fiscalperiod_obj.build_ctx_periods(cr, uid, ctx_period_from, ctx_period_to)
        if context.get('periods', False):
            if initial_bal:
                query = obj+".state <> 'draft' AND "+obj+".period_id IN (SELECT id FROM account_period WHERE fiscalyear_id IN (%s)) %s %s" % (fiscalyear_clause, where_move_state, where_move_lines_by_date)
                period_ids = fiscalperiod_obj.search(cr, uid, [('id', 'in', context['periods'])], order='date_start', limit=1)
                if period_ids and period_ids[0]:
                    first_period = fiscalperiod_obj.browse(cr, uid, period_ids[0], context=context)
                    # Find the old periods where date start of those periods less then Start period
                    periods = fiscalperiod_obj.search(cr, uid, [('date_start', '<', first_period.date_start)])
                    periods = ','.join([str(x) for x in periods])
                    if periods:
                        query = obj+".state <> 'draft' AND "+obj+".period_id IN (SELECT id FROM account_period WHERE fiscalyear_id IN (%s) AND id IN (%s)) %s %s" % (fiscalyear_clause, periods, where_move_state, where_move_lines_by_date)
            else:
                ids = ','.join([str(x) for x in context['periods']])
                if context.get('period0', False) and period0_ids:  # US-1391/1
                    ids += ",%s" % (','.join(map(str, period0_ids)), )
                query = obj+".state <> 'draft' AND "+obj+".period_id IN (SELECT id FROM account_period WHERE fiscalyear_id IN (%s) AND id IN (%s)) %s %s" % (fiscalyear_clause, ids, where_move_state, where_move_lines_by_date)
        else:
            query = obj+".state <> 'draft' AND "+obj+".period_id IN (SELECT id FROM account_period WHERE fiscalyear_id IN (%s)) %s %s" % (fiscalyear_clause, where_move_state, where_move_lines_by_date)

        if context.get('journal_ids', False):
            if context.get('rev_journal_ids', False):
                journal_operator = 'NOT IN'
            else:
                journal_operator = 'IN'
            query += ' AND '+obj+'.journal_id %s (%s)' % (journal_operator, ','.join(map(str, context['journal_ids'])))

        if context.get('chart_account_id', False):
            child_ids = account_obj._get_children_and_consol(cr, uid, [context['chart_account_id']], context=context)
            query += ' AND '+obj+'.account_id IN (%s)' % ','.join(map(str, child_ids))

        # period 0
        if period0_ids:
            if not context.get('period0', False):
                # US-822: by default in reports exclude period 0 (IB journals)
                query += ' AND %s.period_id not in (%s)' % (obj, ','.join(map(str, period0_ids)), )

        if context.get('state_agnostic', False):
            query = query.replace(obj+".state <> 'draft' AND ", '')

        query += company_clause
        return query

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        data = self._default_get(cr, uid, fields, context=context, from_web=from_web)
        for f in list(data.keys()):
            if f not in fields:
                del data[f]
        return data

    def create_analytic_lines(self, cr, uid, ids, context=None):
        """
        Create analytic lines on analytic-a-holic accounts that have an analytical distribution.
        """
        if context is None:
            context = {}
        acc_ana_line_obj = self.pool.get('account.analytic.line')
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id

        obj_fields = [
            'debit_currency',
            'credit_currency',
            'analytic_distribution_id',
            'move_id',
            'state',
            'journal_id',
            'source_date',
            'date',
            'document_date',
            'name',
            'ref',
            'currency_id',
            'corrected_line_id',
            'is_write_off',
            'account_id',
            'period_id',
            'is_revaluated_ok',
            'debit',
            'credit',
            'is_addendum_line',
        ]

        for obj_line in self.read(cr, uid, ids, obj_fields, context=context):
            # Prepare some values
            amount = obj_line.get('debit_currency', 0.0) - obj_line.get('credit_currency', 0.0)
            amount_ji_fctal = obj_line.get('debit', 0.0) - obj_line.get('credit', 0.0)
            journal = self.pool.get('account.journal').read(cr, uid, obj_line.get('journal_id', [False])[0], ['analytic_journal_id', 'name'], context=context)
            move = self.pool.get('account.move').read(cr, uid, obj_line.get('move_id', [False])[0], ['analytic_distribution_id', 'status', 'line_id'], context=context)
            account = self.pool.get('account.account').read(cr, uid, obj_line.get('account_id', [False])[0], ['is_analytic_addicted'], context=context)
            aal_obj = self.pool.get('account.analytic.line')
            line_distrib_id = (obj_line.get('analytic_distribution_id', False) and obj_line.get('analytic_distribution_id')[0]) or (move.get('analytic_distribution_id', False) and move.get('analytic_distribution_id')[0]) or False
            # When you create a journal entry manually, we should not have analytic lines if ONE line is invalid!
            other_lines_are_ok = True
            #result = self.search(cr, uid, [('move_id', '=', move.get('id', False)), ('move_id.status', '=', 'manu'), ('state', '!=', 'valid')], count=1)
            if move.get('status', False) == 'manu':
                result = self.search(cr, uid, [('move_id', '=', move.get('id', False)), ('state', '!=', 'valid')], count=1)
                if result and result > 0:
                    other_lines_are_ok = False
            # Check that line have analytic-a-holic account and have a distribution
            if line_distrib_id and account.get('is_analytic_addicted', False) and other_lines_are_ok:
                ana_state = self.pool.get('analytic.distribution')._get_distribution_state(cr, uid, line_distrib_id, {}, account.get('id'),
                                                                                           amount=amount  # booking amount
                                                                                           )
                # For manual journal entries, do not raise an error. But delete all analytic distribution linked to other_lines because if one line is invalid, all lines should not create analytic lines
                invalid_state = ana_state in ('invalid', 'invalid_small_amount')
                if invalid_state and move.get('status', '') == 'manu':
                    ana_line_ids = acc_ana_line_obj.search(cr, uid, [('move_id', 'in', move.get('line_id', []))])
                    acc_ana_line_obj.unlink(cr, uid, ana_line_ids)
                    continue
                elif invalid_state:
                    raise osv.except_osv(_('Warning'), _('Invalid analytic distribution.'))
                if not journal.get('analytic_journal_id', False):
                    raise osv.except_osv(_('Warning'),_("No Analytic Journal! You have to define an analytic journal on the '%s' journal!") % (journal.get('name', ''), ))
                distrib_obj = self.pool.get('analytic.distribution').browse(cr, uid, line_distrib_id, context=context)
                # create lines
                for distrib_lines in [distrib_obj.funding_pool_lines, distrib_obj.free_1_lines, distrib_obj.free_2_lines]:
                    aji_greater_amount = {
                        'amount': 0.,
                        'is': False,
                        'id': False,
                        'iso': 0.,
                    }

                    # US-1463/2: are all lines eguals by amount ?
                    if distrib_lines:
                        amounts = list(set([ dl.percentage*amount/100 for dl in distrib_lines ]))
                        if len(amounts) == 1:
                            aji_greater_amount['iso'] = round(amounts[0], 2)

                    dl_total_amount_rounded = 0.
                    for distrib_line in distrib_lines:
                        curr_date = currency_date.get_date(self, cr, obj_line.get('document_date', False),
                                                           obj_line.get('date', False), source_date=obj_line.get('source_date', False))
                        context.update({'currency_date': curr_date})
                        anal_amount = distrib_line.percentage*amount/100
                        anal_amount_rounded = round(anal_amount, 2)
                        dl_total_amount_rounded += anal_amount_rounded
                        # get the AJI with the biggest absolute value (it will be used for a potential adjustment
                        # to ensure JI = AJI amounts)
                        if abs(anal_amount_rounded) > abs(aji_greater_amount['amount']):
                            # US-119: breakdown by fp line or free 1, free2
                            # register the aji that will have the greatest amount
                            aji_greater_amount['amount'] = anal_amount_rounded
                            aji_greater_amount['is'] = True
                        else:
                            aji_greater_amount['is'] = False
                        analytic_currency_id = obj_line.get('currency_id', [False])[0]
                        amount_aji_book = -1 * anal_amount_rounded
                        # functional amount
                        if obj_line.get('is_revaluated_ok'):
                            # (US-1682) if it's a revaluation line get the functional amount directly from the JI
                            # to avoid slight differences between JI and AJI amounts caused by computation
                            amount_aji_fctal = -1 * distrib_line.percentage * amount_ji_fctal / 100
                        elif obj_line.get('is_addendum_line'):
                            # US-1766: AJIs linked to FXA entry should have fct amount = booking amount
                            # and book currency = fct currency
                            analytic_currency_id = company_currency
                            amount_aji_fctal = -1 * distrib_line.percentage * amount_ji_fctal / 100
                            amount_aji_book = -1 * distrib_line.percentage * amount_ji_fctal / 100
                        else:
                            amount_aji_fctal = -1 * self.pool.get('res.currency').compute(
                                cr, uid, obj_line.get('currency_id', [False])[0], company_currency, anal_amount,
                                round=False, context=context)
                        line_vals = {
                            'name': obj_line.get('name', ''),
                            'date': obj_line.get('date', False),
                            'ref': obj_line.get('ref', False),
                            'journal_id': journal.get('analytic_journal_id', [False])[0],
                            'amount': amount_aji_fctal,
                            'amount_currency': amount_aji_book,  # booking amount
                            'account_id': distrib_line.analytic_id.id,
                            'general_account_id': account.get('id'),
                            'move_id': obj_line.get('id'),
                            'distribution_id': distrib_obj.id,
                            'user_id': uid,
                            'currency_id': analytic_currency_id,
                            'distrib_line_id': '%s,%s'%(distrib_line._name, distrib_line.id),
                            'document_date': obj_line.get('document_date', False),
                            'source_date': curr_date,
                            'real_period_id': obj_line['period_id'] and obj_line['period_id'][0] or False,  # US-945/2
                        }
                        # Update values if we come from a funding pool
                        if distrib_line._name == 'funding.pool.distribution.line':
                            destination_id = distrib_line.destination_id and distrib_line.destination_id.id or False
                            line_vals.update({'cost_center_id': distrib_line.cost_center_id and distrib_line.cost_center_id.id or False,
                                              'destination_id': destination_id,})
                        # Update value if we come from a write-off
                        if obj_line.get('is_write_off', False):
                            line_vals.update({'from_write_off': True,})
                        # Add source_date value for account_move_line that are a correction of another account_move_line
                        if obj_line.get('corrected_line_id', False) and obj_line.get('source_date', False):
                            line_vals.update({'source_date': obj_line.get('source_date', False)})
                        aji_id = aal_obj.create(cr, uid, line_vals, context=context)
                        if aji_greater_amount['is']:
                            aji_greater_amount['id'] = aji_id

                    if abs(amount) > 0. and abs(dl_total_amount_rounded) > 0.:
                        if abs(dl_total_amount_rounded - amount) > 0.001 and \
                                aji_greater_amount['id']:
                            # US-119 deduce the rounding gap and apply it
                            # to the AJI of greater amount
                            # http://jira.unifield.org/browse/US-119?focusedCommentId=38217&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel#comment-38217
                            # and US-1463
                            fixed_amount = aji_greater_amount['amount'] - (round(dl_total_amount_rounded, 2) - amount)
                            func_amount = None

                            if aji_greater_amount['iso'] > 0:
                                # US-1463/2
                                # AD lines with same ratio/amount
                                # and 50/50 breakdown
                                if len(distrib_lines) == 2:
                                    diff = round(dl_total_amount_rounded - amount, 2)
                                    #print 'difff', diff, 'rounded', dl_total_amount_rounded, 'amount', amount
                                    if (abs(diff)) < 0.001:
                                        diff = 0.  # non significative gap
                                    fixed_amount = round(aji_greater_amount['iso'] - diff, 2)
                                    #print 'fixed_amount', fixed_amount, 'aji_greater_amount', aji_greater_amount['iso']
                            else:
                                # US-1463/1
                                func_amount = -1 * self.pool.get('res.currency').compute(cr, uid, obj_line.get('currency_id', [False])[0], company_currency, fixed_amount, round=False, context=context)
                                func_amount = round(func_amount, 2)
                            fixed_amount_vals = {
                                'amount_currency': -1 * fixed_amount,
                            }
                            if func_amount is not None:
                                fixed_amount_vals['amount'] = func_amount
                            aal_obj.write(cr, uid, [aji_greater_amount['id']],
                                          fixed_amount_vals, context=context)

        return True


    def _default_get_move_form_hook(self, cursor, user, data):
        '''Called in the end of default_get method for manual entry in account_move form'''
        if 'analytic_account_id' in data:
            del(data['analytic_account_id'])
        if 'account_tax_id' in data:
            del(data['account_tax_id'])
        return data

    def convert_to_period(self, cr, uid, context=None):
        if context is None:
            context = {}
        period_obj = self.pool.get('account.period')
        #check if the period_id changed in the context from client side
        if context.get('period_id', False):
            period_id = context.get('period_id')
            if type(period_id) == str:
                ids = period_obj.search(cr, uid, [('name', 'ilike', period_id)])
                context.update({
                    'period_id': ids[0]
                })
        return context

    def _default_get(self, cr, uid, fields, context=None, from_web=False):
        if context is None:
            context = {}
        if not context.get('journal_id', False) and context.get('search_default_journal_id', False):
            context['journal_id'] = context.get('search_default_journal_id')
        account_obj = self.pool.get('account.account')
        period_obj = self.pool.get('account.period')
        journal_obj = self.pool.get('account.journal')
        move_obj = self.pool.get('account.move')
        tax_obj = self.pool.get('account.tax')
        fiscal_pos_obj = self.pool.get('account.fiscal.position')
        partner_obj = self.pool.get('res.partner')
        context = self.convert_to_period(cr, uid, context)
        # Compute simple values
        data = super(account_move_line, self).default_get(cr, uid, fields, context=context, from_web=from_web)
        # Starts: Manual entry from account.move form
        if context.get('lines',[]):
            total_new = 0.00
            for line_record in context['lines']:
                if not isinstance(line_record, (tuple, list)):
                    line_record_detail = self.read(cr, uid, line_record, ['analytic_account_id','debit','credit','name','reconcile_id','tax_code_id','tax_amount','account_id','ref','currency_id','date_maturity','amount_currency','partner_id', 'reconcile_partial_id'])
                else:
                    line_record_detail = line_record[2]
                total_new += (line_record_detail['debit'] or 0.00)- (line_record_detail['credit'] or 0.00)
                for item in list(line_record_detail.keys()):
                    data[item] = line_record_detail[item]
            if context['journal']:
                journal_data = journal_obj.browse(cr, uid, context['journal'], context=context)
                if journal_data.type == 'purchase':
                    if total_new > 0:
                        account = journal_data.default_credit_account_id
                    else:
                        account = journal_data.default_debit_account_id
                else:
                    if total_new > 0:
                        account = journal_data.default_credit_account_id
                    else:
                        account = journal_data.default_debit_account_id
                if account and ((not fields) or ('debit' in fields) or ('credit' in fields)) and 'partner_id' in data and (data['partner_id']):
                    part = partner_obj.browse(cr, uid, data['partner_id'], context=context)
                    account = fiscal_pos_obj.map_account(cr, uid, part and part.property_account_position or False, account.id)
                    account = account_obj.browse(cr, uid, account, context=context)
                    data['account_id'] =  account.id

            s = -total_new
            data['debit'] = s > 0 and s or 0.0
            data['credit'] = s < 0 and -s or 0.0
            data = self._default_get_move_form_hook(cr, uid, data)
            return data
        # Ends: Manual entry from account.move form
        if not 'move_id' in fields: #we are not in manual entry
            return data
        # Compute the current move
        move_id = False
        partner_id = False
        if context.get('journal_id', False) and context.get('period_id', False):
            if 'move_id' in fields:
                cr.execute('SELECT move_id \
                    FROM \
                        account_move_line \
                    WHERE \
                        journal_id = %s and period_id = %s AND create_uid = %s AND state = %s \
                    ORDER BY id DESC limit 1',
                           (context['journal_id'], context['period_id'], uid, 'draft'))
                res = cr.fetchone()
                move_id = (res and res[0]) or False
                if not move_id:
                    return data
                else:
                    data['move_id'] = move_id
            if 'date' in fields:
                cr.execute('SELECT date \
                    FROM \
                        account_move_line \
                    WHERE \
                        journal_id = %s AND period_id = %s AND create_uid = %s \
                    ORDER BY id DESC',
                           (context['journal_id'], context['period_id'], uid))
                res = cr.fetchone()
                if res:
                    data['date'] = res[0]
                else:
                    period = period_obj.browse(cr, uid, context['period_id'],
                                               context=context)
                    data['date'] = period.date_start
        if not move_id:
            return data
        total = 0
        ref_id = False
        move = move_obj.browse(cr, uid, move_id, context=context)
        if 'name' in fields:
            data.setdefault('name', move.line_id[-1].name)

        for l in move.line_id:
            partner_id = partner_id or l.partner_id.id
            ref_id = ref_id or l.ref
            total += (l.debit or 0.0) - (l.credit or 0.0)

        if 'ref' in fields:
            data['ref'] = ref_id
        if 'partner_id' in fields:
            data['partner_id'] = partner_id

        if move.journal_id.type == 'purchase':
            if total > 0:
                account = move.journal_id.default_credit_account_id
            else:
                account = move.journal_id.default_debit_account_id
        else:
            if total > 0:
                account = move.journal_id.default_credit_account_id
            else:
                account = move.journal_id.default_debit_account_id
        part = partner_id and partner_obj.browse(cr, uid, partner_id) or False
        # part = False is acceptable for fiscal position.
        account = fiscal_pos_obj.map_account(cr, uid, part and part.property_account_position or False, account.id)
        if account:
            account = account_obj.browse(cr, uid, account, context=context)

        if account and ((not fields) or ('debit' in fields) or ('credit' in fields)):
            data['account_id'] = account.id
            # Propose the price VAT excluded, the VAT will be added when confirming line
            if account.tax_ids:
                taxes = fiscal_pos_obj.map_tax(cr, uid, part and part.property_account_position or False, account.tax_ids)
                tax = tax_obj.browse(cr, uid, taxes)
                for t in tax_obj.compute_inv(cr, uid, tax, total, 1):
                    total -= t['amount']

        s = -total
        data['debit'] = s > 0  and s or 0.0
        data['credit'] = s < 0  and -s or 0.0

        return data

    def on_create_write(self, cr, uid, id, context=None):
        if not id:
            return []
        ml = self.browse(cr, uid, id, context=context)
        return [x.id for x in ml.move_id.line_id]

    def _balance(self, cr, uid, ids, name, arg, context=None):
        if context is None:
            context = {}
        c = context.copy()
        c['initital_bal'] = True
        sql = """SELECT l2.id, SUM(l1.debit-l1.credit)
                    FROM account_move_line l1, account_move_line l2
                    WHERE l2.account_id = l1.account_id
                      AND l1.id <= l2.id
                      AND l2.id IN %%s AND %s GROUP BY l2.id""" % self._query_get(cr, uid, obj='l1', context=c)  # ignore_sql_check

        cr.execute(sql, [tuple(ids)])
        result = dict(cr.fetchall())
        for id in ids:
            result.setdefault(id, 0.0)
        return result

    def _invoice(self, cursor, user, ids, name, arg, context=None):
        invoice_obj = self.pool.get('account.invoice')
        res = {}
        for line_id in ids:
            res[line_id] = False
        cursor.execute('SELECT l.id, i.id ' \
                       'FROM account_move_line l, account_invoice i ' \
                       'WHERE l.move_id = i.move_id ' \
                       'AND l.id IN %s',
                       (tuple(ids),))
        invoice_ids = []
        for line_id, invoice_id in cursor.fetchall():
            res[line_id] = invoice_id
            invoice_ids.append(invoice_id)
        invoice_names = {False: ''}
        for invoice_id, name in invoice_obj.name_get(cursor, 1, invoice_ids, context=context):
            invoice_names[invoice_id] = name
        for line_id in list(res.keys()):
            invoice_id = res[line_id]
            res[line_id] = (invoice_id, invoice_names[invoice_id])
        return res

    def _get_purchase_order_id(self, cr, uid, ids, name, arg, context=None):
        """
        Returns a dict with key = id of the JI, and value = id of the related PO,
        in case the JI is linked to an invoice which is linked to a PO
        """
        if context is None:
            context = {}
        res = {}
        for aml in self.browse(cr, uid, ids, fields_to_fetch=['invoice'], context=context):
            po = aml.invoice and aml.invoice.purchase_ids and aml.invoice.purchase_ids[0]  # only one PO can be linked to an SI
            res[aml.id] = po and po.id or False
        return res

    def name_get(self, cr, uid, ids, context=None):
        # Override default name_get (since it displays the move line reference)
        if not ids:
            return []
        result = []
        for line in self.browse(cr, uid, ids, context=context):
            result.append((line.id, line.move_id.name))
        return result

    def _balance_search(self, cursor, user, obj, name, args, domain=None, context=None):
        if context is None:
            context = {}
        if not args:
            return []
        where = ' AND '.join(['(abs(sum(debit-credit))'+x[1]+str(x[2])+')' for x in args])
        cursor.execute('SELECT id, SUM(debit-credit) FROM account_move_line \
                        GROUP BY id, debit, credit having '+where)  # not_a_user_entry
        res = cursor.fetchall()
        if not res:
            return [('id', '=', '0')]
        return [('id', 'in', [x[0] for x in res])]

    def _invoice_search(self, cursor, user, obj, name, args, context=None):
        if not args:
            return []
        invoice_obj = self.pool.get('account.invoice')
        i = 0
        while i < len(args):
            fargs = args[i][0].split('.', 1)
            if len(fargs) > 1:
                args[i] = (fargs[0], 'in', invoice_obj.search(cursor, user,
                                                              [(fargs[1], args[i][1], args[i][2])]))
                i += 1
                continue
            if isinstance(args[i][2], str):
                res_ids = invoice_obj.name_search(cursor, user, args[i][2], [],
                                                  args[i][1])
                args[i] = (args[i][0], 'in', [x[0] for x in res_ids])
            i += 1
        qu1, qu2 = [], []
        for x in args:
            if x[1] != 'in':
                if (x[2] is False) and (x[1] == '='):
                    qu1.append('(i.id IS NULL)')
                elif (x[2] is False) and (x[1] == '<>' or x[1] == '!='):
                    qu1.append('(i.id IS NOT NULL)')
                else:
                    qu1.append('(i.id %s %s)' % (x[1], '%s'))
                    qu2.append(x[2])
            elif x[1] == 'in':
                if len(x[2]) > 0:
                    qu1.append('(i.id IN (%s))' % (','.join(['%s'] * len(x[2]))))
                    qu2 += x[2]
                else:
                    qu1.append(' (False)')
        if qu1:
            qu1 = ' AND' + ' AND'.join(qu1)
        else:
            qu1 = ''
        cursor.execute('''
            SELECT l.id
            FROM account_move_line l, account_invoice i
            WHERE l.move_id = i.move_id ''' + qu1, qu2)  # not_a_user_entry
        res = cursor.fetchall()
        if not res:
            return [('id', '=', '0')]
        return [('id', 'in', [x[0] for x in res])]

    def _get_move_lines(self, cr, uid, ids, context=None):
        result = []
        for move in self.pool.get('account.move').browse(cr, uid, ids, context=context):
            for line in move.line_id:
                result.append(line.id)
        return result

    def _get_line_account_type(self, cr, uid, ids, field_name=None, arg=None, context=None):
        if isinstance(ids, int):
            ids = [ids]
        ret = {}
        for line in self.browse(cr, uid, ids, fields_to_fetch=['account_id']):
            ret[line.id] = line.account_id and line.account_id.user_type and line.account_id.user_type.name or False
        return ret

    def _store_journal_account(self, cr, uid, ids, context=None):
        return self.pool.get('account.move.line').search(cr, uid, [('account_id', 'in', ids)])

    def _store_journal_account_type(self, cr, uid, ids, context=None):
        return self.pool.get('account.move.line').search(cr, uid, [('account_id.user_type', 'in', ids)])

    def _get_reconcile_total_partial_id(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Informs for each move line if a reconciliation or a partial reconciliation have been made. Else return False.
        """
        if isinstance(ids, int):
            ids = [ids]
        ret = {}
        for line in self.read(cr, uid, ids, ['reconcile_id','reconcile_partial_id']):
            if line['reconcile_id']:
                ret[line['id']] = line['reconcile_id']
            elif line['reconcile_partial_id']:
                ret[line['id']] = line['reconcile_partial_id']
            else:
                ret[line['id']] = False
        return ret

    def _search_reconcile_total_partial(self, cr, uid, ids, field_names, args, context=None):
        """
        Search either total reconciliation name or partial reconciliation name
        """
        if context is None:
            context = {}
        arg = []
        for x in args:
            if x[0] == 'reconcile_total_partial_id' and x[1] in ['=','ilike','like'] and x[2]:
                arg.append('|')
                arg.append(('reconcile_id', x[1], x[2]))
                arg.append(('reconcile_partial_id', x[1], x[2]))
            elif x[0] == 'reconcile_total_partial_id':
                raise osv.except_osv(_('Error'), _('Operator not supported!'))
            else:
                arg.append(x)
        return arg

    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'quantity': fields.float('Quantity', digits=(16,2), help="The optional quantity expressed by this line, eg: number of product sold. The quantity is not a legal requirement but is very useful for some reports."),
        'product_uom_id': fields.many2one('product.uom', 'UoM'),
        'product_id': fields.many2one('product.product', 'Product'),
        'debit': fields.float('Debit', digits_compute=dp.get_precision('Account')),
        'credit': fields.float('Credit', digits_compute=dp.get_precision('Account')),
        'account_id': fields.many2one('account.account', 'Account',
                                      required=True, ondelete="cascade", domain=[('type','<>','view'),
                                                                                 ('type', '<>', 'closed')], select=2, hide_default_menu=True),
        'move_id': fields.many2one('account.move', 'Move', ondelete="cascade", help="The move of this entry line.", select=2, required=True),
        'narration': fields.related('move_id','narration', type='text', relation='account.move', string='Narration', write_relate=False),
        'ref': fields.related('move_id', 'ref', string='Reference', type='char', size=64, store=True, write_relate=False),
        'statement_id': fields.many2one('account.bank.statement', 'Statement', help="The bank statement used for bank reconciliation", select=1),
        'reconcile_id': fields.many2one('account.move.reconcile', 'Reconcile', readonly=True, ondelete='set null', select=2),
        'reconcile_partial_id': fields.many2one('account.move.reconcile', 'Partial Reconcile', readonly=True, ondelete='set null', select=2),
        'amount_currency': fields.float('Amount Currency', help="The amount expressed in an optional other currency if it is a multi-currency entry.", digits_compute=dp.get_precision('Account')),
        'currency_id': fields.many2one('res.currency', 'Currency', help="The optional other currency if it is a multi-currency entry."),
        'period_id': fields.many2one('account.period', 'Period', required=True, select=2),
        'fiscalyear_id': fields.related('period_id', 'fiscalyear_id', type='many2one', relation='account.fiscalyear', string='Fiscal Year', store=False, write_relate=False),
        'journal_id': fields.many2one('account.journal', 'Journal', required=True, select=1),
        'blocked': fields.boolean('Litigation', help="You can check this box to mark this journal item as a litigation with the associated partner"),
        'partner_id': fields.many2one('res.partner', 'Partner', select=1, ondelete='restrict'),
        'date_maturity': fields.date('Due date', select=True ,help="This field is used for payable and receivable journal entries. You can put the limit date for the payment of this line."),
        'date': fields.related('move_id','date', string='Effective date', type='date', required=True, select=True,
                               store = {
                                   'account.move': (_get_move_lines, ['date'], 20)
                               }, readonly=True),
        'date_created': fields.date('Creation date', select=True),
        'analytic_lines': fields.one2many('account.analytic.line', 'move_id', 'Analytic lines'),
        'centralisation': fields.selection([('normal','Normal'),('credit','Credit Centralisation'),('debit','Debit Centralisation'),('currency','Currency Adjustment')], 'Centralisation', size=8),
        'balance': fields.function(_balance, fnct_search=_balance_search, method=True, string='Balance'),
        'state': fields.selection([('draft','Unbalanced'), ('valid','Valid')], 'State', readonly=True,
                                  help='When new move line is created the state will be \'Draft\'.\n* When all the payments are done it will be in \'Valid\' state.'),
        'tax_code_id': fields.many2one('account.tax.code', 'Tax Account', help="The Account can either be a base tax code or a tax code account."),
        'tax_amount': fields.float('Tax/Base Amount', digits_compute=dp.get_precision('Account'), select=True, help="If the Tax account is a tax code account, this field will contain the taxed amount.If the tax account is base tax code, "\
                                   "this field will contain the basic amount(without tax)."),
        'invoice': fields.function(_invoice, method=True, string='Invoice',
                                   type='many2one', relation='account.invoice', fnct_search=_invoice_search),
        'purchase_order_id': fields.function(_get_purchase_order_id, method=True, string='Purchase Order',
                                             type='many2one', relation='purchase.order', readonly=True, store=False),
        'account_tax_id':fields.many2one('account.tax', 'Tax'),
        'analytic_account_id': fields.many2one('account.analytic.account', 'Analytic Account'),
        #TODO: remove this
        #'amount_taxed':fields.float("Taxed Amount", digits_compute=dp.get_precision('Account')),
        'company_id': fields.related('account_id', 'company_id', type='many2one', relation='res.company', string='Company', store=True, readonly=True),
        # UF-1536: Fix residual amount (to be checked during UNIFIELD REFACTORING)
        'is_counterpart': fields.boolean('Is counterpart?', readonly=True),
        'debit_currency': fields.float('Book. Debit', digits_compute=dp.get_precision('Account')),
        'credit_currency': fields.float('Book. Credit', digits_compute=dp.get_precision('Account')),
        'functional_currency_id': fields.related('account_id', 'company_id', 'currency_id', type="many2one", relation="res.currency",
                                                 string="Func. Currency", store=False, write_relate=False),
        # Those fields are for UF-173: Accounting Journals.
        # Since they are used in the move line view, they are added in Multi-Currency.
        'account_type': fields.function(_get_line_account_type, type='char', size=64, method=True, string="Account Type",
                                        store={
                                            'account.move.line': (lambda self, cr, uid, ids, c=None: ids, ['account_id'], 10),
                                            'account.account': (_store_journal_account, ['user_type'], 10),
                                            'account.account.type': (_store_journal_account_type, ['name'], 10),
                                        }
                                        ),
        'reconcile_total_partial_id': fields.function(_get_reconcile_total_partial_id, fnct_search=_search_reconcile_total_partial,
                                                      type="many2one", relation="account.move.reconcile", method=True, string="Reconcile"),
    }

    def _get_currency(self, cr, uid, context=None):
        if context is None:
            context = {}
        if not context.get('journal_id', False):
            return False
        cur = self.pool.get('account.journal').browse(cr, uid, context['journal_id']).currency
        return cur and cur.id or False

    _defaults = {
        'blocked': False,
        'centralisation': 'normal',
        'date_created': lambda *a: time.strftime('%Y-%m-%d'),
        'state': 'draft',
        'currency_id': _get_currency,
        'journal_id': lambda self, cr, uid, c: c.get('journal_id', c.get('journal',False)),
        'account_id': lambda self, cr, uid, c: c.get('account_id', False),
        'period_id': lambda self, cr, uid, c: c.get('period_id', False),
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'account.move.line', context=c),
        'is_counterpart': lambda *a: False,
        # prevent NULL value in sql record
        'debit': 0,
        'credit': 0,
        'debit_currency': 0.0,
        'credit_currency': 0.0,
    }
    _sql_constraints = [
        ('credit_debit1', 'CHECK (credit*debit=0)',  'Wrong credit or debit value in accounting entry !'),
        ('credit_debit2', 'CHECK (credit+debit>=0)', 'Wrong credit or debit value in accounting entry !'),
        ('booking_credit_debit1', 'CHECK (credit_currency * debit_currency = 0)', 'Wrong credit or debit value in booking currency!'),
        ('booking_credit_debit2', 'CHECK (credit_currency + debit_currency >= 0)', 'Wrong credit or debit value in booking currency!'),
    ]

    def _auto_init(self, cr, context=None):
        ret = super(account_move_line, self)._auto_init(cr, context=context)
        cr.execute('SELECT indexname FROM pg_indexes WHERE indexname = \'account_move_line_journal_id_period_id_index\'')
        if not cr.fetchone():
            cr.execute('CREATE INDEX account_move_line_journal_id_period_id_index ON account_move_line (journal_id, period_id)')
        cr.execute('SELECT indexname FROM pg_indexes WHERE indexname = \'account_move_line_move_id_id_index\'')
        if not cr.fetchone():
            cr.execute('CREATE INDEX account_move_line_move_id_id_index ON account_move_line (move_id DESC, id)')
        return ret

    def _check_no_view(self, cr, uid, ids, context=None):
        lines = self.browse(cr, uid, ids, context=context)
        for l in lines:
            if l.account_id.type == 'view':
                return False
        return True

    def _check_no_closed(self, cr, uid, ids, context=None):
        lines = self.browse(cr, uid, ids, context=context)
        for l in lines:
            if l.account_id.type == 'closed':
                return False
        return True

    def _check_company_id(self, cr, uid, ids, context=None):
        lines = self.browse(cr, uid, ids, context=context)
        for l in lines:
            if l.company_id != l.account_id.company_id or l.company_id != l.period_id.company_id:
                return False
        return True

    _constraints = [
        (_check_no_view, 'You can not create move line on view account.', ['account_id']),
        (_check_no_closed, 'You can not create move line on closed account.', ['account_id']),
        (_check_company_id, 'Company must be same for its related account and period.',['company_id'] ),
    ]

    def onchange_partner_id(self, cr, uid, ids, move_id, partner_id, account_id=None, debit=0, credit=0, date=False, journal=False):
        partner_obj = self.pool.get('res.partner')
        payment_term_obj = self.pool.get('account.payment.term')
        journal_obj = self.pool.get('account.journal')
        fiscal_pos_obj = self.pool.get('account.fiscal.position')
        val = {}
        val['date_maturity'] = False

        if not partner_id:
            return {'value':val}
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        part = partner_obj.browse(cr, uid, partner_id)

        if part.property_payment_term:
            res = payment_term_obj.compute(cr, uid, part.property_payment_term.id, 100, date)
            if res:
                val['date_maturity'] = res[0][0]
        if not account_id:
            id1 = part.property_account_payable.id
            id2 =  part.property_account_receivable.id
            if journal:
                jt = journal_obj.browse(cr, uid, journal).type
                #FIXME: Bank and cash journal are such a journal we can not assume a account based on this 2 journals
                # Bank and cash journal can have a payment or receipt transaction, and in both type partner account
                # will not be same id payment then payable, and if receipt then receivable
                #if jt in ('sale', 'purchase_refund', 'bank', 'cash'):
                if jt in ('sale', 'purchase_refund'):
                    val['account_id'] = fiscal_pos_obj.map_account(cr, uid, part and part.property_account_position or False, id2)
                elif jt in ('purchase', 'sale_refund', 'expense', 'bank', 'cash'):
                    val['account_id'] = fiscal_pos_obj.map_account(cr, uid, part and part.property_account_position or False, id1)
                if val.get('account_id', False):
                    d = self.onchange_account_id(cr, uid, ids, val['account_id'])
                    val.update(d['value'])
        return {'value':val}

    def onchange_account_id(self, cr, uid, ids, account_id=False, partner_id=False):
        account_obj = self.pool.get('account.account')
        partner_obj = self.pool.get('res.partner')
        fiscal_pos_obj = self.pool.get('account.fiscal.position')
        val = {}
        if account_id:
            res = account_obj.browse(cr, uid, account_id)
            tax_ids = res.tax_ids
            if tax_ids and partner_id:
                part = partner_obj.browse(cr, uid, partner_id)
                tax_id = fiscal_pos_obj.map_tax(cr, uid, part and part.property_account_position or False, tax_ids)[0]
            else:
                tax_id = tax_ids and tax_ids[0].id or False
            val['account_tax_id'] = tax_id
        return {'value': val}

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        if context is None:
            context = {}
        if context and context.get('next_partner_only', False):
            if not context.get('partner_id', False):
                partner = self.get_next_partner_only(cr, uid, offset, context)
            else:
                partner = context.get('partner_id', False)
            if not partner:
                return []
            args.append(('partner_id', '=', partner[0]))
        return super(account_move_line, self).search(cr, uid, args, offset,
                                                     limit, order, context, count)

    def get_next_partner_only(self, cr, uid, offset=0, context=None):
        cr.execute(
            """
             SELECT p.id
             FROM res_partner p
             RIGHT JOIN (
                SELECT l.partner_id AS partner_id, SUM(l.debit) AS debit, SUM(l.credit) AS credit
                FROM account_move_line l
                LEFT JOIN account_account a ON (a.id = l.account_id)
                    LEFT JOIN res_partner p ON (l.partner_id = p.id)
                    WHERE a.reconcile IS TRUE
                    AND l.reconcile_id IS NULL
                    AND (p.last_reconciliation_date IS NULL OR l.date > p.last_reconciliation_date)
                    AND l.state <> 'draft'
                    GROUP BY l.partner_id
                ) AS s ON (p.id = s.partner_id)
                WHERE debit > 0 AND credit > 0
                ORDER BY p.last_reconciliation_date LIMIT 1 OFFSET %s""", (offset, )
        )
        return cr.fetchone()


    def view_header_get(self, cr, user, view_id, view_type, context=None):
        if context is None:
            context = {}
        context = self.convert_to_period(cr, user, context=context)
        if context.get('account_id', False):
            cr.execute('SELECT code FROM account_account WHERE id = %s', (context['account_id'], ))
            res = cr.fetchone()
            if res:
                res = _('Entries: ')+ (res[0] or '')
            return res
        if (not context.get('journal_id', False)) or (not context.get('period_id', False)):
            return False
        cr.execute('SELECT code FROM account_journal WHERE id = %s', (context['journal_id'], ))
        j = cr.fetchone()[0] or ''
        cr.execute('SELECT code FROM account_period WHERE id = %s', (context['period_id'], ))
        p = cr.fetchone()[0] or ''
        if j or p:
            return j + (p and (':' + p) or '')
        return False

    def onchange_date(self, cr, user, ids, date, context=None):
        """
        Returns a dict that contains new values and context
        @param cr: A database cursor
        @param user: ID of the user currently logged in
        @param date: latest value from user input for field date
        @param args: other arguments
        @param context: context arguments, like lang, time zone
        @return: Returns a dict which contains new values, and context
        """
        res = {}
        if context is None:
            context = {}
        period_pool = self.pool.get('account.period')
        pids = period_pool.search(cr, user, [('date_start','<=',date), ('date_stop','>=',date)])
        if pids:
            res.update({
                'period_id':pids[0]
            })
            context.update({
                'period_id':pids[0]
            })
        return {
            'value':res,
            'context':context,
        }

    def _check_moves(self, cr, uid, context=None):
        # use the first move ever created for this journal and period
        if context is None:
            context = {}
        cr.execute('SELECT id, state, name FROM account_move WHERE journal_id = %s AND period_id = %s ORDER BY id limit 1', (context['journal_id'],context['period_id']))
        res = cr.fetchone()
        if res:
            if res[1] != 'draft':
                raise osv.except_osv(_('UserError'),
                                     _('The account move (%s) for centralisation ' \
                                       'has been confirmed!') % res[2])
        return res

    def _remove_move_reconcile(self, cr, uid, move_ids=None, context=None):
        # Function remove move rencocile ids related with moves
        obj_move_line = self.pool.get('account.move.line')
        obj_move_rec = self.pool.get('account.move.reconcile')
        unlink_ids = []
        if not move_ids:
            return True
        recs = obj_move_line.read(cr, uid, move_ids, ['reconcile_id', 'reconcile_partial_id'])
        full_recs = [x for x in recs if x['reconcile_id']]
        rec_ids = [rec['reconcile_id'][0] for rec in full_recs]
        part_recs = [x for x in recs if x['reconcile_partial_id']]
        part_rec_ids = [rec['reconcile_partial_id'][0] for rec in part_recs]
        unlink_ids += rec_ids
        unlink_ids += part_rec_ids
        if unlink_ids:
            # get all the JIs linked to the same reconciliations
            linked_aml = self.search(cr, uid, ['|',
                                               ('reconcile_id', 'in', unlink_ids),
                                               ('reconcile_partial_id', 'in', unlink_ids)],
                                     order='NO_ORDER', context=context)
            # first update reconciliation/unreconciliation dates and unreconcile_txt for all the JIs of the reconciliations
            for aml in linked_aml:
                obj_move_line.write(cr, uid, aml, {
                    'reconcile_date': False,  # US-533 reset reconcilation date
                    # US-1868 add unreconciliation date and unreconcile number
                    'unreconcile_date': time.strftime('%Y-%m-%d'),
                    'unreconcile_txt': obj_move_line.browse(cr, uid, aml, context=context, fields_to_fetch=['reconcile_txt']).reconcile_txt,
                }, context=context)

            # if full reconcile linked to an invoice, set it as (re-)open
            cr.execute('''
                select distinct(inv.id)
                    from account_invoice inv
                    left join account_move_line move_line on move_line.move_id = inv.move_id
                    where
                        move_line.reconcile_id in %s and
                        move_line.is_counterpart
                ''', (tuple(unlink_ids), )
            )
            inv_ids = [x[0] for x in cr.fetchall()]

            # then delete the account.move.reconciles
            obj_move_rec.unlink(cr, uid, unlink_ids)

            if inv_ids:
                netsvc.LocalService("workflow").trg_validate(uid, 'account.invoice', inv_ids, 'open_test', cr)
        return True

    def check_unlink(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        if not context.get('sync_update_execution'):
            return self._update_check(cr, uid, ids, context)
        # When coming from sync, deletion should be less restrictive.
        for l in self.browse(cr, uid, ids):
            if l.move_id.state != 'draft' and l.state != 'draft' and (not l.journal_id.entry_posted) \
                    and context.get('sync_update_session') != l.move_id.posted_sync_sequence:
                raise osv.except_osv(_('Error !'), _('You can not do this modification on a confirmed entry ! Please note that you can just change some non important fields !'))
            if l.reconcile_id:
                raise osv.except_osv(_('Error !'), _('You can not do this modification on a reconciled entry ! Please note that you can just change some non important fields !'))

    def unlink(self, cr, uid, ids, context=None, check=True):
        if context is None:
            context = {}
        move_obj = self.pool.get('account.move')
        #self._update_check(cr, uid, ids, context)
        self.check_unlink(cr, uid, ids, context)
        result = False
        for line in self.browse(cr, uid, ids, context=context):
            context['journal_id'] = line.journal_id.id
            context['period_id'] = line.period_id.id
            result = super(account_move_line, self).unlink(cr, uid, [line.id], context=context)
            if check:
                move_obj.validate(cr, uid, [line.move_id.id], context=context)
        return result

    def _check_date(self, cr, uid, vals, context=None, check=True):
        if context is None:
            context = {}
        move_obj = self.pool.get('account.move')
        journal_obj = self.pool.get('account.journal')
        period_obj = self.pool.get('account.period')
        journal_id = False
        if 'date' in list(vals.keys()):
            if 'journal_id' in vals and 'journal_id' not in context:
                journal_id = vals['journal_id']
            if 'period_id' in vals and 'period_id' not in context:
                period_id = vals['period_id']
            elif 'journal_id' not in context and 'move_id' in vals:
                if vals.get('move_id', False):
                    m = move_obj.browse(cr, uid, vals['move_id'])
                    journal_id = m.journal_id.id
                    period_id = m.period_id.id
            else:
                journal_id = context.get('journal_id', False)
                period_id = context.get('period_id', False)
            if journal_id:
                journal = journal_obj.browse(cr, uid, journal_id, context=context)
                if journal.allow_date and period_id:
                    period = period_obj.browse(cr, uid, period_id, context=context)
                    if not time.strptime(vals['date'][:10],'%Y-%m-%d') >= time.strptime(period.date_start, '%Y-%m-%d') or not time.strptime(vals['date'][:10], '%Y-%m-%d') <= time.strptime(period.date_stop, '%Y-%m-%d'):
                        raise osv.except_osv(_('Error'),_('The date of your Journal Entry is not in the defined period!'))
        else:
            return True

    def _hook_call_update_check(self, cr, uid, ids, vals, context):
        if ('account_id' in vals) or ('journal_id' in vals) or ('period_id' in vals) or ('move_id' in vals) or ('debit' in vals) or ('credit' in vals) or ('date' in vals):
            self._update_check(cr, uid, ids, context)

    def write(self, cr, uid, ids, vals, context=None, check=True, update_check=True):
        if not ids:
            return True
        if context is None:
            context={}
        move_obj = self.pool.get('account.move')
        account_obj = self.pool.get('account.account')
        journal_obj = self.pool.get('account.journal')
        if vals.get('account_tax_id', False):
            raise osv.except_osv(_('Unable to change tax !'), _('You can not change the tax, you should remove and recreate lines !'))
        self._check_date(cr, uid, vals, context, check)
        if ('account_id' in vals) and not account_obj.read(cr, uid, vals['account_id'], ['active'])['active']:
            raise osv.except_osv(_('Bad account!'), _('You can not use an inactive account!'))
        if update_check:
            self._hook_call_update_check(cr, uid, ids, vals, context)

        todo_date = None
        if vals.get('date', False):
            todo_date = vals['date']
            del vals['date']

        for line in self.browse(cr, uid, ids, context=context):
            ctx = context.copy()
            if ('journal_id' not in ctx):
                if line.move_id:
                    ctx['journal_id'] = line.move_id.journal_id.id
                else:
                    ctx['journal_id'] = line.journal_id.id
            if ('period_id' not in ctx):
                if line.move_id:
                    ctx['period_id'] = line.move_id.period_id.id
                else:
                    ctx['period_id'] = line.period_id.id
            #Check for centralisation
            journal = journal_obj.browse(cr, uid, ctx['journal_id'], context=ctx)
            if journal.centralisation:
                self._check_moves(cr, uid, context=ctx)
        result = super(account_move_line, self).write(cr, uid, ids, vals, context)
        if check:
            done = []
            for line in self.browse(cr, uid, ids):
                if line.move_id.id not in done:
                    done.append(line.move_id.id)
                    move_obj.validate(cr, uid, [line.move_id.id], context)
                    if todo_date:
                        move_obj.write(cr, uid, [line.move_id.id], {'date': todo_date}, context=context)
        self._check_on_ji_big_amounts(cr, uid, ids, context=context)
        return result

    def _hook_check_period_state(self, cr, uid, result=False, context=None, raise_hq_closed=True, *args, **kargs):
        """
        Check period state
        """
        if not result:
            return False
        res = True
        for (state,) in result:
            if state == 'done':
                if raise_hq_closed:
                    raise osv.except_osv(_('Error !'), _('You can not add/modify entries in a closed journal.'))
                res = False
                break
        return res

    def _update_journal_check(self, cr, uid, journal_id, period_id,
                              context=None, raise_hq_closed=True):
        journal_obj = self.pool.get('account.journal')
        period_obj = self.pool.get('account.period')
        jour_period_obj = self.pool.get('account.journal.period')
        cr.execute('SELECT state FROM account_journal_period WHERE journal_id = %s AND period_id = %s', (journal_id, period_id))
        result = cr.fetchall()
        if result:
            res = self._hook_check_period_state(cr, uid, result,
                                                context=context, raise_hq_closed=raise_hq_closed)
        else:
            journal = journal_obj.browse(cr, uid, journal_id, context=context)
            period = period_obj.browse(cr, uid, period_id, context=context)
            jour_period_obj.create(cr, uid, {
                'name': (journal.code or journal.name)+':'+(period.name or ''),
                'journal_id': journal.id,
                'period_id': period.id
            })
            res = True
        return res

    def _update_check(self, cr, uid, ids, context=None):
        done = {}
        for line in self.browse(cr, uid, ids, context=context):
            if line.period_id and line.period_id.is_system:
                continue  # US-822 bypass checks below for period 0/16
            if line.move_id.state != 'draft' and (not line.journal_id.entry_posted):
                raise osv.except_osv(_('Error !'), _('You can not do this modification on a confirmed entry ! Please note that you can just change some non important fields !'))
            if line.reconcile_id:
                raise osv.except_osv(_('Error !'), _('You can not do this modification on a reconciled entry ! Please note that you can just change some non important fields !'))
            t = (line.journal_id.id, line.period_id.id)
            if t not in done:
                self._update_journal_check(cr, uid, line.journal_id.id, line.period_id.id, context)
                done[t] = True
        return True

    def _check_on_ji_big_amounts(self, cr, uid, ids, context=None):
        """
        Prevents booking amounts having more than 10 digits before the comma, i.e. amounts starting from 10 billions.
        The goal is to avoid losing precision, see e.g.: "%s" % 10000000000.01  # '10000000000.0'
        (and to avoid decimal.InvalidOperation due to huge amounts).
        Checks are done only on user manual actions.
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        too_big_amount = 10**10
        if context.get('from_web_menu') or context.get('from_je_import') or context.get('from_invoice_move_creation'):
            aml_fields = ['debit_currency', 'credit_currency', 'amount_currency', 'name']
            for aml in self.browse(cr, uid, ids, fields_to_fetch=aml_fields, context=context):
                booking_amount = aml.debit_currency or aml.credit_currency or aml.amount_currency or 0.0
                if abs(booking_amount) >= too_big_amount:
                    raise osv.except_osv(_('Error'), _('The amount of the line "%s" is more than 10 digits.') % aml.name)

    def create(self, cr, uid, vals, context=None, check=True):
        account_obj = self.pool.get('account.account')
        tax_obj = self.pool.get('account.tax')
        move_obj = self.pool.get('account.move')
        journal_obj = self.pool.get('account.journal')
        invoice_line_obj = self.pool.get('account.invoice.line')
        if context is None:
            context = {}
        move_date = False
        if vals.get('move_id', False):
            move_data = self.pool.get('account.move').read(cr, uid, vals['move_id'], ['company_id', 'date'])
            if move_data.get('company_id'):
                vals['company_id'] = move_data['company_id'][0]
            move_date = move_data.get('date')
            if not vals.get('date') and move_date:
                vals['date'] = move_date

        self._check_date(cr, uid, vals, context, check)
        if ('account_id' in vals) and not account_obj.read(cr, uid, vals['account_id'], ['active'])['active']:
            raise osv.except_osv(_('Bad account!'), _('You can not use an inactive account!'))
        if 'journal_id' in vals:
            context['journal_id'] = vals['journal_id']
        if 'period_id' in vals:
            context['period_id'] = vals['period_id']
        if ('journal_id' not in context) and ('move_id' in vals) and vals['move_id']:
            m = move_obj.browse(cr, uid, vals['move_id'])
            context['journal_id'] = m.journal_id.id
            context['period_id'] = m.period_id.id

        self._update_journal_check(cr, uid, context['journal_id'], context['period_id'], context)
        move_id = vals.get('move_id', False)
        journal = journal_obj.browse(cr, uid, context['journal_id'], context=context)
        if not move_id:
            if journal.centralisation:
                #Check for centralisation
                res = self._check_moves(cr, uid, context)
                if res:
                    vals['move_id'] = res[0]
            if not vals.get('move_id', False):
                if journal.sequence_id:
                    #name = self.pool.get('ir.sequence').get_id(cr, uid, journal.sequence_id.id)
                    v = {
                        'date': vals.get('date', time.strftime('%Y-%m-%d')),
                        'period_id': context['period_id'],
                        'journal_id': context['journal_id']
                    }
                    if vals.get('ref', ''):
                        v.update({'ref': vals['ref']})
                    move_id = move_obj.create(cr, uid, v, context)
                    vals['move_id'] = move_id
                else:
                    raise osv.except_osv(_('No piece number !'), _('Can not create an automatic sequence for this piece !\n\nPut a sequence in the journal definition for automatic numbering or create a sequence manually for this piece.'))
        ok = not (journal.type_control_ids or journal.account_control_ids)
        if ('account_id' in vals):
            account = account_obj.browse(cr, uid, vals['account_id'], context=context)
            if journal.type_control_ids:
                type = account.user_type
                for t in journal.type_control_ids:
                    if type.code == t.code:
                        ok = True
                        break
            if journal.account_control_ids and not ok:
                for a in journal.account_control_ids:
                    if a.id == vals['account_id']:
                        ok = True
                        break
        if not ok:
            raise osv.except_osv(_('Bad account !'), _('You can not use this general account in this journal !'))

        if vals.get('analytic_account_id',False):
            if journal.analytic_journal_id:
                vals['analytic_lines'] = [(0,0, {
                    'name': vals['name'],
                    'date': vals.get('date', time.strftime('%Y-%m-%d')),
                    'account_id': vals.get('analytic_account_id', False),
                    'unit_amount': vals.get('quantity', 1.0),
                    'amount': vals.get('debit', 0.0) or vals.get('credit', 0.0),
                    'general_account_id': vals.get('account_id', False),
                    'journal_id': journal.analytic_journal_id.id,
                    'ref': vals.get('ref', False),
                    'user_id': uid
                })]

        # update the reversal in case of a refund cancel/modify
        if vals.get('invoice_line_id', False):
            inv_line = invoice_line_obj.browse(cr, uid, vals['invoice_line_id'],
                                               fields_to_fetch=['reversed_invoice_line_id'], context=context)
            if inv_line.reversed_invoice_line_id:
                vals['reversal'] = True
                reversed_amls = invoice_line_obj.browse(cr, uid, inv_line.reversed_invoice_line_id.id,
                                                        fields_to_fetch=['move_lines'], context=context).move_lines
                vals['reversal_line_id'] = reversed_amls and reversed_amls[0].id or False

        result = super(osv.osv, self).create(cr, uid, vals, context=context)
        # CREATE Taxes
        if vals.get('account_tax_id', False):
            tax_id = tax_obj.browse(cr, uid, vals['account_tax_id'])
            total = vals['debit'] - vals['credit']
            if journal.refund_journal:
                base_code = 'ref_base_code_id'
                tax_code = 'ref_tax_code_id'
                account_id = 'account_paid_id'
                base_sign = 'ref_base_sign'
                tax_sign = 'ref_tax_sign'
            else:
                base_code = 'base_code_id'
                tax_code = 'tax_code_id'
                account_id = 'account_collected_id'
                base_sign = 'base_sign'
                tax_sign = 'tax_sign'
            tmp_cnt = 0
            for tax in tax_obj.compute_all(cr, uid, [tax_id], total, 1.00).get('taxes'):
                #create the base movement
                if tmp_cnt == 0:
                    if tax[base_code]:
                        tmp_cnt += 1
                        self.write(cr, uid,[result], {
                            'tax_code_id': tax[base_code],
                            'tax_amount': tax[base_sign] * abs(total)
                        })
                else:
                    data = {
                        'move_id': vals['move_id'],
                        'journal_id': vals['journal_id'],
                        'period_id': vals['period_id'],
                        'name': tools.ustr(vals['name'] or '') + ' ' + tools.ustr(tax['name'] or ''),
                        'date': vals['date'],
                        'partner_id': vals.get('partner_id',False),
                        'ref': vals.get('ref',False),
                        'account_tax_id': False,
                        'tax_code_id': tax[base_code],
                        'tax_amount': tax[base_sign] * abs(total),
                        'account_id': vals['account_id'],
                        'credit': 0.0,
                        'debit': 0.0,
                    }
                    if data['tax_code_id']:
                        self.create(cr, uid, data, context)
                #create the VAT movement
                data = {
                    'move_id': vals['move_id'],
                    'journal_id': vals['journal_id'],
                    'period_id': vals['period_id'],
                    'name': tools.ustr(vals['name'] or '') + ' ' + tools.ustr(tax['name'] or ''),
                    'date': vals['date'],
                    'partner_id': vals.get('partner_id',False),
                    'ref': vals.get('ref',False),
                    'account_tax_id': False,
                    'tax_code_id': tax[tax_code],
                    'tax_amount': tax[tax_sign] * abs(tax['amount']),
                    'account_id': tax[account_id] or vals['account_id'],
                    'credit': tax['amount']<0 and -tax['amount'] or 0.0,
                    'debit': tax['amount']>0 and tax['amount'] or 0.0,
                }
                if data['tax_code_id']:
                    self.create(cr, uid, data, context)
            del vals['account_tax_id']

        if check and ((not context.get('no_store_function')) or journal.entry_posted):
            tmp = move_obj.validate(cr, uid, [vals['move_id']], context)
            if vals.get('date') and vals.get('date') != move_date:
                move_obj.write(cr, uid, [vals['move_id']], {'date': vals.get('date')}, context)
            if journal.entry_posted and tmp:
                move_obj.button_validate(cr,uid, [vals['move_id']], context)
        self._check_on_ji_big_amounts(cr, uid, result, context=context)
        return result

    def get_related_entry_ids(self, cr, uid, ids=False, entry_seqs=None, context=None):
        """
        Returns the ids of all the JIs related to the selected JIs and/or Entry Sequences (list), i.e.:
        1) those having the same Entry Sequence as the selected JIs (including the selected JIs themselves)
        2) those having the same reference as one of the JIs found in 1)
        3) those having an Entry Sequence matching exactly with the reference of one of the JIs found in 1)
        4) those being partially or totally reconciled with one of the JIs found in 1)
        5) those whose reference contains EXACTLY the Entry Sequence of one of the selected JIs
        6) those having the same Entry Sequence as one of the JIs found in 2), 3) 4) or 5)
        """
        if context is None:
            context = {}
        if entry_seqs is None:
            entry_seqs = []
        am_obj = self.pool.get('account.move')
        related_amls = set()
        account_move_ids = []
        if entry_seqs:
            account_move_ids = am_obj.search(cr, uid, [('name', 'in', entry_seqs)], order='NO_ORDER', context=context) or []
        if ids:
            if isinstance(ids, int):
                ids = [ids]
            selected_amls = self.browse(cr, uid, ids, fields_to_fetch=['move_id'], context=context)
            for selected_aml in selected_amls:
                account_move_ids.append(selected_aml.move_id.id)
                entry_seqs.append(selected_aml.move_id.name)
        if account_move_ids and entry_seqs:
            # get the ids of all the related JIs
            account_move_ids = list(set(account_move_ids))
            entry_seqs = list(set(entry_seqs))
            # JIs having the same Entry Seq = JIs of the same JE
            same_seq_ji_ids = self.search(cr, uid, [('move_id', 'in', account_move_ids)], order='NO_ORDER', context=context)
            related_amls.update(same_seq_ji_ids)

            # check on ref and reconciliation
            set_of_refs = set()
            set_of_reconcile_ids = set()
            for aml in self.browse(cr, uid, same_seq_ji_ids,
                                   fields_to_fetch=['ref', 'reconcile_id', 'reconcile_partial_id'], context=context):
                aml.ref and set_of_refs.add(aml.ref)
                aml.reconcile_id and set_of_reconcile_ids.add(aml.reconcile_id.id)
                aml.reconcile_partial_id and set_of_reconcile_ids.add(aml.reconcile_partial_id.id)

            # JEs with Entry Sequence = ref of one of the JIs of the account_move
            je_ids = am_obj.search(cr, uid, [('name', 'in', list(set_of_refs))], order='NO_ORDER', context=context)

            domain_related_jis = ['|', '|', '|', '|',
                                  '&', ('ref', 'in', list(set_of_refs)), ('ref', '!=', ''),
                                  ('ref', 'in', entry_seqs),
                                  ('move_id', 'in', je_ids),
                                  ('reconcile_id', 'in', list(set_of_reconcile_ids)),
                                  ('reconcile_partial_id', 'in', list(set_of_reconcile_ids))]
            related_ji_ids = self.search(cr, uid, domain_related_jis, order='NO_ORDER', context=context)
            related_amls.update(related_ji_ids)

            # check on Entry Seq. (compared with those of the related JIs found)
            seq_je_ids = set(am.move_id.id for am in self.browse(cr, uid, related_ji_ids, fields_to_fetch=['move_id'], context=context))
            same_seq_related_ji_ids = self.search(cr, uid, [('move_id', 'in', list(seq_je_ids))], order='NO_ORDER', context=context)
            related_amls.update(same_seq_related_ji_ids)
        return list(related_amls)

    def get_related_entries(self, cr, uid, ids, context=None):
        """
        Returns a JI view with all the JIs related to the selected one (see get_related_entry_ids for details)
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        active_ids = context.get('active_ids', [])  # to detect if the user has selected several JIs
        if len(ids) != 1 or len(active_ids) > 1:
            raise osv.except_osv(_('Error'),
                                 _('The related entries feature can only be used with one Journal Item.'))
        ir_model_obj = self.pool.get('ir.model.data')
        selected_entry_seq = self.browse(cr, uid, ids[0], fields_to_fetch=['move_id'], context=context).move_id.name
        related_entry_ids = self.get_related_entry_ids(cr, uid, ids=ids, context=context)
        domain = [('id', 'in', related_entry_ids)]
        search_view_id = ir_model_obj.get_object_reference(cr, uid, 'account_mcdb', 'mcdb_view_account_move_line_filter')
        search_view_id = search_view_id and search_view_id[1] or False
        return {
            'name': _('Related entries: Entry Sequence %s') % selected_entry_seq,
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'search_view_id': [search_view_id],
            'context': context,
            'domain': domain,
            'target': 'current',
        }

account_move_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
