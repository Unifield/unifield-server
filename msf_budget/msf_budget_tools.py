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

from osv import fields, osv
import datetime
from dateutil.relativedelta import relativedelta

class msf_budget_tools(osv.osv):
    _name = "msf.budget.tools"
    
    def _get_account_parent(self, browse_account, account_list, chart_of_account_ids):
        if browse_account.parent_id and \
           browse_account.parent_id.id and \
           browse_account.parent_id.id not in chart_of_account_ids and \
           browse_account.parent_id.id not in account_list:
            account_list.append(browse_account.parent_id.id)
            self._get_account_parent(browse_account.parent_id, account_list, chart_of_account_ids)
        return
    
    def _get_expense_accounts(self, cr, uid, context=None):
        res = []
        account_obj = self.pool.get('account.account')
        # get the last parent
        chart_of_account_ids = account_obj.search(cr, uid, [('code', '=', 'MSF')], context=context)
        # get normal expense accounts
        general_account_ids = account_obj.search(cr, uid, [('user_type_code', '=', 'expense'),
                                                           ('type', '!=', 'view')], context=context)
        view_account_ids = []
        # go through parents
        for account in account_obj.browse(cr, uid, general_account_ids, context=context):
            self._get_account_parent(account, view_account_ids, chart_of_account_ids)
        return {'general_accounts': general_account_ids,
                'view_accounts': view_account_ids}

    def _create_view_line_amounts(self, cr, uid, account_id, actual_amounts, context=None):
        if account_id not in actual_amounts:
            account = self.pool.get('account.account').browse(cr, uid, account_id, context=context)
            result = [0] * 12
            for child_account in account.child_id:
                if child_account.id not in actual_amounts:
                    self._create_view_line_amounts(cr, uid, child_account.id, actual_amounts, context=context)
                result = [sum(pair) for pair in zip(result, actual_amounts[child_account.id])]
            actual_amounts[account_id] = result
        return
    
    def _get_cc_children(self, browse_cost_center, cost_center_list):
        for child in browse_cost_center.child_ids:
            if child.type == 'view':
                self._get_cc_children(child, cost_center_list)
            else:
                cost_center_list.append(child.id)
        return
    
    def _get_cost_center_ids(self, browse_cost_center):
        if browse_cost_center.type == 'normal':
            # Normal budget, just return a 1-item list
            return [browse_cost_center.id]
        else:
            # View budget: return all non-view cost centers below this one
            cost_center_list = []
            self._get_cc_children(browse_cost_center, cost_center_list)
            return cost_center_list
    
    def _get_actual_amounts(self, cr, uid, output_currency_id, domain=[], context=None):
        # Input: domain for the selection of analytic lines (cost center, date, etc...)
        # Output: a dict of list {general_account_id: [jan_actual, feb_actual,...]}
        res = {}
        if context is None:
            context = {}
        
        # list to store every account in the budget (normal only for the time being)
        account_ids = self._get_expense_accounts(cr, uid, context=context)
        
        # Fill all general accounts
        for account_id in account_ids['general_accounts']:
            res[account_id] = [0] * 12
                    
        # fill search domain (one search for all analytic lines)
        domain.append(('general_account_id', 'in', account_ids['general_accounts']))
        
        # Analytic domain is now done; lines are retrieved and added
        analytic_line_obj = self.pool.get('account.analytic.line')
        analytic_lines = analytic_line_obj.search(cr, uid, domain, context=context)
        # use currency_table_id
        currency_table = None
        if 'currency_table_id' in context:
            currency_table = context['currency_table_id']
        
        # parse each line and add it to the right array
        for analytic_line in analytic_line_obj.browse(cr, uid, analytic_lines, context=context):
            date_context = {'date': analytic_line.source_date or analytic_line.date,
                            'currency_table_id': currency_table}
            actual_amount = self.pool.get('res.currency').compute(cr,
                                                                  uid,
                                                                  analytic_line.currency_id.id,
                                                                  output_currency_id, 
                                                                  analytic_line.amount_currency or 0.0,
                                                                  round=True,
                                                                  context=date_context)
            # add the amount to correct month
            month = datetime.datetime.strptime(analytic_line.date, '%Y-%m-%d').month
            res[analytic_line.general_account_id.id][month - 1] += round(actual_amount)
            
        # after all lines are parsed, absolute of every column
        for line in res.keys():
            res[line] = map(abs, res[line])
                
        # do the view lines
        for account_id in account_ids['view_accounts']:
            self._create_view_line_amounts(cr, uid, account_id, res, context=context)
        
        return res
    
msf_budget_tools()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
