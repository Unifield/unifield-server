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

class report_budget_actual_2(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(report_budget_actual_2, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'getMonthAllocation': self.getMonthAllocation,
            'byMonth': self.byMonth,
            'isComm': self.isComm,
            'getBreak': self.getBreak,
            'getComm': self.getComm,
            'getF1': self.getF1,
            'getF2': self.getF2,
            'getGranularity': self.getGranularity,
            'getGranularityCode': self.getGranularityCode,
            'getEndMonth': self.getEndMonth,
            'getDateStop': self.getDateStop,
            'getCostCenters': self.getCostCenters,
        })
        return

    def getF2(self,line):
        if int(line.budget_amount) == 0:
            return ''
        return '=(+RC[-2])/RC[-3]'

    def getF1(self,line):
        if int(line.budget_amount) == 0:
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
                res = _('Accounts and Destinations')
            elif g == 'expense':
                res = _('Accounts')
            elif g == 'view':
                res = _('Parent Accounts only')
        return res

    def getGranularityCode(self,):
        res = 'all'
        parameters = self.localcontext.get('data', {}).get('form', {})
        if 'granularity' in parameters and parameters['granularity']:
            return parameters['granularity']
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

    def getDateStop(self, default):
        """
        Return the last date of given period in parameters. If no parameters, return 'default' value.
        """
        res = default
        parameters = self.localcontext.get('data',{}).get('form',{})
        if 'period_id' in parameters:
            period_data = self.pool.get('account.period').read(self.cr, self.uid, parameters['period_id'], ['date_stop'])
            date_stop = period_data.get('date_stop', False)
            if date_stop:
                res = date_stop
        return res

    def getCostCenters(self, cost_center_id):
        """
        Get all child for the given cost center.
        """
        return self.pool.get('account.analytic.account').search(self.cr, self.uid, [('parent_id', 'child_of', cost_center_id)])

    def getMonthAllocation(self, line, cost_center_ids, date_start, date_stop, end_month, add_commitment=False, context=None):
        """
        Get analytic allocation for the given budget_line 
        """
        # Some checks
        if context is None:
            context = {}
        # Prepare some values
        line_type = line.line_type
        res = []

        ###################
        #
        # FIXME: check if currency_table_id is in context for changing amounts
        #
        ###################

        # Construct conditions to fetch right analytic lines
        sql_conditions = ""
        sql_conditions_params = []
        if line_type == 'destination':
            sql_conditions += """ AND aal.destination_id = %s """
            sql_conditions_params.append(line.destination_id.id)
        if line_type in ['destination', 'normal']:
            sql_conditions += """ AND aal.general_account_id = %s """
            sql_conditions_params.append(line.account_id.id)
        else:
            sql_conditions += """ AND aal.general_account_id IN %s """
            sql_conditions_params.append(tuple(self.pool.get('account.account').search(self.cr, self.uid, [('parent_id', 'child_of', line.account_id.id)]),))
        # Prepare main SQL request
        if add_commitment:
            sql = """SELECT date_part('month', aal.date) AS month, CASE WHEN j.type != 'engagement' THEN 'other' ELSE j.type END AS type, ROUND(COALESCE(SUM(aal.amount), 0), 0)
                FROM account_analytic_line AS aal, account_analytic_journal AS j
                WHERE aal.journal_id = j.id
                AND aal.cost_center_id IN %s
                AND aal.date >= %s
                AND aal.date <= %s
            """
            # PARAMS (sql): cost_center_ids, date_start, date_stop
            sql_end = """ GROUP BY month, type ORDER BY month"""
        else:
            sql = """SELECT date_part('month', aal.date) AS month, ROUND(COALESCE(SUM(aal.amount), 0), 0)
                FROM account_analytic_line AS aal, account_analytic_journal AS j
                WHERE aal.journal_id = j.id
                AND j.type != 'engagement'
                AND aal.cost_center_id IN %s
                AND aal.date >= %s
                AND aal.date <= %s
            """
            # PARAMS (sql): cost_center_ids, date_start, date_stop
            sql_end = """ GROUP BY month ORDER BY month"""
        # Do sql request
        request = sql + sql_conditions + sql_end
        params = [tuple(cost_center_ids), '%s' % date_start, '%s' % date_stop] + sql_conditions_params
        self.cr.execute(request, params) # Will return a list of tuple: (month_number, journal_type, value)
        #+ If not add_commitment, we have a list of tuple as: (month_number, value)
        analytics = self.cr.fetchall()
        # Create a dict with analytics result
        result = {}
        for analytic in analytics:
            if add_commitment:
                month_nb, journal_type, month_amount = analytic
            else:
                journal_type = 'other' # because this information is not in result
                month_nb, month_amount = analytic
            if month_nb in result:
                result[int(month_nb)].update({
                    'commitment': journal_type == 'engagement' and month_amount or 0.0,
                    'actual': journal_type != 'engagement' and month_amount*-1 or 0.0,
                })
            else:
                result.update({
                    int(month_nb): {
                        'budget': getattr(line, 'month' + str(int(month_nb)), 0.0),
                        'commitment': journal_type == 'engagement' and month_amount or 0.0,
                        'actual': journal_type != 'engagement' and month_amount*-1 or 0.0,
                    },
                })
        # Prepare month allocations by using previous analytics result and adding missing values
        for x in xrange(1, end_month + 1, 1):
            if x not in result:
                result.update({
                    x: {
                        'budget': getattr(line, 'month' + str(x), 0.0),
                        'commitment': 0.0,
                        'actual': 0.0,
                    }
                })
        # Transformation/conversion of 'result' to be a list (advantage: keep the sort/order)
        for month in result.keys():
            amounts = result[month]
            budget = amounts.get('budget', 0.0)
            commitment = amounts.get('commitment', 0.0)
            actual = amounts.get('actual', 0.0)
            res.append([budget, commitment, actual])
        return res

SpreadsheetReport('report.budget.criteria.2','msf.budget','addons/msf_budget/report/budget_criteria_xls.mako', parser=report_budget_actual_2)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
