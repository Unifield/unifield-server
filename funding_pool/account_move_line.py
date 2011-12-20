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

    def create_analytic_lines(self, cr, uid, ids, context={}):
        # Some verifications
        if not context:
            context = {}
        acc_ana_line_obj = self.pool.get('account.analytic.line')
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        for obj_line in self.browse(cr, uid, ids, context=context):
            if obj_line.analytic_distribution_id and obj_line.account_id.user_type_code == 'expense':
                if not obj_line.journal_id.analytic_journal_id:
                    raise osv.except_osv(_('No Analytic Journal !'),_("You have to define an analytic journal on the '%s' journal!") % (obj_line.journal_id.name, ))
                distrib_obj = self.pool.get('analytic.distribution').browse(cr, uid, obj_line.analytic_distribution_id.id, context=context)
                # create lines
                for distrib_lines in [distrib_obj.cost_center_lines, distrib_obj.funding_pool_lines, distrib_obj.free_1_lines, distrib_obj.free_2_lines]:
                    for distrib_line in distrib_lines:
                        context.update({'date': obj_line.source_date or obj_line.date})
                        line_vals = {
                                     'name': obj_line.name,
                                     'date': obj_line.date,
                                     'ref': obj_line.ref,
                                     'journal_id': obj_line.journal_id.analytic_journal_id.id,
                                     'amount': -1 * self.pool.get('res.currency').compute(cr, uid, obj_line.currency_id.id, company_currency, 
                                        distrib_line.amount or 0.0, round=False, context=context),
                                     'amount_currency': -1 * distrib_line.amount,
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

    def button_analytic_distribution(self, cr, uid, ids, context={}):
        """
        Launch the analytic distribution wizard from a journal item (account_move_line)
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # we get the analytical distribution object linked to this line
        distrib_id = False
        move_line_obj = self.browse(cr, uid, ids[0], context=context)
        # Get amount using account_move_line amount_currency field
        amount = move_line_obj.amount_currency and move_line_obj.amount_currency or 0.0
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = move_line_obj.currency_id and move_line_obj.currency_id.id or company_currency
        if move_line_obj.analytic_distribution_id:
            distrib_id = move_line_obj.analytic_distribution_id.id
        else:
            raise osv.except_osv(_('No Analytic Distribution !'),_("You have to define an analytic distribution on the move line!"))
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

account_move_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
