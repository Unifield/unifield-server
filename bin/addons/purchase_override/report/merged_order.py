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


    def str_to_time(self, time):
        if isinstance(time, str):
            if time == 'False':
                time = False

        if time:
            return self.pool.get('date.tools').get_date_formatted(self.cr, self.uid, datetime=time)

        return ''


report_sxw.report_sxw('report.purchase.order.merged','purchase.order','addons/purchase_override/report/merged_order.rml',parser=merged_order, header=False)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

