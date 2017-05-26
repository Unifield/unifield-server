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

from report import report_sxw
from common_report_header import common_report_header
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from time import strptime

from vertical_integration import report as reportvi

class account_liquidity_balance(report_sxw.rml_parse, common_report_header):

    def __init__(self, cr, uid, name, context=None):
        self.liquidity_sql = reportvi.hq_report_ocb.liquidity_sql  # same SQL request as in OCB VI
        self.period_id = False
        self.instance_ids = False
        super(account_liquidity_balance, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'get_register_data': self._get_register_data,
        })

    def _get_register_data(self):
        """
        Returns a list of dicts, each containing the data of the liquidity registers for the selected period and instances
        """
        instance_ids = self.instance_ids
        period_id = self.period_id
        period = self.pool.get('account.period').browse(self.cr, self.uid, period_id, context=self.context,
                                                        fields_to_fetch=['date_start', 'date_stop'])
        last_day_of_period = period.date_stop
        first_day_of_period = period.date_start
        tm = strptime(first_day_of_period, '%Y-%m-%d')
        year_num = tm.tm_year
        year = str(year_num)
        month = '%02d' % (tm.tm_mon)
        period_yyyymm = "{0}{1}".format(year, month)
        params = (tuple([period_yyyymm]), first_day_of_period, period.id, last_day_of_period, tuple(instance_ids))
        self.cr.execute(self.liquidity_sql, params)
        return self.cr.dictfetchall()

    def set_context(self, objects, data, ids, report_type=None):
        # get the selection made by the user
        self.period_id = data['form'].get('period_id', False)
        self.instance_ids = data['form'].get('instance_ids', False)
        self.context = data.get('context', {})
        return super(account_liquidity_balance, self).set_context(objects, data, ids, report_type)

SpreadsheetReport('report.account.liquidity.balance', 'account.bank.statement',
        'addons/account/report/account_liquidity_balance.mako', parser=account_liquidity_balance)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
