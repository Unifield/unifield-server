# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

class sale_order_allocation_report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(sale_order_allocation_report, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'get_distrib_lines': self.get_distrib_lines,
            'get_total_amount': self.get_total_amount,
        })

    def get_distrib_lines(self, line):
        '''
        Return the analytic distribution lines for the order line in parameter
        '''
        distrib = line.analytic_distribution_id or line.order_id.analytic_distribution_id
        return distrib.cost_center_lines or [False]

    def get_total_amount(self, fo):
        total = 0.0
        if fo and fo.order_line:
            for line in fo.order_line:
                if line.price_subtotal:
                    distrib_lines = self.get_distrib_lines(line)
                    total_line = distrib_lines and sum([(dline and dline.percentage * line.price_subtotal / 100) or 0.0 \
                                                        for dline in distrib_lines]) or 0.0
                    total += total_line
        return total

report_sxw.report_sxw('report.sale.order.allocation.report',
                      'sale.order',
                      'addons/sale/report/sale_order_allocation_report.rml',
                      parser=sale_order_allocation_report, header="landscape")

SpreadsheetReport('report.fo.allocation.report.xls', 'sale.order',
                  'addons/sale/report/fo_allocation_report.mako', parser=sale_order_allocation_report)