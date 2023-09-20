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

import time
from report import report_sxw

class merged_order(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(merged_order, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'to_time': self.str_to_time,
            'enumerate': enumerate,
            'getOrigin': self._get_origin,
            'get_merged_lines': self.get_merged_lines,
        })

    def _get_origin(self, origin, number=5):
        res = []
        if origin:
            split_orig = origin.split(';')
        else:
            split_orig = []
        i = 0
        tmp_orig = ''
        while i < len(split_orig):
            tmp_orig += split_orig[i]
            i += 1

            if i != len(split_orig):
                tmp_orig += ';'

            if i % number == 0:
                res.append(tmp_orig)
                tmp_orig = ''

        if len(split_orig) < number:
            res.append(tmp_orig)
            tmp_orig = ''

        return res

    def get_merged_lines(self, order):
        all_prod = {}
        line_obj = self.pool.get('purchase.order.line')
        line_ids = line_obj.search(self.cr, self.uid, [('order_id', '=', order.id), ('state', 'not in', ['cancel', 'cancel_r'])])

        for line in line_obj.browse(self.cr, self.uid, line_ids, context=self.localcontext):
            if not line.product_id:
                p_key = line.nomenclature_description
                p_name = line.nomenclature_description
                default_code = ''
            else:
                p_key = line.product_id.id
                p_name = line.product_id.name
                default_code = line.product_id.default_code

            key = (p_key, line.product_uom.id)
            if key not in all_prod:
                all_prod[key] = {
                    'default_code': default_code,
                    'supplier_code': line.supplier_code,
                    'name': p_name,
                    'price_unit': line.price_unit,
                    'price_subtotal': line.price_subtotal,
                    'product_uom': line.product_uom.name,
                    'quantity': line.product_qty,
                    'comment': line.comment or '',
                    'product_uom_rounding': line.product_uom.rounding,
                    'mml_status': self.getSel(line, 'mml_status'),
                    'msl_status': self.getSel(line, 'msl_status'),
                    'red': line.mml_status=='F' or line.msl_status=='F',
                }
            else:
                all_prod[key]['price_unit'] = ((all_prod[key]['price_unit'] * all_prod[key]['quantity']) + (line.product_qty*line.price_unit)) / (line.product_qty+all_prod[key]['quantity'])
                all_prod[key]['quantity'] += line.product_qty
                all_prod[key]['price_subtotal'] += line.price_subtotal
                if line.comment:
                    all_prod[key]['comment'] += ' %s' % line.comment

        return sorted(all_prod.values(), key=lambda x: x['default_code'] or x['name'])

    def str_to_time(self, time):
        if isinstance(time, str):
            if time == 'False':
                time = False

        if time:
            return self.pool.get('date.tools').get_date_formatted(self.cr, self.uid, datetime=time)

        return ''


report_sxw.report_sxw('report.purchase.order.merged','purchase.order','addons/purchase_override/report/merged_order.rml',parser=merged_order, header=False)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

