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
import datetime
from tools.translate import _
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport

class report_budget_criteria(report_sxw.report_sxw):
    _name = 'report.budget.criteria'
    
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)
    
    def _get_budget_header(self, cr, uid, budget, parameters, context=None):
        pool = pooler.get_pool(cr.dbname)
        # Dictionary for selection
        wizard_obj = pool.get('wizard.budget.criteria.export')
        breakdown_selection = dict(wizard_obj._columns['breakdown'].selection)
        granularity_selection = dict(wizard_obj._columns['granularity'].selection)
        result =  [['Budget name:', budget.name],
                   ['Budget code:', budget.code],
                   ['Fiscal year:', budget.fiscalyear_id.name],
                   ['Cost center:', budget.cost_center_id.name],
                   ['Decision moment:', budget.decision_moment_id.name],
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
    
    def _get_budget_lines(self, cr, uid, budget_line_ids, parameters, context=None):
        if context is None:
            context = {}
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
        formatted_monthly_amounts = []
        monthly_amounts = pool.get('msf.budget.line')._get_monthly_amounts(cr,
                                                                           uid,
                                                                           budget_line_ids,
                                                                           context=context)
        for amount_line in monthly_amounts:
            formatted_amount_line = [amount_line[0]]
            formatted_amount_line += [locale.format("%d", amount, grouping=True) for amount in amount_line[1:]]
            formatted_monthly_amounts.append(formatted_amount_line)
        result += formatted_monthly_amounts
        return result
    
    def _enc(self, st):
        if isinstance(st, unicode):
            return st.encode('utf8')
        return st
    
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
            writer.writerow(map(self._enc,line))
        out = buffer.getvalue()
        buffer.close()
        return (out, 'csv')

report_budget_criteria('report.msf.budget.criteria', 'msf.budget', False, parser=False)

    

class report_budget_actual_2(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(report_budget_actual_2, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'getLines': self.getLines,
            'byMonth': self.byMonth,
            'isComm': self.isComm,
            'getBreak': self.getBreak,
            'getComm': self.getComm,
            'getF1': self.getF1,
            'getF2': self.getF2,
            'getGranularity': self.getGranularity,
            'getEndMonth': self.getEndMonth,
        })
        return

    def getF2(self,line):
        if int(line[1]) == 0:
            return ''
        return '=(+RC[-2])/RC[-3]'

    def getF1(self,line):
        if int(line[1]) == 0:
            return ''
        return '=(RC[-3]+RC[-2])/RC[-4]'

    def getComm(self,):
        parameters = self.localcontext.get('data',{}).get('form',{})
        if 'commitment' in parameters and parameters['commitment']:
            return 'Yes'
        return 'No'

    def getBreak(self,):
        parameters = self.localcontext.get('data',{}).get('form',{})
        if 'breakdown' in parameters and parameters['breakdown'] == 'year':
            return 'Total figure'
        return 'By month'

    def byMonth(self,):
        parameters = self.localcontext.get('data',{}).get('form',{})
        if 'breakdown' in parameters and parameters['breakdown'] == 'month':
            return True
        return False

    def isComm(self,):
        parameters = self.localcontext.get('data',{}).get('form',{})
        if 'commitment' in parameters and parameters['commitment']:
            return True
        return False

    def getGranularity(self,):
        res = ''
        parameters = self.localcontext.get('data', {}).get('form', {})
        if 'granularity' in parameters and parameters['granularity']:
            g = parameters['granularity']
            if g == 'all':
                res = _('Expenses and destinations')
            elif g == 'expense':
                res = _('Expenses')
            elif g == 'parent':
                res = _('Parent Expenses only')
        return res

    def getEndMonth(self, context=None):
        """
        Get number of last month. by default 12.
        """
        if not context:
            context = {}
        parameters = self.localcontext.get('data',{}).get('form',{})
        res = 12
        if 'period_id' in parameters:
            period = self.pool.get('account.period').browse(self.cr, self.uid, parameters['period_id'], context=context)
            res = datetime.datetime.strptime(period.date_stop, '%Y-%m-%d').month
        return res

    def getLines(self, lines, context=None):
        budget_line_ids = [x.id for x in lines]
        parameters = self.localcontext.get('data',{}).get('form',{})
        if not context:
            context = {}
        result = []
        # Column header
        month_stop = self.getEndMonth()
        header = ['Account']
        # check if month detail is needed
        if 'breakdown' in parameters and parameters['breakdown'] == 'month':
            month_list = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
            for month in range(month_stop):
                header.append(month_list[month] + ' (Budget)')
                header.append(month_list[month] + ' (Actual)')
        header += ['Total (Budget)', 'Total (Actual)']
        result.append(header)
        # Update context
        context.update(parameters)
        # Retrieve lines
        formatted_monthly_amounts = []
        monthly_amounts = self.pool.get('msf.budget.line')._get_monthly_amounts(self.cr,
                                                                           self.uid,
                                                                           budget_line_ids,
                                                                           context=context)

        result += monthly_amounts
        return result[1:]

SpreadsheetReport('report.budget.criteria.2','msf.budget','addons/msf_budget/report/budget_criteria_xls.mako', parser=report_budget_actual_2)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
