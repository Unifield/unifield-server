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

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from tools.translate import _
import datetime


class reserved_products_report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(reserved_products_report, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'getInstanceName': self.get_instance_name,
            'getDate': self.get_date,
            'getLoc': self.get_loc,
            'getProd': self.get_prod,
            'getLines': self.get_lines,
        })

    def get_instance_name(self):
        return self.pool.get('res.users').browse(self.cr, self.uid, self.uid).company_id.instance_id.name

    def get_date(self):
        return datetime.date.today()

    def get_loc(self):
        return self.datas['loc_name']

    def get_prod(self):
        return self.datas['prod_name']

    def get_lines(self):
        return self.datas['lines_data']


SpreadsheetReport(
    'report.reserved.products.report_xls',
    'reserved.products.wizard',
    'stock/report/reserved_products_report_xls.mako',
    parser=reserved_products_report
)
