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
from msf_doc_import.msf_import_export_conf import MODEL_DATA_DICT
import osv


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
            'getHeaderInfo': self.getHeaderInfo,
        })
        return

    def getHeaderInfo(self, model, selection, prod_list_id=False, supp_cata_id=False, context=None):
        '''
        Get header info which are located at the very top of export template. 
        Only available for some models (product.list or supplier.catalogue)
        '''
        def get_field_name(model, field):
            ''' get displayable name for the given field '''
            if selection == 'supplier_catalogue_update':
                res = MODEL_DATA_DICT.get('supplier_catalogue_update').get('custom_field_name', {}).get(field)
                if res:
                    return res
            field_id = self.pool.get('ir.model.fields').search(self.cr, self.uid, [('model', '=', model), ('name', '=', field)], context=context)
            field_desc = field
            if field_id:
                field_desc = self.pool.get('ir.model.fields').read(self.cr, self.uid, field_id[0], ['field_description'], context=context)['field_description']
            return field_desc

        def get_field_type(model, field):
            ''' get ttype for the given field '''
            field_id = self.pool.get('ir.model.fields').search(self.cr, self.uid, [('model', '=', model), ('name', '=', field)], context=context)
            ttype = None
            if field_id:
                ttype = self.pool.get('ir.model.fields').read(self.cr, self.uid, field_id[0], ['ttype'], context=context)['ttype']
            return ttype

        def get_attr_name(obj, field):
            ''' get displayable name for the given field '''
            attr = getattr(obj, field)
            res = attr
            ttype = get_field_type(obj._name, field)
            if ttype in ('many2one',):
                res = attr.name or ''
            elif ttype == 'selection':
                res = self.pool.get('ir.model.fields').get_selection(self.cr, self.uid, obj._name, field, attr, context=context) or ''
            elif ttype in ('char','text'):
                res = attr or ''
            elif ttype == 'boolean':
                res = attr and 'Yes' or 'No'
            return res

        if context is None:
            context = {}

        header_rows = []
        if selection == 'product_list_update':
            prod_list = self.pool.get('product.list').browse(self.cr, self.uid, prod_list_id, context=context)
            for field in MODEL_DATA_DICT['product_list_update'].get('header_info', []):
                header_rows.append(
                    (get_field_name('product.list', field), get_attr_name(prod_list,field)) # (name, value)
                )
        elif selection == 'supplier_catalogue_update':
            supp_cata = self.pool.get('supplier.catalogue').browse(self.cr, self.uid, supp_cata_id, context=context)            
            for field in MODEL_DATA_DICT['supplier_catalogue_update'].get('header_info', []):
                header_rows.append(
                    (get_field_name('supplier.catalogue', field), get_attr_name(supp_cata,field)) # (name, value)
                )

        return header_rows


    def getHeaders(self, model, field_list, rows, selection, context=None):
        '''
        get the column names of the table. Set the type of the column and the
        size of it.
        '''
        import_export_obj = self.pool.get('msf.import.export')
        return import_export_obj._get_headers(self.cr, self.uid, model,
                selection=selection, field_list=field_list, rows=rows, context=context)

    def getRows(self, data):
        """
        Return list of lines from given generic export
        """
        context = data['context']
        if context is None:
            context={}
        if data['template_only']:
            return []
        if not data['domain']:
            data['domain'] = []
        fields = data['fields']
        model_obj = self.pool.get(data['model'])

        # get ids:
        if data['selection'] == 'supplier_catalogue_update' and data.get('supp_cata_id'):
            data['domain'].append( ('catalogue_id', '=', data['supp_cata_id']) )
        elif data['selection'] == 'product_list_update' and data.get('prod_list_id'):
            data['domain'].append( ('list_id', '=', data['prod_list_id']) )
        ids = model_obj.search(self.cr, self.uid, data['domain'], limit=data['nb_lines'])

        # get rows:
        rows = []
        chunk_size = 100
        fields = [x.replace('.', '/') for x in fields]
        for i in range(0, len(ids), chunk_size):
            ids_chunk = ids[i:i + chunk_size]
            context['translate_selection_field'] = True
            rows.extend(model_obj.export_data(self.cr, self.uid, ids_chunk, fields, context=context)['datas'])

        # sort supplier catalogue line
        if data['model'] == 'supplier.catalogue.line':
            rows = sorted(rows, key=itemgetter(1,0))
        return rows

XlsWebKitParser(
    'report.wizard.export.generic',
    'msf.import.export',
    'addons/msf_doc_import/report/export_generic.mako',
    parser=report_generic_export_parser,
)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
