# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF
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

class donation_certificate(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(donation_certificate, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'getLines': self._get_lines,
            'getTotalValue': self._get_total_value,
        })

    def _get_total_value(self, pick):
        '''
        Return a message with a calculated price
        '''
        curr_obj = self.pool.get('res.currency')
        tot_value = 0
        for move in pick.move_lines:
            tot_value += move.product_qty * round(curr_obj.compute(self.cr, self.uid, move.price_currency_id.id,
                                                                   pick.company_id.currency_id.id, move.price_unit,
                                                                   round=False, context=self.localcontext), 2)

        return round(tot_value, 2)

    def _get_lines(self, pick):
        lines = []
        for move in pick.move_lines:
            lines.append({
                'item': move.line_number,
                'p_code': move.product_id and move.product_id.default_code or '',
                'p_desc': move.product_id and move.product_id.name or '',
                'qty_and_uom': '%s %s' % (round(move.product_qty, 0), move.product_uom and move.product_uom.name or ''),
                'batch': move.prodlot_id and move.prodlot_id.name or '',
                'exp_date': move.prodlot_id and move.prodlot_id.life_date or move.expired_date or '',
                'currency': move.price_currency_id.name,
                'unit_price': move.price_unit,
                'tot_value': move.product_qty * move.price_unit,
                'comments': move.comment or '',
            })

        return lines


report_sxw.report_sxw('report.order.type.donation.certificate',
                      'stock.picking',
                      'addons/order_types/report/donation_certificate.rml',
                      parser=donation_certificate, header=False)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
