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

import time
import csv
import StringIO
import pooler
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport

class report_account_analytic_chart_export(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        if not context:
            context = {}
        super(report_account_analytic_chart_export, self).__init__(cr, uid, name, context=context)

SpreadsheetReport('report.account.analytic.chart.export','account.analytic.account','addons/analytic_distribution/report/report_account_analytic_chart_export.mako', parser=report_account_analytic_chart_export)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
