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
            'companyCurrency': self.getCompanyCurrency,
            'process': self.process,
            'getAccountName': self.getAccountName,
            'getAccountNameEx': self.getAccountNameEx,
            'currencyTable': self.getCurrencyTable,
        })
        return

    def getF2(self,line):
        if int(line['budget_amount']) == 0:
            return ''
        return '=(+RC[-2])/RC[-3]'

    def getF1(self,line):
        if int(line['budget_amount']) == 0:
            return ''
        return '=(RC[-3]+RC[-2])/RC[-4]'

    def getComm(self,):
        parameters = self.localcontext.get('data',{}).get('form',{})
        if 'commitment' in parameters and parameters['commitment']:
            return _('Yes')
        return _('No')

    def getBreak(self,):
        parameters = self.localcontext.get('data',{}).get('form',{})
        if 'breakdown' in parameters and parameters['breakdown'] == 'year':
            return _('Total figure')
        return _('By month')

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

    def getCurrencyTable(self,):
        parameters = self.localcontext.get('data', {}).get('form', {})
        res = parameters.get('currency_table_id', False)
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
        res = default and default.val
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

    def getCompanyCurrency(self):
        """
        Fetch company currency
        """
        return self.pool.get('res.users').browse(self.cr, self.uid, self.uid).company_id.currency_id.id

    def getMonthAllocation(self, line, cost_center_ids, date_start, date_stop, end_month, company_currency, add_commitment=False, currency_table=False, context=None):
        """
        Get analytic allocation for the given budget_line
        """
        # Some checks
        if context is None:
            context = {}
        # Prepare some values
        line_type = line.get('line_type', '')
        res = []
        date_context = {'date': date_stop, 'currency_table_id': currency_table}
        cur_obj = self.pool.get('res.currency')
        # Construct conditions to fetch right analytic lines
        sql_conditions = ""
        sql_conditions_params = []
        account_id = line.get('account_id', [False])[0]
        if line_type == 'destination':
            sql_conditions += """ AND aal.destination_id = %s """
            sql_conditions_params.append(line.get('destination_id', [False])[0])
        if line_type in ['destination', 'normal']:
            sql_conditions += """ AND aal.general_account_id = %s """
            sql_conditions_params.append(account_id)
        else:
            sql_conditions += """ AND aal.general_account_id IN %s """
            sql_conditions_params.append(tuple(self.pool.get('account.account').search(self.cr, self.uid, [('parent_id', 'child_of', account_id)]),))
        # Prepare main SQL request
        if add_commitment:
            sql = """SELECT aal.currency_id, date_part('month', aal.date) AS month, CASE WHEN j.type != 'engagement' THEN 'other' ELSE j.type END AS type, ROUND(COALESCE(SUM(aal.amount), 0), 0), COALESCE(SUM(aal.amount_currency), 0)
                FROM account_analytic_line AS aal, account_analytic_journal AS j
                WHERE aal.journal_id = j.id
                AND aal.cost_center_id IN %s
                AND aal.date >= %s
                AND aal.date <= %s
            """
            # PARAMS (sql): cost_center_ids, date_start, date_stop
            sql_end = """ GROUP BY aal.currency_id, month, type ORDER BY month"""
        else:
            sql = """SELECT aal.currency_id, date_part('month', aal.date) AS month, ROUND(COALESCE(SUM(aal.amount), 0), 0), COALESCE(SUM(aal.amount_currency), 0)
                FROM account_analytic_line AS aal, account_analytic_journal AS j
                WHERE aal.journal_id = j.id
                AND j.type != 'engagement'
                AND aal.cost_center_id IN %s
                AND aal.date >= %s
                AND aal.date <= %s
            """
            # PARAMS (sql): cost_center_ids, date_start, date_stop
            sql_end = """ GROUP BY aal.currency_id, month ORDER BY month"""
        # Do sql request
        request = sql + sql_conditions + sql_end
        params = [tuple(cost_center_ids), date_start, date_stop] + sql_conditions_params
        self.cr.execute(request, params) # Will return a list of tuple: (currency_id, month_number, journal_type, value, booking_value)
        #+ If not add_commitment, we have a list of tuple as: (currency_id, month_number, value, booking_value)
        analytics = self.cr.fetchall()
        # Create a dict with analytics result
        result = {}
        # Prepare default values
        for x in xrange(1, end_month + 1, 1):
            result.update({
                x: {
                    'budget': line.get('month' + str(x), 0.0),
                    'commitment': 0.0,
                    'actual': 0.0,
                }
            })
        # Browse analytic result
        for analytic in analytics:
            if add_commitment:
                currency_id, month_nb, journal_type, month_amount, booking_amount = analytic
            else:
                journal_type = 'other' # because this information is not in result
                currency_id, month_nb, month_amount, booking_amount = analytic
            # As we have either actual amount or commitment one, we change key regarding this
            key = 'actual'
            if journal_type == 'engagement':
                key = 'commitment'
            line_amount = month_amount*-1 or 0.0
            # Compute amount regarding functional currency
            if currency_table and currency_id != company_currency:
                line_amount = cur_obj.compute(self.cr, self.uid, currency_id, company_currency, booking_amount*-1, round=False, context=date_context)
            if int(month_nb) in result:
                # Use previous amount to increment it (and do not loose previous one)
                if key in result[int(month_nb)]:
                    line_amount += result[int(month_nb)][key]
                result[int(month_nb)].update({
                    key: line_amount or 0.0
                })
            else:
                result[int(month_nb)] = {
                        key: line_amount or 0.0
                    }
        # Transformation/conversion of 'result' to be a list (advantage: keep the sort/order)
        for month in result.keys():
            amounts = result[month]
            budget = amounts.get('budget', 0.0)
            commitment = amounts.get('commitment', 0.0)
            actual = amounts.get('actual', 0.0)
            res.append([budget, commitment, actual])
        return res

    def getAccountName(self, name):
        """
        Do a separation between accont code and account name
        """
        return self.getAccountNameEx(name, ' ')
        
    def getAccountNameEx(self, name, separator):
        """
        Do a separation between accont code and account name
        """
        res = ''
        if name:
            split = name.split(separator)
            if len(split) and len(split) > 1:
                res = ' '.join(split[1:])
        return res
    def process(self, budget_line_ids, add_commitment=False, currency_table=False):
        """
        Permit to process all lines in one transaction to improve report generation.
        """
        # Some checks
        if not budget_line_ids:
            return {}, {}
        context = {}
        parameters = self.localcontext.get('data',{}).get('form',{})
        if 'period_id' in parameters:
            context.update({'period_id': parameters['period_id']})
        # Prepare some values
        ids = [x.id for x in budget_line_ids]
        fields = [
            'account_code',
            'name',
            'account_id',
            'destination_id',
            'budget_amount',
            'actual_amount',
            'line_type',
            'month1',
            'month2',
            'month3',
            'month4',
            'month5',
            'month6',
            'month7',
            'month8',
            'month9',
            'month10',
            'month11',
            'month12'
        ]
        # Update fields with commitment amount if add_commitment is True
        if add_commitment:
            fields.append('comm_amount')
            context.update({'commitment': True})
        if currency_table:
            context.update({'currency_table_id': currency_table})
        # Fetch line values
        line_vals = self.pool.get('msf.budget.line').read(self.cr, self.uid, ids, fields, context=context)
        if not line_vals:
            return {}, {}
        # Sort first by line_type DESC. Then sort by account_code.
        #+ This is to have first all budget lines sorted by code, then in each code the normal line then budget lines (with destination axis)
        res = sorted(line_vals, key=lambda x: x.get('line_type', ''), reverse=True)
        res = sorted(res, key=lambda x: x.get('account_code', ''))
        return res

SpreadsheetReport('report.budget.criteria.2','msf.budget','addons/msf_budget/report/budget_criteria_xls.mako', parser=report_budget_actual_2)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
