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
    
    def fill_header_data(self, cr, uid, import_data, context={}):
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
                raise osv.except_osv(_('Warning !'), _("The fiscal year %s is not defined in the database!" % import_data[2][1]))
            else:
                result.update({'fiscalyear_id': fy_ids[0]})
        # cost center code
        if import_data[3][1] == "":
            raise osv.except_osv(_('Warning !'), _("The budget has no cost center!"))
        else:
            cc_ids = self.pool.get('account.analytic.account').search(cr, uid, [('code', '=', import_data[3][1]),
                                                                                ('category', '=', 'OC')], context=context)
            if len(cc_ids) == 0:
                raise osv.except_osv(_('Warning !'), _("The cost center %s is not defined in the database!" % import_data[3][1]))
            else:
                result.update({'cost_center_id': cc_ids[0]})
        # decision moment
        if import_data[4][1] == "":
            raise osv.except_osv(_('Warning !'), _("The budget has no decision moment!"))
        else:
            result.update({'decision_moment': import_data[4][1]})
        # currency table code (not mandatory)
        if import_data[5][1] != "":
            curr_table_ids = self.pool.get('res.currency.table').search(cr, uid, [('code', '=', import_data[6][1])], context=context)
            if len(curr_table_ids) == 0:
                raise osv.except_osv(_('Warning !'), _("The currency table %s is not defined in the database!" % import_data[6][1]))
            else:
                result.update({'currency_table_id': curr_table_ids[0]})
        return result
    
    def fill_budget_line_data(self, cr, uid, import_data, context={}):
        result = []
        # Check that the account exists
        for import_line in import_data[8:]:
            budget_line_vals = {}
            if import_line[0] == "":
                raise osv.except_osv(_('Warning !'), _("A budget line has no account!"))
            else:
                account_ids = self.pool.get('account.account').search(cr,
                                                                      uid,
                                                                      [('code', '=', import_line[0])],
                                                                      context=context)
                if len(account_ids) == 0:
                    raise osv.except_osv(_('Warning !'), _("Account %s does not exist in database!" % import_line[0]))
                else:
                    account = self.pool.get('account.account').browse(cr,uid,account_ids[0], context=context)
                    if account.user_type_code != 'expense':
                        raise osv.except_osv(_('Warning !'), _("Account %s is not an expense account!" % import_line[0]))
                    else:
                        budget_line_vals.update({'account_id': account_ids[0]})
            budget_values = "["
            for budget_value in import_line[1:13]:
                if budget_value == "":
                    budget_values += "0"
                else:
                    # try to parse as int
                    try:
                        test_value = int(budget_value)
                    except:
                        raise osv.except_osv(_('Warning !'), _("The value '%s' is not an integer!") % budget_value)
                    budget_values += budget_value
                budget_values += ","
            budget_values = budget_values[:-1] + "]"
            budget_line_vals.update({'budget_values': budget_values})
            
            result.append(budget_line_vals)
            
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
            # Parse budget general info and except if issue
            budget_vals = self.fill_header_data(cr, uid, import_data, context)
            # Parse budget lines and except if issue
            budget_line_vals = self.fill_budget_line_data(cr, uid, import_data, context)
            
            # Version this budget data
            # Search for latest budget
            db_budget_ids = budget_obj.search(cr,
                                              uid,
                                              [('code','=',budget_vals['code']),
                                               ('name','=',budget_vals['name']),
                                               ('fiscalyear_id','=',budget_vals['fiscalyear_id']),
                                               ('cost_center_id','=',budget_vals['cost_center_id']),
                                               ('latest_version','=',True)],
                                              context=context)
            
            if len(db_budget_ids) == 0:
                # No budget found; the created one is the first one (and latest)
                budget_vals.update({'version': 1,
                                    'latest_version': True})
            else:
                # Latest budget found; increment version or overwrite
                latest_budget_id = db_budget_ids[0]
                latest_budget = budget_obj.read(cr, uid, [latest_budget_id], ['version', 'state'])[0]
                if latest_budget['version'] and latest_budget['state']:
                    if latest_budget['state'] == 'draft':
                        # latest budget is draft
                        # TODO pop-up to overwrite it
                        # Remove old budget
                        budget_obj.unlink(cr, uid, [latest_budget_id], context=context)
                        # Prepare creation of the "new" one
                        budget_vals.update({'version': latest_budget['version'],
                                            'latest_version': True})
                    else:
                        # latest budget is validated
                        # a new version will be created...
                        budget_vals.update({'version': latest_budget['version'] + 1,
                                            'latest_version': True})
                        # ...and the old one loses its "latest version" status
                        self.pool.get('msf.budget').write(cr,
                                                          uid,
                                                          [latest_budget_id],
                                                          vals={'latest_version': False},
                                                          context=context)
                        
            # Create the final budget and its lines
            created_budget_id = budget_obj.create(cr, uid, vals=budget_vals, context=context)
            for line_vals in budget_line_vals:
                line_vals.update({'budget_id': created_budget_id})
                self.pool.get('msf.budget.line').create(cr, uid, vals=line_vals, context=context)
            
        return {'type' : 'ir.actions.act_window_close'}

wizard_budget_import()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: