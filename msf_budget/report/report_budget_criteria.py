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
                res = _('Accounts and Destinations')
            elif g == 'expense':
                res = _('Accounts')
            elif g == 'parent':
                res = _('Parent Accounts only')
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

    def getLines(self, obj, context=None):
        """
        Get all needed lines in the right format to be used by the Report
        """
        # Prepare some values
        parameters = self.localcontext.get('data',{}).get('form',{})
        if not context:
            context = {}
        context.update(parameters) # update context with params to fetch right values
        context.update({'report': True}) # in order to get all needed lines from one2many_budget_lines
        lines = self.pool.get('msf.budget').browse(self.cr, self.uid, [obj.id], context=context)[0].budget_line_ids
        budget_line_ids = [x.id for x in lines]
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
