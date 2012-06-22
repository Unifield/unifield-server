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
    
    def _create_reporting_line(self, cr, uid, reporting_currency_id, line, parent_hierarchy, data, out_currency_id=None, context=None):
        max_parent_hierarchy = parent_hierarchy
        
        #convert to output currency if it has been selected
        line_allocated_budget = line.allocated_budget
        line_allocated_real = line.allocated_real
        line_project_budget = line.project_budget
        line_project_real = line.project_real
        
        # if the output currency has been selected other than the reporting currency
        if out_currency_id and out_currency_id != reporting_currency_id:
            currency_obj = self.pool.get('res.currency')
            line_allocated_budget = currency_obj.compute(cr, uid, reporting_currency_id, out_currency_id,
                                                    line_allocated_budget or 0.0, round=True, context=context)

            line_allocated_real = currency_obj.compute(cr, uid, reporting_currency_id, out_currency_id,
                                                  line_allocated_real or 0.0,round=True, context=context)

            line_project_budget = currency_obj.compute(cr, uid, reporting_currency_id, out_currency_id,
                                                  line_project_budget or 0.0, round=True, context=context)

            line_project_real = currency_obj.compute(cr, uid, reporting_currency_id, out_currency_id,
                                                line_project_real or 0.0, round=True, context=context)
        
        data.append([parent_hierarchy,
                     line.code,
                     line.name,
                     locale.format("%d", line_allocated_budget, grouping=True),
                     locale.format("%d", line_allocated_real, grouping=True),
                     '' if line_allocated_budget == 0 else str(locale.format("%d", round(line_allocated_real/line_allocated_budget * 100), grouping=True)) + "%",
                     locale.format("%d", line_project_budget, grouping=True),
                     locale.format("%d", line_project_real, grouping=True),
                     '' if line_project_budget == 0 else str(locale.format("%d", round(line_project_real/line_project_budget * 100), grouping=True)) + "%"])
        
        for child_line in line.child_ids:
            max_parent_hierarchy = self._create_reporting_line(cr, uid, reporting_currency_id, child_line, parent_hierarchy + 1, data, out_currency_id, context)
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
        total_allocated_budget = 0
        total_project_budget = 0
        total_allocated_real = 0
        total_project_real = 0
        
        # check the output currency if it has been selected        
        out_currency_amount = contract.grant_amount
        out_currency_id = None
        if 'output_currency' in context:
            out_currency_id = context.get('output_currency').id
        
        max_parent_hierarchy = 0 # 0 for contract line
        temp_analytic_data = []
        currency_obj = self.pool.get('res.currency')
        
        # create "real" lines
        for line in contract.actual_line_ids:
            if not line.parent_id:
                line_allocated_budget = line.allocated_budget
                line_allocated_real = line.allocated_real
                line_project_budget = line.project_budget
                line_project_real = line.project_real
                
                # if the output currency has been selected other than the reporting currency then convert the given value to 
                # the selected output currency for exporting
                if out_currency_id and out_currency_id != contract.reporting_currency.id:
                    currency_obj = self.pool.get('res.currency')
                    line_allocated_budget = currency_obj.compute(cr, uid, contract.reporting_currency.id, out_currency_id,
                                                            line_allocated_budget or 0.0, round=True, context=context)
        
                    line_allocated_real = currency_obj.compute(cr, uid, contract.reporting_currency.id, out_currency_id,
                                                          line_allocated_real or 0.0,round=True, context=context)
        
                    line_project_budget = currency_obj.compute(cr, uid, contract.reporting_currency.id, out_currency_id,
                                                          line_project_budget or 0.0, round=True, context=context)
        
                    line_project_real = currency_obj.compute(cr, uid, contract.reporting_currency.id, out_currency_id,
                                                        line_project_real or 0.0, round=True, context=context)
    
                total_allocated_budget += round(line_allocated_budget)
                total_project_budget += round(line_project_budget)
                total_allocated_real += round(line_allocated_real)
                total_project_real += round(line_project_real)
                current_max_parent_hierarchy = self._create_reporting_line(cr, uid, contract.reporting_currency.id, line, 1, temp_analytic_data, out_currency_id, context)
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
                               locale.format("%d", total_allocated_budget, grouping=True),
                               locale.format("%d", total_allocated_real, grouping=True),
                               '' if total_allocated_budget == 0 else str(locale.format("%d", round(total_allocated_real/total_allocated_budget * 100), grouping=True)) + "%",
                               locale.format("%d", total_project_budget, grouping=True),
                               locale.format("%d", total_project_real, grouping=True),
                               '' if total_project_budget == 0 else str(locale.format("%d", round(total_project_real/total_project_budget * 100), grouping=True)) + "%"]]


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
