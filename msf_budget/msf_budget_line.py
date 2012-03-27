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

# Overloading the one2many.get for budget lines
# (used for filtering budget lines in the form view;
# dirty as f*ck, but hey, it works)
class one2many_budget_lines(fields.one2many):
    
    def get(self, cr, obj, ids, name, uid=None, offset=0, context=None, values=None):
        if context is None:
            context = {}
        if values is None:
            values = {}
        res = {}
        display_type = {}
        
        for budget in obj.read(cr, uid, ids, ['display_type']):
            res[budget['id']] = []
            display_type[budget['id']] = budget['display_type']

        budget_line_obj = obj.pool.get('msf.budget.line')
        budget_line_ids = budget_line_obj.search(cr, uid, [('budget_id', 'in', ids)])
        if budget_line_ids:
            for budget_line in  budget_line_obj.read(cr, uid, budget_line_ids, ['line_type', 'budget_id'], context=context):
                budget_id = budget_line['budget_id'][0]
                if display_type[budget_id] == 'all' \
                or (display_type[budget_id] == 'view' and budget_line['line_type'] == 'view'):
                    res[budget_id].append(budget_line['id'])
        return res

class msf_budget_line(osv.osv):
    _name = "msf.budget.line"
    
    def _create_view_line_amounts(self, cr, uid, account_id, actual_amounts, context={}):
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
    
    def _get_cost_center_ids(self, browse_budget):
        if browse_budget.type == 'normal':
            # Normal budget, just return a 1-item list
            return [browse_budget.cost_center_id.id]
        else:
            # View budget: return all non-view cost centers below this one
            cost_center_list = []
            self._get_cc_children(browse_budget.cost_center_id, cost_center_list)
            return cost_center_list
        
    def _get_budget_amounts(self, cr, uid, ids, context=None):
        # Input: list of budget lines
        # Output: a dict of list {general_account_id: [jan_budget, feb_budget,...]}
        res = {}
        if context is None:
            context = {}
            
        if len(ids) > 0:
            budget = self.browse(cr, uid, ids[0], context=context).budget_id
            
            if budget.type == 'normal':
                # Budget values are stored in lines; just retrieve and add them
                for budget_line in self.browse(cr, uid, ids, context=context):
                    if budget_line.budget_values:
                        res[budget_line.account_id.id] = eval(budget_line.budget_values)
                    else:
                        res[budget_line.account_id.id] = [0] * 12
            else:
                # fill with 0s
                for budget_line in self.browse(cr, uid, ids, context=context):
                    res[budget_line.account_id.id] = [0] * 12
                # Not stored in lines; retrieve child budgets, get their budget values and add
                cost_center_list = self._get_cost_center_ids(budget)
                # For each cost center, get the latest non-draft budget
                for cost_center_id in cost_center_list:
                    cr.execute("SELECT id FROM msf_budget WHERE fiscalyear_id = %s \
                                                            AND cost_center_id = %s \
                                                            AND state != 'draft' \
                                                            AND type = 'normal' \
                                                            ORDER BY version DESC LIMIT 1",
                                                           (budget.fiscalyear_id.id,
                                                            cost_center_id))
                    if cr.rowcount:
                        # A budget was found; get its lines and their amounts
                        child_budget_id = cr.fetchall()[0][0]
                        child_line_ids = self.search(cr,
                                                     uid,
                                                     [('budget_id', '=', child_budget_id)],
                                                     context=context)
                        child_budget_amounts = self._get_budget_amounts(cr, uid, child_line_ids, context=context)
                        for child_line in self.browse(cr, uid, child_line_ids, context=context):
                            if child_line.account_id.id not in res:
                                res[child_line.account_id.id] = child_budget_amounts[child_line.account_id.id]
                            else:
                                res[child_line.account_id.id] = [sum(pair) for pair in 
                                                                 zip(child_budget_amounts[child_line.account_id.id],
                                                                     res[child_line.account_id.id])]

        return res
        
    
    def _get_actual_amounts(self, cr, uid, ids, context=None):
        # Input: list of budget lines
        # Output: a dict of list {general_account_id: [jan_actual, feb_actual,...]}
        res = {}
        if context is None:
            context = {}
        # global values
        engagement_journal_ids = self.pool.get('account.analytic.journal').search(cr, uid, [('code', '=', 'ENG')], context=context)
        
        # list to store every account in the budget
        general_account_ids = []
        # list to store accounts for view lines
        view_line_account_ids = []
        
        # we discard the ids, and retrieve them all
        # Otherwise, view lines don't have values in "view lines only" display mode
        budget_line_ids = []
        if len(ids) > 0:
            budget = self.browse(cr, uid, ids[0], context=context).budget_id
            cr.execute("SELECT id FROM msf_budget_line WHERE budget_id = %s" % budget.id)
            budget_line_ids = [i[0] for i in cr.fetchall()]
        
            # Browse each budget line for type
            for budget_line in self.browse(cr, uid, budget_line_ids, context=context):
                if budget_line.line_type == 'normal':
                    # add to list of accounts
                    res[budget_line.account_id.id] = [0] * 12
                    general_account_ids.append(budget_line.account_id.id)
                else:
                    view_line_account_ids.append(budget_line.account_id.id)
                    
            cost_center_ids = self._get_cost_center_ids(budget_line.budget_id)
                    
            # Create search domain (one search for all analytic lines)
            actual_domain = [('general_account_id', 'in', general_account_ids)]
            actual_domain.append(('account_id', 'in', cost_center_ids))
            actual_domain.append(('date', '>=', budget_line.budget_id.fiscalyear_id.date_start))
            actual_domain.append(('date', '<=', budget_line.budget_id.fiscalyear_id.date_stop))
            # 3. commitments
            # if commitments are set to False in context, the ENG analytic journal is removed
            # from the domain
            if 'commitment' in context and not context['commitment'] and len(engagement_journal_ids) > 0:
                actual_domain.append(('journal_id', '!=', engagement_journal_ids[0]))
            
            # Analytic domain is now done; lines are retrieved and added
            analytic_line_obj = self.pool.get('account.analytic.line')
            analytic_lines = analytic_line_obj.search(cr, uid, actual_domain, context=context)
            # use currency_table_id
            currency_table = None
            if 'currency_table_id' in context:
                currency_table = context['currency_table_id']
            main_currency_id = budget_line.budget_id.currency_id.id
            
            # parse each line and add it to the right array
            for analytic_line in analytic_line_obj.browse(cr, uid, analytic_lines, context=context):
                date_context = {'date': analytic_line.source_date or analytic_line.date,
                                'currency_table_id': currency_table}
                actual_amount = self.pool.get('res.currency').compute(cr,
                                                                      uid,
                                                                      analytic_line.currency_id.id,
                                                                      main_currency_id, 
                                                                      analytic_line.amount_currency or 0.0,
                                                                      round=True,
                                                                      context=date_context)
                # add the amount to correct month
                month = datetime.datetime.strptime(analytic_line.date, '%Y-%m-%d').month
                res[analytic_line.general_account_id.id][month - 1] += round(actual_amount)
                
            # after all lines are parsed, absolute of every column
            for budget_line in res.keys():
                res[budget_line] = map(abs, res[budget_line])
                    
            # do the view lines
            for account_id in view_line_account_ids:
                self._create_view_line_amounts(cr, uid, account_id, res, context=context)
            
        return res
    
    def _compute_total_amounts(self, cr, uid, budget_amount_list, actual_amount_list, context={}):
        # period_id
        budget_amount = 0
        actual_amount = 0
        month_stop = 0
        if 'period_id' in context:
            period = self.pool.get('account.period').browse(cr, uid, context['period_id'], context=context)
            month_stop = datetime.datetime.strptime(period.date_stop, '%Y-%m-%d').month
        else:
            month_stop = 12
        # actual amount
        if actual_amount_list:
            for i in range(month_stop):
                actual_amount += actual_amount_list[i]
        # budget amount
        if budget_amount_list:
            for i in range(month_stop):
                budget_amount += budget_amount_list[i]
                
        return {'actual_amount': actual_amount,
                'budget_amount': budget_amount}
    
    def _get_total_amounts(self, cr, uid, ids, field_names=None, arg=None, context=None):
        res = {}
        if context is None:
            context = {}
        
        actual_amounts = self._get_actual_amounts(cr, uid, ids, context)
        budget_amounts = self._get_budget_amounts(cr, uid, ids, context)
        
        # Browse each line
        for budget_line in self.browse(cr, uid, ids, context=context):
            line_amounts = self._compute_total_amounts(cr,
                                                       uid,
                                                       budget_amounts[budget_line.account_id.id],
                                                       actual_amounts[budget_line.account_id.id],
                                                       context=context)
            actual_amount = line_amounts['actual_amount']
            budget_amount = line_amounts['budget_amount']
                    
            # We have budget amount and actual amount, compute the remaining ones
            percentage = 0.0
            if budget_amount != 0.0:
                percentage = round((actual_amount / budget_amount) * 100.0)
            res[budget_line.id] = {'budget_amount': budget_amount,
                                   'actual_amount': actual_amount,
                                   'balance': budget_amount - actual_amount,
                                   'percentage': percentage}
        
        return res
    
    def _get_monthly_amounts(self, cr, uid, ids, context=None):
        res = []
        if context is None:
            context = {}
            
        actual_amounts = self._get_actual_amounts(cr, uid, ids, context)
        budget_amounts = self._get_budget_amounts(cr, uid, ids, context)
        
        # if period id, only retrieve a subset
        month_stop = 0
        if 'period_id' in context:
            period = self.pool.get('account.period').browse(cr, uid, context['period_id'], context=context)
            month_stop = datetime.datetime.strptime(period.date_stop, '%Y-%m-%d').month
        else:
            month_stop = 12
                
        # Browse each line
        for budget_line in self.browse(cr, uid, ids, context=context):
            if budget_line.line_type == 'view' or ('granularity' in context and context['granularity'] == 'all'):
                line_actual_amounts = actual_amounts[budget_line.account_id.id]
                line_budget_amounts = budget_amounts[budget_line.account_id.id]
                
                line_values = [budget_line.account_id.code + " " + budget_line.account_id.name]
                if 'breakdown' in context and context['breakdown'] == 'month':
                    # Need to add breakdown values
                    for i in range(month_stop):
                        
                        line_values.append(line_budget_amounts[i])
                        line_values.append(line_actual_amounts[i])
                
                total_amounts = self._compute_total_amounts(cr,
                                                           uid,
                                                           line_budget_amounts,
                                                           line_actual_amounts,
                                                           context=context)
                line_values.append(total_amounts['budget_amount'])
                line_values.append(total_amounts['actual_amount'])
                # add to result
                res.append(line_values)
            
        return res
    
    _columns = {
        'budget_id': fields.many2one('msf.budget', 'Budget', ondelete='cascade'),
        'account_id': fields.many2one('account.account', 'Account', required=True, domain=[('type', '!=', 'view')]),
        'budget_values': fields.char('Budget Values (list of float to evaluate)', size=256),
        'budget_amount': fields.function(_get_total_amounts, method=True, store=False, string="Budget amount", type="float", readonly="True", multi="all"),
        'actual_amount': fields.function(_get_total_amounts, method=True, store=False, string="Actual amount", type="float", readonly="True", multi="all"),
        'balance': fields.function(_get_total_amounts, method=True, store=False, string="Balance", type="float", readonly="True", multi="all"),
        'percentage': fields.function(_get_total_amounts, method=True, store=False, string="Percentage", type="float", readonly="True", multi="all"),
        'parent_id': fields.many2one('msf.budget.line', 'Parent Line'),
        'child_ids': fields.one2many('msf.budget.line', 'parent_id', 'Child Lines'),
        'line_type': fields.selection([('view','View'),
                                       ('normal','Normal')], 'Line type', required=True),
    }
    
    _defaults = {
        'line_type': 'normal',
    }
    
    def get_parent_line(self, cr, uid, vals, context={}):
        # Method to check if the used account has a parent,
        # and retrieve or create the corresponding parent line.
        # It also adds budget values to parent lines
        if 'account_id' in vals and 'budget_id' in vals:
            # search for budget line
            account = self.pool.get('account.account').browse(cr, uid, vals['account_id'], context=context)
            chart_of_account_ids = self.pool.get('account.account').search(cr, uid, [('code', '=', 'MSF')], context=context)
            if account.parent_id and account.parent_id.id not in chart_of_account_ids:
                parent_account_id = account.parent_id.id
                parent_line_ids = self.search(cr, uid, [('account_id', '=', parent_account_id),
                                                        ('budget_id', '=', vals['budget_id'])], context=context)
                if len(parent_line_ids) > 0:
                    # Parent line exists
                    if 'budget_values' in vals:
                        # we add the budget values to the parent one
                        parent_line = self.browse(cr, uid, parent_line_ids[0], context=context)
                        parent_budget_values = [sum(pair) for pair in zip(eval(parent_line.budget_values),
                                                                          eval(vals['budget_values']))]
                        # write parent
                        super(msf_budget_line, self).write(cr,
                                                           uid,
                                                           parent_line_ids,
                                                           {'budget_values': str(parent_budget_values)},
                                                           context=context)
                        # use method on parent with original budget values
                        self.get_parent_line(cr,
                                             uid,
                                             {'account_id': parent_line.account_id.id,
                                              'budget_id': parent_line.budget_id.id,
                                              'budget_values': vals['budget_values']},
                                             context=context)
                    # add parent id to vals
                    vals.update({'parent_id': parent_line_ids[0]})
                else:
                    # Create parent line and add it to vals, except if it's the main parent
                    parent_vals = {'budget_id': vals['budget_id'],
                                   'account_id': parent_account_id,
                                   'line_type': 'view'}
                    # default parent budget values: the one from the (currently) only child
                    if 'budget_values' in vals:
                        parent_vals.update({'budget_values': vals['budget_values']})
                    parent_budget_line_id = self.create(cr, uid, parent_vals, context=context)
                    vals.update({'parent_id': parent_budget_line_id})
        return
            
    
    def create(self, cr, uid, vals, context=None):
        self.get_parent_line(cr, uid, vals, context=context)
        return super(msf_budget_line, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        self.get_parent_line(cr, uid, vals, context=context)
        return super(msf_budget_line, self).write(cr, uid, ids, vals, context=context)
    
    def name_get(self, cr, user, ids, context=None):
        result = self.browse(cr, user, ids, context=context)
        res = []
        for rs in result:
            account = rs.account_id
            res += [(rs.id, account.code + " " + account.name)]
        return res
    
msf_budget_line()

class msf_budget(osv.osv):
    _name = "msf.budget"
    _inherit = "msf.budget"
    
    _columns = {
        'budget_line_ids': one2many_budget_lines('msf.budget.line', 'budget_id', 'Budget Lines'),
    }
    
msf_budget()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
