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
        budget_line_obj = self.pool.get('msf.budget.line')
        if 'budget_vals' in context and 'latest_budget_id' in context and 'budget_line_vals' in context:
            # Overwrite budget
            budget_obj.write(cr, uid, [context['latest_budget_id']], vals=context['budget_vals'], context=context)
            # Delete old lines
            old_line_ids = budget_line_obj.search(cr, uid, [('budget_id','=',context['latest_budget_id'])], context=context)
            budget_line_obj.unlink(cr, uid, old_line_ids, context=context)
            # Recreate the lines
            for line_vals in context['budget_line_vals']:
                line_vals.update({'budget_id': context['latest_budget_id']})
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