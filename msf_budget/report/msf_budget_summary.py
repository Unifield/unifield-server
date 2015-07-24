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


class msf_budget_summary(osv.osv_memory):
    _name = "msf.budget.summary"
    
    _action_budget_summary_line_label = 'Budget lines'

    def _get_analytic_domain(self, cr, uid, summary_id, context=None):
        summary_line = self.browse(cr, uid, summary_id, context=context)
        cost_center_ids = self.pool.get('msf.budget.tools')._get_cost_center_ids(cr, uid, summary_line.budget_id.cost_center_id)

        return [('cost_center_id', 'in', cost_center_ids),
                ('date', '>=', summary_line.budget_id.fiscalyear_id.date_start),
                ('date', '<=', summary_line.budget_id.fiscalyear_id.date_stop)]

    def _get_amounts(self, cr, uid, ids, field_names=None, arg=None, context=None):
        """
        Fetch total budget amount from the linked budget
        Fetch actual amount (all analytic lines) for the given budgets and its childs.
        """
        # Prepare some values
        res = {}
        for summary_line in self.browse(cr, uid, ids, context=context):
            actual_amount = 0.0
            budget_amount = 0.0
            if summary_line.budget_id.type == 'view':
                for child_line in summary_line.child_ids:
                    child_amounts = self._get_amounts(cr, uid, [child_line.id], context=context)
                    actual_amount += child_amounts[child_line.id]['actual_amount']
                    budget_amount += child_amounts[child_line.id]['budget_amount']
            else:
                #  Budget Amount (use total budget amount field)
                budget_amount = summary_line.budget_id.total_budget_amount
                # Actual amount is the sum of amount of all analytic lines that correspond to the budget elements (commitments included)
                sql = """
                    SELECT SUM(amount)
                    FROM account_analytic_line
                    WHERE cost_center_id = %s
                    AND date >= %s
                    AND date <= %s
                """
                cc_id = summary_line.budget_id.cost_center_id.id
                date_start = summary_line.budget_id.fiscalyear_id.date_start
                date_stop = summary_line.budget_id.fiscalyear_id.date_stop
                # REF-25 Improvement: Use a SQL request instead of browse
                cr.execute(sql, (cc_id, date_start, date_stop))
                if cr.rowcount:
                    tmp_res = cr.fetchall()
                    tmp_amount = tmp_res and tmp_res[0] and tmp_res[0][0] or 0.0
                    actual_amount += tmp_amount

            actual_amount = abs(actual_amount)
            res[summary_line.id] = {
                'actual_amount': actual_amount,
                'budget_amount': budget_amount,
                'balance_amount': budget_amount - actual_amount,  # utp-857
            }
        return res

    _columns = {
        'budget_id': fields.many2one('msf.budget', 'Budget', required=True),
        
        'name': fields.related('budget_id', 'name', type="char", string="Budget Name", store=False),
        'code': fields.related('budget_id', 'code', type="char", string="Budget Code", store=False),
        'budget_amount': fields.function(_get_amounts, method=True, store=False, string="Budget Amount", type="float", multi="all"),
        'actual_amount': fields.function(_get_amounts, method=True, store=False, string="Actual Amount", type="float", multi="all"),
        'balance_amount': fields.function(_get_amounts, method=True, store=False, string="Balance Amount", type="float", multi="all"),  # utp-857
        
        'parent_id': fields.many2one('msf.budget.summary', 'Parent'),
        'child_ids': fields.one2many('msf.budget.summary', 'parent_id', 'Children'),
    }

    _defaults = {
        'parent_id': lambda *a: False
    }

    def create(self, cr, uid, vals, context=None):
        """
        Create a summary line for each child of the cost center used by the budget given in vals
        """
        # Some checks
        if context is None:
            context = {}
        # Prepare some values
        sql = """
            SELECT id
            FROM msf_budget
            WHERE fiscalyear_id = %s
            AND cost_center_id = %s
            AND decision_moment_id = %s
            AND state != 'draft'
            ORDER BY version DESC
            LIMIT 1"""
        res = super(msf_budget_summary, self).create(cr, uid, vals, context=context)
        if 'budget_id' in vals:
            budget = self.pool.get('msf.budget').read(cr, uid, vals['budget_id'], ['fiscalyear_id', 'decision_moment_id', 'cost_center_id'], context=context)
            if budget.get('cost_center_id', False):
                itself = budget.get('cost_center_id')[0]
                cost_center = self.pool.get('account.analytic.account').read(cr, uid, itself, ['child_ids'])
                for child_id in cost_center.get('child_ids', []):
                    cr.execute(sql, (budget.get('fiscalyear_id', [False])[0], child_id, budget.get('decision_moment_id', [False])[0]))
                    if cr.rowcount:
                        child_budget_id = cr.fetchall()[0][0]
                        self.create(cr, uid, {'budget_id': child_budget_id, 'parent_id': res}, context=context)
        return res
        
    def action_open_budget_summary_budget_lines(self, cr, uid, ids, context=None):
        res = {}
        if context is None:
            context = {}
            
        mb_obj = self.pool.get('msf.budget')
        mbs_obj = self.pool.get('msf.budget.summary')
        mbsl_obj = self.pool.get('msf.budget.summary.line')
            
        # get summary line
        summary_line_id = context.get('active_id', False)
        if not summary_line_id:
            return res
        # search for the line to validate it truly exists as osv.memory
        check_ids = mbs_obj.search(cr, uid, [
            ('id', '=', summary_line_id),
        ], context=context)
        if not check_ids:
            return res
        
        # get relating budget needed data (read for perfs)
        summary_r = mbs_obj.read(cr, uid, [summary_line_id],
            ['budget_id', 'child_ids', ], context=context)[0]
        # abort if no budget found or not a last level summary node (perfs)
        if not summary_r['budget_id']:
            raise osv.except_osv(_('Error'), _('Budget not found'))
        if summary_r['child_ids']:
            raise osv.except_osv(_('Warning'),
                _('Only childest budget is drillable'))
        budget_id = summary_r['budget_id']
        budget_code = mb_obj.read(cr, uid, [budget_id], ['code', ],
            context=context)[0]['code']
        
        # build tree
        context['granularity'] = 'expense'
        root_id = mbsl_obj.build_tree(cr, uid, budget_id, context=context)
        
        # set action
        name = budget_code or ''
        name += self._action_budget_summary_line_label
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid,
            'msf_budget', 'view_msf_budget_summary_budget_line_tree')[1]
        res = {
            'name': name,
            'type': 'ir.actions.act_window',
            'res_model': 'msf.budget.summary.line',
            'view_type': 'tree',
            'view_mode': 'tree',
            'view_id': [view_id],
            'domain': [('id', '=', root_id)],
            'context': context,
        }
        
        return res

msf_budget_summary()


class msf_budget_summary_line(osv.osv_memory):
    _name = "msf.budget.summary.line"

    _columns = {
        'budget_id': fields.many2one('msf.budget', 'Budget', required=True),
        'budget_line_id': fields.many2one('msf.budget.line', 'Budget Line', required=True),
        
        'name': fields.related('budget_line_id', 'name', type="char", string="Budget Name", store=False),
        'budget_amount': fields.related('budget_line_id', 'budget_amount', type="float", string="Budget Amount", store=False),
        'actual_amount': fields.related('budget_line_id', 'actual_amount', type="float", string="Actual Amount", store=False),
        'balance_amount': fields.related('budget_line_id', 'balance', type="float", string="Balance Amount", store=False),
 
        'parent_id': fields.many2one('msf.budget.summary.line', 'Parent'),
        'child_ids': fields.one2many('msf.budget.summary.line', 'parent_id', 'Children'),
    }

    _defaults = {
        'parent_id': lambda *a: False
    }
    
    _float_fields_to_fix = [
        'budget_amount',
        'actual_amount',
        'balance_amount',
    ]
    
    def read(self, cr, uid, ids, fields, context=None, load='_classic_write'):
        res = super(msf_budget_summary_line, self).read(cr, uid, ids, fields,
            context=context, load=load)
        
        for r in res:
            for f in self._float_fields_to_fix:
                if f in r and not r[f]:
                   r[f] = 0.
        return res

    def build_tree(self, cr, uid, budget_id, context=None):
        mbl_obj = self.pool.get('msf.budget.line')
        
        id = False
        root_id = False
        parent_level_ids = {}
        
        budget_lines_ids = mbl_obj.search(cr, uid, [
            ('budget_id', '=', budget_id),
            ('line_type', 'in', ('view', 'normal')),
        ], context=context)
 
        for bl_r in mbl_obj.read(cr, uid, budget_lines_ids, ['name'],
            context=context):
                
            # get account level                
            parts = bl_r['name'].split(' ')
            account = parts[0]
            len_account = len(account)
    
            # set parent from level
            if len_account == 1:
                parent_id = False
            elif 1 < len_account < 4:
                parent_id = parent_level_ids.get(len_account - 1, False)
            elif len_account == 5:
                parent_id = parent_level_ids.get(3, False)
            else:
                parent_id = False
            
            # set vals
            vals = {
                'budget_id': budget_id,
                'budget_line_id': bl_r['id'],
                'parent_id': parent_id,
            }
            id = self.create(cr, uid, vals, context=context)
            if not id:
                break
            if not root_id:
               root_id = id 
                
            # update parent for next iteration
            if 1 <= len_account < 4:
                parent_level_ids[len_account] = id
                
        return root_id
 
msf_budget_summary_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
