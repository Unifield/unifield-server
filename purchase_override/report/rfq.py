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

class rfq(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(rfq, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'to_time': self.str_to_time,
            'enumerate': enumerate,
            'encode_origin': self._encode_origin,
        })
        
    def str_to_time(self, time):
        if isinstance(time, str):
            if time == 'False':
                time = False
                
        if time:
            return self.pool.get('date.tools').get_date_formatted(self.cr, self.uid, datetime=time)
        
        return ''
        
    def _encode_origin(self, origin):
        if origin:
            return origin.replace(';', '; ')
        return ''
            
report_sxw.report_sxw('report.msf.purchase.quotation','purchase.order','addons/purchase_override/report/rfq.rml',parser=rfq, header=False)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
