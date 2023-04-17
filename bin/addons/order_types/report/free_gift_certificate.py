# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting
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
from osv import osv
from tools.translate import _
from report import report_sxw


class free_gift_certificate(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(free_gift_certificate, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'getCurrency': self._get_currency,
            'getTotalAmount': self._get_total_amount,
        })

    def _get_total_amount(self, pick, currency_id):
        total = 0.00
        for move in pick.move_lines:
            move_price = move.price_unit or move.product_id.standard_price
            if move.price_currency_id and move.price_currency_id.id != currency_id:
                move_price = self.pool.get('res.currency').compute(self.cr, self.uid, move.price_currency_id.id,
                                                                   currency_id, move_price, round=False, context=self.localcontext)
            total += move.product_qty * move_price
        return total

    def _get_currency(self, pick):
        '''
        Return information about the currency.
        '''
        res = {}
        currency = pick.sale_id and pick.sale_id.pricelist_id.currency_id or False
        company = self.pool.get('res.users').browse(self.cr, self.uid, self.uid).company_id
        if currency:
            res['currency_id'] = currency.id
            res['currency_name'] = currency.name
        elif company:
            res['currency_id'] = company.currency_id and company.currency_id.id or False
            res['currency_name'] = company.currency_id and company.currency_id.name or False

        return res


report_sxw.report_sxw('report.order.type.free.gift.certificate', 'stock.picking', 'addons/order_types/report/free_gift_certificate.rml', parser=free_gift_certificate, header=False)
