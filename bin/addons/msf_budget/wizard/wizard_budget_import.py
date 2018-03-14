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
from osv import osv
from osv import fields
from tools.translate import _

import base64
import StringIO
import csv
import time


class imported_msf_budget_line(osv.osv):
    _name = 'imported.msf.budget.line'
    _description = 'Temporary budget line imported from a CSV'
    _rec_name = 'account_id'

    _columns = {
        'account_id': fields.many2one('account.account', 'Account', required=True, domain=[('type', '!=', 'view')]),
        'destination_id': fields.many2one('account.analytic.account', 'Destination', domain=[('category', '=', 'DEST')], required=True),
        'month1': fields.float("Month 01"),
        'month2': fields.float("Month 02"),
        'month3': fields.float("Month 03"),
        'month4': fields.float("Month 04"),
        'month5': fields.float("Month 05"),
        'month6': fields.float("Month 06"),
        'month7': fields.float("Month 07"),
        'month8': fields.float("Month 08"),
        'month9': fields.float("Month 09"),
        'month10': fields.float("Month 10"),
        'month11': fields.float("Month 11"),
        'month12': fields.float("Month 12"),
        'sequence': fields.char("Sequence", size=64, required=True, readonly=True),
    }

imported_msf_budget_line()


class wizard_budget_import(osv.osv_memory):
    _name = 'wizard.budget.import'
    _description = 'Budget Import'

    _columns = {
        'import_file': fields.binary("CSV File"),
        'import_date': fields.integer("Import date"),
    }

    def split_budgets(self, import_data):
        """
        Split budget file into several budget_data by using a curious way: split on the line that is empty and that next line have data and that the line is not the end of the budget file.
        """
        # Prepare some values
        result = []
        current_budget = []
        # Browse all lines
        for i in range(len(import_data)):
            # Conditions for appending a new budget:
            # - line is empty
            # - next line has some data
            # - line is not at the end of file (at least 1 line must exist below)
            if (len(import_data[i]) == 0 or import_data[i][0] == ''):
                if i < (len(import_data) - 1) and len(import_data[i+1]) != 0 and import_data[i+1][0] != '':
                    # split must be done
                    result.append(current_budget)
                    current_budget = []
            else:
                # append line to current budget
                current_budget.append(import_data[i])
        # last append
        result.append(current_budget)
        return result

    def _read_budget_info(self, cr, uid, info, context=None):
        """
        Read the five first lines from the given info.
        Info should be a list of lists.
        Check:
          - fiscalyear
          - cost center
          - decision moment
        """
        # Some checks
        if context is None:
            context = {}
        # Prepare some values
        res = {}
        budget_info = {}
        for line_index, variable, error_msg in [(0, 'budget_name', _('The budget has no name!')), (1, 'budget_code', _('The budget has no code!')), (2, 'fy', _('The budget has no fiscal year!')), (3, 'cost_center', _('The budget has no cost center!')), (4, 'decision_moment', _('The budget has no decision moment!'))]:
            budget_info[variable] = info[line_index] and info[line_index][1] or False
            if not budget_info[variable]:
                raise osv.except_osv(_('Error'), error_msg)
        # Check budget info
        fy = budget_info['fy']
        cost_center = budget_info['cost_center']
        decision_moment = budget_info['decision_moment']
        # - fiscalyear
        fy_ids = self.pool.get('account.fiscalyear').search(cr, uid, [('code', '=', fy)], context=context)
        if len(fy_ids) == 0:
            raise osv.except_osv(_('Warning !'), _("The fiscal year %s is not defined in the database!") % (fy,))
        else:
            res.update({'fiscalyear_id': fy_ids[0]})
        # - cost center
        cc_ids = self.pool.get('account.analytic.account').search(cr, uid, [('code', '=', cost_center), ('category', '=', 'OC')], context=context)
        if len(cc_ids) == 0:
            raise osv.except_osv(_('Warning !'), _("The cost center %s is not defined in the database!") % (cost_center,))
        else:
            cc = self.pool.get('account.analytic.account').read(cr, uid, cc_ids[0], ['type'], context=context)
            if cc.get('type', False) and cc.get('type') == 'view':
                raise osv.except_osv(_('Warning !'), _("The cost center %s is not an allocable cost center! The budget for it will be created automatically.") % (cost_center,))
            else:
                res.update({'cost_center_id': cc_ids[0]})
        # - decision moment
        moment_ids = self.pool.get('msf.budget.decision.moment').search(cr, uid, [('name', '=', decision_moment)], context=context)
        if len(moment_ids) == 0:
            raise osv.except_osv(_('Warning !'), _("The decision moment %s is not defined in the database!") % (decision_moment,))
        else:
            res.update({'decision_moment_id': moment_ids[0]})
        # Add missing info
        res.update({'name': budget_info['budget_name'], 'code': budget_info['budget_code']})
        return res

    def _read_and_write_budget_lines(self, cr, uid, lines, sequence, context=None):
        """
        Read line by line and write content into a table.
        """
        # Some checks
        if context is None:
            context = {}
        # Prepare some values
        imported_obj = self.pool.get('imported.msf.budget.line')
        a_obj = self.pool.get('account.account')
        d_obj = self.pool.get('account.analytic.account')
        link_obj = self.pool.get('account.destination.link')
        account_tuples = [] # list of tuple already checked
        # Browse lines, check accounts, destinations and complete value
        for line in lines:
            vals = {'sequence': sequence}
            # check account/destination content
            if line[0] == "":
                raise osv.except_osv(_('Warning !'), _("A budget line has no account!"))
            codes = line[0].split(' ')
            if len(codes) == 1:
                raise osv.except_osv(_('Warning !'), _("No destination was set! Please add it for line %s") % (line[0],))
            account_code = codes[0]
            destination_code = codes[1]
            # check that tuple account/destination was not been already used previously
            if (account_code, destination_code) in account_tuples:
                raise osv.except_osv(_('Warning !'), _("Account/destination %s/%s is twice in the file!") % (account_code, destination_code,))
            # check account/destination existence
            account_ids = a_obj.search(cr, uid, [('code', '=', account_code)], context=context)
            if not account_ids:
                raise osv.except_osv(_('Warning !'), _("Account %s does not exist in database!") % (account_code,))
            destination_ids = d_obj.search(cr, uid, [('code', '=', destination_code), ('category', '=', 'DEST')], context=context)
            if not destination_ids:
                raise osv.except_osv(_('Warning !'), _("Destination %s does not exist in database!") % (destination_code,))
            # check account/destination reconciliation (compatible)
            link_ids = link_obj.search(cr, uid, [('account_id', '=', account_ids[0]), ('destination_id', '=', destination_ids[0])])
            if not link_ids:
                raise osv.except_osv(_('Warning !'), _("Destination %s is not linked to account %s!") % (destination_code, account_code,))
            # Remember account/destination tuple
            account_tuples.append((account_code, destination_code))
            # Check this account is not analytic-a-holic
            account = a_obj.read(cr, uid, account_ids[0], ['is_analytic_addicted'], context=context)
            if not account.get('is_analytic_addicted', False):
                raise osv.except_osv(_('Warning !'), _("Account %s is not an analytic-a-holic account!") % (account_code,))
            # Update vals with account and destination
            vals.update({
                'account_id': account_ids[0],
                'destination_id': destination_ids[0],
            })
            # Check budget values from month1 to month12
            budget_values = {}
            for i, budget_value in enumerate(line[1:13], 1):
                if budget_value == "":
                    budget_values.update({'month'+str(i): 0.0})
                else:
                    # try to parse as float
                    try:
                        float_value = round(float(budget_value), 2)
                    except:
                        raise osv.except_osv(_('Warning !'), _("The value '%s' is not an float!") % budget_value)
                    budget_values.update({'month'+str(i): float_value})
            # Sometimes, the CSV has not all the needed columns. It's padded.
            #+ We so complete values from budget_values length to 12. So len+1 to 12+1 (=13)
            if len(budget_values) != 12:
                for x in xrange(len(budget_values)+1, 13, 1):
                    budget_values.update({'month'+str(x): 0.0,})
            # Update vals with month values and create line
            vals.update(budget_values)
            imported_obj.create(cr, uid, vals, context=context)
        return True

    def button_import(self, cr, uid, ids, context=None):
        """
        Launch budget import process
        """
        # Some checks
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        # Prepare some values
        budgets_2be_approved = {}
        tool_obj = self.pool.get('msf.budget.tools')
        budget_obj = self.pool.get('msf.budget')
        sql = """
            DELETE FROM imported_msf_budget_line
            WHERE sequence = %s"""
        sql_budget = """
            SELECT id, version, state
            FROM msf_budget WHERE code = %s
            AND name = %s
            AND fiscalyear_id = %s
            AND cost_center_id = %s
            AND decision_moment_id = %s
            ORDER BY version DESC LIMIT 1"""
        # Browse each wizard, take it's file, read it, then process lines.
        for w in self.read(cr, uid, ids, ['import_file'], context=context):
            # First prepare some values
            wiz_file = w.get('import_file', False)
            # Then check that file is here
            if not wiz_file:
                raise osv.except_osv(_('Error'), _('Nothing to import.'))

            # US-212: If multi-click on import button, we check
            # if the same file was imported in the 5 last seconds
            imports = self.search(cr, uid, [], context=context)
            for import_db in imports:
                if import_db != w.get('id', 0):
                    import_obj = self.read(cr, uid, import_db,
                                           ['import_file', 'import_date'],
                                           context=context)
                    search_import_file = import_obj.get('import_file', False)
                    date = time.time() - 5
                    date_import = import_obj['import_date']

                    if search_import_file == wiz_file and date_import >= date:
                        return {}

            # And finally read it!
            import_file = base64.decodestring(wiz_file)
            import_string = StringIO.StringIO(import_file)
            import_data = list(csv.reader(import_string, quoting=csv.QUOTE_ALL, delimiter=','))
            # A budget import file can contain more than 1 budget. So split budget into multiples ones and browse budget by budget
            for budget_data in self.split_budgets(import_data):
                # Create a sequence for next processes
                seq = self.pool.get('ir.sequence').get(cr, uid, 'budget.import')
                # Read budget header
                budget_vals = self._read_budget_info(cr, uid, budget_data[0:6], context=context)
                # Check version of this budget regarding data
                cr.execute(sql_budget, (budget_vals['code'], budget_vals['name'], budget_vals['fiscalyear_id'], budget_vals['cost_center_id'], budget_vals['decision_moment_id']))
                add_to_approval = False
                if not cr.rowcount:
                    # No budget found; the created one is the first one (and latest)
                    budget_vals.update({'version': 1})
                else:
                    # Latest budget found; increment version or overwrite
                    latest_budget_id, latest_budget_version, latest_budget_state = cr.fetchall()[0]
                    if latest_budget_version and latest_budget_state:
                        if latest_budget_state == 'draft':
                            # latest budget is draft
                            # Prepare creation of the "new" one (with no lines)
                            budget_vals.update({'version': latest_budget_version})
                            add_to_approval = True
                        else:
                            # latest budget is validated
                            # a new version will be created...
                            budget_vals.update({'version': latest_budget_version + 1})
                # Create budget
                budget_id = budget_obj.create(cr, uid, budget_vals, context=context)
                # Add it to list of being approved if needed
                if add_to_approval:
                    # add to approval list
                    budget_to_approve = {
                        'latest_budget_id': latest_budget_id,
                        'created_budget_id': budget_id
                    }
                    budgets_2be_approved[budget_vals['name']] = budget_to_approve
                # Read each line. Lines are declared after the six first lines. Write content into a database with the given sequence.
                self._read_and_write_budget_lines(cr, uid, budget_data[6:], seq, context=context)
                # Create budget line
                tool_obj.create_budget_lines(cr, uid, budget_id, seq, context=context)
                # Delete lines that comes from the given sequence
                cr.execute(sql, (seq,))

        self.write(cr, uid, ids, {'import_date': time.time()}, context=context)
        # Open a different wizard regarding number of budget to be approved.
        #+ - if budget to approve, use a wizard to permit user to approve budget
        #+ - otherwise use a wizard for user to inform user the import is OK
        if len(budgets_2be_approved) > 0:
            budget_list = ""
            for budget_name in budgets_2be_approved.keys():
                budget_list += budget_name + "\n"
            wizard_id = self.pool.get('wizard.budget.import.confirm').create(cr, uid, {'budget_list': budget_list}, context=context)
            context.update({'budgets': budgets_2be_approved})
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
            # Final confirmation wizard
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
