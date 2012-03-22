# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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

class account_move_line(osv.osv):
    _inherit = 'account.move.line'

    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
    }

    def create_analytic_lines(self, cr, uid, ids, context=None):
        acc_ana_line_obj = self.pool.get('account.analytic.line')
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        for obj_line in self.browse(cr, uid, ids, context=context):
            # Prepare some values
            amount = obj_line.debit_currency - obj_line.credit_currency
            if obj_line.analytic_distribution_id and obj_line.account_id.user_type_code == 'expense':
                if not obj_line.journal_id.analytic_journal_id:
                    raise osv.except_osv(_('Warning'),_("No Analytic Journal! You have to define an analytic journal on the '%s' journal!") % (obj_line.journal_id.name, ))
                distrib_obj = self.pool.get('analytic.distribution').browse(cr, uid, obj_line.analytic_distribution_id.id, context=context)
                # create lines
                for distrib_lines in [distrib_obj.cost_center_lines, distrib_obj.funding_pool_lines, distrib_obj.free_1_lines, distrib_obj.free_2_lines]:
                    for distrib_line in distrib_lines:
                        context.update({'date': obj_line.source_date or obj_line.date})
                        anal_amount = distrib_line.percentage*amount/100
                        line_vals = {
                                     'name': obj_line.name,
                                     'date': obj_line.date,
                                     'ref': obj_line.ref,
                                     'journal_id': obj_line.journal_id.analytic_journal_id.id,
                                     'amount': -1 * self.pool.get('res.currency').compute(cr, uid, obj_line.currency_id.id, company_currency, 
                                        anal_amount, round=False, context=context),
                                     'amount_currency': -1 * anal_amount,
                                     'account_id': distrib_line.analytic_id.id,
                                     'general_account_id': obj_line.account_id.id,
                                     'move_id': obj_line.id,
                                     'distribution_id': distrib_obj.id,
                                     'user_id': uid,
                                     'currency_id': obj_line.currency_id.id,
                        }
                        # Update values if we come from a funding pool
                        if distrib_line._name == 'funding.pool.distribution.line':
                            line_vals.update({'cost_center_id': distrib_line.cost_center_id and distrib_line.cost_center_id.id or False,})
                        # Add source_date value for account_move_line that are a correction of another account_move_line
                        if obj_line.corrected_line_id and obj_line.source_date:
                            line_vals.update({'source_date': obj_line.source_date})
                        self.pool.get('account.analytic.line').create(cr, uid, line_vals, context=context)
        return True

account_move_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
