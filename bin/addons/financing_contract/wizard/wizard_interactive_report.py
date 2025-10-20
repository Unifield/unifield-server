# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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
from osv import osv
import locale

class wizard_interactive_report(osv.osv_memory):

    _name = "wizard.interactive.report"
    _inherit = "wizard.csv.report"

    def _get_amount_format(self, context=None):
        """rounding wrapper
        rounding no digit for interactive report, 2 digits for mako/xls report
        returns (has_round(Boolean), format_str(string))
        """
        if context and 'mako' in context:
            return False, "%0.2f"
        return True, "%d"

    def _round(self, amount, context=None):
        """rounding wrapper
        rounding no digit for interactive report, 2 digits for mako/xls report
        return amount
        """
        if context and 'mako' in context:
            # according to stackoverflow rounding does not make sense when using format "%0.2f"
            # http://stackoverflow.com/questions/455612/python-limiting-floats-to-two-decimal-points
            return amount
        return round(amount)  # rounding for 0 digits

    def _create_reporting_line(self, cr, uid, reporting_currency_id, line, parent_hierarchy, data, line_amount_list = {}, out_currency_id=None, context=None):
        has_round, format_str = self._get_amount_format(context)
        max_parent_hierarchy = parent_hierarchy

        #convert to output currency if it has been selected
        if line.id in line_amount_list:
            line_amounts = line_amount_list[line.id]
        else:
            line_amounts =  {'allocated_budget': 0.0,
                             'project_budget': 0.0,
                             'allocated_real': 0.0,
                             'project_real': 0.0}

        # UF-2337: Remove the block of compute, because the value provided in line_amount_list has already been calculated, so it's wrong to recalculate again!
        line_allocated_budget = line_amounts['allocated_budget']
        line_allocated_real = line_amounts['allocated_real']
        line_project_budget = line_amounts['project_budget']
        line_project_real = line_amounts['project_real']

        data.append([parent_hierarchy,
                     line.code,
                     line.name,
                     locale.format_string(format_str, line_allocated_budget, grouping=False),
                     locale.format_string(format_str, line_allocated_real, grouping=False),
                     '0%' if line_allocated_real == 0 or line_allocated_budget == 0 else str(locale.format_string(format_str, self._round(line_allocated_real/line_allocated_budget * 100, context=context), grouping=False)) + "%",
                     locale.format_string(format_str, line_project_budget, grouping=False),
                     locale.format_string(format_str, line_project_real, grouping=False),
                     '0%' if line_project_real == 0 or line_project_budget == 0 else str(locale.format_string(format_str, self._round(line_project_real/line_project_budget * 100, context=context), grouping=False)) + "%"])

        for child_line in line.child_ids:
            new_max_parent_hierarchy = self._create_reporting_line(cr, uid, reporting_currency_id, child_line, parent_hierarchy + 1, data, line_amount_list, out_currency_id, context=context)
            if new_max_parent_hierarchy > max_parent_hierarchy:
                max_parent_hierarchy = new_max_parent_hierarchy
        return max_parent_hierarchy

    def _get_interactive_data(self, cr, uid, contract_id, context=None):
        if context is None:
            context = {}
        has_round, format_str = self._get_amount_format(context)
        contract_obj = self.pool.get('financing.contract.contract')
        bg_obj = self.pool.get('memory.background.report')
        bg_id = context.get('background_id', False)

        # Context updated with wizard's value
        contract = contract_obj.browse(cr, uid, contract_id, context=context)

        # Update the context
        context.update({'reporting_currency': context['out_currency'],
                        'reporting_type': contract.reporting_type,
                        'currency_table_id': contract.currency_table_id.id})

        header_data = self._get_contract_header(cr, uid, contract, context=context)
        footer_data = self._get_contract_footer(cr, uid, contract, context=context)

        # Values to be set
        total_allocated_budget = 0.
        total_project_budget = 0.
        total_allocated_real = 0.
        total_project_real = 0.

        # check the output currency if it has been selected
        out_currency_id = None
        if 'out_currency' in context:
            out_currency_id = context['out_currency']

        max_parent_hierarchy = 0 # 0 for contract line
        temp_analytic_data = []

        # create "real" lines
        line_obj = self.pool.get('financing.contract.format.line')
        actual_line_ids = [x.id for x in contract.actual_line_ids]

        allocated_budget_list = line_obj._get_budget_amount(cr, uid, actual_line_ids, 'allocated_budget', context=context)
        if bg_id:
            bg_obj.update_percent(cr, uid, [bg_id], 0.10)  # 10% of the total process
        project_budget_list = line_obj._get_budget_amount(cr, uid, actual_line_ids, 'project_budget', context=context)
        if bg_id:
            bg_obj.update_percent(cr, uid, [bg_id], 0.20)  # 20% of the total process
        allocated_real_list = line_obj._get_actual_amount(cr, uid, actual_line_ids, 'allocated_real',
                                                          context=context)  # 50% of the total process (see _get_actual_amount method)
        project_real_list = line_obj._get_actual_amount(cr, uid, actual_line_ids, 'project_real',
                                                        context=context)  # 80% of the total process
        line_amount_list = {}
        for id in actual_line_ids:
            line_amount_list[id] = {'allocated_budget': allocated_budget_list[id],
                                    'project_budget': project_budget_list[id],
                                    'allocated_real': allocated_real_list[id],
                                    'project_real': project_real_list[id]}

        for line in contract.actual_line_ids:
            if not line.parent_id:
                line_amounts = line_amount_list[line.id]

                line_allocated_budget = line_amounts['allocated_budget']
                line_allocated_real = line_amounts['allocated_real']
                line_project_budget = line_amounts['project_budget']
                line_project_real = line_amounts['project_real']

                total_allocated_budget += self._round(line_allocated_budget, context=context)
                total_project_budget += self._round(line_project_budget, context=context)
                total_allocated_real += self._round(line_allocated_real, context=context)
                total_project_real += self._round(line_project_real, context=context)
                current_max_parent_hierarchy = self._create_reporting_line(cr, uid, contract.reporting_currency.id, line, 1, temp_analytic_data, line_amount_list, out_currency_id, context=context)
                if current_max_parent_hierarchy > max_parent_hierarchy:
                    max_parent_hierarchy = current_max_parent_hierarchy
        # create header + contract line
        temp_analytic_data = [[0,
                               'Code',
                               'Name',
                               'Earmarked - Budget',
                               'Earmarked - Actuals',
                               'Earmarked - %used',
                               'Total Project - Budget',
                               'Total Project - Actuals',
                               'Total Project - %used']] + temp_analytic_data + [
            [0,
             '',
             'TOTAL',
             locale.format_string(format_str, total_allocated_budget, grouping=False),
             locale.format_string(format_str, total_allocated_real, grouping=False),
             '0%' if total_allocated_real == 0  or total_allocated_budget == 0 else str(locale.format_string(format_str, self._round(total_allocated_real/total_allocated_budget * 100, context=context), grouping=False)) + "%",
             locale.format_string(format_str, total_project_budget, grouping=False),
             locale.format_string(format_str, total_project_real, grouping=False),
             '0%' if total_project_real == 0  or total_project_budget == 0 else str(locale.format_string(format_str, self._round(total_project_real/total_project_budget * 100, context=context), grouping=False)) + "%"]]

        # Now, do the hierarchy
        analytic_data = []
        for temp_line in temp_analytic_data:
            final_line = []
            for i in range(max_parent_hierarchy + 1):
                if i != temp_line[0]:
                    pass
                else:
                    # add code
                    final_line.append(temp_line[1])
            # add name
            final_line.append(temp_line[2])
            # then, add values depending of the reporting type
            if contract.reporting_type != 'project':
                final_line += temp_line[3:6]
            if contract.reporting_type != 'allocated':
                final_line += temp_line[6:9]
            analytic_data.append(final_line)

        if bg_id:
            bg_obj.update_percent(cr, uid, [bg_id], 0.90)  # 90% of the total process
        if context.get('mako',False):
            return analytic_data
        data = header_data + [[]] + analytic_data + [[]] + footer_data
        return data

wizard_interactive_report()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
