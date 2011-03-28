# encoding: utf-8
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2008 PC Solutions (<http://pcsol.be>). All Rights Reserved
#    $Id$
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

class account_budget_definition(osv.osv):
    
    _inherit="crossovered.budget"
    
    _columns={
        'analytic_account_id': fields.many2one('account.analytic.account', 'Analytic Account',required=True),
        'decision_moment': fields.char('Decision Moment', size=32),
    }
    
    def write(self, cr, uid, ids, vals, context=None):
        # We have to set the analytic account and the dates on all budget lines
        budget_lines_obj = self.pool.get('crossovered.budget.lines')
        for budget_line_id in budget_lines_obj.search(cr, uid, [('crossovered_budget_id', '=', ids[0])]):
            
            budget_line_vals = {}
            
            if 'analytic_account_id' in vals:
                budget_line_vals['analytic_account_id'] = vals['analytic_account_id']
            if 'date_from' in vals:
                budget_line_vals['date_from'] = vals['date_from']
            if 'date_to' in vals:
                budget_line_vals['date_to'] = vals['date_to']
                
            budget_lines_obj.write(cr, uid, budget_line_id, budget_line_vals)
        
        return super(account_budget_definition,self).write(cr, uid, ids, vals, context)
    
    
account_budget_definition()

class crossovered_budget_definition_lines(osv.osv):
    _inherit="crossovered.budget.lines"
    
    _columns = {
        'general_budget_code': fields.related('general_budget_id', 'code', type="char", string="Budgetary Position Code", store=False)
    }
    
    def create(self, cr, uid, vals, context=None):
        # We have to retrieve the analytic account and the dates from the parent budget
        budget_obj = self.pool.get('crossovered.budget')
        budget_id = budget_obj.search(cr, uid, [('id', '=', vals['crossovered_budget_id'])])
        budget_attributes = budget_obj.read(cr, uid, budget_id, ['analytic_account_id', 'date_from', 'date_to'])[0]                        
                    
        if 'analytic_account_id' in budget_attributes:
            vals['analytic_account_id'] = budget_attributes['analytic_account_id'][0]
        if 'date_from' in budget_attributes:
            vals['date_from'] = budget_attributes['date_from']
        if 'date_to' in budget_attributes:
            vals['date_to'] = budget_attributes['date_to']
        
        return super(crossovered_budget_definition_lines,self).create(cr, uid, vals, context)
    
    
crossovered_budget_definition_lines()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
