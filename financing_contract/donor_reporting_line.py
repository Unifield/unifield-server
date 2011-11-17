# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import fields, osv

class financing_contract_donor_reporting_line(osv.osv):
    _name = "financing.contract.donor.reporting.line"
    
    def _get_total_costs(self, cr, uid, browse_overhead_line, context=None):
        costs_allocated_budget = 0.0
        costs_project_budget = 0.0
        costs_allocated_real = 0.0
        costs_project_real = 0.0
        # since this is only called from the overhead line, the domain is
        # "all children of the parent line, except the current one"
        for line in browse_overhead_line.parent_id.child_ids:
            if line.id != browse_overhead_line.id:
                child_allocated_values = self._get_allocated_amounts(cr, uid, [line.id], context=context)
                child_project_values = self._get_project_amounts(cr, uid, [line.id], context=context)
                costs_allocated_budget += child_allocated_values[line.id]['allocated_budget']
                costs_project_budget += child_project_values[line.id]['project_budget']
                costs_allocated_real += child_allocated_values[line.id]['allocated_real']
                costs_project_real += child_project_values[line.id]['project_real']
        return {
                'allocated_budget': costs_allocated_budget,
                'project_budget': costs_project_budget,
                'allocated_real': costs_allocated_real,
                'project_real': costs_project_real,
               }

    def _get_account_domain(self, browse_line):
        if browse_line.computation_type != 'children_sum':
            return browse_line.account_domain and eval(browse_line.account_domain) or False
        else:
            account_ids = []
            for child_line in browse_line.child_ids:
                child_domain = self._get_account_domain(child_line)
                if child_domain != False:
                    account_ids += child_domain[2]
            return ('general_account_id', 'in', account_ids)

    def _get_allocated_amounts(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
            Method to compute the allocated budget/amounts, depending on the information in the line
        """
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            if line.computation_type:
                if line.computation_type == 'children_sum':
                    # no values are set, it should be the sum of all children
                    child_allocated_budget = 0.0
                    child_allocated_real = 0.0
                    for child_line in line.child_ids:
                        child_values = self._get_allocated_amounts(cr, uid, [child_line.id], context=context)
                        child_allocated_budget += child_values[child_line.id]['allocated_budget']
                        child_allocated_real += child_values[child_line.id]['allocated_real']
                    res[line.id] = {
                        'allocated_budget': child_allocated_budget,
                        'allocated_real': child_allocated_real,
                    }
                elif line.computation_type == 'amount':
                    # Values were set, they're just returned as such
                    res[line.id] = {
                        'allocated_budget': line.allocated_budget_value,
                        'allocated_real': line.allocated_real_value,
                    }
                elif line.computation_type == 'cost_percentage':
                    # percentage of all costs (sum of all 2nd-level lines, except overhead)
                    total_costs = self._get_total_costs(cr, uid, line, context=context)
                    res[line.id] = {
                        'allocated_budget': total_costs['allocated_budget'] * line.overhead_percentage / 100.0,
                        'allocated_real': total_costs['allocated_real'] * line.overhead_percentage / 100.0,
                    }
                elif line.computation_type == 'grant_percentage':
                    # percentage of all costs (sum of all 2nd-level lines, except overhead)
                    total_costs = self._get_total_costs(cr, uid, line, context=context)
                    res[line.id] = {
                        'allocated_budget': total_costs['allocated_budget'] * line.overhead_percentage / (100.0 - line.overhead_percentage),
                        'allocated_real': total_costs['allocated_real'] * line.overhead_percentage / (100.0 - line.overhead_percentage),
                    }
                elif line.computation_type == 'analytic_sum':
                    # sum of analytic lines, determined by the domain
                    if 'reporting_currency' in context:
                        analytic_line_obj = self.pool.get('account.analytic.line')
                        date_domain = eval(line.date_domain)
                        analytic_domain = [date_domain[0], date_domain[1], eval(line.account_domain), eval(line.funding_pool_domain)]
                        analytic_lines = analytic_line_obj.search(cr, uid, analytic_domain ,context=context)
                        allocated_real_sum = 0.0
                        for analytic_line in analytic_line_obj.browse(cr, uid, analytic_lines, context=context):
                            date_context = {'date': analytic_line.source_date or analytic_line.date}
                            allocated_real_sum += self.pool.get('res.currency').compute(cr,
                                                                                      uid,
                                                                                      analytic_line.currency_id.id,
                                                                                      context['reporting_currency'], 
                                                                                      analytic_line.amount_currency or 0.0,
                                                                                      round=False,
                                                                                      context=date_context)
                        allocated_real_sum = abs(allocated_real_sum)
                        res[line.id] = {
                            'allocated_budget': line.allocated_budget_value,
                            'allocated_real': allocated_real_sum,
                        }
        return res

    def _get_project_amounts(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
            Method to compute the project budget/amounts, depending on the information in the line
        """
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            if line.computation_type:
                if line.computation_type == 'children_sum':
                    # no values are set, it should be the sum of all children
                    child_project_budget = 0.0
                    child_project_real = 0.0
                    for child_line in line.child_ids:
                        child_values = self._get_project_amounts(cr, uid, [child_line.id], context=context)
                        child_project_budget += child_values[child_line.id]['project_budget']
                        child_project_real += child_values[child_line.id]['project_real']
                    res[line.id] = {
                        'project_budget': child_project_budget,
                        'project_real': child_project_real,
                    }
                elif line.computation_type == 'amount':
                    # Values were set, they're just returned as such
                    res[line.id] = {
                        'project_budget': line.project_budget_value,
                        'project_real': line.project_real_value,
                    }
                elif line.computation_type == 'cost_percentage':
                    # percentage of the costs (sum of all 2nd-level lines, except overhead)
                    total_costs = self._get_total_costs(cr, uid, line, context=context)
                    res[line.id] = {
                        'project_budget': total_costs['project_budget'] * line.overhead_percentage / 100.0,
                        'project_real': total_costs['project_real'] * line.overhead_percentage / 100.0,
                    }
                elif line.computation_type == 'grant_percentage':
                    # percentage of all costs (sum of all 2nd-level lines, except overhead)
                    total_costs = self._get_total_costs(cr, uid, line, context=context)
                    res[line.id] = {
                        'project_budget': total_costs['project_budget'] * line.overhead_percentage / (100.0 - line.overhead_percentage),
                        'project_real': total_costs['project_real'] * line.overhead_percentage / (100.0 - line.overhead_percentage),
                    }
                elif line.computation_type == 'analytic_sum':
                    # sum of analytic lines, determined by the domain
                    private_funds_id = self.pool.get('account.analytic.account').search(cr, uid, [('code', '=', 'PF')], context=context)
                    if private_funds_id and 'reporting_currency' in context:
                        analytic_line_obj = self.pool.get('account.analytic.line')
                        date_domain = eval(line.date_domain)
                        analytic_domain = [date_domain[0], date_domain[1], eval(line.account_domain), eval(line.cost_center_domain), ('account_id', '!=', private_funds_id)]
                        analytic_lines = analytic_line_obj.search(cr, uid, analytic_domain ,context=context)
                        project_real_sum = 0.0
                        for analytic_line in analytic_line_obj.browse(cr, uid, analytic_lines, context=context):
                            date_context = {'date': analytic_line.source_date or analytic_line.date}
                            project_real_sum += self.pool.get('res.currency').compute(cr,
                                                                                      uid,
                                                                                      analytic_line.currency_id.id,
                                                                                      context['reporting_currency'], 
                                                                                      analytic_line.amount_currency or 0.0,
                                                                                      round=False,
                                                                                      context=date_context)
                        project_real_sum = abs(project_real_sum)
                        res[line.id] = {
                            'project_budget': line.project_budget_value,
                            'project_real': project_real_sum,
                        }
        return res
    
    _columns = {
        # for every line
        'name': fields.char('Name', size=64, required=True),
        'code': fields.char('Code', size=16, required=True),
        # not shown, to store given amount value
        'allocated_budget_value': fields.float('Budget allocated amount (value)'),
        'project_budget_value': fields.float('Budget project amount (value)'),
        'allocated_real_value': fields.float('Real allocated amount (value)'),
        'project_real_value': fields.float('Real project amount (value)'),
        'overhead_percentage': fields.float('Overhead percentage (value)'),
        # returns wanted value depending of computation type and number of children
        'allocated_budget': fields.function(_get_allocated_amounts, method=True, store=False, string="Funded amount - Budget", type="float", readonly="True", multi="allocated"),
        'project_budget': fields.function(_get_project_amounts, method=True, store=False, string="Total project amount - Budget", type="float", readonly="True", multi="project"),
        'allocated_real': fields.function(_get_allocated_amounts, method=True, store=False, string="Funded amount - Actuals", type="float", readonly="True", multi="allocated"),
        'project_real': fields.function(_get_project_amounts, method=True, store=False, string="Total project amount - Actuals", type="float", readonly="True", multi="project"),
        'computation_type': fields.selection([('children_sum', 'Sum of all children (budget and real)'),
                                              ('analytic_sum', 'Sum of analytic lines'),
                                              ('amount','Given amount'),
                                              ('cost_percentage','Total costs percentage'),
                                              ('grant_percentage','Total grant percentage')], 'Computation type'),
        'date_domain': fields.char('Date domain', size=256),
        'account_domain': fields.char('Account domain', size=256),
        'funding_pool_domain': fields.char('Funding pool domain', size=256),
        'cost_center_domain': fields.char('Cost center domain', size=256),
        'parent_id': fields.many2one('financing.contract.donor.reporting.line', 'Parent line', ondelete='cascade'),
        'child_ids': fields.one2many('financing.contract.donor.reporting.line', 'parent_id', 'Child lines'),
        # for parent reporting line (representing the contract in tree view)
        'contract_id': fields.one2many('financing.contract.contract', 'report_line', 'Contract'),
    }
        
financing_contract_donor_reporting_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
