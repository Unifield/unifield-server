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
    
    def _get_amounts(self, cr, uid, ids, field_names=None, arg=None, context=None):
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
                #  Budget Amount, normal budget
                for budget_line in summary_line.budget_id.budget_line_ids:
                    if budget_line.line_type == 'normal' and budget_line.budget_values:
                        budget_amount += sum(eval(budget_line.budget_values))
                # Actual amount, normal budget
                actual_domain = [('account_id', '=', summary_line.budget_id.cost_center_id.id)]
                actual_domain.append(('date', '>=', summary_line.budget_id.fiscalyear_id.date_start))
                actual_domain.append(('date', '<=', summary_line.budget_id.fiscalyear_id.date_stop))
                analytic_line_obj = self.pool.get('account.analytic.line')
                analytic_lines = analytic_line_obj.search(cr, uid, actual_domain ,context=context)
                for analytic_line in analytic_line_obj.browse(cr, uid, analytic_lines, context=context):
                    actual_amount += analytic_line.amount
            
            res[summary_line.id] = {'actual_amount': actual_amount,
                                    'budget_amount': budget_amount}
            
        return res
    
    _columns = {
        'budget_id': fields.many2one('msf.budget', 'Budget', required=True),
        'name': fields.related('budget_id', 'name', type="char", string="Budget Name", store=False),
        'code': fields.related('budget_id', 'code', type="char", string="Budget Code", store=False),
        'budget_amount': fields.function(_get_amounts, method=True, store=False, string="Budget Amount", type="float", multi="all"),
        'actual_amount': fields.function(_get_amounts, method=True, store=False, string="Actual Amount", type="float", multi="all"),
        'parent_id': fields.many2one('msf.budget.summary', 'Parent'),
        'child_ids': fields.one2many('msf.budget.summary', 'parent_id', 'Children'),
    }
    
    _defaults = {
        'parent_id': lambda *a: False
    }
    
    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        res = super(msf_budget_summary, self).create(cr, uid, vals, context=context)
        if 'budget_id' in vals:
            budget = self.pool.get('msf.budget').browse(cr, uid, vals['budget_id'], context=context)
            if budget.cost_center_id:
                for child_cc in budget.cost_center_id.child_ids:
                    cr.execute("SELECT id FROM msf_budget WHERE fiscalyear_id = %s \
                                                            AND cost_center_id = %s \
                                                            AND state != 'draft' \
                                                            ORDER BY version DESC LIMIT 1",
                                                           (budget.fiscalyear_id.id,
                                                            child_cc.id))
                    if cr.rowcount:
                        child_budget_id = cr.fetchall()[0][0]
                        child_line_id = self.create(cr, uid, {'budget_id': child_budget_id,
                                                              'parent_id': res}, context=context)
        return res

msf_budget_summary()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
