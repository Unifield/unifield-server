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
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport


class log_line(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(log_line, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'order_id': self._get_order_id,
            'get_lines': self._get_lines,
            'get_method': self._get_method,
            'order_name': self._get_order_name,
        })

    def _get_order_id(self, line_id):
        line = self.pool.get('audittrail.log.line').browse(self.cr, self.uid, line_id)
        order = self.pool.get(line.object_id.model).browse(self.cr, self.uid, line.res_id)
        return order

    def _get_order_name(self, line_id):
        line = self.pool.get('audittrail.log.line').browse(self.cr, self.uid, line_id)
        order = self.pool.get(line.object_id.model).browse(self.cr, self.uid, line.res_id)
        name = order.name or self.pool.get(line.object_id.model)._description or ''
        return name

    def _get_lines(self, order):
        model = order._name
        lines = self.pool.get('audittrail.log.line').search(self.cr, self.uid, [('object_id', '=', model), ('res_id', '=', order.id)])
        return self.pool.get('audittrail.log.line').browse(self.cr, self.uid, lines, context=self.localcontext)

    def _get_method(self, o, field):
        sel = self.pool.get(o._name).fields_get(self.cr, self.uid, [field], context=self.localcontext)
        res = dict(sel[field]['selection']).get(getattr(o,field),getattr(o,field))
        return res


report_sxw.report_sxw('report.msf.log.line', 'audittrail.log.line', 'addons/msf_audittrail/report/log_line.rml', parser=log_line, header="internal landscape")

SpreadsheetReport('report.msf.log.line_xls', 'audittrail.log.line', 'addons/msf_audittrail/report/log_line_xls.mako', parser=log_line)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

