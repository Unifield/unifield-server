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
from osv import fields, osv
import locale

class wizard_interactive_report(osv.osv_memory):
    
    _name = "wizard.interactive.report"
    _inherit = "wizard.csv.report"
    
    def _create_reporting_line(self, line, parent_hierarchy, data):
        max_parent_hierarchy = parent_hierarchy
        data.append([parent_hierarchy,
                     line.code,
                     line.name,
                     locale.format("%d", round(line.allocated_budget), grouping=True),
                     locale.format("%d", round(line.allocated_real), grouping=True),
                     '' if line.allocated_real == 0 else str(locale.format("%d", round(line.allocated_real/line.allocated_budget * 100), grouping=True)) + "%",
                     locale.format("%d", round(line.project_budget), grouping=True),
                     locale.format("%d", round(line.project_real), grouping=True),
                     '' if line.project_real == 0 else str(locale.format("%d", round(line.project_real/line.project_budget * 100), grouping=True)) + "%"])
        
        for child_line in line.child_ids:
            max_parent_hierarchy = self._create_reporting_line(child_line, parent_hierarchy + 1, data)
        return max_parent_hierarchy
    
    def _get_interactive_data(self, cr, uid, contract_id, context=None):
        res = {}
        contract_obj = self.pool.get('financing.contract.contract')
        # Context updated with wizard's value
        contract = contract_obj.browse(cr, uid, contract_id, context=context)
        # Update the context
        context.update({'reporting_currency': contract.reporting_currency.id,
                        'reporting_type': contract.reporting_type,
                        'currency_table_id': contract.currency_table_id.id})
        
        header_data = self._get_contract_header(cr, uid, contract, context=context)
        footer_data = self._get_contract_footer(cr, uid, contract, context=context)
        
        # Values to be set
        allocated_budget = 0
        project_budget = 0
        allocated_real = 0
        project_real = 0
        
        max_parent_hierarchy = 0 # 0 for contract line
        temp_analytic_data = []
        # create "real" lines
        for line in contract.actual_line_ids:
            if not line.parent_id:
                allocated_budget += round(line.allocated_budget)
                project_budget += round(line.project_budget)
                allocated_real += round(line.allocated_real)
                project_real += round(line.project_real)
                current_max_parent_hierarchy = self._create_reporting_line(line, 1, temp_analytic_data)
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
                               locale.format("%d", allocated_budget, grouping=True),
                               locale.format("%d", allocated_real, grouping=True),
                               '' if allocated_real == 0 else str(locale.format("%d", round(allocated_real/allocated_budget * 100), grouping=True)) + "%",
                               locale.format("%d", project_budget, grouping=True),
                               locale.format("%d", project_real, grouping=True),
                               '' if project_real == 0 else str(locale.format("%d", round(project_real/project_budget * 100), grouping=True)) + "%"]]


        # Now, do the hierarchy
        analytic_data = []
        for temp_line in temp_analytic_data:
            final_line = []
            for i in range(max_parent_hierarchy + 1):
                if i != temp_line[0]:
                    # add space
                    final_line.append('')
                else:
                    # add code
                    final_line.append(temp_line[1])
            # add name
            final_line.append(temp_line[2])
            # then, add values depending of the reporting type
            if contract.reporting_type != 'project':
                essai = temp_line[3:6]
                final_line += temp_line[3:6]
            if contract.reporting_type != 'allocated':
                final_line += temp_line[6:9]
            analytic_data.append(final_line)
            
        data = header_data + [[]] + analytic_data + [[]] + footer_data
        return data
    
wizard_interactive_report()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
