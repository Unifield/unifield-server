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
from msf_doc_import.wizard.abstract_wizard_import import ImportHeader
from tools.translate import _
from osv import osv



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

    def getHeaders(self, model, field_list, rows):
        '''
        get the column names of the table. Set the type of the column and the
        size of it.
        '''
        headers = []
        model_obj = self.pool.get(model)
        for field_index, field in enumerate(field_list):
            res = {'tech_name': field}
            if '.' in field:
                field = field.split('.')[0]
            if field in model_obj._columns:
                field_obj = model_obj._columns[field]
            elif field in model_obj._inherit_fields:
                field_obj = model_obj._inherit_fields[field][2]
            else:
                raise osv.except_osv(_('Error'),
                                     _('field \'%s\' not found for model \'%s\'. Please contact the support team.')
                                     % (field, model))

            if field_obj._type == 'boolean':
                res['ftype'] = 'Boolean'
                res['size'] = 40
            elif field_obj._type == 'float':
                res['ftype'] = 'Float'
                res['size'] = 80
            elif field_obj._type == 'integer':
                res['ftype'] = 'Number'
                res['size'] = 80
            else:
                res['ftype'] = 'String'

            # automatically set the width of the column by searching for the
            # biggest string in it
            all_cells_chain = [x[field_index] for x in rows if
                    isinstance(x[field_index], basestring)]
            if all_cells_chain:
                longest_chain = max(all_cells_chain, key=len)
                if longest_chain:
                    size = 8*len(longest_chain)
                    size = min(size, 300)
                    size = max(size, 60)
                    res['size'] = size
            else:
                res['size'] = 60
            res['name'] = _(field_obj.string)
            headers.append(ImportHeader(**res))
        return headers

    def getRows(self, model, fields, nb_lines=None):
        """
        Return list of lines from given generic export
        """
        rows = []
        counter = 0
        chunk_size = 100
        model_obj = self.pool.get(model)
        ids = model_obj.search(self.cr, self.uid, [], limit=nb_lines)
        fields = [x.replace('.', '/') for x in fields]
        for i in range(0, len(ids), chunk_size):
            ids_chunk = ids[i:i + chunk_size]
            counter += len(ids_chunk)
            rows.extend(model_obj.export_data(self.cr, self.uid, ids_chunk, fields)['datas'])
            #progression = float(counter) / len(ids)
            #if bg_id:
            #    bg_obj.update_percent(self.cr, self.uid, bg_id, progression)
        return rows

XlsWebKitParser(
    'report.wizard.export.generic',
    'msf.import.export',
    'addons/msf_doc_import/report/export_generic.mako',
    parser=report_generic_export_parser,
)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
