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
        })

    def getInstanceAdress(self,):
        id_c = self.pool.get('res.company').search(self.cr,self.uid,[('name','ilike','MSF')])
        bro = self.pool.get('res.company').browse(self.cr,self.uid,id_c[0])
        projet = bro.instance_id and bro.instance_id.instance or ' '
        mission = bro.instance_id and bro.instance_id.mission or ' '
        code = bro.instance_id and bro.instance_id.code or ' '
        return projet + ' / ' + mission + ' / ' + code

    def getDateCreation(self, o):
        return time.strftime('%d-%b-%y',time.strptime(o.creation_date,'%Y-%m-%d %H:%M:%S'))

    def getDateFrom(self, o):
        return time.strftime('%d-%b-%y',time.strptime(o.period_from,'%Y-%m-%d'))

    def getDateTo(self, o):
        return time.strftime('%d-%b-%y',time.strptime(o.period_to,'%Y-%m-%d'))

    def get_lines(self, o):
        return o.line_ids

report_sxw.report_sxw('report.msf.consumption_report', 'real.average.consumption', 'addons/msf_printed_documents/report/consumption_report.rml', parser=consumption_report, header=False)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
