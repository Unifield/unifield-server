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

# Overloading the one2many.get for budget lines to filter regarding context.
class one2many_budget_lines(fields.one2many):
    
    def get(self, cr, obj, ids, name, uid=None, offset=0, context=None, values=None):
        if context is None:
            context = {}
        if values is None:
            values = {}
        res = {}
        display_type = {}

        domain = ['view', 'normal', 'destination']
        tuples = {
            'parent': ['view'],
            'account': ['view', 'normal'],
            'destination': domain,
        }
        line_obj = obj.pool.get('msf.budget.line')

        if 'granularity' in context:
            display_type = context.get('granularity', False)
            if display_type and display_type in ['parent', 'account', 'destination']:
                domain = tuples[display_type]

        for budget_id in ids:
            res[budget_id] = line_obj.search(cr, uid, [('budget_id', '=', budget_id), ('line_type', 'in', domain)])

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

    def _get_amounts(self, cr, uid, ids, field_names=None, arg=None, context=None):
        """
        Those field can be asked for:
          - actual_amount
          - comm_amount
          - balance
          - percentage
        With some depends:
          - percentage needs actual_amount, comm_amount, balance and budget_amount
          - balance needs actual_amount, comm_amount and budget_amount
        """
        # Some checks
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        budget_ok = False
        actual_ok = False
        commitment_ok = False
        percentage_ok = False
        balance_ok = False
        budget_amounts = {}
        actual_amounts = {}
        comm_amounts = {}
        # Check in which case we are regarding field names. Compute actual and commitment when we need balance and/or percentage.
        if 'budget_amount' in field_names:
            budget_ok = True
        if 'actual_amount' in field_names:
            actual_ok = True
        if 'comm_amount' in field_names:
            actual_ok = True
            commitment_ok = True
        if 'percentage' in field_names:
            budget_ok = True
            actual_ok = True
            commitment_ok = True
            percentage_ok = True
        if 'balance'in field_names:
            budget_ok = True
            actual_ok = True
            commitment_ok = True
            balance_ok = True
        # Compute actual and/or commitments
        if actual_ok or commitment_ok or percentage_ok or balance_ok:
            # COMPUTE ACTUAL/COMMITMENT
            ana_obj = self.pool.get('account.analytic.line')
            company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
            cur_obj = self.pool.get('res.currency')
            # Create default values
            for index in ids:
                if actual_ok:
                    actual_amounts.setdefault(index, 0.0)
                if commitment_ok:
                    comm_amounts.setdefault(index, 0.0)
            # Now, only use 'destination' line to do process and complete parent one at the same time
            sql = """
                SELECT l.id, l.line_type, l.account_id, l.destination_id, b.cost_center_id, b.currency_id, f.date_start, f.date_stop
                FROM msf_budget_line AS l, msf_budget AS b, account_fiscalyear AS f
                WHERE l.budget_id = b.id
                AND b.fiscalyear_id = f.id
                AND l.id IN %s
                ORDER BY l.line_type, l.id;
            """
            cr.execute(sql, (tuple(ids),))
            # Prepare SQL2 request that contains sum of amount of given analytic lines (in functional currency)
            sql2 = """
                SELECT SUM(amount)
                FROM account_analytic_line
                WHERE id in %s;"""
            # Process destination lines
            for line in cr.fetchall():
                # fetch some values
                line_id, line_type, account_id, destination_id, cost_center_id, currency_id, date_start, date_stop = line
                criteria = [
                    ('cost_center_id', '=', cost_center_id),
                    ('date', '>=', date_start),
                    ('date', '<=', date_stop),
                ]
                if line_type == 'destination':
                    criteria.append(('destination_id', '=', destination_id))
                if line_type in ['destination', 'normal']:
                    criteria.append(('general_account_id', '=', account_id)),
                else:
                    criteria.append(('general_account_id', 'child_of', account_id))
                # fill in ACTUAL AMOUNTS
                if actual_ok:
                    actual_criteria = criteria + [('journal_id.type', '!=', 'engagement')]
                    ana_ids = ana_obj.search(cr, uid, actual_criteria)
                    if ana_ids:
                        cr.execute(sql2, (tuple(ana_ids),))
                        mnt_result = cr.fetchall()
                        if mnt_result:
                                actual_amounts[line_id] += mnt_result[0][0] * -1
                # fill in COMMITMENT AMOUNTS
                if commitment_ok:
                    commitment_criteria = criteria + [('journal_id.type', '=', 'engagement')]
                    ana_ids = ana_obj.search(cr, uid, commitment_criteria)
                    if ana_ids:
                        cr.execute(sql2, (tuple(ana_ids),))
                        mnt_result = cr.fetchall()
                        if mnt_result:
                            comm_amounts[line_id] += mnt_result[0][0] * -1

        # Budget line amounts
        if budget_ok:
            sql = """
            SELECT id, COALESCE(month1 + month2 + month3 + month4 + month5 + month6 + month7 + month8 + month9 + month10 + month11 + month12, 0.0)
            FROM msf_budget_line
            WHERE id IN %s;
            """
            cr.execute(sql, (tuple(ids),))
            tmp_res = cr.fetchall()
            if tmp_res:
                budget_amounts = dict(tmp_res)
        # Prepare result
        for line_id in ids:
            actual_amount = line_id in actual_amounts and actual_amounts[line_id] or 0.0
            comm_amount = line_id in comm_amounts and comm_amounts[line_id] or 0.0
            res[line_id] = {'actual_amount': actual_amount, 'comm_amount': comm_amount, 'balance': 0.0, 'percentage': 0.0, 'budget_amount': 0.0,}
            if budget_ok:
                budget_amount = line_id in budget_amounts and budget_amounts[line_id] or 0.0
                res[line_id].update({'budget_amount': budget_amount,})
            if balance_ok:
                balance = budget_amount - actual_amount - comm_amount
                res[line_id].update({'balance': balance,})
            if percentage_ok:
                if budget_amount != 0.0:
                    percentage = round((actual_amount + comm_amount) / budget_amount * 100.0)
                    res[line_id].update({'percentage': percentage,})
        return res

    def _get_total(self, cr, uid, ids, field_names=None, arg=None, context=None):
        """
        Give the sum of all month for the given budget lines
        """
        # Some checks
        if isinstance(ids,(int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        sql = """
            SELECT id, month1 + month2 + month3 + month4 + month5 + month6 + month7 + month8 + month9 + month10 + month11 + month12
            FROM msf_budget_line
            WHERE id IN %s"""
        cr.execute(sql, (tuple(ids),))
        tmp_res = cr.fetchall()
        if tmp_res:
            res = dict(tmp_res)
        return res

    _columns = {
        'budget_id': fields.many2one('msf.budget', 'Budget', ondelete='cascade'),
        'account_id': fields.many2one('account.account', 'Account', required=True, domain=[('type', '!=', 'view')]),
        'destination_id': fields.many2one('account.analytic.account', 'Destination', domain=[('category', '=', 'DEST')]),
        'name': fields.function(_get_name, method=True, store=False, string="Name", type="char", readonly="True", size=512),
        'month1': fields.float("Month 01"),
        'month2': fields.float("Month 02"),
        'month3': fields.float("Month 03"),
        'month4': fields.float("Month 04"),
        'month5': fields.float("Month 05"),
        'month6': fields.float("Month 06"),
        'month7': fields.float("Month 07"),
        'month8': fields.float("Month 08"),
        'month9': fields.float("Month 09"),
        'month10': fields.float("Month 10"),
        'month11': fields.float("Month 11"),
        'month12': fields.float("Month 12"),
        'total': fields.function(_get_total, method=True, store=False, string="Total", type="float", readonly=True, help="Get all month total amount"),
        'budget_values': fields.char('Budget Values (list of float to evaluate)', size=256),
        'budget_amount': fields.function(_get_amounts, method=True, store=False, string="Budget amount", type="float", readonly=True, multi="budget_amounts"),
        'actual_amount': fields.function(_get_amounts, method=True, store=False, string="Actual amount", type="float", readonly=True, multi="budget_amounts"),
        'comm_amount': fields.function(_get_amounts, method=True, store=False, string="Commitments amount", type="float", readonly=True, multi="budget_amounts"),
        'balance': fields.function(_get_amounts, method=True, store=False, string="Balance", type="float", readonly=True, multi="budget_amounts"),
        'percentage': fields.function(_get_amounts, method=True, store=False, string="Percentage", type="float", readonly=True, multi="budget_amounts"),
        'parent_id': fields.many2one('msf.budget.line', 'Parent Line'),
        'child_ids': fields.one2many('msf.budget.line', 'parent_id', 'Child Lines'),
        'line_type': fields.selection([('view','View'),
                                       ('normal','Normal'),
                                       ('destination', 'Destination')], 'Line type', required=True),
        'account_code': fields.related('account_id', 'code', type='char', string='Account code', size=64, store=True),
    }

    _order = 'account_code asc, line_type desc'

    _defaults = {
        'line_type': lambda *a: 'normal',
        'month1': lambda *a: 0.0,
        'month2': lambda *a: 0.0,
        'month3': lambda *a: 0.0,
        'month4': lambda *a: 0.0,
        'month5': lambda *a: 0.0,
        'month6': lambda *a: 0.0,
        'month7': lambda *a: 0.0,
        'month8': lambda *a: 0.0,
        'month9': lambda *a: 0.0,
        'month10': lambda *a: 0.0,
        'month11': lambda *a: 0.0,
        'month12': lambda *a: 0.0,
    }
    
    def get_parent_line(self, cr, uid, vals, context=None):
        # Method to check if the used account has a parent,
        # and retrieve or create the corresponding parent line.
        # It also adds budget values to parent lines. FIXME: improve this to also impact parents that are more than 1 depth (using parent_left for an example)
        parent_account_id = False
        parent_line_ids = []
        parent_vals = {}
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
                # check which month is given in vals
                months = []
                month_vals = {}
                month_in_vals = False
                for index in xrange(1, 13, 1):
                    month = 'month'+str(index)
                    if month in vals:
                        month_in_vals = True
                        months.append(month)
                        # keep month values for parent account
                        month_vals.update({month: vals[month],})
                    else:
                        month_vals.update({month: 0.0,})
                # fetch these months from the parent line and update them with new ones
                if month_in_vals:
                    parent_data = self.read(cr, uid, parent_line_ids[0], months + ['account_id', 'budget_id'], context=context)
                    parent_new_vals = {}
                    for fieldname in parent_data:
                        if fieldname.startswith('month'):
                            parent_new_vals.update({fieldname: parent_data[fieldname] + vals[fieldname]})
                    super(msf_budget_line, self).write(cr, uid, parent_line_ids[0], parent_new_vals, context=context)
                    # use method on parent with original budget values
                    parent_vals = {
                        'account_id': parent_data.get('account_id', [False])[0],
                        'budget_id': parent_data.get('budget_id', [False])[0],
                    }
                    parent_vals.update(month_vals)
                    self.get_parent_line(cr, uid, parent_vals, context=context)
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
                month_vals = {}
                month_in_vals = False
                for index in xrange(1, 13, 1):
                    month = 'month'+str(index)
                    if month in vals:
                        month_in_vals = True
                        month_vals.update({month: vals[month]})
                    else:
                        month_vals.update({month: 0.0})
                if month_in_vals:
                    parent_vals.update(month_vals)
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
