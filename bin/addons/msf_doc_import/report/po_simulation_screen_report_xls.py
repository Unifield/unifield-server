# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting
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

def getIds(self, cr, uid, ids, context=None):
    if context is None:
        context = {}

    if context.get('from_domain') and 'search_domain' in context:
        table_obj = pooler.get_pool(cr.dbname).get(self.table)
        ids = table_obj.search(cr, uid, context.get('search_domain'), limit=5000)
    return ids


class po_simulation_screen_xls(WebKitParser):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header = " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(po_simulation_screen_xls, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context)
        a = super(po_simulation_screen_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')

class parser_po_simulation_screen_xls(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(parser_po_simulation_screen_xls, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'obj_name_get': self._get_name,
        })

    def _get_name(self, obj_name, obj_id):
        pool = pooler.get_pool(self.cr.dbname)
        return pool.get(obj_name).name_get(self.cr, self.uid, [obj_id])[0][1]

po_simulation_screen_xls('report.po.simulation.screen.xls', 'wizard.import.po.simulation.screen', 'addons/msf_doc_import/report/po_simulation_screen_xls_report.mako', parser=parser_po_simulation_screen_xls)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
