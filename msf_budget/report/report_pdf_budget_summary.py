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

class report_pdf_budget_summary(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(report_pdf_budget_summary, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'process': self.process,
        })
        return

    def process(self, budget_lines):
        """
        Fetch all needed values for given lines at the same time to not do multiple calls.
        """
        result = []
        # Read budget lines to fetch values.
        #+ Use 'commitment' in context to include commitment in actual amount
        lines = self.pool.get('msf.budget.line').read(self.cr, self.uid, [x.id for x in budget_lines], ['line_type', 'name', 'account_code', 'budget_amount', 'actual_amount', 'balance', 'percentage'], context={'commitment': False})
        if lines:
            # Sort first by line_type DESC. Then sort by account_code.
            #+ This is to have first all budget lines sorted by code, then in each code the normal line then budget lines (with destination axis)
            result = sorted(lines, key=lambda x: x.get('line_type', ''), reverse=True)
            result = sorted(result, key=lambda x: x.get('account_code', ''))
        return result

report_sxw.report_sxw('report.msf.pdf.budget.summary', 'msf.budget', 'addons/msf_budget/report/budget_summary.rml', parser=report_pdf_budget_summary, header=False)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
