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

class report_account_analytic_chart_export(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        if not context:
            context = {}
        super(report_account_analytic_chart_export, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'localSort': self.localSort,
        })

    def localSort(self, objects, category):
        """
        First give analytic account that have no parent.
        Then sort all kind of analytic accounts by code (except intermission + currency adjustment one)
        Display intermission analytic account
        Finally display currency adjustment analytic account
        """
        # Prepare some values
        res = []
        intermission = False
        fx_gain_loss = False
        parent = False
        # Search in objects (analytic accounts) the intermission account, the adjustment one and those which have no parent
        for o in objects:
            if o.category != category:
                continue
            if not intermission and o.code == 'cc-intermission':
                intermission = o
            if not fx_gain_loss and o.for_fx_gain_loss:
                fx_gain_loss = o
            if not parent and not o.parent_id:
                parent = o
        # Create the table
        if parent:
            res.append(parent)
        res += sorted([x for x in objects if x.category == category and x.parent_id and not x.for_fx_gain_loss and x.code != 'cc-intermission'], key=lambda y: y.code)
        if intermission:
            res.append(intermission)
        if fx_gain_loss:
            res.append(fx_gain_loss)
        return res

SpreadsheetReport('report.account.analytic.chart.export','account.analytic.account','addons/analytic_distribution/report/report_account_analytic_chart_export.mako', parser=report_account_analytic_chart_export)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
