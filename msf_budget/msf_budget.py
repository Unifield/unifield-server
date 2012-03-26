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
from lxml import etree

import datetime

class msf_budget(osv.osv):
    _name = "msf.budget"
    
    _columns={
        'name': fields.char('Name', size=64, required=True),
        'code': fields.char('Code', size=64, required=True),
        'fiscalyear_id': fields.many2one('account.fiscalyear', 'Fiscal Year', required=True),
        'state': fields.selection([('draft','Draft'),('valid','Validated'),('done','Done')], 'State', select=True, required=True),
        'cost_center_id': fields.many2one('account.analytic.account', 'Cost Center', domain=[('category', '=', 'OC'), ('type', '=', 'normal')], required=True),
        'decision_moment': fields.char('Decision Moment', size=32),
        'version': fields.integer('Version'),
        'currency_id': fields.many2one('res.currency', 'Currency', required=True),
        'display_type': fields.selection([('all', 'All lines'), ('view', 'View lines only')], string="Display type"),
        'type': fields.selection([('normal', 'Normal'), ('view', 'View')], string="Budget type"),
    }
    
    _defaults = {
        'currency_id': lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
        'state': 'draft',
        'display_type': 'all',
        'type': 'normal',
    }
    
    def create(self, cr, uid, vals, context=None):
        res = super(msf_budget, self).create(cr, uid, vals, context=context)
        analytic_obj = self.pool.get('account.analytic.account')
        # If the "parent" budget does not exist, create it.
        budget = self.browse(cr, uid, res, context=context)
        if budget.cost_center_id and budget.cost_center_id.parent_id:
            parent_cost_center = budget.cost_center_id.parent_id
            parent_budget_ids = self.search(cr,
                                            uid,
                                            [('fiscalyear_id','=',budget.fiscalyear_id.id),
                                             ('cost_center_id','=',parent_cost_center.id)])
            if len(parent_budget_ids) == 0:
                parent_budget_id = self.create(cr,
                                               uid,
                                               {'name': "Budget " + budget.fiscalyear_id.code[4:6] + " - " + parent_cost_center.name,
                                                'code': "BU" + budget.fiscalyear_id.code[4:6] + " - " + parent_cost_center.code,
                                                'fiscalyear_id': budget.fiscalyear_id.id,
                                                'cost_center_id': budget.cost_center_id.parent_id.id,
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
    def button_display_type(self, cr, uid, ids, context={}, *args, **kwargs):
        """
        Change display type
        """
        display_types = {}
        for budget in self.read(cr, uid, ids, ['display_type']):
            display_types[budget['id']] = budget['display_type']
            
        for budget_id in ids:
            self.write(cr, uid, [budget_id], {'display_type': display_types[budget_id] == 'all' and 'view' or 'all'}, context=context)
        return True
    
    
    def budget_summary_open_window(self, cr, uid, ids, context=None):
        parent_line_id = False
        fiscalyear_ids = self.pool.get('account.fiscalyear').search(cr, uid, [('date_start', '<=', datetime.date.today()),
                                                                              ('date_stop', '>=', datetime.date.today())], context=context)
        if len(fiscalyear_ids) == 0:
            raise osv.except_osv(_('Warning !'), _("The fiscal year for the current date is not defined!"))
        else:
            fiscalyear_id = fiscalyear_ids[0]
            cost_center_ids = self.pool.get('account.analytic.account').search(cr, uid, [('category', '=', 'OC'),('parent_id','=',False)], context=context)                       
            if len(cost_center_ids) != 0:
                cr.execute("SELECT id FROM msf_budget WHERE fiscalyear_id = %s \
                                                        AND cost_center_id = %s \
                                                        AND state != 'draft' \
                                                        ORDER BY version DESC LIMIT 1",
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
