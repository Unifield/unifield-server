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

class msf_budget(osv.osv):
    _name = "msf.budget"
    
    _columns={
        'name': fields.char('Name', size=64, required=True),
        'code': fields.char('Code', size=16, required=True),
        'fiscalyear_id': fields.many2one('account.fiscalyear', 'Fiscal Year', required=True),
        'state': fields.selection([('draft','Draft'),('validate','Validated'),('done','Done')], 'State', select=True, required=True),
        'cost_center_id': fields.many2one('account.analytic.account', 'Cost Center', domain=[('category', '=', 'OC'), ('type', '=', 'normal')], required=True),
        'decision_moment': fields.char('Decision Moment', size=32, required=True),
        'version': fields.integer('Version',required=True),
        'currency_id': fields.many2one('res.currency', 'Currency', required=True),
        'budget_line_ids': fields.one2many('msf.budget.line', 'budget_id', 'Budget Lines'),
    }
    
    _defaults = {
        'currency_id': lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
        'version': 1,
        'state': 'draft',
    }

    def copy(self, cr, uid, id, defaults={}, context={}):
        budget = self.browse(cr, uid, id, context=context)
        defaults.update({'version': budget.version + 1})
        return super(msf_budget,self).copy(cr, uid, id, defaults, context=context)

msf_budget()

class msf_budget_line(osv.osv):
    _name = "msf.budget.line"
    
    def _get_amounts(self, cr, uid, ids, field_names=None, arg=None, context=None):
        res = {}
        if context is None:
            context = {}
        # global values
        engagement_journal_ids = self.pool.get('account.analytic.journal').search(cr, uid, [('code', '=', 'ENG')], context=context)
        
        # Browse each line
        for budget_line in self.browse(cr, uid, ids, context=context):
            budget_amount = 0.0
            actual_amount = 0.0
            month_stop = 0
            actual_domain = []
            budget_value_list = eval(budget_line.budget_values)
            # "Global" domain: cost center, account, date must be after fiscal year's start
            actual_domain.append(('general_account_id', '=', budget_line.account_id.id))
            actual_domain.append(('account_id', '=', budget_line.budget_id.cost_center_id.id))
            actual_domain.append(('date', '>=', budget_line.budget_id.fiscalyear_id.date_start))
            # 1. period_id
            if 'period_id' in context:
                period = self.pool.get('account.period').browse(cr, uid, context['period_id'], context=context)
                month_stop = datetime.datetime.strptime(period.date_stop, '%Y-%m-%d').month
                actual_domain.append(('date', '<=', period.date_stop))
            else:
                month_stop = 12
                actual_domain.append(('date', '<=', budget_line.budget_id.fiscalyear_id.date_stop))
            # if set in context, budget values are added until the period's month
            # otherwise, all are added (month_stop = 12)
            for i in range(month_stop):
                budget_amount += budget_value_list[i]
            # 2. commitments
            # if commitments are set to False in context, the ENG analytic journal is removed
            # from the domain
            if 'commitment' in context and not context['commitment'] and len(engagement_journal_ids) > 0:
                actual_domain.append(('journal_id', '!=', engagement_journal_ids[0]))
            
            # Analytic domain is now done; lines are retrieved and added
            analytic_line_obj = self.pool.get('account.analytic.line')
            analytic_lines = analytic_line_obj.search(cr, uid, actual_domain ,context=context)
            # 3. currency_table_id
            currency_table = None
            if 'currency_table_id' in context:
                currency_table = context['currency_table_id']
            main_currency_id = budget_line.budget_id.currency_id.id
            
            for analytic_line in analytic_line_obj.browse(cr, uid, analytic_lines, context=context):
                date_context = {'date': analytic_line.source_date or analytic_line.date,
                                'currency_table_id': currency_table}
                actual_amount += self.pool.get('res.currency').compute(cr,
                                                                          uid,
                                                                          analytic_line.currency_id.id,
                                                                          main_currency_id, 
                                                                          analytic_line.amount_currency or 0.0,
                                                                          round=True,
                                                                          context=date_context)
            actual_amount = abs(actual_amount)
            
            # We have budget amount and actual amount, compute the remaining ones
            percentage = 0.0
            if budget_amount != 0.0:
                percentage = round((actual_amount / budget_amount) * 100.0, 2)
            res[budget_line.id] = {'budget_amount': budget_amount,
                                   'actual_amount': actual_amount,
                                   'balance': budget_amount - actual_amount,
                                   'percentage': percentage}
        
        return res
    
    _columns={
        'budget_id': fields.many2one('msf.budget', 'Budget', required=True),
        'account_id': fields.many2one('account.account', 'Account', required=True),
        'budget_values': fields.char('Budget Values (list of float to evaluate)', size=256, required=True),
        'budget_amount': fields.function(_get_amounts, method=True, store=False, string="Budget amount", type="float", readonly="True", multi="all"),
        'actual_amount': fields.function(_get_amounts, method=True, store=False, string="Actual amount", type="float", readonly="True", multi="all"),
        'balance': fields.function(_get_amounts, method=True, store=False, string="Balance", type="float", readonly="True", multi="all"),
        'percentage': fields.function(_get_amounts, method=True, store=False, string="Percentage", type="float", readonly="True", multi="all"),
        'parent_id': fields.many2one('msf.budget.line', 'Parent Line'),
        'child_ids': fields.one2many('msf.budget.line', 'parent_id', 'Child Lines'),
    }
    
msf_budget_line()

class msf_budget(osv.osv):
    _name = "msf.budget"
    _inherit = "msf.budget"
    
    _columns={
        'budget_line_ids': fields.one2many('msf.budget.line', 'budget_id', 'Budget Lines'),
    }

msf_budget()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
