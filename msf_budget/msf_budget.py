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
    
    def create(self, cr, uid, vals, context=None):
        res = super(msf_budget, self).create(cr, uid, vals, context=context)
        # If the "parent" budget does not exist and we're not on the proprietary instance level already, create it.
        budget = self.browse(cr, uid, res, context=context)
        prop_instance = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
        if prop_instance.top_cost_center_id and budget.cost_center_id and budget.cost_center_id.id != prop_instance.top_cost_center_id.id and budget.cost_center_id.parent_id:
            parent_cost_center = budget.cost_center_id.parent_id
            parent_budget_ids = self.search(cr,
                                            uid,
                                            [('fiscalyear_id','=',budget.fiscalyear_id.id),
                                             ('cost_center_id','=',parent_cost_center.id),
                                             ('decision_moment_id','=',budget.decision_moment_id.id)])
            if len(parent_budget_ids) == 0:
                parent_budget_id = self.create(cr,
                                               uid,
                                               {'name': "Budget " + budget.fiscalyear_id.code[4:6] + " - " + parent_cost_center.name,
                                                'code': "BU" + budget.fiscalyear_id.code[4:6] + " - " + parent_cost_center.code,
                                                'fiscalyear_id': budget.fiscalyear_id.id,
                                                'cost_center_id': budget.cost_center_id.parent_id.id,
                                                'decision_moment_id': budget.decision_moment_id.id,
                                                'type': 'view'}, context=context)
                # Create all lines for all accounts/destinations (no budget values, those are retrieved)
                expense_account_ids = self.pool.get('account.account').search(cr, uid, [('is_analytic_addicted', '=', True),
                                                                                        ('user_type_report_type', '!=', 'none'),
                                                                                        ('type', '!=', 'view')], context=context)
                destination_obj = self.pool.get('account.destination.link')
                destination_link_ids = destination_obj.search(cr, uid, [('account_id', 'in',  expense_account_ids)], context=context)
                account_destination_ids = [(dest.account_id.id, dest.destination_id.id)
                                           for dest
                                           in destination_obj.browse(cr, uid, destination_link_ids, context=context)]
                for account_id, destination_id in account_destination_ids:
                    budget_line_vals = {'budget_id': parent_budget_id,
                                        'account_id': account_id,
                                        'destination_id': destination_id,
                                        'line_type': 'destination'}
                    self.pool.get('msf.budget.line').create(cr, uid, budget_line_vals, context=context)
                # validate this parent
                self.write(cr, uid, [parent_budget_id], {'state': 'valid'}, context=context)
        return res
    
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
        
msf_budget()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
