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
import calendar
import tools
from tools.translate import _

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport

CONSUMPTION_TYPE = [
    ('fmc', _('FMC -- Forecasted Monthly Consumption')),
    ('amc', _('AMC -- Average Monthly Consumption')),
    ('rac', _('RAC -- Real Average Consumption')),
    ('rr-amc', _('RR-AMC -- RR Average Monthly Consumption')),
]


class product_likely_expire_report_parser(report_sxw.rml_parse):
    """UTP-770/UTP-411"""
    def __init__(self, cr, uid, name, context=None):
        super(product_likely_expire_report_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'getReportPeriod': self._get_report_period,
            'getReportConsumptionType': self._get_report_consumption_type,
            'getReportDates': self._get_report_dates,
            'getReportDatesWithExpiry': self._get_report_dates_with_expiry,
            'getReportNoExpiryFromTo': self._get_report_no_expiry_from_to,
            'getLines': self._get_lines,
            'getLikelyExpiryValueTotal': self._get_likely_expiry_value_total,
            'getLineItems': self._get_line_items,
            'getMonthItemLines': self._get_month_item_lines,
            'getRmlTables': self._get_rml_tables,
            'getRmlNextMonth': self._get_rml_next_month,
            'getRmlLineItemNextMonth': self._get_rml_line_item_next_month,
            'getExpiredQtyColData': self._get_expired_qty_col_data,
            'getAddress': self._get_instance_addr,
            'getCurrency': self._get_currency,
            'toDate': self.str_to_time,
            'toUstr': self.to_ustr,
        })
        self._dates_context = {}
        self._report_context = {}

    def _get_report_period(self, report):
        """get period header(str)"""
        dt_from = self.formatLang(report.date_from, date=True)
        dt_to = self.formatLang(report.date_to, date=True)
        res = tools.ustr("%s - %s" % (dt_from, dt_to,))
        return res

    def _get_report_consumption_type(self, report):
        """get consumption type header(str)"""
        res = ""
        for val, label in CONSUMPTION_TYPE:
            if val == report.consumption_type:
                if val in ('amc', 'rr-amc'):
                    return _(label) + tools.ustr(' (' + self.str_to_time(report.consumption_from) + ' - ' + self.str_to_time(report.consumption_to) + ')')
                else:
                    return _(label)
        return res

    def _get_report_dates(self, report):
        """get months period header(str)
        return list(tuple(date, str)) of month headers (1st day of month)"""
        return self.pool.get('product.likely.expire.report').get_report_dates_multi(report)

    def _get_report_dates_with_expiry(self, report):
        dates = self.pool.get('product.likely.expire.report').get_report_dates_multi(report)
        res = []
        self._report_context['no_expiry_from_to'] = {}
        for dt_tuple in dates:
            if not self._get_month_item_lines_ids(report, dt_tuple[0]):
                self._report_context['no_expiry_from_to'][dt_tuple[1]] = "No expiry for %s" % (dt_tuple[1], )
            res.append(dt_tuple)
        return res

    def _get_report_no_expiry_from_to(self, date):
        if date:
            return self._report_context.get('no_expiry_from_to', {}).get(date)
        return False

    def _get_lines(self, report, type='all'):
        """get report lines('product.likely.expire.report.line')"""
        line_obj = self.pool.get('product.likely.expire.report.line')
        domain = [('report_id', '=', report.id)]
        line_ids = line_obj.search(self.cr, self.uid, domain)
        return line_obj.browse(self.cr, self.uid, line_ids)

    def _get_likely_expiry_value_total(self, report):
        """get likely expiry value total (float)"""
        lines = self._get_lines(report)
        res = 0.
        for l in lines:
            res += l.total_likely_value
        return res

    def _get_line_items(self, line):
        """get line items 'product.likely.expire.report.item'
        for each line 'product.likely.expire.report.line'
        ordered by id
        """
        item_obj = self.pool.get('product.likely.expire.report.item')
        domain = [('line_id', '=', line.id)]
        items_ids = item_obj.search(self.cr, self.uid, domain)
        if not items_ids:
            return False
        return item_obj.browse(self.cr, self.uid, items_ids)

    def _get_month_item_lines_ids(self, report, month_date, report_type=''):
        """get month items('product.likely.expire.report.item')
        """
        lines_obj = self.pool.get('product.likely.expire.report.line')
        item_obj = self.pool.get('product.likely.expire.report.item')
        item_line_obj = self.pool.get('product.likely.expire.report.item.line')

        # 'report lines' in 'month_date'
        domain = [('report_id', '=', report.id)]
        lines_ids = lines_obj.search(self.cr, self.uid, domain)

        if month_date == 'expired_qty_col':
            domain = [
                ('line_id', 'in', lines_ids),
                ('name', '=', 'expired_qty_col'),
            ]
        else:
            dt_from = '%d-%d-01' % (month_date.year, month_date.month, )
            dt_to = '%d-%d-%s' % (month_date.year, month_date.month, calendar.monthrange(month_date.year, month_date.month)[1])
            domain = [
                ('line_id', 'in', lines_ids),
                ('period_start', '>=', dt_from),
                ('period_start', '<=', dt_to)
            ]
            if report_type == 'xls':
                domain.append(('name', '!=', 'expired_qty_col'))

        items_ids = item_obj.search(self.cr, self.uid, domain)

        # 'line item' lines
        domain = [('item_id', 'in', items_ids)]
        item_lines_ids = item_line_obj.search(self.cr, self.uid, domain,
                                              order='expired_date')
        return item_lines_ids

    def _get_month_item_lines(self, report, month_date, report_type=''):
        """get month items('product.likely.expire.report.item')
        """
        item_line_obj = self.pool.get('product.likely.expire.report.item.line')
        return item_line_obj.browse(self.cr, self.uid, self._get_month_item_lines_ids(report, month_date, report_type=report_type))

    def _get_rml_tables(self, report, month_cols_count):
        """
        compute number of table to display given:
            - month_cols_count: cols count to display
            - total month count in report
        return a fake list of table count len for repeatIn
        """
        if not month_cols_count or month_cols_count < 1:
            month_cols_count = 1
        res = month_cols_count
        dates = self._get_report_dates(report)
        if dates:
            l = len(dates)
            if month_cols_count > 1:
                res = l // month_cols_count
                if l % month_cols_count:
                    res += 1
        if not res or res < 1:
            res = 1
        res_list = []
        for i in range(res):
            res_list.append(i)
        return res_list

    def _get_rml_next_month(self, report):
        if not 0 in self._dates_context:
            self._dates_context[0] = {
                'dates': self._get_report_dates(report),
                'index': 0,
            }
        date_tuple = self._dates_context[0]['dates'][self._dates_context[0]['index']]
        self._dates_context[0]['index'] += 1
        return date_tuple[1]

    def _get_rml_line_item_next_month(self, report, line):
        """get line items 'product.likely.expire.report.item'
        for each line 'product.likely.expire.report.line'
        of the month (for rml report)
        """
        if not line.id in self._dates_context:
            self._dates_context[line.id] = {
                'dates': self._get_report_dates(report),
                'index': 0,
            }
        date_tuple = self._dates_context[line.id]['dates'][self._dates_context[line.id]['index']]
        self._dates_context[line.id]['index'] += 1
        month_date = date_tuple[0]

        item_obj = self.pool.get('product.likely.expire.report.item')
        dt_from = '%d-%d-01' % (month_date.year, month_date.month, )
        dt_to = '%d-%d-%s' % (month_date.year, month_date.month, calendar.monthrange(month_date.year, month_date.month)[1], )
        domain = [
            ('line_id', '=', line.id),
            ('period_start', '>=', dt_from),
            ('period_start', '<=', dt_to),
        ]
        items_ids = item_obj.search(self.cr, self.uid, domain,
                                    order='period_start')  # items ordered by date
        if isinstance(items_ids, int):
            items_ids = [items_ids]
        res = ''
        if line.in_stock != line.total_expired:
            if items_ids:
                item = item_obj.browse(self.cr, self.uid, items_ids)[0]
                aqty = item.available_qty
                if not aqty:
                    aqty = 0.
                if item.expired_qty:
                    res = "%s (%s)" % (self.formatLang(aqty), self.formatLang(item.expired_qty), )
                else:
                    res = self.formatLang(aqty)
        else:
            res = '0.00'
        return res

    def _get_expired_qty_col_data(self, line_id):
        item_obj = self.pool.get('product.likely.expire.report.item')

        item_ids = item_obj.search(self.cr, self.uid, [('line_id', '=', line_id), ('name', '=', 'expired_qty_col')])
        if item_ids:
            expired_qty = item_obj.browse(self.cr, self.uid, item_ids[0]).expired_qty or '0'
        else:
            expired_qty = ''

        return expired_qty

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

    def to_ustr(self, val):
        return tools.ustr(val)


report_sxw.report_sxw('report.product.likely.expire.report_pdf', 'product.likely.expire.report', 'consumption_calculation/report/product_likely_expire.rml', parser=product_likely_expire_report_parser, header=False)

class product_likely_expire_report_xls_parser(SpreadsheetReport):
    """UTP-770"""
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        super(product_likely_expire_report_xls_parser, self).__init__(name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        a = super(product_likely_expire_report_xls_parser, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')
product_likely_expire_report_xls_parser('report.product.likely.expire.report_xls', 'product.likely.expire.report', 'addons/consumption_calculation/report/product_likely_expire_xls.mako', parser=product_likely_expire_report_parser, header='internal')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
