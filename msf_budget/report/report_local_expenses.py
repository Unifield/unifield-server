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
from osv import osv
import pooler
from report_webkit.webkit_report import WebKitParser
import xml.sax.saxutils

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
        domain = [('journal_id', 'not in', bad_journal_ids)]
        if 'form' in data:
            # general variables
            result_data = []
            month_stop = data['form']['month_stop']
            # Booking currency
            if 'booking_currency_id' in data['form']:
                domain.append(('currency_id', '=', data['form']['booking_currency_id']))
            # Cost Center
            cost_center = pool.get('account.analytic.account').browse(cr, uid, data['form']['cost_center_id'], context=context)
            cost_center_ids = pool.get('msf.budget.tools')._get_cost_center_ids(cost_center)
            domain.append(('account_id', 'in', cost_center_ids))
            # Dates
            fiscalyear = pool.get('account.fiscalyear').browse(cr, uid, data['form']['fiscalyear_id'], context=context)
            domain.append(('date', '>=', fiscalyear.date_start))
            domain.append(('date', '<=', fiscalyear.date_stop))
            # Get expenses
            expenses = pool.get('msf.budget.tools')._get_actual_amounts(cr,
                                                                        uid,
                                                                        data['form']['output_currency_id'],
                                                                        domain,
                                                                        context=context)
            # make the total row
            if 'breakdown' in data['form'] and data['form']['breakdown'] == 'month':
                total_line = [0] * month_stop
            else:
                total_line = []
            total_amount = 0
            for expense_account in pool.get('account.account').browse(cr, uid, expenses.keys(), context=context):
                rounded_values = map(int, map(round, expenses[expense_account.id][0:month_stop]))
                # add line to result (code, name)...
                if expense_account.type == 'view' or data['form']['granularity'] == 'all':
                    line = [expense_account.code, xml.sax.saxutils.escape(expense_account.name)]
                    # ...monthly amounts, ...
                    if 'breakdown' in data['form'] and data['form']['breakdown'] == 'month':
                        line += rounded_values
                    # ...and the total.
                    line += [sum(rounded_values)]
                    # append to result
                    result_data.append(line)
                if expense_account.type != 'view':
                    # add to the total
                    total_line = [sum(pair) for pair in zip(rounded_values, total_line)]
                    total_amount += sum(rounded_values)
            # Format total
            total_line = ['Total', ''] + total_line + [total_amount]
            data['form']['report_lines'] = result_data
            data['form']['total_line'] = total_line
                
        a = super(report_local_expenses, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')
    
report_local_expenses('report.local.expenses','account.analytic.line','addons/msf_budget/report/report_local_expenses_xls.mako')
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
