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
from msf_doc_import.msf_import_export import msf_import_export
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
                     ('name', '!=', 'Hidden Menu')],
                    order='name')
            for menu_id in menu_ids:
                menu_list.append((level, menu_id))
                self.getMenuList(menu_id, menu_list, level+1)
        else:
            child_menu_ids = menu_obj.search(self.cr, self.uid,
                        [('parent_id', '=', menu_id)],
                        order='name')
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
        group_ids = group_obj.search(self.cr, self.uid,
                [('visible_res_groups', '=', 't')], order='name',
                context=context)
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
            column_lenght = msf_import_export.get_excel_size_from_string(longest_chain)

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
