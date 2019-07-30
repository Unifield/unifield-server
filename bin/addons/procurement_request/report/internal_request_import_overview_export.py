# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
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


class internal_request_import_overview_export(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(internal_request_import_overview_export, self).__init__(cr, uid, name, context=context)
        self.cr = cr
        self.uid = uid
        self.localcontext.update({
            'time': time,
            'getHeaderErrors': self._get_header_errors,
            'getErrors': self._get_errors,
        })

    def _get_header_errors(self, import_id):
        imp_err_lines_obj = self.pool.get('internal.request.import.error.line')
        err_lines_ids = imp_err_lines_obj.search(self.cr, self.uid, [('ir_import_id', '=', import_id),
                                                                     ('header_line', '=', True)], context=self.localcontext)

        return imp_err_lines_obj.browse(self.cr, self.uid, err_lines_ids, fields_to_fetch=['line_message'], context=self.localcontext)

    def _get_errors(self, import_id):
        imp_err_lines_obj = self.pool.get('internal.request.import.error.line')
        err_lines_ids = imp_err_lines_obj.search(self.cr, self.uid, [('ir_import_id', '=', import_id),
                                                                     ('header_line', '=', False)], context=self.localcontext)

        return imp_err_lines_obj.browse(self.cr, self.uid, err_lines_ids, fields_to_fetch=['line_number', 'line_message', 'data_summary', 'red'], context=self.localcontext)


class internal_request_import_overview_export_xls(SpreadsheetReport):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse,
                 header='external', store=False):
        super(internal_request_import_overview_export_xls, self).__init__(name, table,
                                                                          rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        a = super(internal_request_import_overview_export_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')


internal_request_import_overview_export_xls(
    'report.internal_request_import_overview_export',
    'internal.request.import',
    'addons/procurement_request/report/internal_request_import_overview_export_xls.mako',
    parser=internal_request_import_overview_export,
    header=False)
