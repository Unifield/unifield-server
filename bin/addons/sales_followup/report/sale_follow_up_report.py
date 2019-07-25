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


class sale_follow_up_report_parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(sale_follow_up_report_parser, self).__init__(cr, uid, name,
                                                           context=context)
        self.localcontext.update({
            'time': time,
            'parse_date_xls': self._parse_date_xls,
            'upper': self._upper,
        })
        self._dates_context = {}
        self._report_context = {}

        #self.module_instance = self.pool.get('sale.order.followup')

    def _parse_date_xls(self, dt_str, is_datetime=True):
        if not dt_str or dt_str == 'False':
            return ''
        if is_datetime:
            dt_str = dt_str[0:10] if len(dt_str) >= 10 else ''
        if dt_str:
            dt_str += 'T00:00:00.000'
        return dt_str

    def _upper(self, s):
        if not isinstance(s, (str, unicode)):
            return s
        if s:
            return s.upper()
        return s

report_sxw.report_sxw(
    'report.sales.follow.up.report_pdf',
    'sale.order.followup',
    'addons/sales_followup/report/sale_follow_up_report.rml',
    parser=sale_follow_up_report_parser,
    header=False)


class sale_follow_up_report_xls(SpreadsheetReport):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse,
                 header='external', store=False):
        super(sale_follow_up_report_xls, self).__init__(name, table,
                                                        rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        a = super(sale_follow_up_report_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')

sale_follow_up_report_xls(
    'report.sales.follow.up.report_xls',
    'sale.order.followup',
    'addons/sales_followup/report/sale_follow_up_report_xls.mako',
    parser=sale_follow_up_report_parser,
    header=False)
