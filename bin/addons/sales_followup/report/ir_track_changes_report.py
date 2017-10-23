# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
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


class ir_track_changes_report_parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(ir_track_changes_report_parser, self).__init__(cr, uid, name, context=context)
        self.cr = cr
        self.uid = uid
        self.user_company = self._get_user_company()
        self.localcontext.update({
            'time': time,
            'getLines': self._get_ir_lines,
            'userCompany': self.user_company,
        })

    def _get_ir_lines(self, report):
        '''
        Return the lines for the report
        '''
        result = []
        for line in report.order_line_ids:
            result.append(self.pool.get('sale.order.line').browse(self.cr, self.uid, line))

        return sorted(result, key=lambda r: (r['order_id']['name']), reverse=True)

    def _get_user_company(self):
        '''
        Return user's current company
        '''
        return self.pool.get('res.users').browse(self.cr, self.uid, self.uid).company_id


class ir_track_changes_report_xls(SpreadsheetReport):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse,
                 header='external', store=False):
        super(ir_track_changes_report_xls, self).__init__(name, table,
                                                          rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        a = super(ir_track_changes_report_xls, self).create(cr, uid, ids,
                                                            data, context)
        return (a[0], 'xls')

ir_track_changes_report_xls(
    'report.ir.track.changes.report_xls',
    'ir.track.changes.wizard',
    'addons/sales_followup/report/ir_track_changes_report_xls.mako',
    parser=ir_track_changes_report_parser,
    header=False)
