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
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport

class monthly_budget(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(monthly_budget, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
        })
        return

report_sxw.report_sxw('report.msf.pdf.budget.monthly', 'msf.budget', 'addons/msf_budget/report/monthly_budget.rml', parser=monthly_budget, header=False)


class monthly_budget2(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(monthly_budget2, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
        })
        return

SpreadsheetReport('report.xls.budget.monthly','msf.budget','addons/msf_budget/report/monthly_budget.mako', parser=monthly_budget2)
