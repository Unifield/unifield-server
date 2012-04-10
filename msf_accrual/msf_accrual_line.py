# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import fields, osv

class msf_accrual_line(osv.osv):
    _name = 'msf.accrual.line'
    
    def onchange_period(self, cr, uid, ids, period_id, context=None):
        if period_id is False:
            return {'value': {'date': False}}
        else:
            period = self.pool.get('account.period').browse(cr, uid, period_id, context=context)
            return {'value': {'date': period.date_stop}}
    
    def _get_functional_amount(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for accrual_line in self.browse(cr, uid, ids, context=context):
            date_context = {'date': accrual_line.date}
            res[accrual_line.id] =  self.pool.get('res.currency').compute(cr,
                                                                          uid,
                                                                          accrual_line.currency_id.id,
                                                                          accrual_line.functional_currency_id.id, 
                                                                          accrual_line.accrual_amount or 0.0,
                                                                          round=True,
                                                                          context=date_context)
        return res
    
    _columns = {
        'date': fields.date("Date"),
        'period_id': fields.many2one('account.period', 'Period', required=True, domain=[('state', '=', 'draft')]),
        'description': fields.char('Description', size=64, required=True),
        'reference': fields.char('Reference', size=64, required=True),
        'expense_account_id': fields.many2one('account.account', 'Expense Account', required=True, domain=[('type', '!=', 'view'), ('user_type_code', '=', 'expense')]),
        'accrual_account_id': fields.many2one('account.account', 'Accrual Account', required=True, domain=[('type', '!=', 'view'), ('user_type_code', 'in', ['receivables', 'payables', 'debt'])]),
        'accrual_amount': fields.float('Accrual Amount', required=True),
        'currency_id': fields.many2one('res.currency', 'Currency', required=True),
        'journal_id': fields.many2one('account.journal', 'Journal', required=True),
        'third_party_type': fields.selection([('res.partner', 'Partner'),
                                              ('hr.employee', 'Employee')], 'Third Party', required=True),
        'partner_id': fields.many2one('res.partner', 'Third Party Partner'),
        'employee_id': fields.many2one('hr.employee', 'Third Party Employee'),
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
        'functional_amount': fields.function(_get_functional_amount, method=True, store=False, string="Functional Amount", type="float", readonly="True"),
        'functional_currency_id': fields.many2one('res.currency', 'Functional Currency', required=True, readonly=True),
        'state': fields.selection([('draft', 'Draft'),
                                   ('posted', 'Posted')], 'Status', required=True),
        # Field to store the third party's name for list view
        'third_party_name': fields.char('Third Party', size=64),
    }
    
    _defaults = {
        'third_party_type': 'res.partner',
        'journal_id': lambda self,cr,uid,c: self.pool.get('account.journal').search(cr, uid, [('code', '=', 'AC')])[0],
        'functional_currency_id': lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
        'state': 'draft',
    }
    
    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if 'third_party_type' in vals:
            if vals['third_party_type'] == 'hr.employee' and 'employee_id' in vals:
                employee = self.pool.get('hr.employee').browse(cr, uid, vals['employee_id'], context=context)
                vals['third_party_name'] = employee.name
            elif vals['third_party_type'] == 'res.partner' and 'partner_id' in vals:
                partner = self.pool.get('res.partner').browse(cr, uid, vals['partner_id'], context=context)
                vals['third_party_name'] = partner.name
        if 'period_id' in vals:
            period = self.pool.get('account.period').browse(cr, uid, vals['period_id'], context=context)
            vals['date'] = period.date_stop
        return super(msf_accrual_line, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        if context is None:
            context = {}
        if 'third_party_type' in vals:
            if vals['third_party_type'] == 'hr.employee' and 'employee_id' in vals:
                employee = self.pool.get('hr.employee').browse(cr, uid, vals['employee_id'], context=context)
                vals['third_party_name'] = employee.name
            elif vals['third_party_type'] == 'res.partner' and 'partner_id' in vals:
                partner = self.pool.get('res.partner').browse(cr, uid, vals['partner_id'], context=context)
                vals['third_party_name'] = partner.name
        if 'period_id' in vals:
            period = self.pool.get('account.period').browse(cr, uid, vals['period_id'], context=context)
            vals['date'] = period.date_stop
        return super(msf_accrual_line, self).write(cr, uid, ids, vals, context=context)
    
    def button_duplicate(self, cr, uid, ids, context=None):
        """
        Copy given lines and delete all links
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Browse lines
        for line in self.browse(cr, uid, ids, context=context):
            default_vals = ({
                'description': '(copy) ' + line.description,
            })
            if line.analytic_distribution_id:
                # the distribution must be copied, not just the id
                new_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, line.analytic_distribution_id.id, {}, context=context)
                if new_distrib_id:
                    default_vals.update({'analytic_distribution_id': new_distrib_id})
            self.copy(cr, uid, line.id, default_vals, context=context)
        return True
    
    def button_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Launch analytic distribution wizard on an invoice line
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        accrual_line = self.browse(cr, uid, ids[0], context=context)
        # Search elements for currency
        currency = accrual_line.currency_id and accrual_line.currency_id.id
        # Get analytic distribution id from this line
        distrib_id = accrual_line and accrual_line.analytic_distribution_id and accrual_line.analytic_distribution_id.id or False
        # Prepare values for wizard
        vals = {
            'total_amount': accrual_line.accrual_amount or 0.0,
            'accrual_line_id': accrual_line.id,
            'currency_id': currency or False,
            'state': 'dispatch',
            'account_id': accrual_line.expense_account_id and accrual_line.expense_account_id.id or False,
        }
        if distrib_id:
            vals.update({'distribution_id': distrib_id,})
        # Create the wizard
        wiz_obj = self.pool.get('analytic.distribution.wizard')
        wiz_id = wiz_obj.create(cr, uid, vals, context=context)
        # Update some context values
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
            'from_accrual_line': True
        })
        # Open it!
        return {
                'name': 'Analytic distribution',
                'type': 'ir.actions.act_window',
                'res_model': 'analytic.distribution.wizard',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [wiz_id],
                'context': context,
        }
    
msf_accrual_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
