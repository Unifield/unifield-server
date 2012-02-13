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
from report import report_sxw
import locale

class monthly_budget(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(monthly_budget, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'process': self.process,
        })
        return

    def process(self, selected_lines):
        result = []
        # Parse each budget line
        for line in selected_lines:
            if line.budget_values:
                budget_values = eval(line.budget_values)
                total = locale.format("%d", sum(budget_values), grouping=True)
                formatted_budget_values = [locale.format("%d", x, grouping=True) for x in budget_values]
                budget_line = [line.account_id.code + " " + line.account_id.name]
                budget_line += formatted_budget_values
                budget_line.append(total)
                # append to result
                result.append(budget_line)
        return result

report_sxw.report_sxw('report.msf.pdf.budget.monthly', 'msf.budget', 'addons/msf_budget/report/monthly_budget.rml', parser=monthly_budget, header=False)
