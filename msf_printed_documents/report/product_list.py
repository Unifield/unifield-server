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

class product_list(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(product_list, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'enumerate': enumerate,
            'get_lines': self.get_lines,
            'get_lines_old': self.get_lines_old,
            'getDateCrea': self.getDateCrea,
            'getDateModif': self.getDateModif,
            'getType': self.getType,
            'getDateRemoved': self.getDateRemoved,
            'getInstanceAdress': self.getInstanceAdress,
        })

    def getInstanceAdress(self,c):
        instance = c.instance_id
        return '%s / %s / %s' % (instance.instance, instance.mission or '', instance.code)

    def getType(self, o):
        if o.type == 'list':
            return "List"
        return "Sublist"

    def getDateCrea(self, o):
        return time.strftime('%d/%b/%Y',time.strptime(o.creation_date,'%Y-%m-%d'))

    def getDateModif(self, o):
        return time.strftime('%d/%b/%Y',time.strptime(o.last_update_date,'%Y-%m-%d'))

    def getDateRemoved(self, o):
        return time.strftime('%d/%b/%Y',time.strptime(o.removal_date,'%Y-%m-%d'))

    def get_lines(self, o):
        return o.product_ids

    def get_lines_old(self, o):
        return o.old_product_ids

report_sxw.report_sxw('report.msf.product_list', 'product.list', 'addons/msf_printed_documents/report/product_list.rml', parser=product_list, header=False)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
