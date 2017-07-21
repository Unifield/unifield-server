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

from datetime import datetime
from datetime import timedelta

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport


class sale_donation_stock_moves_report_parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(sale_donation_stock_moves_report_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
        })

class sale_donation_stock_moves_report_xls(SpreadsheetReport):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse,
                 header='external', store=False):
        super(sale_donation_stock_moves_report_xls, self).__init__(name, table,
                                                              rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        a = super(sale_donation_stock_moves_report_xls, self).create(cr, uid, ids,
                                                                data, context)
        return (a[0], 'xls')

sale_donation_stock_moves_report_xls(
    'report.sale.donation.stock.moves.report_xls',
    'sale.donation.stock.moves',
    'addons/sale/report/sale_donation_stock_moves_report_xls.mako',
    parser=sale_donation_stock_moves_report_parser,
    header=False)
