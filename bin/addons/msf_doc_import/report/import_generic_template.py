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
from msf_doc_import.msf_import_export_conf import MODEL_DATA_DICT, MODEL_DICT
import tools


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
            if selection == 'product_list_update':
                res = MODEL_DATA_DICT.get('product_list_update').get('custom_field_name', {}).get(field)
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
        if 'lang' in MODEL_DICT.get(selection, {}):
            context['lang'] = MODEL_DICT[selection]['lang']
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
        new_ctx = context.copy()
        if 'lang' in MODEL_DICT.get(data['selection'], {}):
            new_ctx['lang'] = MODEL_DICT[data['selection']]['lang']
        if data['selection'] in ['destinations', 'funding_pools']:
            new_ctx['account_only_code'] = True
        for i in range(0, len(ids), chunk_size):
            ids_chunk = ids[i:i + chunk_size]
            context['translate_selection_field'] = True
            rows.extend(model_obj.export_data(self.cr, self.uid, ids_chunk, fields, context=new_ctx)['datas'])

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

class report_user_access_export_parser(report_generic_export_parser):

    def __init__(self, cr, uid, name, context=None):
        super(report_user_access_export_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'getUserAccessRows': self.getUserAccessRows,
        })
        return

    def getMenuList(self, menu_id=None, menu_list=None, level=0):
        '''
        return list of (level, menu_id) ordered by name and position, for
        example:
        id:   complete path:
        11:   Accounting
        46:   Accounting/Budgets
        33:   Accounting/Budgets/Analytic Accounts
        65:   Accounting/Charts

        will result in [(0, 11), (1, 46), (2, 33), (1, 65)]
        '''
        if menu_list is None:
            menu_list = []
        menu_obj = self.pool.get('ir.ui.menu')
        if menu_id is None:
            # take first level : the ones that don't have parent_id
            menu_ids = menu_obj.search(self.cr, self.uid,
                                       [('parent_id', '=', None),
                                        ('name', '!=', 'Hidden Menu'),
                                        ('active', 'in', ['t', 'f'])],
                                       order='name', context={'ir.ui.menu.full_list': True})
            for menu_id in menu_ids:
                menu_list.append((level, menu_id))
                self.getMenuList(menu_id, menu_list, level+1)
        else:
            child_menu_ids = menu_obj.search(self.cr, self.uid,
                                             [('parent_id', '=', menu_id), ('active', 'in', ['t', 'f'])],
                                             order='name', context={'ir.ui.menu.full_list': True})
            for menu_id in child_menu_ids:
                menu_list.append((level, menu_id))
                self.getMenuList(menu_id, menu_list, level+1)
        return menu_list

    def getUserAccessRows(self, context=None):
        '''
        return a list of of tuples representing the cells of the table.
        The first row is the header
        '''
        group_obj = self.pool.get('res.groups')
        menu_obj = self.pool.get('ir.ui.menu')
        data_obj = self.pool.get('ir.model.data')
        import_export_obj = self.pool.get('msf.import.export')
        menu_list = self.getMenuList()
        menu_id_list = [x[1] for x in menu_list]

        # read all menu names
        menu_read_result = menu_obj.read(self.cr, self.uid,
                                         menu_id_list, ['name'], context)
        menu_name_dict = dict((x['id'], x['name']) for x in menu_read_result)

        # read all ir.model.data informations
        data_ids = data_obj.search(self.cr, self.uid,
                                   [('model', '=', 'ir.ui.menu'),
                                    ('res_id', 'in', menu_id_list),
                                       ('module', '!=', 'sd')],
                                   context=context)
        data_read_result = data_obj.read(self.cr, self.uid,
                                         data_ids, ['res_id', 'module', 'name'], context=context)
        data_read_dict = dict((x['res_id'], x) for x in data_read_result)

        # build the text part
        row_list = []
        for level, menu_id in menu_list:
            data = data_read_dict[menu_id]
            name = menu_name_dict[menu_id]
            row = {
                'module': data['module'],
                'xml_id': data['name'],
                'level': level*'+',
                'name': name,
                'menu_id': menu_id
            }
            row_list.append(row)

        # build the access right part
        no_export_groups = [('base', 'group_erp_manager'), ('base', 'group_extended'), ('base', 'group_no_one'), ('sync_common', 'sync_read_group')]
        ignore_goups = []
        for module, xmlid in no_export_groups:
            try:
                ignore_goups.append(data_obj.get_object_reference(self.cr, self.uid, module, xmlid)[1])
            except:
                pass
        group_dom = [('visible_res_groups', '=', 't')]

        if ignore_goups:
            group_dom.append(('id', 'not in', ignore_goups))

        group_ids = group_obj.search(self.cr, self.uid, group_dom, order='name', context=context)
        group_read_result = group_obj.read(self.cr, self.uid, group_ids,
                                           ['name', 'level', 'menu_access'], context=context)
        group_dict = dict((x['id'], x) for x in group_read_result)
        group_name_list = []

        # order by this prefix order
        prefix_order = ['Sup_', 'Sync_', 'User_', 'Fin_', 'UniData']
        groups_remain = group_ids[:]
        for prefix in prefix_order:
            for group_id in group_ids:
                group = group_dict[group_id]
                group_name = group['name']

                if group['name'].startswith(prefix):
                    group_name_list.append((group_id, group_name))
                    groups_remain.remove(group_id)

        # at the end of the list, add the group that where not matching any prefix
        for group_id in groups_remain:
            group = group_dict[group_id]
            group_name_list.append((group_id, group['name']))

        # add group level to the group_name (see US-2067)
        new_group_name_list = []
        for group_id, group_name in group_name_list:
            group = group_dict[group_id]
            if group['level'] == 'hq':
                group_name += '$HQ'
            elif group['level'] == 'coordo':
                group_name += '$CO'
            new_group_name_list.append((group_id, group_name))
        group_name_list = new_group_name_list

        final_rows = []
        # setup the access rights into the rows
        for row in row_list:
            final_row = [row['module'], row['xml_id'], row['level'], row['name']]
            for group_id, group_name in group_name_list:
                group_available = row['menu_id'] in group_dict[group_id]['menu_access']
                final_row.append(group_available)
            final_rows.append(final_row)

        # build the header
        headers = ['module', 'xml_id', 'Level', 'Name']
        headers.extend([x[1] for x in group_name_list])
        final_header = []
        for index, header in enumerate(headers):
            if index > 3:
                # for better readability, set a mimimum size for boolean
                # columns
                longest_chain = 'x'*10
            else:
                # for other get the size of the longuest chain
                all_string_list = [tools.ustr(row[index]) for row in final_rows]
                longest_chain = max(all_string_list, key=len)
            column_lenght = import_export_obj.get_excel_size_from_string(longest_chain)

            # set the style according to the prefix
            if header.startswith('Sup_'):
                style = 'header_supply'
            elif header.startswith('Sync_') or header.startswith('User_'):
                style = 'header_synchro'
            elif header.startswith('Fin_'):
                style = 'header_finance'
            elif header.startswith('UniData'):
                style = 'header_finance'
            else:
                style = 'header_no_style'
            current_header = (header, column_lenght, style)
            final_header.append(current_header)

        return [final_header] + final_rows

XlsWebKitParser(
    'report.wizard.export.user.access',
    'msf.import.export',
    'addons/msf_doc_import/report/export_user_access.mako',
    parser=report_user_access_export_parser,
)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
