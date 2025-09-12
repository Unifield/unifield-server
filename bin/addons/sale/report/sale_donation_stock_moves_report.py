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
from tools.translate import _
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport


class sale_donation_stock_moves_report_parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(sale_donation_stock_moves_report_parser, self).__init__(cr, uid, name, context=context)
        self.cr = cr
        self.uid = uid
        self.user_company = self._get_user_company()
        self.localcontext.update({
            'time': time,
            'getMoves': self._get_moves,
            'isQtyOut': self._is_qty_out,
            'getQty': self._get_qty,
            'computeCurrency': self._compute_currency,
            'userCompany': self.user_company,
            'getRtTranslation': self.get_rt_translation,
        })

    def _get_moves(self, report):
        '''
        Return the moves for the report
        '''
        result = []
        for move_id in report.sm_ids:
            move = self.pool.get('stock.move').browse(self.cr, self.uid, move_id)
            if self._get_qty(move) != 0:
                result.append(move)

        return sorted(result, key=lambda r: (r['date']), reverse=True)

    def _is_qty_out(self, move):
        '''
        Check if the move is an in or an out
        '''
        out = False

        if (move.location_id.usage == 'internal') and (move.location_dest_id and move.location_dest_id.usage in ('customer', 'supplier')):
            out = True

        return out

    def _get_qty(self, move):
        '''
        Return the move's product quantity
        '''
        uom_obj = self.pool.get('product.uom')

        qty = uom_obj._compute_qty(self.cr, self.uid, move.product_uom.id,
                                   move.product_qty,
                                   move.product_id.uom_id.id)

        return qty

    def _get_user_company(self):
        '''
        Return user's current company
        '''
        return self.pool.get('res.users').browse(self.cr, self.uid, self.uid).company_id

    def _compute_currency(self, move):
        '''
        Compute an amount of a given currency to the instance's currency
        '''
        currency_obj = self.pool.get('res.currency')

        if move.type == 'in':
            if move.price_unit is None:
                return round(move.product_id.standard_price, 2)
            else:
                price = move.price_unit
        elif move.type == 'out' and move.sale_line_id:
            price = move.sale_line_id.price_unit
        else:
            return 0.00

        if not move.price_currency_id:
            if move.type == 'in':
                from_currency_id = move.partner_id.property_product_pricelist_purchase.currency_id.id
            else:
                from_currency_id = move.partner_id.property_product_pricelist.currency_id.id
        else:
            from_currency_id = move.price_currency_id.id

        context = {'currency_date': move.date}
        to_currency_id = self.user_company['currency_id'].id

        if from_currency_id == to_currency_id:
            return round(price, 2)

        return round(currency_obj.compute(self.cr, self.uid, from_currency_id, to_currency_id, price, round=False, context=context), 2)

    def get_rt_translation(self, rt_name, rt_code):
        if not rt_code:
            return rt_name

        donation_rts = {
            9: _('Donation (standard)'),
            10: _('Donation to prevent losses'),
            11: _('In-Kind Donation'),
            22: _('Programmatic Donation')
        }

        return donation_rts.get(rt_code, rt_name)



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
