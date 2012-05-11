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
from tools.translate import _

import base64
import StringIO
import csv

class wizard_budget_import(osv.osv_memory):
    _name = 'wizard.budget.import'
    _description = 'Budget Import'

    _columns = {
        'import_file': fields.binary("CSV File"),
    }
    
    def split_budgets(self, import_data):
        result = []
        current_budget = []
        for i in range(len(import_data)):
            # Conditions for appending a new budget:
            # - line is empty
            # - next line has some data
            # - line is not at the end of file (at least 1 line must exist below)
            if (len(import_data[i]) == 0 or import_data[i][0] == ''):
                if i < (len(import_data) - 1) \
                and len(import_data[i+1]) != 0 and import_data[i+1][0] != '':
                    # split must be done
                    result.append(current_budget)
                    current_budget = []
            else:
                # append line to current budget
                current_budget.append(import_data[i])
        # last append
        result.append(current_budget)
        return result
    
    def fill_header_data(self, cr, uid, import_data, context=None):
        result = {}
        # name
        if import_data[0][1] == "":
            raise osv.except_osv(_('Warning !'), _("The budget has no name!"))
        else:
            result.update({'name': import_data[0][1]})
        # code
        if import_data[1][1] == "":
            raise osv.except_osv(_('Warning !'), _("The budget has no code!"))
        else:
            result.update({'code': import_data[1][1]})
        # fiscal year code
        if import_data[2][1] == "":
            raise osv.except_osv(_('Warning !'), _("The budget has no fiscal year!"))
        else:
            fy_ids = self.pool.get('account.fiscalyear').search(cr, uid, [('code', '=', import_data[2][1])], context=context)
            if len(fy_ids) == 0:
                raise osv.except_osv(_('Warning !'), _("The fiscal year %s is not defined in the database!") % (import_data[2][1],))
            else:
                result.update({'fiscalyear_id': fy_ids[0]})
        # cost center code
        if import_data[3][1] == "":
            raise osv.except_osv(_('Warning !'), _("The budget has no cost center!"))
        else:
            cc_ids = self.pool.get('account.analytic.account').search(cr, uid, [('code', '=', import_data[3][1]),
                                                                                ('category', '=', 'OC')], context=context)
            if len(cc_ids) == 0:
                raise osv.except_osv(_('Warning !'), _("The cost center %s is not defined in the database!") % (import_data[3][1],))
            else:
                cost_center = self.pool.get('account.analytic.account').browse(cr, uid, cc_ids[0], context=context)
                if cost_center.type == 'view':
                    raise osv.except_osv(_('Warning !'), _("The cost center %s is not an allocable cost center! The budget for it will be created automatically.") % (import_data[3][1],))
                else:
                    result.update({'cost_center_id': cc_ids[0]})
        # decision moment
        if import_data[4][1] == "":
            raise osv.except_osv(_('Warning !'), _("The budget has no decision moment!"))
        else:
            moment_ids = self.pool.get('msf.budget.decision.moment').search(cr, uid, [('name', '=', import_data[4][1])], context=context)
            if len(moment_ids) == 0:
                raise osv.except_osv(_('Warning !'), _("The decision moment %s is not defined in the database!") % (import_data[4][1],))
            else:
                result.update({'decision_moment_id': moment_ids[0]})
        return result
    
    def fill_budget_line_data(self, cr, uid, import_data, context=None):
        # Create a "tracker" for lines to create
        created_lines = {}
        expense_account_ids = self.pool.get('account.account').search(cr, uid, [('user_type_code', '=', 'expense'),
                                                                                ('type', '!=', 'view')], context=context)
        for expense_account_id in expense_account_ids:
            created_lines[expense_account_id] = False
        result = []
        # Check that the account exists
        for import_line in import_data[6:]:
            budget_line_vals = {}
            if import_line[0] == "":
                raise osv.except_osv(_('Warning !'), _("A budget line has no account!"))
            else:
                account_ids = self.pool.get('account.account').search(cr,
                                                                      uid,
                                                                      [('code', '=', import_line[0])],
                                                                      context=context)
                if len(account_ids) == 0:
                    raise osv.except_osv(_('Warning !'), _("Account %s does not exist in database!") % (import_line[0],))
                else:
                    account = self.pool.get('account.account').browse(cr,uid,account_ids[0], context=context)
                    if account.user_type_code != 'expense':
                        raise osv.except_osv(_('Warning !'), _("Account %s is not an expense account!") % (import_line[0],))
                    elif account_ids[0] in created_lines and created_lines[account_ids[0]]:
                        # Line already created in the file, return a warning
                        raise osv.except_osv(_('Warning !'), _("Account %s is twice in the file!")%(import_line[0],))
                    elif account.type != 'view':
                        # Only create "normal" budget lines (view accounts are just discarded)
                        budget_line_vals.update({'account_id': account_ids[0]})
                        budget_values = []
                        for budget_value in import_line[1:13]:
                            if budget_value == "":
                                budget_values.append(0)
                            else:
                                # try to parse as int
                                try:
                                    int_value = int(budget_value)
                                except:
                                    raise osv.except_osv(_('Warning !'), _("The value '%s' is not an integer!") % budget_value)
                                budget_values.append(int_value)
                        # Sometimes, the CSV has not all the needed columns. It's padded.
                        if len(budget_values) != 12:
                            budget_values += [0]*(12-len(budget_values))
                        budget_line_vals.update({'budget_values': str(budget_values)})
                        # Update created lines dictionary
                        created_lines[account_ids[0]] = True
                        result.append(budget_line_vals)
        # If expense accounts are not in the file, create those
        missing_lines = [x for x in created_lines if created_lines[x] == False]
        budget_values = str([0]*12)
        for expense_account_id in missing_lines:
            result.append({'account_id': expense_account_id,
                           'budget_values': budget_values})
        # sort them by name
        result = sorted(result)
        return result

    def import_csv_budget(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        budget_obj = self.pool.get('msf.budget')
        # read file
        for wizard in self.browse(cr, uid, ids, context=context):
            budget_line_vals = []
            import_file = base64.decodestring(wizard.import_file)
            import_string = StringIO.StringIO(import_file)
            import_data = list(csv.reader(import_string, quoting=csv.QUOTE_ALL, delimiter=','))
            # Split budgets (if more than one)
            split_budget_data = self.split_budgets(import_data)
            
            # dict of existing budgets
            budgets_to_be_approved = {}
            # parse each budget
            for budget_data in split_budget_data:
                # Parse budget general info and except if issue
                budget_vals = self.fill_header_data(cr, uid, budget_data, context)
                # Parse budget lines and except if issue
                budget_line_vals = self.fill_budget_line_data(cr, uid, budget_data, context)
                
                # Version this budget data
                # Search for latest budget
                cr.execute("SELECT id, version, state FROM msf_budget WHERE code = %s \
                                                                        AND name = %s \
                                                                        AND fiscalyear_id = %s \
                                                                        AND cost_center_id = %s \
                                                                        AND decision_moment_id = %s \
                                                                        ORDER BY version DESC LIMIT 1",
                                                                       (budget_vals['code'],
                                                                        budget_vals['name'],
                                                                        budget_vals['fiscalyear_id'],
                                                                        budget_vals['cost_center_id'],
                                                                        budget_vals['decision_moment_id']))
                    
                
                if not cr.rowcount:
                    # No budget found; the created one is the first one (and latest)
                    budget_vals.update({'version': 1})
                    # Create the final budget and its lines
                    created_budget_id = budget_obj.create(cr, uid, vals=budget_vals, context=context)
                    for line_vals in budget_line_vals:
                        line_vals.update({'budget_id': created_budget_id})
                        self.pool.get('msf.budget.line').create(cr, uid, vals=line_vals, context=context)
                else:
                    # Latest budget found; increment version or overwrite
                    latest_budget_id, latest_budget_version, latest_budget_state = cr.fetchall()[0]
                    if latest_budget_version and latest_budget_state:
                        if latest_budget_state == 'draft':
                            # latest budget is draft
                            # Prepare creation of the "new" one (with no lines)
                            budget_vals.update({'version': latest_budget_version})
                            # Create budget (removed in next step if needed)
                            # This is to avoid passing too much stuff in the context
                            created_budget_id = budget_obj.create(cr, uid, vals=budget_vals, context=context)
                            for line_vals in budget_line_vals:
                                line_vals.update({'budget_id': created_budget_id})
                                self.pool.get('msf.budget.line').create(cr, uid, vals=line_vals, context=context)
                            # add to approval list
                            budget_to_be_approved = {'latest_budget_id': latest_budget_id,
                                                     'created_budget_id': created_budget_id}
                            budgets_to_be_approved[budget_vals['name']] = budget_to_be_approved
                            # skip creation
                            continue
                        else:
                            # latest budget is validated
                            # a new version will be created...
                            budget_vals.update({'version': latest_budget_version + 1})
                            # Create the final budget and its lines
                            created_budget_id = budget_obj.create(cr, uid, vals=budget_vals, context=context)
                            for line_vals in budget_line_vals:
                                line_vals.update({'budget_id': created_budget_id})
                                self.pool.get('msf.budget.line').create(cr, uid, vals=line_vals, context=context)
                            
                    
        if len(budgets_to_be_approved) > 0:
            # we open a wizard
            budget_list = ""
            for budget_name in budgets_to_be_approved.keys():
                budget_list += budget_name + "\n"
            wizard_id = self.pool.get('wizard.budget.import.confirm').create(cr,
                                                                             uid,
                                                                             {'budget_list': budget_list},
                                                                             context=context)
            context.update({'budgets': budgets_to_be_approved})
            return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'wizard.budget.import.confirm',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'target': 'new',
                    'res_id': wizard_id,
                    'context': context
                   }
        else:
            # we open a wizard
            return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'wizard.budget.import.finish',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': context
            }

wizard_budget_import()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
