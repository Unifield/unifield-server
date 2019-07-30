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
from tools.translate import _

import datetime

class msf_budget(osv.osv):
    _name = "msf.budget"
    _description = 'MSF Budget'
    _trace = True

    def _get_total_budget_amounts(self, cr, uid, ids, field_names=None, arg=None, context=None):
        res = {}
        sql = """
        SELECT expense.budget_id, COALESCE(expense.total, 0.0) - COALESCE(income.total, 0.0) AS diff
        FROM (
            SELECT budget_id, SUM(COALESCE(month1 + month2 + month3 + month4 + month5 + month6 + month7 + month8 + month9 + month10 + month11 + month12, 0.0)) AS total
            FROM msf_budget_line AS l, account_account AS a, account_account_type AS t
            WHERE budget_id IN %s
            AND l.account_id = a.id
            AND a.user_type = t.id
            AND t.code = 'expense'
            AND a.type != 'view'
            AND l.line_type = 'destination'
            GROUP BY budget_id
        ) AS expense
        LEFT JOIN (
            SELECT budget_id, SUM(COALESCE(month1 + month2 + month3 + month4 + month5 + month6 + month7 + month8 + month9 + month10 + month11 + month12, 0.0)) AS total
            FROM msf_budget_line AS l, account_account AS a, account_account_type AS t
            WHERE budget_id IN %s
            AND l.account_id = a.id
            AND a.user_type = t.id
            AND t.code = 'income'
            AND a.type != 'view'
            AND l.line_type = 'destination'
            GROUP BY budget_id
        ) AS income ON expense.budget_id = income.budget_id"""
        cr.execute(sql, (tuple(ids),tuple(ids),))
        tmp_res = cr.fetchall()
        if not tmp_res:
            return res
        for b_id in ids:
            res.setdefault(b_id, 0.0)
        res.update(dict(tmp_res))
        return res

    def _get_instance_type(self, cr, uid, ids, field_names=None, arg=None, context=None):
        """
        Retrieve instance type regarding cost center id and check on instances which one have this cost center as "top cost center for budget"
        """
        if not context:
            context = {}
        res = {}
        for budget in self.browse(cr, uid, ids):
            res[budget.id] = 'project'
            if budget.cost_center_id:
                target_ids = self.pool.get('account.target.costcenter').search(cr, uid, [('cost_center_id', '=', budget.cost_center_id.id), ('is_top_cost_center', '=', True), ('instance_id.level', '=', 'coordo')])
                if target_ids:
                    res[budget.id] = 'coordo'
            if not budget.cost_center_id.parent_id:
                res[budget.id] = 'section'
        return res

    def _search_instance_type(self, cr, uid, obj, name, args, context=None):
        """
        Search all budget that have a cost coster used in a top_cost_center for an instance for the given type
        """
        res = []
        if not context:
            context = {}
        if not args:
            return res
        if args[0] and args[0][2]:
            target_ids = self.pool.get('account.target.costcenter').search(cr, uid, [('is_top_cost_center', '=', True), ('instance_id.level', '=', 'coordo')])
            coordo_ids = [x and x.cost_center_id and x.cost_center_id.id for x in self.pool.get('account.target.costcenter').browse(cr, uid, target_ids)]
            hq_ids = self.pool.get('account.analytic.account').search(cr, uid, [('parent_id', '=', False)])
            if isinstance(hq_ids, (int, long)):
                hq_ids = [hq_ids]
            if args[0][2] == 'section':
                return [('cost_center_id', 'in', hq_ids)]
            elif args[0][2] == 'coordo':
                return [('cost_center_id', 'in', coordo_ids)]
            elif args[0][2] == 'project':
                return [('cost_center_id', 'not in', hq_ids), ('cost_center_id', 'not in', coordo_ids)]
        return res

    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'code': fields.char('Code', size=64, required=True),
        'fiscalyear_id': fields.many2one('account.fiscalyear', 'Fiscal Year', required=True),
        'state': fields.selection([('draft','Draft'),('valid','Validated'),('done','Done')], 'State', select=True, required=True),
        'cost_center_id': fields.many2one('account.analytic.account', 'Cost Center', domain=[('category', '=', 'OC'), ('type', '=', 'normal')], required=True),
        'decision_moment_id': fields.many2one('msf.budget.decision.moment', 'Decision Moment', required=True),
        'decision_moment_order': fields.related('decision_moment_id', 'order', string="Decision Moment Order", readonly=True, store=True, type="integer"),
        'version': fields.integer('Version'),
        'currency_id': fields.many2one('res.currency', 'Currency', required=True),
        'type': fields.selection([('normal', 'Normal'), ('view', 'View')], string="Budget type"),
        'total_budget_amount': fields.function(_get_total_budget_amounts, method=True, store=False, string="Total Budget Amount", type="float", readonly=True),
        'instance_type': fields.function(_get_instance_type, fnct_search=_search_instance_type, method=True, store=False, string='Instance type', type='selection', selection=[('section', 'HQ'), ('coordo', 'Coordo'), ('project', 'Project')], readonly=True),
    }

    _defaults = {
        'currency_id': lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
        'state': 'draft',
        'type': 'normal',
    }

    _order = 'decision_moment_order desc, version, code'

    def _check_parent(self, cr, uid, vals, context=None):
        """
        Check budget's parent to see if it exist.
        Create it if we're on another instance that top cost center one.
        Note: context can contains a list of budget lines. This permit to avoid problem of budget line template time consuming.
        We hope the copy() will take less time than the creation of an entire budget template.
        """
        # Some checks
        if context is None:
            context = {}
        # Prepare some values
        top_cost_center = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id.top_cost_center_id
        ana_obj = self.pool.get('account.analytic.account')
        fy_obj = self.pool.get('account.fiscalyear')
        tool_obj = self.pool.get('msf.budget.tools')
        # Fetch cost center info (id and parent)
        cc_id = vals.get('cost_center_id', False)
        cc = ana_obj.read(cr, uid, cc_id, ['parent_id'], context=context)
        parent_id = cc.get('parent_id', False) and cc.get('parent_id')[0] or False
        # Fetch fiscalyear info
        fy_id = vals.get('fiscalyear_id', False)
        fy = fy_obj.read(cr, uid, fy_id, ['code'])
        # Fetch decision moment id
        decision_moment_id = vals.get('decision_moment_id', False)

        # Check that no parent cost center exists for the given values
        if cc_id and cc_id != top_cost_center.id and parent_id:
            parent_cost_center = ana_obj.read(cr, uid, parent_id, ['code', 'name'], context=context)
            have_parent_budget = self.search(cr, uid, [('fiscalyear_id', '=', fy_id), ('cost_center_id', '=', parent_id), ('decision_moment_id', '=', decision_moment_id)], count=1, context=context)
            if have_parent_budget == 0:
                # Create budget's parent
                budget_vals = {
                    'name': "Budget " + fy.get('code', '')[4:6] + " - " + parent_cost_center.get('name', ''),
                    'code': "BU" + fy.get('code')[4:6] + " - " + parent_cost_center.get('code', ''),
                    'fiscalyear_id': fy_id,
                    'cost_center_id': parent_id,
                    'decision_moment_id': decision_moment_id,
                    'type': 'view'
                }
                parent_budget_id = self.create(cr, uid, budget_vals, context=context)
                # Create budget's line.
                tool_obj.create_budget_lines(cr, uid, parent_budget_id, context=context)
                # Validate this parent
                self.write(cr, uid, [parent_budget_id], {'state': 'valid'}, context=context)
        return True

    def create(self, cr, uid, vals, context=None):
        """
        Create a budget then check its parent.
        """
        res = super(msf_budget, self).create(cr, uid, vals, context=context)
        # Check parent budget
        self._check_parent(cr, uid, vals, context=context)
        return res

    def _get_children(self, cr, uid, cost_center_id, cc_children_list, context=None):
        """
        Updates cc_children_list with the children of the cost center whose id is in parameter
        Also adds the children's children, and so forth...
        """
        if context is None:
            context = {}
        analytic_acc_obj = self.pool.get('account.analytic.account')
        cc_children_ids = analytic_acc_obj.search(cr, uid, [('parent_id', '=', cost_center_id)], order='NO_ORDER', context=context)
        for cc_child_id in cc_children_ids:
            if cc_child_id not in cc_children_list:  # avoid process repetition and recursion issues
                cc_children_list.append(cc_child_id)
                if analytic_acc_obj.search_exist(cr, uid, [('parent_id', '=', cc_child_id)], context=context):
                    self._get_children(cr, uid, cc_child_id, cc_children_list, context)

    def _check_all_done(self, cr, uid, budget, cost_center_id, cc_children_list, context=None):
        """
        Returns True if all the children budgets have the state "done", False otherwise.
        """
        if context is None:
            context = {}
        self._get_children(cr, uid, cost_center_id, cc_children_list, context)  # update cc_children_list
        children_budget_ids = self.search(cr, uid, [('cost_center_id', 'in', cc_children_list),
                                                    ('decision_moment_id', '=', budget.decision_moment_id.id),
                                                    ('fiscalyear_id', '=', budget.fiscalyear_id.id),
                                                    ('id', '!=', budget.id)], order='NO_ORDER', context=context)
        children_budgets = self.read(cr, uid, children_budget_ids, ['state'], context=context)
        all_done = True
        for budget in children_budgets:
            if budget['state'] != 'done':
                all_done = False
                break
        return all_done

    def _set_to_done(self, cr, uid, budget, cost_center, cc_children_list, cc_parent_list, context=None):
        """
        Sets the state "done" to the parent of the Cost Center in parameter if all its children have the state "done".
        If so, does the same for the parent's parent, and so forth.
        """
        if context is None:
            context = {}
        cc_parent = cost_center.parent_id
        if cc_parent and self._check_all_done(cr, uid, budget, cc_parent.id, cc_children_list, context):
            cc_parent_list.append(cc_parent.id)
            budget_parent_ids = self.search(cr, uid,
                                            [('cost_center_id', '=', cc_parent.id),
                                             ('decision_moment_id', '=', budget.decision_moment_id.id),
                                             ('fiscalyear_id', '=', budget.fiscalyear_id.id),
                                             ('state', '!=', 'done')], order='NO_ORDER', context=context)
            self.write(cr, uid, budget_parent_ids, {'state': 'done'}, context=context)
            if cc_parent.parent_id and cc_parent.parent_id.id not in cc_parent_list:  # avoid recursion issues
                self._set_to_done(cr, uid, budget, cc_parent, cc_children_list, cc_parent_list, context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        Goal is to update parent budget regarding these criteria:
          - context is synchronization
          - state is in vals
          - state is different from draft (validated or done)
        """

        if not ids:
            return True
        if context is None:
            context = {}
        res = super(msf_budget, self).write(cr, uid, ids, vals, context=context)
        if context.get('sync_update_execution', False) and vals.get('state', False) and vals.get('state') != 'draft':
            # Update parent budget
            self.update_parent_budgets(cr, uid, ids, context=context)

        budget = self.browse(cr, uid, ids, context=context)[0]
        if budget.type == 'normal' and vals.get('state') == 'done':  # do not process for view accounts
            # set the parent budgets to 'done' IF all their children budgets are 'done'
            cc_children_list = []
            cc_parent_list = []
            self._set_to_done(cr, uid, budget, budget.cost_center_id, cc_children_list, cc_parent_list, context)
        return res

    def update(self, cr, uid, ids, context=None):
        """
        Update given budget. But only update view one.
        """
        # Some checks
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        ana_obj = self.pool.get('account.analytic.account')
        line_obj = self.pool.get('msf.budget.line')
        sql = """
            SELECT
                SUM(COALESCE(month1, 0)),
                SUM(COALESCE(month2, 0)),
                SUM(COALESCE(month3, 0)),
                SUM(COALESCE(month4, 0)),
                SUM(COALESCE(month5, 0)),
                SUM(COALESCE(month6, 0)),
                SUM(COALESCE(month7, 0)),
                SUM(COALESCE(month8, 0)),
                SUM(COALESCE(month9, 0)),
                SUM(COALESCE(month10, 0)),
                SUM(COALESCE(month11, 0)),
                SUM(COALESCE(month12, 0))
            FROM msf_budget_line
            WHERE id IN %s"""
        # Filter budget to only update those that are view one
        to_update = self.search(cr, uid, [('id', 'in', ids), ('type', '=', 'view')])
        # Then update budget, one by one, line by line...
        for budget in self.browse(cr, uid, to_update, context=context):
            cost_center_id = budget.cost_center_id and budget.cost_center_id.id or False
            if not cost_center_id:
                raise osv.except_osv(_('Error'), _('Problem while reading Cost Center for the given budget: %s') % (budget.get('name', ''),))
            child_cc_ids = ana_obj.search(cr, uid, [('parent_id', 'child_of', cost_center_id)])
            budget_ids = []
            # For each CC, search the last budget
            for cc_id in child_cc_ids:
                cc_args = [
                    ('cost_center_id', '=', cc_id),
                    ('type', '!=', 'view'),
                    ('state', '!=', 'draft'),
                    ('decision_moment_id', '=', budget.decision_moment_id.id),
                    ('fiscalyear_id', '=', budget.fiscalyear_id.id),
                ]
                corresponding_budget_ids = self.search(cr, uid, cc_args, limit=1, order='version DESC')
                if corresponding_budget_ids:
                    budget_ids.append(corresponding_budget_ids)
            # Browse each budget line to update it
            for budget_line in budget.budget_line_ids:
                line_vals = {
                    'month1': 0.0,
                    'month2': 0.0,
                    'month3': 0.0,
                    'month4': 0.0,
                    'month5': 0.0,
                    'month6': 0.0,
                    'month7': 0.0,
                    'month8': 0.0,
                    'month9': 0.0,
                    'month10': 0.0,
                    'month11': 0.0,
                    'month12': 0.0
                }
                # search all linked budget lines
                args = [('budget_id', 'in', budget_ids), ('account_id', '=', budget_line.account_id.id), ('line_type', '=', budget_line.line_type)]
                if budget_line.destination_id:
                    args.append(('destination_id', '=', budget_line.destination_id.id))
                child_line_ids = line_obj.search(cr, uid, args, context=context)
                if child_line_ids:
                    cr.execute(sql, (tuple(child_line_ids),))
                    if cr.rowcount:
                        tmp_res = cr.fetchall()
                        res = tmp_res and tmp_res[0]
                        if res:
                            for x in xrange(1, 13, 1):
                                try:
                                    line_vals.update({'month'+str(x): res[x - 1]})
                                except IndexError:
                                    continue
                line_obj.write(cr, uid, [budget_line.id], line_vals)
        return True

    def update_parent_budgets(self, cr, uid, ids, context=None):
        """
        Search all parent budget and update them.
        """
        # Some checks
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # We only need to update parent budgets.
        # So we search all parent cost center (but only them, so we don't care about cost center that are linked to given budgets)
        # Then we use these parent cost centers to find budgets to update (only budget lines), for the related fiscal year
        budgets = self.read(cr, uid, ids, ['cost_center_id'])
        cost_center_ids = [x.get('cost_center_id', False) and x.get('cost_center_id')[0] or 0 for x in budgets]
        cc_parent_ids = self.pool.get('account.analytic.account')._get_parent_of(cr, uid, cost_center_ids, context=context)
        parent_ids = [x for x in cc_parent_ids if x not in cost_center_ids]
        fiscal_years = {}
        for budg in self.read(cr, uid, ids, ['fiscalyear_id'], context=context):
            fiscal_years[budg.get('fiscalyear_id')[0]] = True
        for fy in fiscal_years.keys():
            to_update = self.search(cr, uid, [('cost_center_id', 'in', parent_ids), ('fiscalyear_id', '=', fy)])
            # Update budgets
            self.update(cr, uid, to_update, context=context)
        return True

    def button_display_type(self, cr, uid, ids, context=None, *args, **kwargs):
        """
        Just reset the budget view to give the context to the one2many_budget_lines object
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # do not erase the previous context!
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        return {
            'name': _('Budgets'),
            'type': 'ir.actions.act_window',
            'res_model': 'msf.budget',
            'target': 'crush',
            'view_mode': 'form,tree',
            'view_type': 'form',
            'res_id': ids[0],
            'context': context,
        }

    def budget_summary_open_window(self, cr, uid, ids, context=None):
        budget_id = False
        if not ids:
            fiscalyear_id = self.pool.get('account.fiscalyear').find(cr, uid, datetime.date.today(), True, context=context)
            prop_instance = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
            if prop_instance.top_cost_center_id:
                cr.execute("SELECT id FROM msf_budget WHERE fiscalyear_id = %s \
                            AND cost_center_id = %s \
                            AND state != 'draft' \
                            ORDER BY decision_moment_order DESC, version DESC LIMIT 1",
                           (fiscalyear_id,
                            prop_instance.top_cost_center_id.id))
                if cr.rowcount:
                    # A budget was found
                    budget_id = cr.fetchall()[0][0]
        else:
            if isinstance(ids, (int, long)):
                ids = [ids]
            budget_id = ids[0]

        if budget_id:
            parent_line_id = self.pool.get('msf.budget.summary').create(cr,
                                                                        uid, {'budget_id': budget_id}, context=context)
            if parent_line_id:
                context.update({'display_fp': True})
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'msf.budget.summary',
                    'view_type': 'tree',
                    'view_mode': 'tree',
                    'target': 'current',
                    'domain': [('id', '=', parent_line_id)],
                    'context': context
                }
        return {}

    def action_confirmed(self, cr, uid, ids, context=None):
        """
        At budget validation we should update all parent budgets.
        To do this, each parent need to take all its validated children budget at the last version.
        """
        # Some checks
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Only validate budget that are draft!
        to_validate = []
        for budget in self.read(cr, uid, ids, ['state']):
            if budget.get('state', '') and budget.get('state') == 'draft':
                to_validate.append(budget.get('id', 0))
        # Change budget statuses. Important in order to include given budgets in their parents!
        self.write(cr, uid, to_validate, {'state': 'valid'}, context=context)
        # Update parent budget
        self.update_parent_budgets(cr, uid, to_validate, context=context)
        return True

    def unlink(self, cr, uid, ids, context=None):
        '''
        UFTP-156: Make sure that the validated budget cannot be deleted
        '''
        for budget in self.browse(cr, uid, ids, context=context):
            if budget.state == 'valid':
                raise osv.except_osv(_('Error'), _('You cannot delete the validated budget!'))

        return super(msf_budget, self).unlink(cr, uid, budget.id, context=context)

msf_budget()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
