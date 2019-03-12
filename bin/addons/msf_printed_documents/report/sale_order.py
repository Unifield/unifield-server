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

class order(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(order, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'to_time': self.str_to_time,
            'get_from': self.get_from,
            'enumerate': enumerate,
            'getTotalLines': self.get_total_lines,
        })

    def str_to_time(self, time):
        if isinstance(time, str):
            if time == 'False':
                time = False

        if time:
            return self.pool.get('date.tools').get_date_formatted(self.cr, self.uid, datetime=time)

        return ''

    def get_from(self, partner_id):
        addr_id = self.pool.get('res.partner').address_get(self.cr, self.uid, partner_id)['default']
        return self.pool.get('res.partner.address').browse(self.cr, self.uid, addr_id).name

    def get_total_lines(self, sale_id):
        sale_domain = [('order_id', '=', sale_id), ('state', 'not in', ['cancel', 'cancel_r'])]
        return len(self.pool.get('sale.order.line').search(self.cr, self.uid, sale_domain, context=self.localcontext))


report_sxw.report_sxw('report.msf.sale.order', 'sale.order', 'addons/msf_printed_documents/report/sale_order.rml', parser=order, header=False)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

