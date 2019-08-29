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


class po_track_changes_report_parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(po_track_changes_report_parser, self).__init__(cr, uid, name, context=context)
        self.cr = cr
        self.uid = uid
        self.user_company = self._get_user_company()
        self.localcontext.update({
            'time': time,
            'getLines': self._get_po_lines,
            'userCompany': self.user_company,
            'computeCurrency': self._compute_currency
        })

    def _get_po_lines(self, report):
        '''
        Return the lines for the report
        '''
        result = []
        for line in report.po_line_ids:
            result.append(self.pool.get('purchase.order.line').browse(self.cr, self.uid, line))

        return sorted(result, key=lambda r: (r['order_id']['name']), reverse=True)

    def _get_user_company(self):
        '''
        Return user's current company
        '''
        return self.pool.get('res.users').browse(self.cr, self.uid, self.uid).company_id

    def _compute_currency(self, pol, original=False):
        '''
        Compute an amount of a given currency to the instance's currency
        '''
        currency_obj = self.pool.get('res.currency')

        from_currency_id = pol.currency_id.id
        price = pol.price_unit
        if original:
            if pol.original_currency_id:
                from_currency_id = pol.original_currency_id.id
            if pol.original_price:
                price = pol.original_price

        context = {'date': pol.date_planned}
        to_currency_id = self.user_company['currency_id'].id

        if from_currency_id == to_currency_id:
            return round(pol.price_unit, 2)

        return round(currency_obj.compute(self.cr, self.uid, from_currency_id, to_currency_id, price, round=False, context=context), 2)


class po_track_changes_report_xls(SpreadsheetReport):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse,
                 header='external', store=False):
        super(po_track_changes_report_xls, self).__init__(name, table,
                                                          rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        a = super(po_track_changes_report_xls, self).create(cr, uid, ids,
                                                            data, context)
        return (a[0], 'xls')

po_track_changes_report_xls(
    'report.po.track.changes.report_xls',
    'po.track.changes.wizard',
    'addons/purchase_followup/report/po_track_changes_report_xls.mako',
    parser=po_track_changes_report_parser,
    header=False)
