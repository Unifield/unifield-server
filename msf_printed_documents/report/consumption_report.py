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

class consumption_report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(consumption_report, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'enumerate': enumerate,
            'get_lines': self.get_lines,
            'getDateCreation': self.getDateCreation,
            'getDateFrom': self.getDateFrom,
            'getDateTo': self.getDateTo,
            'getInstanceAdress': self.getInstanceAdress,
            'getExpDate': self.getExpDate,
        })

    def getExpDate(self,line):
        return time.strftime('%d/%b/%Y',time.strptime(line.expiry_date,'%Y-%m-%d'))

    def getInstanceAdress(self,c):
        instance = c.instance_id
        return '%s / %s / %s' % (instance.instance, instance.mission or '', instance.code)

    def getDateCreation(self, o):
        return time.strftime('%d/%b/%Y',time.strptime(o.creation_date,'%Y-%m-%d %H:%M:%S'))

    def getDateFrom(self, o):
        return time.strftime('%d/%b/%Y',time.strptime(o.period_from,'%Y-%m-%d'))

    def getDateTo(self, o):
        return time.strftime('%d/%b/%Y',time.strptime(o.period_to,'%Y-%m-%d'))

    def get_lines(self, o):
        return o.line_ids

report_sxw.report_sxw('report.msf.consumption_report', 'real.average.consumption', 'addons/msf_printed_documents/report/consumption_report.rml', parser=consumption_report, header=False)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
