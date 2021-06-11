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
from msf_supply_doc_export.msf_supply_doc_export import WebKitParser
from msf_supply_doc_export.msf_supply_doc_export import getIds


class supplier_catalogue_lines_report_parser(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context=None):
        super(supplier_catalogue_lines_report_parser, self).__init__(cr, uid, name, context=context)

        self.localcontext.update({
            'getLines': self._get_lines,
            'getOrders': self._get_orders,
        })
        self._nb_lines = 0
        self._lines_iterator = 0

        if context.get('background_id'):
            self.back_browse = self.pool.get('memory.background.report').browse(self.cr, self.uid, context['background_id'])
        else:
            self.back_browse = None

    def _get_orders(self, objs):
        for o in objs:
            self._nb_lines += len(o.line_ids)

        return objs

    def _get_lines(self, cat_brw):
        for cat_line in cat_brw.line_ids:
            self._lines_iterator += 1
            if self.back_browse and self._nb_lines:
                percent = float(self._lines_iterator) / float(self._nb_lines)
                self.pool.get('memory.background.report').update_percent(self.cr, self.uid, [self.back_browse.id], percent)

            yield cat_line

        return


class supplier_catalogue_lines_report_xls(WebKitParser):

    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header = " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(supplier_catalogue_lines_report_xls, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context)
        a = super(supplier_catalogue_lines_report_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')

supplier_catalogue_lines_report_xls(
    'report.supplier.catalogue.lines.xls',
    'supplier.catalogue',
    'addons/supplier_catalogue/report/report_supplier_catalogue_lines_xls.mako',
    parser=supplier_catalogue_lines_report_parser,
)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
