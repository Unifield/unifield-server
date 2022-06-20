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
import pooler
from report_webkit.webkit_report import WebKitParser
import xml.sax.saxutils
from tools.translate import _


class report_local_expenses(WebKitParser):
    _name = 'report.local.expenses'

    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header= " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(report_local_expenses, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def create(self, cr, uid, ids, data, context=None):
        pool = pooler.get_pool(cr.dbname)
        # fill domain for lines, depending on the data['form']
        # Exclude unwanted journals (HQ, Engagement, Donation)
        bad_journal_ids = pool.get('account.analytic.journal').search(cr,
                                                                      uid,
                                                                      [('type', 'in', ['hq','engagement','donation'])],
                                                                      context=context)
        # UTP-944: As we can have other account than 6, we need to restrict Local expenses to only expenses accounts !
        domain = [('journal_id', 'not in', bad_journal_ids), ('general_account_id.user_type_code', '=', 'expense'), ('general_account_id.user_type_report_type', '!=', 'none')]
        if 'form' in data:
            # general variables
            wizard_obj = pool.get('wizard.local.expenses')
            currency_obj = pool.get('res.currency')
            breakdown_selection = dict(wizard_obj._columns['breakdown'].selection)
            granularity_selection = dict(wizard_obj._columns['granularity'].selection)
            result_data = []
            header_data = [[_('Local expenses report')],
                           [_('Breakdown:'), breakdown_selection[data['form']['breakdown']]],
                           [_('Granularity:'), granularity_selection[data['form']['granularity']]]]
            month_start = data['form']['month_start']
            month_stop = data['form']['month_stop']
            # Booking currency
            if 'booking_currency_id' in data['form']:
                domain.append(('currency_id', '=', data['form']['booking_currency_id']))
                booking_currency = currency_obj.browse(cr, uid, data['form']['booking_currency_id'], context=context)
                # Add booking currency to header
                header_data.append([_('Booking currency:'), booking_currency.name])

            # Add output currency to header
            output_currency = currency_obj.browse(cr, uid, data['form']['output_currency_id'], context=context)
            header_data.append([_('Output currency:'), output_currency.name])
            # Cost Center
            cost_center = pool.get('account.analytic.account').browse(cr, uid, data['form']['cost_center_id'], context=context)
            cost_center_ids = pool.get('msf.budget.tools')._get_cost_center_ids(cr, uid, cost_center)
            domain.append(('cost_center_id', 'in', cost_center_ids))
            # Add cost center to header
            header_data.append([_('Cost center:'), cost_center.name])
            # Dates
            fiscalyear = pool.get('account.fiscalyear').browse(cr, uid, data['form']['fiscalyear_id'], context=context)
            domain.append(('date', '>=', fiscalyear.date_start))
            domain.append(('date', '<=', fiscalyear.date_stop))
            # add fiscal year to header
            header_data.append([_('Fiscal year:'), fiscalyear.name])
            # Period name for header
            if 'start_period_id' in data['form']:
                period = pool.get('account.period').browse(cr,
                                                           uid,
                                                           data['form']['start_period_id'],
                                                           context=context)
                header_data.append([_('Period from:'), period.name])
                domain.append(('date', '>=', period.date_start))
            if 'end_period_id' in data['form']:
                period = pool.get('account.period').browse(cr,
                                                           uid,
                                                           data['form']['end_period_id'],
                                                           context=context)
                header_data.append([_('Period to:'), period.name])
                domain.append(('date', '<=', period.date_stop))
            # Get expenses. UTP-944: break down the _get_actual_amounts method to only return expense accounts and not income or donation accounts (extra-accounting accounts)
            context.update({'only_expenses': True})
            expenses = pool.get('msf.budget.tools')._get_actual_amounts(cr,
                                                                        uid,
                                                                        data['form']['output_currency_id'],
                                                                        domain,
                                                                        context=context)
            # we only save the main accounts, not the destinations (new key: account id only)
            expenses = dict([(item[0], expenses[item]) for item in expenses.keys() if item[1] is False])

            # make the total row
            if 'breakdown' in data['form'] and data['form']['breakdown'] == 'month':
                total_line = [0] * (month_stop - month_start + 1)
            else:
                total_line = []
            total_amount = 0
            # Search the chart of account account (those that have no parent_id
            parent_view_id = pool.get('account.account').search(cr, uid, [('parent_id', '=', False)])

            account_list = pool.get('account.account').browse(cr, uid, expenses.keys(), context=context)

            # sorting by account code in ALPHABETICAL order, i.e. 60, 600, 60000, 60010, (...) 601, 60100, 60110, etc.
            for expense_account in sorted(account_list, key=lambda x: x.code):
                expense_values = expenses[expense_account.id][month_start - 1:month_stop]
                if expense_account.type != 'view':
                    total_amount += sum(expense_values)
                    total_line = [sum(pair) for pair in zip(expense_values, total_line)]
                # add line to result (code, name)...
                if expense_account.type == 'view' or data['form']['granularity'] == 'all': # Add all view lines and only expenses one if user asked for it (granularity == 'by account'
                    # search if this account have a parent view that is not "parent_view_id"
                    is_under_the_big_one = False
                    if expense_account.parent_id and expense_account.parent_id.id in parent_view_id:
                        is_under_the_big_one = True
                    # If not under the Chart of account view account, then display it
                    if not is_under_the_big_one:
                        line = [expense_account.type, expense_account.code, xml.sax.saxutils.escape(expense_account.name)]
                        # ...monthly amounts, ...
                        if 'breakdown' in data['form'] and data['form']['breakdown'] == 'month':
                            line += expense_values
                        # ...and the total.
                        line += [sum(expense_values)]
                        # append to result
                        result_data.append(line)
            # Format total
            total_line = [_('Total'), ''] + total_line + [total_amount]

            data['form']['header'] = header_data
            data['form']['report_lines'] = result_data
            data['form']['total_line'] = total_line

        a = super(report_local_expenses, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')

report_local_expenses('report.local.expenses','account.analytic.line','addons/msf_budget/report/report_local_expenses_xls.mako')
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
