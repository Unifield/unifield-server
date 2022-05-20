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
import datetime
from tools.translate import _
from base import currency_date


class msf_budget_tools(osv.osv):
    _name = "msf.budget.tools"

    def get_expense_accounts(self, cr, uid, context=None):
        """
        Get all "is_analytic_addicted" accounts except if context notify to only use expense ones.
        By using this method you also retrieve ALL parents EXCEPT the first one: MSF account.
        """
        # Checks
        if context is None:
            context = {}
        # Prepare some values
        res = []
        account_obj = self.pool.get('account.account')
        # get the last parent
        top_ids = account_obj.search(cr, uid, [('code', '=', 'MSF')], context=context)
        # get normal analytic-a-holic accounts. UTP-944: only expenses ones if "only_expenses" in context. Do not include Extra-accounting accounts and incomes one.
        domain = [('type', '!=', 'view'), ('user_type_report_type', '!=', 'none')]
        if context.get('only_expenses', False) and context.get('only_expenses') is True:
            domain += [('user_type_code', '=', 'expense'), ('user_type_report_type', '=', 'expense')]
        else:
            domain += [('is_analytic_addicted', '=', True)]
        account_ids = account_obj.search(cr, uid, domain, context=context)
        if account_ids:
            parent_ids = account_obj._get_parent_of(cr, uid, account_ids, context=context)
            if parent_ids:
                res = [x for x in parent_ids if x not in top_ids]
        return res

    def get_budget_line_template(self, cr, uid, context=None):
        """
        Create a template that contains all budget line main values for a new budget.
        """
        # Some checks
        if context is None:
            context = {}
        # Prepare some values
        res = []
        # Search all income/expense accounts (except if context contains "only_expenses" set to True)
        account_ids = self.get_expense_accounts(cr, uid, context=context)
        if not account_ids:
            return []
        # We use a SQL request to keep an order of accounts regarding their parents so that parents could be created before their childs.
        sql = """
            SELECT id, CASE WHEN type != 'view' THEN 'normal' ELSE 'view' END AS account_type, parent_id
            FROM account_account
            WHERE id IN %s
            ORDER BY parent_left"""
        cr.execute(sql, (tuple(account_ids),))
        if not cr.rowcount:
            raise osv.except_osv(_('Error'), _('Unable to find needed info.'))
        tmp_res = cr.fetchall()
        # We take destination ids for a given account (and we make a dictionnary to be quickly used)
        accounts = self.pool.get('account.account').read(cr, uid, account_ids, ['destination_ids'], context=context)
        destinations = {}
        for account in accounts:
            destinations[account.get('id')] = account.get('destination_ids')
        # We then create the final result with all needed elements
        for line_id, line_type, parent_id in tmp_res:
            line_vals = {
                'id': line_id,
                'type': line_type,
                'parent_id': parent_id,
                'destination_ids': []
            }
            if line_id in destinations:
                line_vals.update({'destination_ids': destinations[line_id]})
            res.append(line_vals)
        return res

    def create_budget_lines(self, cr, uid, budget_id, sequence=False, context=None):
        """
        Create budget lines for a given budget.
        If no budget: do nothing.
        If no sequence: only create budget lines without any specific amounts.

        Creation synthesis:
        1/ get the initial template
        2/ for each line create its budget line
        3/a) if sequence: fetch budget values and fill in destination lines, normal lines and parents
        3/b) if NO sequence, just create destination lines, normal lines and parents.
        """
        # Some checks
        if context is None:
            context = {}
        if not budget_id:
            return False
        # Prepare some values
        a_obj = self.pool.get('account.account')
        chart_of_account_ids = a_obj.search(cr, uid, [('code', '=', 'MSF')], context=context)
        budget_line_obj = self.pool.get('msf.budget.line')
        imported_obj = self.pool.get('imported.msf.budget.line')
        sql = """
            SELECT SUM(COALESCE(month1, 0.0)), SUM(COALESCE(month2, 0.0)), SUM(COALESCE(month3, 0.0)), SUM(COALESCE(month4, 0.0)), SUM(COALESCE(month5, 0.0)), SUM(COALESCE(month6, 0.0)), SUM(COALESCE(month7, 0.0)), SUM(COALESCE(month8, 0.0)), SUM(COALESCE(month9, 0.0)), SUM(COALESCE(month10, 0.0)), SUM(COALESCE(month11, 0.0)), SUM(COALESCE(month12, 0.0))
            FROM msf_budget_line
            WHERE id IN %s"""
        # Get budget line template from budget tools
        template = self.get_budget_line_template(cr, uid, context=context)
        # Browse each budget line and create needed values
        to_proceed = []
        mapping_accounts = {}
        for budget_line in template:
            # Create budget line
            line_id = budget_line.get('id')
            line_type = budget_line.get('type')
            parent_id = budget_line.get('parent_id', False)
            # Do not use top parent account (those in chart_of_account_ids)
            if parent_id in chart_of_account_ids:
                parent_id = False
            budget_line_vals = {
                'budget_id': budget_id,
                'account_id': line_id,
                'line_type': line_type,
                'month1': 0.0,
                'month2': 0.0,
                'month3': 0.0,
                'month4': 0.0,
                'month5': 0.0,
                'month6': 0.0,
                'month7': 0.0,
                'month8': 0.0,
                'month9': 0.0,
                'month10': 0.0,
                'month11': 0.0,
                'month12': 0.0,
            }
            if parent_id:
                if parent_id not in mapping_accounts:
                    raise osv.except_osv(_('Error'), _('You did not create budget line in the right order. A parent does not exist!'))
                budget_line_vals.update({'parent_id': mapping_accounts[parent_id]})
            # Create line
            budget_line_id = budget_line_obj.create(cr, uid, budget_line_vals, context=context)
            to_proceed.append(budget_line_id)
            mapping_accounts[line_id] = budget_line_id
            if line_type == 'normal':
                # Update vals with the new line type
                budget_line_vals.update({
                    'line_type': 'destination',
                })
                # Browse each destination to create its line
                for destination_id in budget_line.get('destination_ids', []):
                    budget_line_vals.update({
                        'destination_id': destination_id,
                        'month1': 0.0,
                        'month2': 0.0,
                        'month3': 0.0,
                        'month4': 0.0,
                        'month5': 0.0,
                        'month6': 0.0,
                        'month7': 0.0,
                        'month8': 0.0,
                        'month9': 0.0,
                        'month10': 0.0,
                        'month11': 0.0,
                        'month12': 0.0,
                        'parent_id': budget_line_id
                    })
                    # Fetch values if sequence is given (which permit to find some lines)
                    if sequence:
                        # Search if the CSV file have this kind of tuple account/destination and fetch values
                        csv_line_ids = imported_obj.search(cr, uid, [('account_id', '=', line_id), ('destination_id', '=', destination_id)], context=context)
                        # If yes, complete budget values from month1 to month12
                        if csv_line_ids:
                            csv_line = imported_obj.read(cr, uid, csv_line_ids[0], ['month1', 'month2', 'month3', 'month4', 'month5', 'month6', 'month7', 'month8', 'month9', 'month10', 'month11', 'month12'])
                            budget_line_vals.update({
                                'month1': csv_line.get('month1', 0.0),
                                'month2': csv_line.get('month2', 0.0),
                                'month3': csv_line.get('month3', 0.0),
                                'month4': csv_line.get('month4', 0.0),
                                'month5': csv_line.get('month5', 0.0),
                                'month6': csv_line.get('month6', 0.0),
                                'month7': csv_line.get('month7', 0.0),
                                'month8': csv_line.get('month8', 0.0),
                                'month9': csv_line.get('month9', 0.0),
                                'month10': csv_line.get('month10', 0.0),
                                'month11': csv_line.get('month11', 0.0),
                                'month12': csv_line.get('month12', 0.0),
                            })
                    # Create destination line
                    budget_line_obj.create(cr, uid, budget_line_vals, context=context)
        # Fill in parent lines (only if sequence is given which means that we have probably some values in destination lines)
        if sequence:
            vals_headers = ['month1', 'month2', 'month3', 'month4', 'month5', 'month6', 'month7', 'month8', 'month9', 'month10', 'month11', 'month12']
            for budget_line_id in to_proceed:
                # Search child_ids
                child_ids = budget_line_obj.search(cr, uid, [('parent_id', 'child_of', budget_line_id)])
                # Do the sum of them
                cr.execute(sql, (tuple(child_ids),))
                tmp_res = cr.fetchall()
                # If result, write on the given budget line the result
                if tmp_res:
                    budget_line_vals = dict(zip(vals_headers, tmp_res[0]))
                    budget_line_obj.write(cr, uid, budget_line_id, budget_line_vals, context=context)
        return True

    def _create_expense_account_line_amounts(self, cr, uid, account_ids, actual_amounts, context=None):
        # Some checks
        if context is None:
            context = {}
        if isinstance(account_ids, (int, long)):
            account_ids = [account_ids]
        a_obj = self.pool.get('account.account')
        # Browse accounts
        for account_id in account_ids:
            if (account_id, False) not in actual_amounts:
                account = a_obj.browse(cr, uid, account_id, context=context)
                result = [0] * 12
                if account.type == 'view':
                    # children are accounts
                    for child_account in account.child_id:
                        if (child_account.id, False) not in actual_amounts:
                            self._create_expense_account_line_amounts(cr, uid, child_account.id, actual_amounts, context=context)
                        result = [sum(pair) for pair in zip(result, actual_amounts[child_account.id, False])]
                else:
                    # children are account, destination tuples (already in actual_amounts)
                    # get all tuples starting with (account_id)
                    for account_destination in [tuple_acc_dest for tuple_acc_dest in actual_amounts.keys() if tuple_acc_dest[0] == account_id and tuple_acc_dest[1] is not False]:
                        result = [sum(pair) for pair in zip(result, actual_amounts[account_destination])]
                actual_amounts[account_id, False] = result
        return

    def _get_cost_center_ids(self, cr, uid, browse_cost_center):
        return self.pool.get('account.analytic.account').search(cr, uid, [('parent_id', 'child_of', browse_cost_center.id)])

    def _get_actual_amounts(self, cr, uid, output_currency_id, domain=[], context=None):
        # Input: domain for the selection of analytic lines (cost center, date, etc...)
        # Output: a dict of list {(general_account_id, destination_id): [jan_actual, feb_actual,...]}
        res = {}
        if context is None:
            context = {}
        destination_obj = self.pool.get('account.destination.link')
        # list to store every existing destination link in the system
        account_ids = self.get_expense_accounts(cr, uid, context=context)

        destination_link_ids = destination_obj.search(cr, uid, [('account_id', 'in',  account_ids)], context=context)
        account_destination_ids = [(dest.account_id.id, dest.destination_id.id)
                                   for dest
                                   in destination_obj.browse(cr, uid, destination_link_ids, context=context)]

        # Fill all general accounts
        for account_id, destination_id in account_destination_ids:
            res[account_id, destination_id] = [0] * 12

        # fill search domain (one search for all analytic lines)
        account_dest_combinations = {}
        # create a dict with key = account, and value = list of the related possible destinations
        for acc_dest_id in account_destination_ids:
            if acc_dest_id[0] not in account_dest_combinations:
                account_dest_combinations[acc_dest_id[0]] = []
            account_dest_combinations[acc_dest_id[0]].append(acc_dest_id[1])
        i = 0
        for acc in account_dest_combinations:
            i += 1
            if i < len(account_dest_combinations):
                # don't add the "or" at least iteration
                domain.append('|')
            domain.append('&')
            domain.append(('general_account_id', '=', acc))
            domain.append(('destination_id', 'in', account_dest_combinations[acc]))

        # Analytic domain is now done; lines are retrieved and added
        analytic_line_obj = self.pool.get('account.analytic.line')
        keep_looping = True
        offset = 0
        while keep_looping:
            analytic_lines = analytic_line_obj.search(cr, uid, domain, offset=offset, limit=1000, context=context)
            if not analytic_lines:
                break
            if isinstance(analytic_lines, int) or len(analytic_lines) < 1000:
                keep_looping = False
            offset += 1000
            # use currency_table_id
            currency_table = None
            if 'currency_table_id' in context:
                currency_table = context['currency_table_id']

            if 'background_id' in context:
                bg_id = context['background_id']
                bg_report_obj = self.pool.get('memory.background.report')
            else:
                bg_id = None
                bg_report_obj = None

            # parse each line and add it to the right array
            analytic_line_count = 0
            for analytic_line in analytic_line_obj.browse(cr, uid, analytic_lines, context=context):
                curr_date = currency_date.get_date(self, cr, analytic_line.document_date, analytic_line.date, source_date=analytic_line.source_date)
                date_context = {'currency_date': curr_date,
                                'currency_table_id': currency_table}
                actual_amount = self.pool.get('res.currency').compute(cr,
                                                                      uid,
                                                                      analytic_line.currency_id.id,
                                                                      output_currency_id,
                                                                      analytic_line.amount_currency or 0.0,
                                                                      round=True,
                                                                      context=date_context)
                # add the amount to correct month
                month = datetime.datetime.strptime(analytic_line.date, '%Y-%m-%d').month
                res[analytic_line.general_account_id.id, analytic_line.destination_id.id][month - 1] += round(actual_amount, 2)

                if bg_report_obj:
                    analytic_line_count += 1
                    percent = analytic_line_count / float(len(analytic_lines) + 1)  # add 1
                    # to the total because task is not finish at the end of the for
                    # loop, there is some ZIP work to do
                    bg_report_obj.update_percent(cr, uid, [bg_id], percent)

        # after all lines are parsed, absolute of every column
        for line in res.keys():
            res[line] = [-x for x in res[line]]

        # do the view lines
        self._create_expense_account_line_amounts(cr, uid, account_ids, res, context=context)

        return res

msf_budget_tools()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
