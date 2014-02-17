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
            # Override display_type if we come from a report
            if context.get('report', False) and context.get('granularity', False):
                display_type[budget['id']] = context.get('granularity')

        budget_line_obj = obj.pool.get('msf.budget.line')
        budget_line_ids = budget_line_obj.search(cr, uid, [('budget_id', 'in', ids)])
        if budget_line_ids:
            for budget_line in  budget_line_obj.read(cr, uid, budget_line_ids, ['line_type', 'budget_id'], context=context):
                budget_id = budget_line['budget_id'][0]
                if display_type[budget_id] == 'all' \
                or (display_type[budget_id] == 'view' and budget_line['line_type'] == 'view') \
                or (display_type[budget_id] == 'expense' and budget_line['line_type'] != 'destination'):
                    res[budget_id].append(budget_line['id'])
        return res

class msf_budget_line(osv.osv):
    _name = "msf.budget.line"

    def _get_comm_amounts(self, cr, uid, ids, context=None):
        res = {}
        if context is None:
            context = {}
        engagement_journal_ids = self.pool.get('account.analytic.journal').search(cr, uid, [('type', '=', 'engagement')], context=context)
        budget_line_ids = []
        if len(ids) > 0:
            budget = self.browse(cr, uid, ids[0], context=context).budget_id
            output_currency_id = budget.currency_id.id
            cost_center_ids = self.pool.get('msf.budget.tools')._get_cost_center_ids(budget.cost_center_id)
            actual_domain = [('cost_center_id', 'in', cost_center_ids)]
            actual_domain.append(('date', '>=', budget.fiscalyear_id.date_start))
            actual_domain.append(('date', '<=', budget.fiscalyear_id.date_stop))
            actual_domain.append(('journal_id', 'in', engagement_journal_ids))
            res = self.pool.get('msf.budget.tools')._get_actual_amounts(cr, uid, output_currency_id, actual_domain, context=context)
        return res

    def _get_actual_amounts(self, cr, uid, ids, context=None):
        # Input: list of budget lines
        # Output: a dict of list {general_account_id: [jan_actual, feb_actual,...]}
        res = {}
        if context is None:
            context = {}
        # global values
        engagement_journal_ids = self.pool.get('account.analytic.journal').search(cr, uid, [('type', '=', 'engagement')], context=context)
        
        # we discard the ids, but retrieve the budget from it
        # Otherwise, view lines don't have values in "view lines only" display mode
        budget_line_ids = []
        if len(ids) > 0:
            budget = self.browse(cr, uid, ids[0], context=context).budget_id
            output_currency_id = budget.currency_id.id
                    
            cost_center_ids = self.pool.get('msf.budget.tools')._get_cost_center_ids(budget.cost_center_id)
                    
            # Create search domain (one search for all analytic lines)
            actual_domain = [('cost_center_id', 'in', cost_center_ids)]
            actual_domain.append(('date', '>=', budget.fiscalyear_id.date_start))
            actual_domain.append(('date', '<=', budget.fiscalyear_id.date_stop))
            # 3. commitments
            # if commitments are set to False in context, the engagement analytic journals are removed
            # from the domain
            actual_domain.append(('journal_id', 'not in', engagement_journal_ids))
            # Call budget_tools method
            res = self.pool.get('msf.budget.tools')._get_actual_amounts(cr, uid, output_currency_id, actual_domain, context=context)
        
        return res
        
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
                    budget_line_destination_id = budget_line.destination_id and budget_line.destination_id.id or False
                    if budget_line.budget_values:
                        res[budget_line.account_id.id, budget_line_destination_id] = eval(budget_line.budget_values)
                    else:
                        res[budget_line.account_id.id, budget_line_destination_id] = [0] * 12
            else:
                # fill with 0s
                for budget_line in self.browse(cr, uid, ids, context=context):
                    budget_line_destination_id = budget_line.destination_id and budget_line.destination_id.id or False
                    res[budget_line.account_id.id, budget_line_destination_id] = [0] * 12
                # Not stored in lines; retrieve child budgets, get their budget values and add
                cost_center_list = self.pool.get('msf.budget.tools')._get_cost_center_ids(budget.cost_center_id)
                # For each cost center, get the latest non-draft budget
                for cost_center_id in cost_center_list:
                    cr.execute("SELECT id FROM msf_budget WHERE fiscalyear_id = %s \
                                                            AND cost_center_id = %s \
                                                            AND decision_moment_id = %s \
                                                            AND state != 'draft' \
                                                            AND type = 'normal' \
                                                            ORDER BY version DESC LIMIT 1",
                                                           (budget.fiscalyear_id.id,
                                                            cost_center_id,
                                                            budget.decision_moment_id.id))
                    if cr.rowcount:
                        # A budget was found; get its lines and their amounts
                        child_budget_id = cr.fetchall()[0][0]
                        child_line_ids = self.search(cr,
                                                     uid,
                                                     [('budget_id', '=', child_budget_id)],
                                                     context=context)
                        child_budget_amounts = self._get_budget_amounts(cr, uid, child_line_ids, context=context)
                        for child_line in self.browse(cr, uid, child_line_ids, context=context):
                            child_line_destination_id = child_line.destination_id and child_line.destination_id.id or False
                            if (child_line.account_id.id, child_line_destination_id) not in res:
                                res[child_line.account_id.id, child_line_destination_id] = child_budget_amounts[child_line.account_id.id, child_line_destination_id]
                            else:
                                res[child_line.account_id.id, child_line_destination_id] = [sum(pair) for pair in 
                                                                                                             zip(child_budget_amounts[child_line.account_id.id, child_line_destination_id],
                                                                                                             res[child_line.account_id.id, child_line_destination_id])]

        return res
    
    def _compute_total_amounts(self, cr, uid, budget_amount_list, actual_amount_list, comm_amount_list, context=None):
        # period_id
        if context is None:
            context = {}
        budget_amount = 0
        actual_amount = 0
        comm_amount = 0
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
        # comm amount
        if comm_amount_list:
            for i in range(month_stop):
                comm_amount += comm_amount_list[i]
                
        return {'actual_amount': actual_amount,
                'comm_amount': comm_amount,
                'budget_amount': budget_amount}
    
    def _get_total_amounts(self, cr, uid, ids, field_names=None, arg=None, context=None):
        res = {}
        if context is None:
            context = {}
        
        actual_amounts = self._get_actual_amounts(cr, uid, ids, context)
        budget_amounts = self._get_budget_amounts(cr, uid, ids, context)
        comm_amounts = self._get_comm_amounts(cr, uid, ids, context)
        
        # Browse each line
        for budget_line in self.browse(cr, uid, ids, context=context):
            budget_line_destination_id = budget_line.destination_id and budget_line.destination_id.id or False
            line_amounts = self._compute_total_amounts(cr,
                                                       uid,
                                                       (budget_line.account_id.id, budget_line_destination_id) in budget_amounts \
                                                       and budget_amounts[budget_line.account_id.id, budget_line_destination_id] \
                                                       or [0] * 12,
                                                       (budget_line.account_id.id, budget_line_destination_id) in actual_amounts \
                                                       and actual_amounts[budget_line.account_id.id, budget_line_destination_id] \
                                                       or [0] * 12,
                                                       (budget_line.account_id.id, budget_line_destination_id) in comm_amounts \
                                                       and comm_amounts[budget_line.account_id.id, budget_line_destination_id] \
                                                       or [0] * 12,
                                                       context=context)

            actual_amount = line_amounts['actual_amount']
            budget_amount = line_amounts['budget_amount']
            comm_amount = line_amounts['comm_amount']

            # We have budget amount and actual amount, compute the remaining ones
            percentage = 0.0
            if budget_amount != 0.0:
                percentage = round((actual_amount / budget_amount) * 100.0)
            res[budget_line.id] = {'budget_amount': budget_amount,
                                   'actual_amount': actual_amount,
                                   'comm_amount': comm_amount,
                                   'balance': budget_amount - actual_amount,
                                   'percentage': percentage}
        
        return res
    
    def _get_monthly_amounts(self, cr, uid, ids, context=None):
        res = []
        if context is None:
            context = {}
            
        actual_amounts = self._get_actual_amounts(cr, uid, ids, context)
        budget_amounts = self._get_budget_amounts(cr, uid, ids, context)
        comm_amounts = self._get_comm_amounts(cr, uid, ids, context)
        
        # if period id, only retrieve a subset
        month_stop = 0
        if 'period_id' in context:
            period = self.pool.get('account.period').browse(cr, uid, context['period_id'], context=context)
            month_stop = datetime.datetime.strptime(period.date_stop, '%Y-%m-%d').month
        else:
            month_stop = 12
                
        # Browse each line
        for budget_line in self.browse(cr, uid, ids, context=context):
            budget_line_destination_id = budget_line.destination_id and budget_line.destination_id.id or False

            if budget_line.line_type == 'view' \
                or ('granularity' in context and context['granularity'] == 'all') \
                or ('granularity' in context and context['granularity'] == 'expense' and budget_line.line_type != 'destination'):
                line_actual_amounts = [0] * 12
                line_budget_amounts = [0] * 12
                line_comm_amounts = [0] * 12
                if (budget_line.account_id.id, budget_line_destination_id) in actual_amounts:
                    line_actual_amounts = actual_amounts[budget_line.account_id.id, budget_line_destination_id]
                if (budget_line.account_id.id, budget_line_destination_id) in budget_amounts:
                    line_budget_amounts = budget_amounts[budget_line.account_id.id, budget_line_destination_id]
                if (budget_line.account_id.id, budget_line_destination_id) in comm_amounts:
                    line_comm_amounts = comm_amounts[budget_line.account_id.id, budget_line_destination_id]
                

                line_code = budget_line.account_id.code
                line_destination = ''
                if budget_line.destination_id:
                    line_destination = budget_line.destination_id.code
                line_name = budget_line.account_id.name
                line_values = [(line_code,line_destination,line_name)]

                if 'breakdown' in context and context['breakdown'] == 'month':
                    # Need to add breakdown values
                    for i in range(month_stop):
                        line_values.append(line_budget_amounts[i])
                        line_values.append(line_comm_amounts[i])
                        line_values.append(line_actual_amounts[i])
                
                total_amounts = self._compute_total_amounts(cr,
                                                           uid,
                                                           line_budget_amounts,
                                                           line_actual_amounts,
                                                           line_comm_amounts,
                                                           context=context)

                line_values.append(total_amounts['budget_amount'])
                line_values.append(total_amounts['comm_amount'])
                line_values.append(total_amounts['actual_amount'])

                # add to result
                res.append(line_values)
            
        return res
    
    def _get_name(self, cr, uid, ids, field_names=None, arg=None, context=None):
        result = self.browse(cr, uid, ids, context=context)
        res = {}
        for rs in result:
            account = rs.account_id
            name = account.code 
            if rs.destination_id:
                name += " "
                name += rs.destination_id.code
            name += " "
            name += account.name
            res[rs.id] = name
        return res

    def _get_budget_line_amount(self, cr, uid, ids, field_names=None, arg=None, context=None):
        """
        Get the sum of budget_values content from a given budget line.
        """
        res = {}
        sql = """
        SELECT id, budget_values
        FROM msf_budget_line
        WHERE id IN %s;
        """
        cr.execute(sql, (tuple(ids),))
        tmp_res = cr.fetchall()
        if not tmp_res:
            return res
        tmp_res = dict(tmp_res)
        for l_id in ids:
            res.setdefault(l_id, 0.0)
            if l_id in tmp_res:
                res[l_id] = sum(eval(tmp_res[l_id])) or 0.0
        return res

    def _get_actual_amount(self, cr, uid, ids, field_names=None, arg=None, context=None):
        """
        The actual amount is composed of the total of analytic lines corresponding to these criteria:
          - cost center that is used on the budget
          - fiscalyear used on the budget (date should be between date_start and date_stop from the fiscalyear)
          - account_id on the budget line
          - destination_id on the budget line
        """
        # Prepare some values
        res = {}
        ana_obj = self.pool.get('account.analytic.line')
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        cur_obj = self.pool.get('res.currency')
        if isinstance(ids, (int, long)):
            ids = [ids]
        new_ids = list(ids)
### METHOD 2 ###
#        # Search all child because 'view' line must have all their children to be calculated
#        budget_lines = {}
#        for line_id in ids:
#            child_ids = self.search(cr, uid, [('parent_id', 'child_of', line_id)])
#            if child_ids:
#                for child_id in child_ids:
#                    budget_lines.setdefault(child_id, [])
#                    budget_lines[child_id].append(line_id)
#                    new_ids += child_ids
### ###

### ALL METHODS ###
#        child_ids = self.search(cr, uid, [('parent_id', 'child_of', ids)])
#        if child_ids:
#            new_ids += child_ids
#            new_ids = list(set(new_ids))
### ###
        # Create default values
        for index in new_ids:
            res.setdefault(index, 0.0)
        # Now, only use 'destination' line to do process and complete parent one at the same time
        sql = """
            SELECT l.id, l.parent_id, l.line_type, l.account_id, l.destination_id, b.cost_center_id, b.currency_id, f.date_start, f.date_stop
            FROM msf_budget_line AS l, msf_budget AS b, account_fiscalyear AS f
            WHERE l.budget_id = b.id
            AND b.fiscalyear_id = f.id
            AND l.id IN %s
            ORDER BY l.line_type, l.id;
        """
        cr.execute(sql, (tuple(new_ids),))
        # Prepare SQL2 request that contains sum of amount of given analytic lines (in functional currency)
        sql2 = """
            SELECT SUM(amount)
            FROM account_analytic_line
            WHERE id in %s;"""
        # Process destination lines
        for line in cr.fetchall():
            # fetch some values
            line_id, parent_id, line_type, account_id, destination_id, cost_center_id, currency_id, date_start, date_stop = line
            criteria = [
                ('cost_center_id', '=', cost_center_id),
                ('date', '>=', date_start),
                ('date', '<=', date_stop),
                ('journal_id.type', '!=', 'engagement'),
            ]
            if line_type == 'destination':
                criteria.append(('destination_id', '=', destination_id))
            if line_type in ['destination', 'normal']:
                criteria.append(('general_account_id', '=', account_id)),
            else:
                criteria.append(('general_account_id', 'child_of', account_id))
            ana_ids = ana_obj.search(cr, uid, criteria)
            if ana_ids:
                cr.execute(sql2, (tuple(ana_ids),))
                mnt_result = cr.fetchall()
                if mnt_result:
                    res[line_id] += mnt_result[0][0]
        return res

### METHOD 2 ###
#            ana_ids = ana_obj.search(cr, uid, [('general_account_id', '=', account_id), ('cost_center_id', '=', cost_center_id), ('destination_id', '=', destination_id), ('date', '>=', date_start), ('date', '<=', date_stop), ('journal_id.type', '!=', 'engagement')])
#            if ana_ids:
#                cr.execute(sql2, (tuple(ana_ids),))
#                mnt_result = cr.fetchall()
#                if mnt_result:
#                    # NB: No need to recompute the amount as budget are in functional currency and that analytic line have 'amount' in functional currency
#                    #amount = cur_obj.compute(cr, uid, company_currency, currency_id, mnt_result[0][0], round=False, context=context)
#                    res[line_id] += mnt_result[0][0]
#                    for parent in budget_lines[line_id]:
#                        if parent != line_id:
#                            res[parent] += mnt_result[0][0]
#                    # Update parent until parent_id is False
#                    if parent_id:
#                        res[parent_id] += mnt_result[0][0]
#                        parent_ids.append(parent_id)
#                        parent = self.read(cr, uid, parent_id, ['parent_id'])
#                        sup_parent_id = parent.get('parent_id', False)
#                        if sup_parent_id:
#                            res[sup_parent_id[0]] += res[parent_id]
#                        while sup_parent_id:
#                            parent = self.read(cr, uid, sup_parent_id[0], ['parent_id'])
#                            sup_parent_id = parent.get('parent_id', False)
#                            if sup_parent_id:
#                                res[sup_parent_id[0]] += res[parent_id]
### END OF METHOD 2 ###

### METHOD 3 ###
#        # Complete parents
#        for budget_line in budget_lines:
#            for child in budget_lines[budget_line][0]:
#                print child
#                res[budget_line] += res[child]

#        if parent_ids:
#            sql3 = """
#                SELECT id, parent_id
#                FROM msf_budget_line
#                WHERE id IN %s"""
#            cr.execute(sql3, (tuple(parent_ids),))
#            result = cr.fetchall()
#            for couple in result:
#                l_id, parent_id = couple
#                res[parent_id] += res[l_id]
#        return res
### END OF METHOD 3 ###

    _columns = {
        'budget_id': fields.many2one('msf.budget', 'Budget', ondelete='cascade'),
        'account_id': fields.many2one('account.account', 'Account', required=True, domain=[('type', '!=', 'view')]),
        'destination_id': fields.many2one('account.analytic.account', 'Destination', domain=[('category', '=', 'DEST')]),
        'name': fields.function(_get_name, method=True, store=False, string="Name", type="char", readonly="True", size=512),
        'budget_values': fields.char('Budget Values (list of float to evaluate)', size=256),
        'budget_amount': fields.function(_get_budget_line_amount, method=True, store=False, string="Budget amount", type="float", readonly="True"),
        'actual_amount': fields.function(_get_actual_amount, method=True, store=False, string="Actual amount", type="float", readonly="True"),
        'comm_amount': fields.function(_get_total_amounts, method=True, store=False, string="Commitments amount", type="float", readonly="True", multi="all"),
        'balance': fields.function(_get_total_amounts, method=True, store=False, string="Balance", type="float", readonly="True", multi="all"),
        'percentage': fields.function(_get_total_amounts, method=True, store=False, string="Percentage", type="float", readonly="True", multi="all"),
        'parent_id': fields.many2one('msf.budget.line', 'Parent Line'),
        'child_ids': fields.one2many('msf.budget.line', 'parent_id', 'Child Lines'),
        'line_type': fields.selection([('view','View'),
                                       ('normal','Normal'),
                                       ('destination', 'Destination')], 'Line type', required=True),
        'account_code': fields.related('account_id', 'code', type='char', string='Account code', size=64, store=True),
    }

    _order = 'account_code asc, line_type desc'

    _defaults = {
        'line_type': 'normal',
    }
    
    def get_parent_line(self, cr, uid, vals, context=None):
        # Method to check if the used account has a parent,
        # and retrieve or create the corresponding parent line.
        # It also adds budget values to parent lines
        parent_account_id = False
        parent_line_ids = []
        if vals.get('account_id', False) and vals.get('budget_id', False):
            if 'destination_id' in vals:
                # Special case: the line has a destination, so the parent is a line
                # with the same account and no destination
                parent_account_id = vals['account_id']
                parent_line_ids = self.search(cr, uid, [('account_id', '=', vals['account_id']),
                                                        ('budget_id', '=', vals['budget_id']),
                                                        ('line_type', '=', 'normal')], context=context)
            else:
                # search for budget line
                account = self.pool.get('account.account').browse(cr, uid, vals['account_id'], context=context)
                chart_of_account_ids = self.pool.get('account.account').search(cr, uid, [('code', '=', 'MSF')], context=context)
                if account.parent_id and account.parent_id.id in chart_of_account_ids:
                    # no need to create the parent
                    return
                else:
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
                               'account_id': parent_account_id}
                if 'line_type' in vals and vals['line_type'] == 'destination':
                    parent_vals['line_type'] = 'normal'
                else:
                    parent_vals['line_type'] = 'view'
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
    
msf_budget_line()

class msf_budget(osv.osv):
    _name = "msf.budget"
    _inherit = "msf.budget"
    
    _columns = {
        'budget_line_ids': one2many_budget_lines('msf.budget.line', 'budget_id', 'Budget Lines'),
    }
    
msf_budget()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
