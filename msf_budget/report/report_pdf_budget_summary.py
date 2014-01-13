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
        self.account_codes = self.get_account_codes()
        self.localcontext.update({
            'process': self.process,
            'isBold': self.isBold,
        })
        return

    def get_account_codes(self):
        account_view_ids = self.pool.get('account.account').search(self.cr, self.uid, [('type', '=', 'view')])
        account_codes = [x.get('code', False) and x.get('code') for x in self.pool.get('account.account').read(self.cr, self.uid, account_view_ids, ['code'])]
        return account_codes

    def isBold(self, line):
      if line[0] and line[0].split() and line[0].split()[0] in self.account_codes:
          return True
      return False

    def process(self, selected_lines):
        result = []
        line_names = {}
        pool = pooler.get_pool(self.cr.dbname)
        # Retrieve all names and ids
        for line in selected_lines:
            line_name = line.account_id.code
            if line.destination_id:
                line_name += " "
                line_name += line.destination_id.code
            line_name += " "
            line_name += line.account_id.name
            line_names[line.id] = line_name
        # Process all lines for amounts (avoids multiple calls)
        total_amounts = pool.get('msf.budget.line')._get_total_amounts(self.cr, self.uid, line_names.keys())
        
        sorted_line_names = sorted(line_names)
        
        # regroup both dicts in a list
        for line_id in sorted_line_names:
            result_line = [line_names[line_id],total_amounts[line_id]['budget_amount'],total_amounts[line_id]['actual_amount'], total_amounts[line_id]['balance'], float(total_amounts[line_id]['percentage'])]
            result.append(result_line)
        return result

report_sxw.report_sxw('report.msf.pdf.budget.summary', 'msf.budget', 'addons/msf_budget/report/budget_summary.rml', parser=report_pdf_budget_summary, header=False)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
