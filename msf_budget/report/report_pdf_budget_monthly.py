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
from tools.translate import _
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport

class monthly_budget(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(monthly_budget, self).__init__(cr, uid, name, context=context)
        self.account_codes = self.get_account_codes()
        self.localcontext.update({
            'process': self.process,
            'account_codes': self.account_codes,
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
        # Parse each budget line
        budget_line_ids = [budget_line.id for budget_line in selected_lines]
        budget_amounts = self.pool.get('msf.budget.line')._get_budget_amounts(self.cr, self.uid, budget_line_ids)
        
        for line in selected_lines:
            budget_line_destination_id = line.destination_id and line.destination_id.id or False
            budget_amount = budget_amounts[line.account_id.id, budget_line_destination_id]
            total = sum(budget_amount)
            formatted_budget_values = budget_amount
            # Format name
            line_name = line.account_id.code
            if line.destination_id:
                line_name += " "
                line_name += line.destination_id.code
            line_name += " "
            line_name += line.account_id.name
            
            budget_line = [line_name]
            budget_line += formatted_budget_values
            budget_line.append(total)
            # append to result
            result.append(budget_line)
        return result

report_sxw.report_sxw('report.msf.pdf.budget.monthly', 'msf.budget', 'addons/msf_budget/report/monthly_budget.rml', parser=monthly_budget, header=False)


class monthly_budget2(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(monthly_budget2, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'process': self.process,
            'fetchViewCodes': self.fetchViewCodes,
        })
        return

    def fetchViewCodes(self):
        account_view_ids = self.pool.get('account.account').search(self.cr, self.uid, [('user_type.code', '=', 'view')])
        account_codes = [x.get('code', False) and x.get('code') for x in self.pool.get('account.account').read(self.cr, self.uid, account_view_ids, ['code'])]
        return account_codes

    def process(self, selected_lines):
        result = []
        # Parse each budget line
        budget_line_ids = [budget_line.id for budget_line in selected_lines]
        budget_amounts = self.pool.get('msf.budget.line')._get_budget_amounts(self.cr, self.uid, budget_line_ids)
        
        for line in selected_lines:
            budget_line_destination_id = line.destination_id and line.destination_id.id or False
            budget_amount = budget_amounts[line.account_id.id, budget_line_destination_id]
            total = locale.format("%d", sum(budget_amount), grouping=True)
            formatted_budget_values = budget_amount
            # Format name

            col_1 = line.account_id.code
            if line.destination_id:
               col_1 += " - "
               col_1 += line.destination_id.code
            col_2 = line.account_id.name
            
            budget_line = [col_1]
            budget_line += [col_2]
            budget_line += formatted_budget_values
            budget_line.append(total)
            # append to result
            result.append(budget_line)

        return result

SpreadsheetReport('report.xls.budget.monthly','msf.budget','addons/msf_budget/report/budget_monthly_xls.mako', parser=monthly_budget2)
