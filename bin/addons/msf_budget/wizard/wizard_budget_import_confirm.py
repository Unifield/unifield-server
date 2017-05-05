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
from osv import osv, fields

class wizard_budget_import_confirm(osv.osv_memory):
    _name = 'wizard.budget.import.confirm'
    
    _columns = {
        'budget_list': fields.text("Budget list"),
    }

    def button_confirm(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        budget_obj = self.pool.get('msf.budget')
        if 'budgets' in context:
            for budget in context['budgets'].values():
                # Delete old budget
                budget_obj.unlink(cr, uid, [budget['latest_budget_id']], context=context)
        # we open a wizard
        return {
                'type': 'ir.actions.act_window',
                'res_model': 'wizard.budget.import.finish',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'context': context
        }

    def button_cancel(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        budget_obj = self.pool.get('msf.budget')
        if 'budgets' in context:
            for budget in context['budgets'].values():
                # Delete new budget
                budget_obj.unlink(cr, uid, [budget['created_budget_id']], context=context)
        return {'type' : 'ir.actions.act_window_close'}

wizard_budget_import_confirm()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: