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
        for obj_line in self.browse(cr, uid, ids, context=context):
            if obj_line.analytic_distribution_id and obj_line.account_id.user_type_code == 'expense':
                if not obj_line.journal_id.analytic_journal_id:
                    raise osv.except_osv(_('No Analytic Journal !'),_("You have to define an analytic journal on the '%s' journal!") % (obj_line.journal_id.name, ))
                distrib_obj = self.pool.get('analytic.distribution').browse(cr, uid, obj_line.analytic_distribution_id.id, context=context)
                # create lines
                for distrib_lines in [distrib_obj.cost_center_lines, distrib_obj.funding_pool_lines, distrib_obj.free_1_lines, distrib_obj.free_2_lines]:
                    for distrib_line in distrib_lines:
                        line_vals = {
                                     'name': obj_line.name,
                                     'date': obj_line.date,
                                     'ref': obj_line.ref,
                                     'journal_id': obj_line.journal_id.analytic_journal_id.id,
                                     'amount': distrib_line.amount,
                                     'account_id': distrib_line.analytic_id.id,
                                     'general_account_id': obj_line.account_id.id,
                                     'move_id': obj_line.id,
                                     'user_id': uid
                        }
                        self.pool.get('account.analytic.line').create(cr, uid, line_vals, context=context)
                    
        return True
    
    def button_analytic_distribution(self, cr, uid, ids, context={}):
        # we get the analytical distribution object linked to this line
        distrib_id = False
        move_line_obj = self.browse(cr, uid, ids[0], context=context)
        amount = abs(move_line_obj.amount_currency)
        if move_line_obj.analytic_distribution_id:
            distrib_id = move_line_obj.analytic_distribution_id.id
        else:
            raise osv.except_osv(_('No Analytic Distribution !'),_("You have to define an analytic distribution on the move line!"))
        wiz_obj = self.pool.get('wizard.costcenter.distribution')
        wiz_id = wiz_obj.create(cr, uid, {'total_amount': amount, 'distribution_id': distrib_id}, context=context)
        # we open a wizard
        return {
                'type': 'ir.actions.act_window',
                'res_model': 'wizard.costcenter.distribution',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [wiz_id],
                'context': {
                    'active_id': ids[0],
                    'active_ids': ids,
               }
        }
    
account_move_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
