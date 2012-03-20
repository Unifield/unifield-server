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
import locale

class report_csv_budget_monthly(report_sxw.report_sxw):
    _name = 'report.csv.budget.monthly'
    
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)
    
    def _get_budget_header(self, budget):
        result =  [['Budget name:', budget.name],
                   ['Budget code:', budget.code],
                   ['Fiscal year:', budget.fiscalyear_id.name],
                   ['Cost center:', budget.cost_center_id.name],
                   ['Decision moment:', budget.decision_moment],
                   ['Version:', budget.version],
                   [],
                   ['Account','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec','Total']]
        return result
    
    def _get_budget_lines(self, cr, uid, budget, context={}):
        pool = pooler.get_pool(cr.dbname)
        result = []
        # Parse each budget line
        budget_line_ids = [budget_line.id for budget_line in budget.budget_line_ids]
        
        budget_amounts = pool.get('msf.budget.line')._get_budget_amounts(cr, uid, budget_line_ids, context=context)
        
        for budget_line in budget.budget_line_ids:
            budget_amount = budget_amounts[budget_line.account_id.id]
            total = locale.format("%d", sum(budget_amount), grouping=True)
            formatted_budget_values = [locale.format("%d", x, grouping=True) for x in budget_amount]
            csv_budget_line = [budget_line.account_id.code + " " + budget_line.account_id.name]
            csv_budget_line += formatted_budget_values
            csv_budget_line.append(total)
            # append to result
            result.append(csv_budget_line)
        return result
    
    def _enc(self, st):
        if isinstance(st, unicode):
            return st.encode('utf8')
        return st
    
    def create(self, cr, uid, ids, data, context=None):
        pool = pooler.get_pool(cr.dbname)
        if len(ids) > 0:
            budget = pool.get('msf.budget').browse(cr, uid, ids[0], context=context)
            header_data = self._get_budget_header(budget)
            budget_line_data = self._get_budget_lines(cr, uid, budget, context=context)
            data = header_data + budget_line_data
        
        buffer = StringIO.StringIO()
        writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
        for line in data:
            writer.writerow(map(self._enc,line))
        out = buffer.getvalue()
        buffer.close()
        return (out, 'csv')
    
report_csv_budget_monthly('report.msf.csv.budget.monthly', 'msf.budget', False, parser=False)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: