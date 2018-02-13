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
from report_webkit.webkit_report import XlsWebKitParser
from operator import itemgetter


XlsWebKitParser(
    'report.wizard.import.generic.template',
    'abstract.wizard.import',
    'addons/msf_doc_import/report/import_generic_template.mako',
)


class report_generic_export_parser(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context=None):
        super(report_generic_export_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'getHeaders': self.getHeaders,
            'getRows': self.getRows,
        })
        return

    def getHeaders(self, model, field_list, rows, context=None):
        '''
        get the column names of the table. Set the type of the column and the
        size of it.
        '''
        import_export_obj = self.pool.get('msf.import.export')
        return import_export_obj._get_headers(self.cr, self.uid, model,
                selection=None, field_list=field_list, rows=rows, context=context)

    def getRows(self, model, fields, nb_lines=None, domain=None,
            template_only=False, context=None):
        """
        Return list of lines from given generic export
        """
        if context is None:
            context={}
        if template_only:
            return []
        if not domain:
            domain = []
        rows = []
        counter = 0
        chunk_size = 100
        model_obj = self.pool.get(model)
        ids = model_obj.search(self.cr, self.uid, domain, limit=nb_lines)
        fields = [x.replace('.', '/') for x in fields]
        for i in range(0, len(ids), chunk_size):
            ids_chunk = ids[i:i + chunk_size]
            counter += len(ids_chunk)
            context['translate_selection_field'] = True
            rows.extend(model_obj.export_data(self.cr, self.uid, ids_chunk, fields, context=context)['datas'])

        # sort supplier catalogue line
        if model == 'supplier.catalogue.line':
            rows = sorted(rows, key=itemgetter(1,0))
        return rows

XlsWebKitParser(
    'report.wizard.export.generic',
    'msf.import.export',
    'addons/msf_doc_import/report/export_generic.mako',
    parser=report_generic_export_parser,
)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
