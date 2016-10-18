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

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport


class stock_mission_report_parser(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context=None):
        super(stock_mission_report_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time
        })


class stock_mission_report_xls_parser(SpreadsheetReport):

    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        super(stock_mission_report_xls_parser, self).__init__(name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        a = super(stock_mission_report_xls_parser, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')

stock_mission_report_xls_parser(
    'report.stock.mission.report_xls',
    'mission.stock.wizard',
    'mission_stock/report/stock_mission_report_xls.mako',
    parser=stock_mission_report_parser,
    header='internal',
)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
