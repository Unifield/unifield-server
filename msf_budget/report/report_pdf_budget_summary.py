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
import pooler

class report_pdf_budget_summary(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(report_pdf_budget_summary, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'process': self.process,
        })
        return

    def process(self, selected_lines):
        result = []
        line_names = {}
        pool = pooler.get_pool(self.cr.dbname)
        # Retrieve all names and ids
        for line in selected_lines:
            line_names[line.id] = line.account_id.code + " " + line.account_id.name
        # Process all lines for amounts (avoids multiple calls)
        total_amounts = pool.get('msf.budget.line')._get_total_amounts(self.cr, self.uid, line_names.keys())
        
        # regroup both dicts in a list
        for line_id in line_names:
            result_line = [line_names[line_id],
                           locale.format("%d", total_amounts[line_id]['budget_amount'], grouping=True),
                           locale.format("%d", total_amounts[line_id]['actual_amount'], grouping=True),
                           locale.format("%d", total_amounts[line_id]['balance'], grouping=True),
                           str(total_amounts[line_id]['percentage'])]
            result.append(result_line)
        return result

report_sxw.report_sxw('report.msf.pdf.budget.summary', 'msf.budget', 'addons/msf_budget/report/budget_summary.rml', parser=report_pdf_budget_summary, header=False)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: