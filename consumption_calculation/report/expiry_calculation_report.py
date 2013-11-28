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
from report_webkit.webkit_report import WebKitParser
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport

class product_likely_expire_report_parser(report_sxw.rml_parse):
    """UTP-770/UTP-411"""
    def __init__(self, cr, uid, name, context=None):
        super(product_likely_expire_report_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'getLines': self._get_lines,
            'getReportDates': self._get_report_dates,
            'getLineMonths': self._get_line_months,
            'getTotal': self._get_total,
            'getAddress': self._get_instance_addr,
            'getCurrency': self._get_currency,
            'toDate': self.str_to_time,
        })
        
    def _get_lines(self, report, type='all'):
        line_obj = self.pool.get('product.likely.expire.report.line')
        domain = [('report_id', '=', report.id)]
        line_ids = line_obj.search(self.cr, self.uid, domain)
        return line_obj.browse(self.cr, self.uid, line_ids)
        
    def _get_report_dates(self, report):
        return report.get_report_dates(self, report)
        
    def _get_line_months(self, line):
        item_obj = self.pool.get('product.likely.expire.report.item')
        domain = [('line_id', '=', line.id)]
        items_ids = line_obj.search(self.cr, self.uid, domain,
                                    order='period_start')
        return item_obj.browse(self.cr, self.uid, items_ids)
    
    def _get_total(self, report, type='all'):
        total = 0.00
        for line in self._get_lines(report, type):
             total += line.product_id and line.product_id.standard_price * line.expired_qty
        return total
    
    def _get_instance_addr(self):
        instance = self.pool.get('res.users').browse(self.cr, self.uid, self.uid).company_id.instance_id
        return '%s / %s / %s' % (instance.instance, instance.mission or '', instance.code)
    
    def _get_currency(self):
        return self.pool.get('res.users').browse(self.cr, self.uid, self.uid).company_id.currency_id.name
    
    def str_to_time(self, dtime=False):
        if not dtime:
            dtime = time.strftime('%Y-%m-%d')
        if dtime:
            return self.pool.get('date.tools').get_date_formatted(self.cr, self.uid, datetime=dtime)
        return ''
report_sxw.report_sxw('report.product.likely.expire.report_pdf', 'product.likely.expire.report', 'addons/consumption_calculation/report/product_likely_expire.rml', parser=product_likely_expire_report_parser, header=False)


class product_likely_expire_report_xls_parser(SpreadsheetReport):
    """UTP-770"""
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        super(product_likely_expire_report_xls_parser, self).__init__(name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        a = super(product_likely_expire_report_xls_parser, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')
product_likely_expire_report_xls_parser('report.product.likely.expire.report_xls', 'product.likely.expire.report', 'addons/consumption_calculation/report/product_likely_expire_xls.mako', parser=product_likely_expire_report_parser, header='internal')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
