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

class order_line_allocation(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(order_line_allocation, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'get_total_amount': self.get_total_amount,
        })

    def get_total_amount(self, po):
        total = 0.0
        if po and po.allocation_report_lines:
            total = sum([line.subtotal or 0.0 for line in po.allocation_report_lines])
        return total

report_sxw.report_sxw('report.purchase.order.allocation.report', 
                      'purchase.order.line.allocation.report', 
                      'addons/purchase_allocation_report/report/order_line_allocation.rml', 
                      parser=order_line_allocation, header="landscape")

SpreadsheetReport('report.po.allocation.report.xls', 'purchase.order',
                  'addons/purchase_allocation_report/report/po_allocation_report.mako', parser=order_line_allocation)


class po_line_allocation_report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(po_line_allocation_report, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
        })

report_sxw.report_sxw('report.po.line.allocation.report', 
                      'purchase.order', 
                      'addons/purchase_allocation_report/report/po_line_allocation_report.rml', 
                      parser=order_line_allocation, header="landscape")

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
