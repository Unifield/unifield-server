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

class gift_certificate(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(gift_certificate, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'get_data': self.get_data,
        })

    def get_data(self, o):
        pick_obj = self.pool.get('stock.picking')
        valuation_obj = self.pool.get('stock.certificate.valuation')

        cert = self.pool.get('stock.print.certificate').browse(self.cr, self.uid, self.datas['certif_id'])
        data = []

        picking = pick_obj.browse(self.cr, self.uid, cert.picking_id.id)
        for move in picking.move_lines:
            valuation = move.product_id.list_price
            val_ids = valuation_obj.search(self.cr, self.uid, [('move_id', '=', move.id), ('print_id', '=', cert.id)])
            if val_ids:
                valuation = valuation_obj.read(self.cr, self.uid, val_ids, ['unit_price'])[0]['unit_price']

            data.append({'product_code': move.product_id.default_code,
                         'product_name': move.product_id.name,
                         'product_qty': move.product_qty,
                         'product_uom': move.product_uom.name,
                         'prodlot_name': move.prodlot_id.name,
                         'life_date': move.prodlot_id.life_date,
                         'valuation': valuation})

        return data

report_sxw.report_sxw('report.order.type.gift.certificate',
                      'stock.picking',
                      'addons/order_types/report/gift_certificate.rml',
                      parser= gift_certificate)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
