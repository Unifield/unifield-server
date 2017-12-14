# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2017 MSF, TeMPO Consulting
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


class cash_request_parser(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context=None):
        if context is None:
            context = {}
        super(cash_request_parser, self).__init__(cr, uid, name, context=context)
        self.total = {}
        self.localcontext.update({
            'total_liquidity': self._get_total_liquidity,
            'total_payable': self._get_total_payable,
            'total_commitment': self._get_total_commitment,
            'total_expense': self._get_total_expense,
            'total_cash_requested': self._get_total_cash_requested,
        })

    def _get_total(self, o):
        """
        Returns a dict with the different totals to display in the export
        """
        if not self.total:
            liquidity = payable = commitment = expense = cash_requested = 0.0
            for rec in o.recap_mission_ids:
                liquidity += rec.liquidity_amount or 0.0
                payable += rec.payable_amount or 0.0
                commitment += rec.commitment_amount or 0.0
                expense += rec.expense_amount or 0.0
                cash_requested += rec.total or 0.0
            self.total = {'liquidity': liquidity,
                          'payable': payable,
                          'commitment': commitment,
                          'expense': expense,
                          'cash_requested': cash_requested}
        return self.total

    def _get_total_liquidity(self, o):
        return self._get_total(o)['liquidity']

    def _get_total_payable(self, o):
        return self._get_total(o)['payable']

    def _get_total_commitment(self, o):
        return self._get_total(o)['commitment']

    def _get_total_expense(self, o):
        return self._get_total(o)['expense']

    def _get_total_cash_requested(self, o):
        return self._get_total(o)['cash_requested']


report_sxw.report_sxw('report.cash.request.export', 'cash.request', 'addons/finance/report/cash_request.rml',
                      parser=cash_request_parser, header='internal')
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
