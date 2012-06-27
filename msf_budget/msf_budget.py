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
        
        for budget in self.browse(cr, uid, ids, context=context):
            total_amounts = self.pool.get('msf.budget.line')._get_total_amounts(cr, uid, [x.id for x in budget.budget_line_ids], context=context)
            
            budget_amount = 0.0
            for budget_line in budget.budget_line_ids:
                if not budget_line.parent_id:
                    res[budget.id] = total_amounts[budget_line.id]['budget_amount']
                    break
        
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
        'display_type': fields.selection([('all', 'Expenses and destinations'),
                                          ('expense', 'Expenses only'),
                                          ('view', 'Parent expenses only')], string="Display type"),
        'type': fields.selection([('normal', 'Normal'), ('view', 'View')], string="Budget type"),
        'total_budget_amount': fields.function(_get_total_budget_amounts, method=True, store=False, string="Total Budget Amount", type="float", readonly="True"),
    }
    
    _defaults = {
        'currency_id': lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
        'state': 'draft',
        'display_type': 'all',
        'type': 'normal',
    }

    _order = 'decision_moment_order desc, version, code'
    
    def create(self, cr, uid, vals, context=None):
        res = super(msf_budget, self).create(cr, uid, vals, context=context)
        # If the "parent" budget does not exist and we're not on the proprietary instance level already, create it.
        budget = self.browse(cr, uid, res, context=context)
        prop_instance_cost_center = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id.cost_center_id.id
        if budget.cost_center_id and budget.cost_center_id.id != prop_instance_cost_center and budget.cost_center_id.parent_id:
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
                # Create all lines for all accounts (no budget values, those are retrieved)
                expense_account_ids = self.pool.get('account.account').search(cr, uid, [('user_type_code', '=', 'expense'),
                                                                                        ('type', '!=', 'view')], context=context)
                for expense_account_id in expense_account_ids:
                    budget_line_vals = {'budget_id': parent_budget_id,
                                        'account_id': expense_account_id}
                    self.pool.get('msf.budget.line').create(cr, uid, budget_line_vals, context=context)
                # validate this parent
                self.write(cr, uid, [parent_budget_id], {'state': 'valid'}, context=context)
        return res
    
    # Methods for display view lines (warning, dirty, but it works)
    def button_display_type(self, cr, uid, ids, context=None, *args, **kwargs):
        """
        Change display type
        """
        display_types = {}
        for budget in self.read(cr, uid, ids, ['display_type']):
            display_types[budget['id']] = budget['display_type']
            
        for budget_id in ids:
            result = 'all'
            if display_types[budget_id] == 'all':
                result = 'expense'
            elif display_types[budget_id] == 'expense':
                result = 'view'
            elif display_types[budget_id] == 'view':
                result = 'all'
            self.write(cr, uid, [budget_id], {'display_type': result}, context=context)
        return True
    
    
    def budget_summary_open_window(self, cr, uid, ids, context=None):
        parent_line_id = False
        fiscalyear_id = self.pool.get('account.fiscalyear').find(cr, uid, datetime.date.today(), True, context=context)
        cost_center_ids = self.pool.get('account.analytic.account').search(cr, uid, [('category', '=', 'OC'), ('parent_id', '=', False)], context=context)                       
        if len(cost_center_ids) != 0:
            cr.execute("SELECT id FROM msf_budget WHERE fiscalyear_id = %s \
                                                    AND cost_center_id = %s \
                                                    AND state != 'draft' \
                                                    ORDER BY decision_moment_order DESC, version DESC LIMIT 1",
                                                    (fiscalyear_id,
                                                     cost_center_ids[0]))
            if cr.rowcount:
                # A budget was found
                budget_id = cr.fetchall()[0][0]
                parent_line_id = self.pool.get('msf.budget.summary').create(cr,
                                                                            uid,
                                                                            {'budget_id': budget_id},
                                                                            context=context)
        
        return {
               'type': 'ir.actions.act_window',
               'res_model': 'msf.budget.summary',
               'view_type': 'tree',
               'view_mode': 'tree',
               'target': 'current',
               'domain': [('id', '=', parent_line_id)],
               'context': context
        }
        
msf_budget()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
