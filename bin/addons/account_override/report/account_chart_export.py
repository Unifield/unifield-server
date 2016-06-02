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

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport

class report_account_chart_export(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        if context is None:
            context = {}

        super(report_account_chart_export, self).__init__(cr, uid, name, context=context)

        self.localcontext.update({
            'get_balance': self._get_balance,
        })

    def _get_balance(self, o, objects):
        if not o.parent_id:
            # US-1179/1f root account: compute total balance
            # when data is filtered, MSF account total balance does not take into account filtering,
            # consistency: always compute it with sum of 1-9 level 1 accounts
            # (accounts are identified by parent as level is not maintained anymore)
            res = 0.
            for c in objects:
                if c.parent_id.id == o.id:
                    res += c.balance
            return res

        return o.balance

SpreadsheetReport('report.account.chart.export','account.account','addons/account_override/report/account_chart_export.mako', parser=report_account_chart_export)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
