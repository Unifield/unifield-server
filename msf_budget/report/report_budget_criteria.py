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
import StringIO
import pooler

class report_budget_criteria(report_sxw.report_sxw):
    _name = 'report.budget.criteria'
    
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)
    
    def _get_budget_header(self, cr, uid, budget, parameters, context={}):
        pool = pooler.get_pool(cr.dbname)
        # Dictionary for selection
        wizard_obj = pool.get('wizard.budget.criteria.export')
        breakdown_selection = dict(wizard_obj._columns['breakdown'].selection)
        granularity_selection = dict(wizard_obj._columns['granularity'].selection)
        result =  [['Budget name:', budget.name],
                   ['Budget code:', budget.code],
                   ['Fiscal year:', budget.fiscalyear_id.name],
                   ['Cost center:', budget.cost_center_id.name],
                   ['Decision moment:', budget.decision_moment],
                   ['Version:', budget.version],
                   ['Commitments:', parameters['commitment'] and 'Included' or 'Excluded'],
                   ['Breakdown:', breakdown_selection[parameters['breakdown']]],
                   ['Granularity:', granularity_selection[parameters['granularity']]]]
        if 'currency_table_id' in parameters:
            currency_table = pool.get('res.currency.table').browse(cr,
                                                                   uid,
                                                                   parameters['currency_table_id'],
                                                                   context=context)
            result.append(['Currency table:', currency_table.name])
        if 'period_id' in parameters:
            period = pool.get('account.period').browse(cr,
                                                       uid,
                                                       parameters['period_id'],
                                                       context=context)
            result.append(['Year-to-date:', period.name])
        return result
    
    def _get_budget_lines(self, cr, uid, budget_line_ids, parameters, context={}):
        pool = pooler.get_pool(cr.dbname)
        result = []
        # Column header
        month_stop = 12
        header = ['Account']
        # check if month detail is needed
        if 'breakdown' in parameters and parameters['breakdown'] == 'month':
            month_list = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
            if 'period_id' in parameters:
                period = pool.get('account.period').browse(cr, uid, parameters['period_id'], context=context)
                month_stop = datetime.datetime.strptime(period.date_stop, '%Y-%m-%d').month
            for month in range(month_stop):
                header.append(month_list[month] + ' (Budget)')
                header.append(month_list[month] + ' (Actual)')
        header += ['Total (Budget)', 'Total (Actual)']
        result.append(header)
        # Update context
        context.update(parameters)
        # Retrieve lines
        result += pool.get('msf.budget.line')._get_monthly_amounts(cr,
                                                                   uid,
                                                                   budget_line_ids,
                                                                   context=context)
        return result
    
    def create(self, cr, uid, ids, data, context=None):
        pool = pooler.get_pool(cr.dbname)
        budget = pool.get('msf.budget').browse(cr, uid, context['active_id'], context=context)
        budget_line_ids = pool.get('msf.budget.line').search(cr, uid, [('budget_id', '=', context['active_id'])], context=context)
        header_data = self._get_budget_header(cr, uid, budget, data['form'], context)
        budget_line_data = self._get_budget_lines(cr, uid, budget_line_ids, data['form'], context)
        data = header_data + [['']] + budget_line_data
        
        buffer = StringIO.StringIO()
        writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
        for line in data:
            writer.writerow(line)
        out = buffer.getvalue()
        buffer.close()
        return (out, 'csv')
    
report_budget_criteria('report.msf.budget.criteria', 'msf.budget', False, parser=False)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: