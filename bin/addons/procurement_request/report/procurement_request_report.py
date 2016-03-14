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

from report import report_sxw
from report_webkit.webkit_report import WebKitParser

import pooler
import time

class procurement_request_report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(procurement_request_report, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'get_name': self.get_name,
        })

    def get_name(self, obj, obj_id):
        '''
        Return the name of the obj_id with the name_get method
        '''
        return self.pool.get(obj).name_get(self.cr, self.uid, [obj_id])[0][1]

report_sxw.report_sxw('report.procurement.request.report','sale.order','addons/procurement_request/report/procurement_request_report.rml',parser=procurement_request_report, header=False)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
