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

    def button_confirm(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        budget_obj = self.pool.get('msf.budget')
        if 'budget_vals' in context and 'latest_budget_id' in context and 'budget_line_vals' in context:
            # Remove old budget
            budget_obj.unlink(cr, uid, [context['latest_budget_id']], context=context)
            # Create the final budget and its lines
            created_budget_id = budget_obj.create(cr, uid, vals=context['budget_vals'], context=context)
            for line_vals in context['budget_line_vals']:
                line_vals.update({'budget_id': created_budget_id})
                self.pool.get('msf.budget.line').create(cr, uid, vals=line_vals, context=context)
        # we open a wizard
        return {
                'type': 'ir.actions.act_window',
                'res_model': 'wizard.budget.import.finish',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'context': context
        }

wizard_budget_import_confirm()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: