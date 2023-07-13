# -*- coding: utf-8 -*-

import time
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
