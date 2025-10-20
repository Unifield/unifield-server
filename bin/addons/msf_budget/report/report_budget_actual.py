# encoding: utf-8
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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
from report import report_sxw
import csv
import io
import pooler
import locale
import datetime
from tools.translate import _

class report_budget_actual(report_sxw.report_sxw):
    _name = 'report.budget.actual'

    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def _get_lines(self, cr, uid, cost_center_id, parameters, context=None):
        if context is None:
            context = {}
        pool = pooler.get_pool(cr.dbname)
        result = []
        temp_result = []
        # Header data
        fiscalyear_id = pool.get('account.fiscalyear').find(cr, uid, datetime.datetime.now().strftime('%Y-%m-%d'), False, context=context)
        if fiscalyear_id:
            fiscalyear = pool.get('account.fiscalyear').browse(cr, uid, fiscalyear_id, context=context)
            cost_center = pool.get('account.analytic.account').browse(cr, uid, cost_center_id, context=context)
            functional_currency_id = pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id

            result =  [[_('Fiscal year:'), fiscalyear.name],
                       [_('Cost center name:'), cost_center.name],
                       [_('Cost center code:'), cost_center.code]]
            if 'currency_table_id' in parameters:
                currency_table = pool.get('res.currency.table').browse(cr,
                                                                       uid,
                                                                       parameters['currency_table_id'],
                                                                       context=context)
                result.append([_('Currency table:'), currency_table.name])
            result.append([_('Report date:'), datetime.datetime.now().strftime("%d/%b/%Y %H:%M")])
            result.append([''])

            # Column header
            header = [_('Account'),_('Jan'),_('Feb'),_('Mar'),_('Apr'),_('May'),_('Jun'),_('Jul'),_('Aug'),_('Sep'),_('Oct'),_('Nov'),_('Dec'),_('Total actual'), _('Total engagement'), _('Total accrual'), _('Total')]
            result.append(header)

            # journal domains
            engagement_journal_ids = pool.get('account.analytic.journal').search(cr, uid, [('type', '=', 'engagement')], context=context)
            accrual_journal_ids = pool.get('account.analytic.journal').search(cr, uid, [('code', '=', 'AC')], context=context)
            engagement_domain = [('journal_id', 'in', engagement_journal_ids)]
            accrual_domain = [('journal_id', 'in', accrual_journal_ids)]
            actual_domain = [('journal_id', 'not in', engagement_journal_ids + accrual_journal_ids)]

            # Cost Center
            cost_center_ids = pool.get('msf.budget.tools')._get_cost_center_ids(cr, uid, cost_center)
            general_domain = [('cost_center_id', 'in', cost_center_ids)]
            # Dates
            general_domain.append(('date', '>=', fiscalyear.date_start))
            general_domain.append(('date', '<=', fiscalyear.date_stop))
            # Update context with currency table
            context.update(parameters)
            # Get actual expenses
            actual_expenses = pool.get('msf.budget.tools')._get_actual_amounts(cr,
                                                                               uid,
                                                                               functional_currency_id,
                                                                               general_domain + actual_domain,
                                                                               context=context)
            # and only keep the main accounts, not the destinations (new key: account id only)
            actual_expenses = dict([(item[0], actual_expenses[item] + [sum(actual_expenses[item])]) for item in list(actual_expenses.keys()) if item[1] is False])

            # Get engagement expenses
            engagement_expenses = pool.get('msf.budget.tools')._get_actual_amounts(cr,
                                                                                   uid,
                                                                                   functional_currency_id,
                                                                                   general_domain + engagement_domain,
                                                                                   context=context)
            # and only keep the main accounts and the sum, not the destinations (new key: account id only)
            engagement_expenses = dict([(item[0], sum(engagement_expenses[item])) for item in list(engagement_expenses.keys()) if item[1] is False])

            # Get accrual expenses
            accrual_expenses = pool.get('msf.budget.tools')._get_actual_amounts(cr,
                                                                                uid,
                                                                                functional_currency_id,
                                                                                general_domain + accrual_domain,
                                                                                context=context)
            # and only keep the main accounts and the sum, not the destinations (new key: account id only)
            accrual_expenses = dict([(item[0], sum(accrual_expenses[item])) for item in list(accrual_expenses.keys()) if item[1] is False])


            for expense_account in pool.get('account.account').browse(cr, uid, list(actual_expenses.keys()), context=context):
                rounded_values = list(map(int, list(map(round, actual_expenses[expense_account.id]))))
                # add line to result (code, name)...
                line = [expense_account.code + " " + expense_account.name]
                # ...monthly actual amounts and total, ...
                line += rounded_values
                # ...engagement total, ...
                line += [int(round(engagement_expenses[expense_account.id]))]
                # ...accrual total, ...
                line += [int(round(accrual_expenses[expense_account.id]))]
                # ...and the grand total.
                line += [int(round(actual_expenses[expense_account.id][-1] + engagement_expenses[expense_account.id] + accrual_expenses[expense_account.id]))]
                # append to result
                temp_result.append(line)

            formatted_monthly_amounts = []
            for amount_line in temp_result:
                formatted_amount_line = [amount_line[0]]
                formatted_amount_line += [locale.format_string("%d", amount, grouping=True) for amount in amount_line[1:]]
                formatted_monthly_amounts.append(formatted_amount_line)
            result += formatted_monthly_amounts
        return result

    def _enc(self, st):
        return st

    def create(self, cr, uid, ids, data, context=None):
        export_data = []
        for cost_center_id in data['form']['cost_center_ids']:
            line_data = self._get_lines(cr, uid, cost_center_id, data['form'], context)
            export_data += line_data
            export_data += [[''], ['']]

        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_ALL)
        for line in export_data:
            writer.writerow(list(map(self._enc,line)))
        out = output.getvalue()
        output.close()
        return (out, 'csv')

report_budget_actual('report.msf.budget.actual', 'msf.budget', False, parser=False)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
