#!/usr/bin/env python
#-*- encoding:utf-8 -*-
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
import tools
from tools.translate import _

class account_bank_statement_line(osv.osv):
    _inherit = "account.bank.statement.line"
    _name = "account.bank.statement.line"

    def _display_analytic_button(self, cr, uid, ids, name, args, context={}):
        """
        Return True for all element that correspond to some criteria:
         - The entry state is draft
         - The account is an expense account
        """
        res = {}
        for absl in self.browse(cr, uid, ids, context=context):
            res[absl.id] = True
            # False if st_line is hard posted
            if absl.state == 'hard':
                res[absl.id] = False
            # False if account not an expense account
            if absl.account_id.user_type.code not in ['expense']:
                res[absl.id] = False
        return res

    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
        'display_analytic_button': fields.function(_display_analytic_button, method=True, string='Display analytic button?', type='boolean', readonly=True, 
            help="This informs system that we can display or not an analytic button", store=False),
    }

    _defaults = {
        'display_analytic_button': lambda *a: True,
    }

    def button_analytic_distribution(self, cr, uid, ids, context={}):
        """
        Launch analytic distribution wizard from a statement line
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # we get the analytical distribution object linked to this line
        distrib_id = False
        statement_line_obj = self.browse(cr, uid, ids[0], context=context)
        amount = statement_line_obj.amount * -1 or 0.0
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = statement_line_obj.statement_id.journal_id.currency and statement_line_obj.statement_id.journal_id.currency.id or company_currency
        if statement_line_obj.analytic_distribution_id:
            distrib_id = statement_line_obj.analytic_distribution_id.id
        else:
            distrib_id = self.pool.get('analytic.distribution').create(cr, uid, {}, context=context)
            newvals={'analytic_distribution_id': distrib_id}
            super(account_bank_statement_line, self).write(cr, uid, ids, newvals, context=context)
        wiz_obj = self.pool.get('wizard.costcenter.distribution')
        wiz_id = wiz_obj.create(cr, uid, {'total_amount': amount, 'distribution_id': distrib_id, 'currency_id': currency}, context=context)
        # we open a wizard
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
            'wizard_ids': {'cost_center': wiz_id},
        })
        return {
                'type': 'ir.actions.act_window',
                'res_model': 'wizard.costcenter.distribution',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [wiz_id],
                'context': context,
        }

account_bank_statement_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
