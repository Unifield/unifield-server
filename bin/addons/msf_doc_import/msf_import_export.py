# encoding: utf-8
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2017 MSF, TeMPO Consulting
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import base64
import time
import logging
import release
import tools

from osv import fields
from osv import osv, orm
from tools.translate import _

from tempfile import TemporaryFile
from lxml import etree
from lxml.etree import XMLSyntaxError
from datetime import datetime

from msf_doc_import.wizard.abstract_wizard_import import ImportHeader
from msf_doc_import.msf_import_export_conf import MODEL_DICT
from msf_doc_import.msf_import_export_conf import MODEL_DATA_DICT

MIN_COLUMN_SIZE = 40
MAX_COLUMN_SIZE = 400

MODEL_HEADER_NOT_CHECKED = ['user.access.configurator', 'hr.employee', 'hq.entries', 'msf.budget']

class msf_import_export(osv.osv_memory):
    _name = 'msf.import.export'
    _description = 'MSF Import Export'
    _inherit = 'abstract.wizard.import'

    def _get_model_list(self, cr, uid, context=None):
        """The list of available model depend on the menu entry selected
        """

        if context is None:
            context = {}

        realuser = hasattr(uid, 'realUid') and uid.realUid or uid
        domain_type = None
        result_list = []
        if 'domain_type' in context:
            domain_type = context['domain_type']
        for key, value in MODEL_DICT.items():
            if key in ['product_list_update', 'supplier_catalogue_update']:
                continue
            if value['domain_type'] == domain_type:
                if self.pool.get('ir.model.access').check(cr, realuser, value['model'], 'write', raise_exception=False, context=context):
                    result_list.append((key, _(value['name'])))
        return [('', '')] + sorted(result_list, key=lambda a: a[0])

    _columns = {
        'display_file_import': fields.boolean('File Import'),
        'display_file_export': fields.boolean('File Export'),
        'model_list_selection': fields.selection(selection=_get_model_list, string='Object to Import/Export', required=True),
        'import_file': fields.binary('File to import .xml'),
        'hide_download_template': fields.boolean('Hide download template'),
        'hide_download_3_entries': fields.boolean('Hide export 3 entries button'),
        'hide_download_all_entries': fields.boolean('Hide export all entries button'),
        'display_import_buttons': fields.boolean('Display import buttons'),
        'csv_button': fields.boolean('Import from CSV'),
        'supplier_catalogue_id': fields.many2one('supplier.catalogue', string='Supplier catalogue'),
        'product_list_id': fields.many2one('product.list', string='Product List'),
    }

    _default = {
        'display_file_import': lambda *a: False,
        'display_file_export': lambda *a: False,
        'hide_download_template': lambda *a: False,
        'hide_download_3_entries': lambda *a: False,
        'hide_download_all_entries': lambda *a: False,
        'display_import_buttons': lambda *a: False,
        'csv_button': lambda *a: False,
    }

    def get_filename(self, cr, uid, model, selection, template_only=False, context=None):
        """Generate a filename for the import/export
        """
        file_name = _(MODEL_DICT[selection]['name'])
        file_name = file_name.replace(' ', '_')
        if template_only:
            file_name = _('%s_Import_Template') % file_name
        elif selection in ('user_groups', 'user_access', 'record_rules', 'access_control_list', 'access_control_list_empty', 'field_access_rules', 'field_access_rule_lines', 'button_access_rules', 'window_actions'):
            file_name = _('%s_Export_%s_%s') % (file_name, release.version.split('-')[0], time.strftime('%Y%m%d'))
        else:
            file_name = _('%s_Export_%s') % (file_name, time.strftime('%Y%m%d'))
        return file_name

    def generic_download(self, cr, uid, ids, template_only=False,
                         nb_lines=None, context=None):
        """Mutualise the code of all download buttons in one place
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        wiz = self.browse(cr, uid, ids[0])
        selection = wiz.model_list_selection
        model = MODEL_DICT[selection]['model']
        if selection not in MODEL_DATA_DICT:
            raise osv.except_osv(_('Error'),
                                 _('Selection \'%s\' not found. '
                                   'Please contact the support team.') % (selection))

        if 'header_list' not in MODEL_DATA_DICT[selection]:
            raise osv.except_osv(_('Error'),
                                 _('The header_list for report \'%s\' is not'
                                   ' defined. Please contact the support team.') % (selection))
        fields = MODEL_DATA_DICT[selection]['header_list']
        domain = MODEL_DICT[selection].get('domain', [])
        context['translate_selection_field'] = True
        data = {
            'model': model,
            'fields': fields,
            'nb_lines': nb_lines,
            'template_only': template_only,
            'domain': domain,
            'target_filename': self.get_filename(cr, uid, model, selection, template_only),
            'prod_list_id': wiz.product_list_id.id,
            'supp_cata_id': wiz.supplier_catalogue_id.id,
            'selection': wiz.model_list_selection,
        }

        if model == 'user.access.configurator':
            report_name = 'wizard.export.user.access'
        else:
            report_name = 'wizard.export.generic'
        return {
            'type': 'ir.actions.report.xml',
            'report_name': report_name,
            'datas': data,
            'context': context,
        }

    def download_all_entries_file(self, cr, uid, ids, context=None):
        """Download a template filled with all datas of the modele
        """
        return self.generic_download(cr, uid, ids, context=context)

    def download_3_entries_file(self, cr, uid, ids, context=None):
        """Download a template filled with the first 3 lines of data
        """
        return self.generic_download(cr, uid, ids, nb_lines=3, context=context)

    def download_template_file(self, cr, uid, ids, context=None):
        """Download the template file (without any data)
        """
        return self.generic_download(cr, uid, ids, template_only=True,
                                     context=context)

    def get_excel_size_from_string(self, string):
        """Compute the string to get the size of it in a excel
        understandable value
        :param string: the str chain to get the excel size
        :return: A int instance
        """
        # this calculation is used to translate the
        # character len to an excel understandable len

        max_digit_width = 7  # For Calabri 11 which is the font used in our reports
        conversion_factor = 3/4.  # to convert from pixel to points
        padding = 15

        # this formule partially come from readings here:
        # http://stackoverflow.com/questions/4577546/calculating-height-width-and-ysplit-xsplit-for-open-xml-spreadsheets?answertab=votes#tab-top
        size = round(max_digit_width*len(string)*conversion_factor+padding)

        # set a max and min len for the columns to avoid ridiculus column size
        size = min(size, MAX_COLUMN_SIZE)
        size = max(size, MIN_COLUMN_SIZE)
        return size

    def get_child_field(self, cr, uid, field, model, fields_get_dict,
                        context=None):
        if context is None:
            context = {}
        if '.' in field:
            model_obj = self.pool.get(model)
            if model not in fields_get_dict:
                fields_get_res = model_obj.fields_get(cr, uid, context=context)
                fields_get_dict[model] = fields_get_res
            else:
                fields_get_res = fields_get_dict[model]


            child_field = field.split('.')[0]
            rest = '.'.join(field.split('.')[1:])
            if child_field == 'id':
                return field, model

            if child_field not in fields_get_res:
                raise osv.except_osv(_('Error'),
                                     _('field \'%s\' not found for model \'%s\'. Please contact the support team.')
                                     % (child_field, model))

            #if child and child !='id' and fields_get_res[child_field].get('relation'):
            child_model = fields_get_res[child_field]['relation']
            if child_model not in fields_get_dict:
                model_obj = self.pool.get(child_model)
                fields_get_res = model_obj.fields_get(cr, uid, context=context)
                fields_get_dict[child_model] = fields_get_res
            return self.get_child_field(cr, uid, rest, child_model, fields_get_dict,
                                        context=context)
        else:
            return field, model

    def _get_headers(self, cr, uid, model, selection=None, field_list=None, rows=None, context=None):
        """Generate a list of ImportHeader objects using the data that retived
        from the field name.
        :param model: Model of the object imported/exported
        :param selection: requried to get the list of fields to compose the header
        :param field_list: if known, the list of the fields to display in the
        header can be passed
        :param rows: Data rows to export. In case of export, the size of the
        columns matter and can be determinied according to the data string length
        :param context: Context of the call, this is particularly important to
        get the language for tranlsating the fields.
        :return: A list of ImportHeader
        """
        if context is None:
            context = {}
        headers = []
        if not field_list:
            field_list = MODEL_DATA_DICT[selection]['header_list']

        new_ctx = context.copy()
        if 'lang' in MODEL_DICT.get(selection, {}):
            new_ctx['lang'] = MODEL_DICT[selection]['lang']

        model_obj = self.pool.get(model)
        fields_get_dict = {}  # keep fields_get result in cache
        fields_get_dict[model] = model_obj.fields_get(cr, uid, context=new_ctx)

        for field_index, field in enumerate(field_list):
            res = {'tech_name': field}
            if selection and field in MODEL_DATA_DICT[selection]['required_field_list']:
                res['required'] = True
            child_field, child_model = self.get_child_field(cr, uid, field, model,
                                                            fields_get_dict, context=new_ctx)
            first_part = field.split('.')[0]

            custom_name = MODEL_DATA_DICT[selection].get('custom_field_name', {}).get(field)
            if custom_name:
                res['name'] = custom_name
            else:
                if child_field == 'id':
                    if first_part != 'id':
                        res['name'] = '%s / XMLID' % fields_get_dict[model][first_part]['string']
                    else:
                        res['name'] = 'id'
                elif first_part not in fields_get_dict[model]:
                    raise osv.except_osv(_('Error'),
                                         _('field \'%s\' not found for model \'%s\'. Please contact the support team.')
                                         % (first_part, model))
                elif first_part != child_field:
                    if child_field not in fields_get_dict[child_model]:
                        raise osv.except_osv(_('Error'),
                                             _('field \'%s\' not found for model \'%s\'. Please contact the support team.')
                                             % (child_field, child_model))
                    res['name'] = '%s / %s' % (fields_get_dict[model][first_part]['string'],
                                               fields_get_dict[child_model][child_field]['string'])
                else:
                    res['name'] = fields_get_dict[model][first_part]['string']


            if child_field == 'id':
                field_type = 'String'
            else:
                field_type = fields_get_dict[child_model][child_field]['type']
            if field_type == 'boolean':
                res['ftype'] = 'Boolean'
            elif field_type == 'float':
                res['ftype'] = 'Float'
            elif field_type == 'integer':
                res['ftype'] = 'Number'
            else:
                res['ftype'] = 'String'

            if not rows:
                # if no data passed, set the column size with the size of the header name
                res['size'] = self.get_excel_size_from_string(res['name'])
            else:
                # automatically set the width of the column by searching for the
                # biggest string in this column
                all_cells_chain = [tools.ustr(x[field_index]) for x in rows]
                res['size'] = MIN_COLUMN_SIZE
                if all_cells_chain:
                    longest_chain = max(all_cells_chain, key=len)
                    if longest_chain:
                        res['size'] = self.get_excel_size_from_string(longest_chain)
            headers.append(ImportHeader(**res))
        return headers

    def domain_type_change(self, cr, uid, ids, model_list_selection, context=None):
        """When the type of object to import/export change, change the buttons
        to display or not according to the new object model
        """
        if context is None:
            context = {}
        result = {'value': {}}

        instance_level = self.pool.get('res.users').browse(cr, uid, uid, fields_to_fetch=['company_id'], context=context).company_id.instance_id.level
        if instance_level == 'project' and model_list_selection == 'products':
            return {
                'value': {'model_list_selection': False},
                'warning': {'title': _('Error'), 'message': _("You can not select 'Products' on a Project instance")}
            }

        result['value']['supplier_catalogue_id'] = False
        result['value']['product_list_id'] = False
        result['value']['display_file_import'] = True
        result['value']['display_file_export'] = True
        if model_list_selection:
            if model_list_selection and model_list_selection in MODEL_DATA_DICT:
                hide_export = MODEL_DATA_DICT[model_list_selection].get('hide_export', False)
                result['value']['display_file_export'] = not hide_export
                result['value']['hide_download_template'] = MODEL_DATA_DICT[model_list_selection].get('hide_download_template', False)
                hide_3 = MODEL_DATA_DICT[model_list_selection].get('hide_download_3_entries', False)
                result['value']['hide_download_3_entries'] = hide_3
                hide_all = MODEL_DATA_DICT[model_list_selection].get('hide_download_all_entries', False)
                result['value']['hide_download_all_entries'] = hide_all
                csv_button = MODEL_DATA_DICT[model_list_selection].get('csv_button', False)
                result['value']['csv_button'] = csv_button

                result['value']['display_file_import'] = MODEL_DATA_DICT[model_list_selection].get('display_file_import', True)
            else:
                result['value']['hide_download_template'] = False
                result['value']['hide_download_3_entries'] = False
                result['value']['hide_download_all_entries'] = False
        return result

    def file_change(self, cr, uid, obj_id, import_file, context=None):
        """Display the import button only if a file as been selected
        """
        if context is None:
            context = {}
        result = {'value': {'display_import_buttons': False}}
        if import_file:
            result['value']['display_import_buttons'] = True
        return result

    def check_xml_syntax(self, cr, uid, xml_string, context=None):
        """Try to parse the xml file and raise if there is an error
        """
        try:
            etree.fromstring(xml_string)
        except XMLSyntaxError:
            raise osv.except_osv(_('Error'), _('File structure is incorrect, '
                                               'please correct. You may generate a template with the File '
                                               'export functionality.'))

    def test_import(self, cr, uid, ids, context=None):
        """Warn if file structure is correct
        """
        if self.check_import(cr, uid, ids, context=context):
            raise osv.except_osv(_('Info'), _('File structure is correct.'))

    def check_import(self, cr, uid, ids, context=None):
        """Verify that a file has been selected and all columns expected are
        present
        """
        obj = self.read(cr, uid, ids[0])
        if not obj['import_file']:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))
        fileobj = TemporaryFile('w+')
        try:
            for wiz in self.browse(cr, uid, ids, context=context):
                selection = wiz.model_list_selection
                model = MODEL_DICT[selection]['model']
                if model in MODEL_HEADER_NOT_CHECKED:
                    continue
                xml_string = base64.decodestring(obj['import_file'])
                self.check_xml_syntax(cr, uid, xml_string, context=context)
                rows, nb_rows = self.read_file(wiz, context=context)
                if MODEL_DATA_DICT[selection].get('header_info'):
                    self.check_header_info(cr, uid, wiz, rows, context=context)
                self.check_missing_columns(cr, uid, wiz, context.get('row', rows.next()), context=context)
        finally:
            fileobj.close()
        return True

    def get_displayable_name(self, cr, uid, model, field_name, context=None):
        '''
        returns displayable name with given technical name
        '''
        if context is None:
            context = {}
        return self.pool.get(model).fields_get(cr, uid, field_name).get(field_name, {}).get('string', False)

    def check_header_info(self, cr, uid, wiz, rows, context=None):
        '''
        Check header info at the very top of the import document. 
        Return True if its OK, else raise exception
        '''
        if context is None:
            context = {}
        model = MODEL_DICT[wiz.model_list_selection]['model']
        parent_model = False
        if model == 'supplier.catalogue.line':
            parent_model = 'supplier.catalogue'
        elif model == 'product.list.line':
            parent_model = 'product.list'

        # get displayble name with technical name in order to be able to check the import file:
        fields_needed = MODEL_DATA_DICT[wiz.model_list_selection].get('header_info') # technical name
        fields_needed_name = []
        for field in fields_needed:
            fields_needed_name.append(
                MODEL_DATA_DICT[wiz.model_list_selection].get('custom_field_name', {}).get(field) or \
                self.get_displayable_name(cr, uid, parent_model, field, context=context)
            )

        fields_gotten = []
        id_check = {
            'product_list_update': {'name': False},
            'supplier_catalogue_update': {'name': False, 'partner_id': False},
        }
        for index, row in enumerate(rows):
            if index > len(fields_needed) - 1:
                context['row'] = row
                break # header info end

            # check if the selected catalogue or product list match with the one we are trying to import:
            if wiz.model_list_selection == 'product_list_update':
                expected_name = MODEL_DATA_DICT['product_list_update'].get('custom_field_name', {}).get('name') or \
                    self.get_displayable_name(cr, uid, parent_model, 'name', context=context)
                if row.cells[0].data == expected_name and row.cells[1].data == wiz.product_list_id.name:
                    id_check[wiz.model_list_selection]['name'] = True
            elif wiz.model_list_selection == 'supplier_catalogue_update':
                expected_name = MODEL_DATA_DICT['supplier_catalogue_update'].get('custom_field_name', {}).get('name') or \
                    self.get_displayable_name(cr, uid, parent_model, 'name', context=context)
                expected_partner = MODEL_DATA_DICT['supplier_catalogue_update'].get('custom_field_name', {}).get('partner_id') or \
                    self.get_displayable_name(cr, uid, parent_model, 'partner_id', context=context)
                if row.cells[0].data == expected_name and row.cells[1].data == wiz.supplier_catalogue_id.name:
                    id_check[wiz.model_list_selection]['name'] = True
                elif row.cells[0].data == expected_partner and row.cells[1].data == wiz.supplier_catalogue_id.partner_id.name:
                    id_check[wiz.model_list_selection]['partner_id'] = True
            fields_gotten.append(row.cells[0].data)

        if not all([id_check[wiz.model_list_selection][x] for x in id_check[wiz.model_list_selection]]):
            raise osv.except_osv(
                _('Error'),
                _("%s selected (%s) doesn't match with the one you are trying to import. Please check following header fields: %s.") % (
                    _('Product list') if wiz.model_list_selection == 'product_list_update' else _('Supplier catalogue'),
                    wiz.product_list_id.name if wiz.model_list_selection == 'product_list_update' else wiz.supplier_catalogue_id.name,
                    ', '.join([self.get_displayable_name(cr, uid, parent_model, x, context=context) for x in id_check[wiz.model_list_selection].keys()]).strip(' ,')
                )
            )

        if len(fields_gotten) != len(fields_needed_name):
            raise osv.except_osv(_('Info'), _('Header info fields must be the following: %s') % ', '.join(fields_needed_name).strip(', '))
        for i, fn in enumerate(fields_needed_name):
            if fields_gotten[i] != fn:
                raise osv.except_osv(_('Info'), _('Line %s: Expected header column %s got %s') % (i+1, fn, fields_gotten[i]))

        return True

    def excel_col(self, col):
        """Covert column number (1,2,...26,27,28...) to excel-style column label
        letters (A,B,..Z,AA,AB,...)."""
        quot, rem = divmod(col-1,26)
        return self.excel_col(quot) + chr(rem+ord('A')) if col!=0 else ''

    def check_missing_columns(self, cr, uid, wizard_brw, head, context=None):
        """Check that the column names in the file match the expected property
        names, raise if any column is missing.
        """
        selection = wizard_brw.model_list_selection
        model = MODEL_DICT[selection]['model']
        model_obj = self.pool.get(model)
        header_columns = [head[i].data for i in range(0, len(head))]
        missing_columns = []
        field_list = MODEL_DATA_DICT[selection]['header_list']

        fields_get_dict = {}  # keep fields_get result in cache
        new_ctx = context.copy()
        if 'lang' in MODEL_DICT.get(selection, {}):
            new_ctx['lang'] = MODEL_DICT[selection]['lang']

        fields_get_dict[model] = model_obj.fields_get(cr, uid, context=new_ctx)
        if len(field_list) != len(header_columns):
            raise osv.except_osv(_('Info'), _('The number of column is not same ' \
                                              'than expected (get %s, expected %s). Check your import file and ' \
                                              'the Object to import/export.') % (len(header_columns), len(field_list)))

        for field_index, field in enumerate(field_list):
            child_field, child_model = self.get_child_field(cr, uid, field, model,
                                                            fields_get_dict, context=new_ctx)
            first_part = field.split('.')[0]
            custom_name = MODEL_DATA_DICT[selection].get('custom_field_name', {}).get(field)
            if custom_name:
                column_name = custom_name
            else:
                if child_field == 'id':
                    if first_part != 'id':
                        column_name = '%s / XMLID' % fields_get_dict[model][first_part]['string']
                    else:
                        column_name = 'id'
                elif first_part not in fields_get_dict[model]:
                    raise osv.except_osv(_('Error'),
                                         _('field \'%s\' not found for model \'%s\'. Please contact the support team.')
                                         % (first_part, model))
                elif first_part != child_field:
                    if child_field not in fields_get_dict[child_model]:
                        raise osv.except_osv(_('Error'),
                                             _('field \'%s\' not found for model \'%s\'. Please contact the support team.')
                                             % (child_field, child_model))
                    column_name = '%s / %s' % (fields_get_dict[model][first_part]['string'],
                                               fields_get_dict[child_model][child_field]['string'])
                else:
                    column_name = fields_get_dict[model][first_part]['string']
            file_column_name = header_columns[field_index] or ''
            if column_name.upper() != file_column_name.upper():
                missing_columns.append(_('Column %s: get \'%s\' expected \'%s\'.')
                                       % (self.excel_col(field_index+1), file_column_name, column_name))
        if missing_columns and model not in MODEL_HEADER_NOT_CHECKED:
            raise osv.except_osv(_('Info'), _('The following columns '
                                              'are missing in the imported file:\n%s') % ',\n'.join(missing_columns))

    def import_csv(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for wiz in self.browse(cr, uid, ids, context=context):
            selection = wiz.model_list_selection
            model = MODEL_DICT[selection]['model']

            if model == 'hq.entries':
                hq_import = self.pool.get('hq.entries.import')
                vals = {'file': wiz.import_file}
                wizard_id = hq_import.create(cr, uid, vals, context=context)
                self.write(cr, uid, [wiz.id], {
                    'state': 'progress',
                    'start_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'info_message': _('Import in progress in the specific wizard.'),
                }, context=context)
                res = hq_import.button_validate(cr, uid, wizard_id,
                                                context=context)
            elif model == 'msf.budget':
                budget_import = self.pool.get('wizard.budget.import')
                vals = {'import_file': wiz.import_file}
                wizard_id = budget_import.create(cr, uid, vals, context=context)
                res = budget_import.button_import(cr, uid, wizard_id,
                                                  context=context)

            else:
                raise osv.except_osv(_('Error'),
                                     _('The model \'%s\' is not made to be imported in CSV file.\n'
                                       'Please contact the support team.') % (model))
            self.write(cr, uid, [wiz.id], {
                'state': 'done',
                'start_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                'info_message': _('Import has been done via the specific wizard. The latter had to give information on the import.'),
            }, context=context)
            return res

    def button_import_xml(self, cr, uid, ids, context=None):
        self.import_xml(cr, uid, ids, context=context)
        return True

    def import_xml(self, cr, uid, ids, raise_on_error=False, context=None):
        """Create a thread to import the data after import checking
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        self.check_import(cr, uid, ids, context=context)

        for wiz in self.browse(cr, uid, ids, context=context):
            rows, nb_rows = self.read_file(wiz, context=context)
            if context.get('row'):
                head = context.get('row')
            else:
                head = rows.next()
            selection = wiz.model_list_selection
            model = MODEL_DICT[selection]['model']

            if model == 'user.access.configurator':
                # special case handling for this one
                model_obj = self.pool.get(model)
                wizard_id = model_obj.create(cr, uid, {}, context)
                model_obj.write(cr, uid, [wizard_id], {'file_to_import_uac':
                                                       wiz.import_file}, context=context)
                return model_obj.do_process_uac(cr, uid, [wizard_id], context=context)

            expected_headers = self._get_headers(cr, uid, model, selection=selection, context=context)
            if model not in MODEL_HEADER_NOT_CHECKED:
                self.check_headers(head, expected_headers, context=context)

            self.write(cr, uid, [wiz.id], {
                'total_lines_to_import': nb_rows,
                'state': 'progress',
                'start_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                'info_message': _('Import in progress, please leave this window open and press the button \'Update\' '
                                  'to show the progression of the import. Otherwise, you can continue to use Unifield'),
            }, context=context)
            wiz.total_lines_to_import = nb_rows - len(MODEL_DATA_DICT[selection].get('header_info', []))

            # set rows' iterator to the good index:
            if MODEL_DATA_DICT[selection].get('header_info'):
                for index, row in enumerate(rows):
                    if index > len(MODEL_DATA_DICT[selection].get('header_info')) - 1:
                        break

            #res = self.bg_import(cr.dbname, uid, wiz, expected_headers, rows, context)
            # thread = threading.Thread(
            #     target=self.bg_import,
            #     args=(cr.dbname, uid, wiz, expected_headers, rows, context),
            # )
            # thread.start()
            # # for now we don't want background but foreground
            # # in case background is needed, just set a value to wait time
            # wait_time = None
            # thread.join(wait_time)
        return self.bg_import(cr, uid, wiz, expected_headers, rows, raise_on_error=raise_on_error,  context=context)

    def _handle_dest_cc_dates(self, cr, uid, data, dest_cc_list, dest_cc_tuple_list, context=None):
        """
        Gets and checks the dest_cc_link_active_from and dest_cc_link_inactive_from dates.
        Updates the dest_cc_tuple_list with tuples containing (cost_center, active_date, inactive_date)
        """
        if context is None:
            context = {}
        dest_cc_active_date_list = []
        dest_cc_inactive_date_list = []
        active_from = (True, 'dest_cc_link_active_from', _("Activation Combination Dest / CC from"))
        inactive_from = (False, 'dest_cc_link_inactive_from', _("Inactivation Combination Dest / CC from"))
        for t in [active_from, inactive_from]:
            active = t[0]
            col_name = t[1]
            col_str = t[2]
            dest_cc_date_list = []
            if data.get(col_name):
                split_char = ';'
                if split_char not in data.get(col_name):
                    split_char = ','
                for cost_center_date in data.get(col_name).split(split_char):
                    cc_date = cost_center_date.strip()
                    if cc_date:
                        cc_date = cc_date.replace(' 00:00:00.00', '')  # can be if there is only one date in the cell
                        try:
                            cc_date = datetime.strptime(cc_date, "%Y-%m-%d")
                        except ValueError:
                            raise Exception(_('The dates in the column "%s" should use the format YYYY-MM-DD.') % col_str)
                    else:
                        cc_date = False  # the related Dest/CC combination has no activation/inactivation date
                    dest_cc_date_list.append(cc_date)
                del data[col_name]
            if len(dest_cc_date_list) > len(dest_cc_list):
                raise Exception(_('The number of dates in the column "%s" exceeds the number of Cost Centers indicated.') % col_str)
            if active:
                dest_cc_active_date_list = dest_cc_date_list[:]
            else:
                dest_cc_inactive_date_list = dest_cc_date_list[:]
        for num, cc in enumerate(dest_cc_list):
            try:
                dest_cc_active_date = dest_cc_active_date_list[num]
            except IndexError:
                dest_cc_active_date = False
            try:
                dest_cc_inactive_date = dest_cc_inactive_date_list[num]
            except IndexError:
                dest_cc_inactive_date = False
            if dest_cc_active_date and dest_cc_inactive_date and dest_cc_active_date >= dest_cc_inactive_date:
                cc_code = self.pool.get('account.analytic.account').read(cr, uid, cc, ['code'], context=context)['code'] or ''
                raise Exception(_('The activation date related to the Cost Center %s must be before the inactivation date.') % cc_code)
            dest_cc_tuple_list.append((cc, dest_cc_active_date, dest_cc_inactive_date))

    def bg_import(self, cr, uid, import_brw, headers, rows, raise_on_error=False, context=None):
        """
        Run the import of lines in background
        :param dbname: Name of the database
        :param uid: ID of the res.users that calls this method
        :param import_brw: browse_record of a wizard.import.batch
        :param headers: List of expected headers
        :param rows: Iterator on file rows
        :param context: Context of the call
        :return: True
        """
        if context is None:
            context = {}

        dbname = cr.dbname

        model = MODEL_DICT[import_brw.model_list_selection]['model']
        impobj = self.pool.get(model)
        acc_obj = self.pool.get('account.account')
        acc_analytic_obj = self.pool.get('account.analytic.account')
        acc_dest_obj = self.pool.get('account.destination.link')
        dest_cc_link_obj = self.pool.get('dest.cc.link')

        cost_centers_cache = {}
        gl_account_cache = {}
        parent_ok_cache = {}
        import_data_obj = self.pool.get('import_data')
        prod_nomenclature_obj = self.pool.get('product.nomenclature')

        # Manage errors
        import_errors = {}
        allow_partial = not raise_on_error and MODEL_DICT[import_brw.model_list_selection].get('partial')
        forced_values =  MODEL_DICT[import_brw.model_list_selection].get('forced_values', {})
        def save_error(errors, row_index):
            if not isinstance(errors, list):
                errors = [errors]
            import_errors.setdefault(row_index+2, [])
            import_errors[row_index+2].extend(errors)

        # Manage warnings
        import_warnings = {}

        def save_warnings(warnings):
            if not isinstance(warnings, list):
                warnings = [warnings]
            import_warnings.setdefault(row_index+2, [])
            import_warnings[row_index+2].extend(warnings)

        start_time = time.time()

        if model == 'product.product':
            # Create the cache
            if not hasattr(self, '_cache'):
                self._cache = {}
            self._cache.setdefault(dbname, {})

            if not hasattr(self.pool.get('product.nomenclature'), '_cache'):
                self.pool.get('product.nomenclature')._cache = {}
            self.pool.get('product.nomenclature')._cache.setdefault(dbname, {})

            # Clear the cache
            self._cache[dbname] = {'product.nomenclature': {'name': {}, 'complete_name': {}},
                                   'product.uom': {'name': {}},
                                   'product.asset.type': {'name': {}},
                                   'product.international.status': {'name': {}},
                                   }
            # Product nomenclature and complete name
            temp_nomen_by_id = {}
            cr.execute('''
                SELECT n.id, coalesce(t.value,n.name), n.parent_id 
                FROM product_nomenclature n 
                LEFT JOIN ir_translation t ON t.lang='en_MF' AND t.name='product.nomenclature,name' AND t.res_id=n.id 
                ORDER BY n.level;
            ''')
            for nv in cr.dictfetchall():
                self._cache[dbname]['product.nomenclature']['name'].update({nv['coalesce']: nv['id']})
                if nv['parent_id'] and temp_nomen_by_id.get(nv['parent_id'], False):
                    temp_full_name = temp_nomen_by_id[nv['parent_id']] + ' | ' + nv['coalesce']
                    temp_nomen_by_id.update({nv['id']: temp_full_name})
                    self._cache[dbname]['product.nomenclature']['complete_name'].update({temp_full_name.lower(): nv['id']})
                else:
                    temp_nomen_by_id.update({nv['id']: nv['coalesce']})
                    self._cache[dbname]['product.nomenclature']['complete_name'].update({nv['coalesce'].lower(): nv['id']})
            # Product category
            cr.execute('SELECT id, family_id FROM product_category;')
            for pc in cr.dictfetchall():
                self.pool.get('product.nomenclature')._cache[dbname].update({pc['family_id']: pc['id']})
            # Product UoM
            cr.execute('SELECT name, id FROM product_uom;')
            for uv in cr.dictfetchall():
                self._cache[dbname]['product.uom']['name'].update({uv['name']: uv['id']})
            # Asset type
            cr.execute('SELECT name, id FROM product_asset_type;')
            for av in cr.dictfetchall():
                self._cache[dbname]['product.asset.type']['name'].update({av['name']: av['id']})
            # International status
            cr.execute('SELECT name, id FROM product_international_status;')
            for iv in cr.dictfetchall():
                self._cache[dbname]['product.international.status']['name'].update({iv['name']: iv['id']})

        fields_def = impobj.fields_get(cr, uid, context=context)
        i = 0

        # custom process to retrieve CC, Destination_ids
        custom_m2m = []
        if import_brw.model_list_selection == 'destinations':
            custom_m2m = ['destination_ids']
        elif import_brw.model_list_selection == 'funding_pools':
            custom_m2m = ['cost_center_ids', 'tuple_destination_account_ids']
        for c_m2m in custom_m2m:
            if c_m2m in fields_def:
                fields_def[c_m2m]['type'] = 'many2many_custom'

        def _get_obj(header, value, fields_def):
            list_obj = header.split('.')
            relation = fields_def[list_obj[0]]['relation']
            if impobj._name == 'product.product' and value in self._cache.get(dbname, {}).get(relation, {}).get(list_obj[1], {}):
                return self._cache[dbname][relation][list_obj[1]][value]
            new_obj = self.pool.get(relation)
            if list_obj[1] == 'id':
                imd_obj = self.pool.get('ir.model.data')

                if '.' in value:
                    module, xml_id = value.rsplit('.', 1)
                else:
                    module, xml_id = model, value
                record_id = imd_obj._get_id(cr, uid, module, xml_id)
                ir_model_data = imd_obj.read(cr, uid, [record_id], ['res_id'])
                if not ir_model_data:
                    raise ValueError('No references to %s.%s' % (module, xml_id))
                newids = [ir_model_data[0]['res_id']]
            else:
                newids = new_obj.search(cr, uid, [(list_obj[1], '=ilike', value)], limit=1)
            if not newids:
                # no obj
                raise osv.except_osv(_('Warning !'), _('%s \'%s\' does not exist') % (new_obj._description, value,))

            if impobj._name == 'product.product':
                self._cache[dbname].setdefault(relation, {})
                self._cache[dbname][relation].setdefault(list_obj[1], {})
                self._cache[dbname][relation][list_obj[1]][value] = newids[0]
            return newids[0]

        def process_data(field, value, fields_def):
            if value is None or field not in fields_def:
                return
            if '.' not in field:
                if fields_def[field]['type'] == 'char' and value and isinstance(value, basestring) and len(value.splitlines()) > 1 and ( field != 'name' or impobj != 'res.partner'):
                    raise osv.except_osv(_('Warning !'), _("New line characters in the field '%s' not allowed. Please fix entry :\n'%s'") % (field, tools.ustr(value)))

                if fields_def[field]['type'] == 'selection':
                    if impobj == 'product.product' and self._cache[dbname].get('product.product.%s.%s' % (field, value), False):
                        value = self._cache[dbname]['product.product.%s.%s' % (field, value)]
                    else:
                        for key, val in fields_def[field]['selection']:
                            if value.lower() in [tools.ustr(key).lower(), tools.ustr(val).lower()]:
                                value = key
                                if impobj == 'product.product':
                                    self._cache[dbname].setdefault('product.product.%s' % field, {})
                                    self._cache[dbname]['product.product.%s.%s' % (field, value)] = key
                                break
                if fields_def[field]['type'] == 'many2many' and field != 'fp_account_ids':
                    new_obj = self.pool.get(fields_def[field]['relation'])
                    ret = [(6, 0, [])]
                    for name in value.split(','):
                        new_id = new_obj.name_search(cr, uid, name)
                        if not new_id:
                            raise osv.except_osv(_('Warning !'), _('%s \'%s\' does not exist') % (new_obj._description, name,))
                        new_id = new_id[0]
                        if isinstance(new_id, (list, tuple)): # name_search may return (id, name) or only id
                            new_id = new_id[0]
                        ret[0][2].append(new_id)
                    return ret
                return value

            else:
                if fields_def[field.split('.')[0]]['type'] in 'many2one':
                    return _get_obj(field, value, fields_def)

            raise osv.except_osv(_('Warning !'), _('%s does not exist')%(value,))

        i = 1
        nb_error = 0
        nb_succes = 0
        nb_update_success = 0
        col_datas = {}
        nb_imported_lines = 0
        nb_lines_deleted = 0
        header_codes = [x[3] for x in headers]

        if import_data_obj.pre_hook.get(impobj._name):
            # for headers mod.
            col_datas = import_data_obj.pre_hook[impobj._name](impobj, cr, uid, header_codes, {}, col_datas)

        processed = []
        rejected = []
        lines_already_updated = [] # ids of the lines already updated
        forbid_creation_of = [] # list of product ids that will not be created
        last_empty_lines = []
        for row_index, row in enumerate(rows):
            res, errors, line_data = self.check_error_and_format_row(import_brw.id, row, headers, context=context)
            if all(not x for x in line_data):
                save_warnings(
                    _('Line seemed empty, so this line was ignored')
                )
                last_empty_lines.append(row_index+2)
                continue
            last_empty_lines = []
            if res < 0:
                if raise_on_error:
                    raise Exception('Line %s: %s' % (row_index+1, '\n'.join(errors)))

                save_error(errors, row_index)
                rejected.append((row_index+1, line_data, '\n'.join(errors)))
                continue

            newo2m = False
            delimiter = False
            o2mdatas = {}
            i += 1
            data = {}
            try:
                if model == 'hq.entries':
                    hq_entries_obj = self.pool.get('hq.entries.import')
                    hq_entries_obj.update_hq_entries(cr, uid, line_data, context=context)
                    continue

                n = 0
                line_ok = True
                if import_data_obj.pre_hook.get(impobj._name):
                    import_data_obj.pre_hook[impobj._name](impobj, cr, uid, header_codes, line_data, col_datas)

                # Search if an object already exist. If not, create it.
                ids_to_update = []
                for n, h in enumerate(header_codes):
                    if h in MODEL_DATA_DICT[import_brw.model_list_selection].get('ignore_field', []):
                        continue
                    if isinstance(line_data[n], basestring):
                        line_data[n] = line_data[n].rstrip()

                    # UFTP-327
                    # if required reject cells with exceeded field length
                    if 'import_data_field_max_size' in context:
                        if h in context['import_data_field_max_size']:
                            max_size = context['import_data_field_max_size'][h]
                            if len(line_data[n]) > max_size:
                                msg_tpl = "field '%s' value exceed field length of %d"
                                msg = msg_tpl % (h , max_size, )
                                error = "Line %s, row: %s, %s" % (i, n, msg, )
                                if raise_on_error:
                                    raise Exception(error)

                                logging.getLogger('import data').info(
                                    'Error %s'% (msg, ))
                                cr.rollback()
                                save_error(error, row_index)
                                nb_error += 1
                                line_ok = False
                                break

                    if newo2m and ('.' not in h or h.split('.')[0] != newo2m or h.split('.')[1] == delimiter):
                        data.setdefault(newo2m, []).append((0, 0, o2mdatas.copy()))
                        o2mdatas = {}
                        delimiter = False
                        newo2m = False
                    if h == 'id' and line_data[n]:
                        ids_to_update = _get_obj('id.id', line_data[n], {'id': {'relation': impobj._name}})

                    elif '.' not in h:
                        # type datetime, date, bool, int, float
                        value = process_data(h, line_data[n], fields_def)
                        if value is not None:
                            data[h] = value
                    else:
                        points = h.split('.')
                        if row[n] and fields_def[points[0]]['type'] == 'one2many':
                            newo2m = points[0]
                            delimiter = points[1]
                            new_fields_def = self.pool.get(fields_def[newo2m]['relation']).fields_get(cr, uid, context=context)
                            o2mdatas[points[1]] = process_data('.'.join(points[1:]), line_data[n], new_fields_def)
                        elif fields_def[points[0]]['type'] == 'many2one':
                            if not line_data[n]:
                                data[points[0]] = False
                            elif line_data[n]:
                                data[points[0]] = _get_obj(h, line_data[n], fields_def) or False
                        elif fields_def[points[0]]['type'] == 'many2many' and line_data[n] :
                            if points[0] == 'fp_account_ids' :
                                value = process_data(points[0], line_data[n], fields_def)
                                if value is not None:
                                    data[points[0]] = value
                            else:
                                data.setdefault(points[0], []).append((4, _get_obj(h, line_data[n], fields_def)))

                if not line_ok:
                    rejected.append((row_index+1, line_data, ''))
                    continue
                if newo2m and o2mdatas:
                    data.setdefault(newo2m, []).append((0, 0, o2mdatas.copy()))

                if import_data_obj.post_hook.get(impobj._name):
                    import_data_obj.post_hook[impobj._name](impobj, cr, uid, data, line_data, header_codes)


                if impobj._name == 'product.product':
                    # Allow to update the product, use xmlid_code or default_code
                    if 'xmlid_code' in data:
                        ids_to_update = impobj.search(cr, uid, [('xmlid_code',
                                                                 '=', data['xmlid_code'])], order='NO_ORDER')
                    if 'default_code' in data:
                        ids_to_update = impobj.search(cr, uid, [('default_code',
                                                                 '=', data['default_code'])], order='NO_ORDER')
                elif impobj._name == 'product.nomenclature':
                    ids_to_update = impobj.search(cr, uid, [('msfid', '=',
                                                             data['msfid'])], order='NO_ORDER')
                elif impobj._name == 'product.category':
                    ids_to_update = impobj.search(cr, uid, [('family_id', '=',
                                                             data['family_id'])], order='NO_ORDER')
                elif impobj._name == 'supplier.catalogue':
                    ids_to_update = impobj.search(cr, uid, [
                        ('name', '=', data['name']),
                        ('partner_id', '=', data['partner_id']),
                    ], order='NO_ORDER')
                if import_brw.model_list_selection == 'supplier_catalogue_update':
                    data['catalogue_id'] = import_brw.supplier_catalogue_id.id
                    ids_to_update = impobj.search(cr, uid, [
                        ('catalogue_id', '=', import_brw.supplier_catalogue_id.id),
                        ('product_id', '=', data['product_id']),
                    ], context=context)
                    if data.get('comment') != '[DELETE]':
                        ids_to_update = [x for x in ids_to_update if x not in lines_already_updated]
                        ids_to_update = [ids_to_update[0]] if ids_to_update else []
                    else:
                        forbid_creation_of.append(data['product_id'])
                    lines_already_updated += ids_to_update
                if import_brw.model_list_selection == 'product_list_update':
                    data['list_id'] = import_brw.product_list_id.id
                    new_product_id = self.pool.get('product.product').search(cr, uid, [('default_code', '=', line_data[0].strip())], context=context)
                    if new_product_id:
                        ids_to_update = impobj.search(cr, uid, [('list_id', '=', import_brw.product_list_id.id), ('name', '=', new_product_id[0])], context=context)
                    data['name'] = new_product_id and new_product_id[0] or False

                if import_brw.model_list_selection == 'access_control_list':
                    ids_to_update = self.pool.get('ir.model.access').search(cr, uid, [('model_id', '=', data.get('model_id')), ('name', '=', data.get('name'))])
                    if len(ids_to_update) > 1:
                        raise Exception('%d records found for model=%s, name=%s' % (len(ids_to_update), data.get('model_id'), data.get('name')))

                if import_brw.model_list_selection == 'field_access_rule_lines':
                    ids_to_update = self.pool.get('msf_field_access_rights.field_access_rule_line').search(cr, uid, [('field_access_rule', '=', data.get('field_access_rule')), ('field', '=', data.get('field'))], context=context)
                    if len(ids_to_update) > 1:
                        raise Exception('%d records found for rule=%s, field=%s' % (len(ids_to_update), data.get('field_access_rule'), data.get('field')))

                if import_brw.model_list_selection == 'field_access_rules':
                    if not data.get('group_ids'):
                        data['group_ids'] = [(6, 0, [])]
                    ids_to_update = self.pool.get('msf_field_access_rights.field_access_rule').search(cr, uid, [('name', '=', data.get('name')), ('model_id', '=', data.get('model_id')), ('active', 'in', ['t', 'f'])], context=context)
                    if len(ids_to_update) > 1:
                        raise Exception('%d records found for rule=%s, model=%s' % (len(ids_to_update), data.get('name'), data.get('model_id')))

                # Funding Pools
                if import_brw.model_list_selection == 'funding_pools':
                    ids_to_update = acc_analytic_obj.search(cr, uid, [('code', '=ilike', data.get('code')), ('category', '=', 'FUNDING')])
                    context['from_import_menu'] = True
                    data['category'] = 'FUNDING'
                    # Parent Analytic Account
                    if data.get('parent_id'):
                        parent_id = acc_analytic_obj.browse(cr, uid, data['parent_id'],
                                                            fields_to_fetch=['type', 'category'], context=context)
                        parent_type = parent_id.type or ''
                        parent_category = parent_id.category or ''
                        if parent_type != 'view' or parent_category != 'FUNDING':
                            raise Exception(_('The Parent Analytic Account must be a View type Funding Pool.'))
                    # Cost Centers
                    if data.get('cost_center_ids'):
                        # Block the possibility to have both a list of Cost Centers and "Allow all Cost Centers" set to "True"
                        if data.get('allow_all_cc_with_fp'):
                            raise Exception(_('Import error for account "%s" : If listing Cost Centers, "Allow all Cost Centers" must be set to False.') % data.get('name'))
                        else:
                            # Listing "Cost Centers" unticks the box "Allow all Cost Centers" in the FP form
                            data['allow_all_cc_with_fp'] = False
                        cc_list = []
                        for cost_center in data.get('cost_center_ids').split(','):
                            cc = cost_center.strip()
                            cc_dom = [('category', '=', 'OC'), ('type', '=', 'normal'),
                                      '|', ('code', '=', cc), ('name', '=', cc)]
                            cc_ids = impobj.search(cr, uid, cc_dom, order='id', limit=1, context=context)
                            if cc_ids:
                                cc_list.append(cc_ids[0])
                            else:
                                raise Exception(_('Cost Center "%s" not found.') % cc)
                        data['cost_center_ids'] = [(6, 0, cc_list)]
                    else:
                        data['cost_center_ids'] = [(6, 0, [])]
                    # Account/Destination
                    if data.get('tuple_destination_account_ids'):
                        # Block the possibility to have both "Accounts/Destinations" and "G/L Accounts
                        if data.get('fp_account_ids'):
                            raise Exception(_('Import error for account "%s" : Listing both Accounts/Destinations and G/L Accounts is not allowed') % data.get('name'))
                        else:
                            # Listing "Accounts/Destinations" unticks the box "Select Accounts Only" in the FP form
                            data['select_accounts_only'] = False
                        dest_acc_list = []
                        for destination_account in data.get('tuple_destination_account_ids').split(','):
                            dest_acc_ids = []
                            dest_acc = destination_account.strip().split()  # ex: ['65000', 'EXP']
                            if len(dest_acc) == 2:
                                gl_acc_ids = acc_obj.search(cr, uid, [('code', '=', dest_acc[0])], limit=1, context=context)
                                dest_dom = [('category', '=', 'DEST'), ('type', '=', 'normal'), ('code', '=', dest_acc[1])]
                                dest_ids = impobj.search(cr, uid, dest_dom, limit=1, context=context)
                                if gl_acc_ids and dest_ids:
                                    acc_dest_dom = [('account_id', '=', gl_acc_ids[0]), ('destination_id', '=', dest_ids[0])]
                                    dest_acc_ids = acc_dest_obj.search(cr, uid, acc_dest_dom, limit=1, context=context)
                            if dest_acc_ids:
                                dest_acc_list.append(dest_acc_ids[0])
                            else:
                                raise Exception(_('Account/Destination "%s" not found.') % destination_account.strip())
                        data['tuple_destination_account_ids'] = [(6, 0, dest_acc_list)]
                    else:
                        data['tuple_destination_account_ids'] = [(6, 0, [])]
                    # G/L Accounts
                    if data.get('fp_account_ids'):
                        gl_list = []
                        # Block the possibility to have both "Accounts/Destinations" and "G/L Accounts
                        if data.get('tuple_destination_account_ids')[0][2]:     # at this stage even though the dest/acc is empty, data['tuple_destination_account_ids'] is filled with (6, 0, [])
                            raise Exception(_('Import error for account "%s" : Listing both Accounts/Destinations and G/L Accounts is not allowed') % data.get('name'))
                        else:
                            # Listing "G/L Accounts" ticks the box "Select Accounts Only" in the FP form
                            data['select_accounts_only'] = True
                        gl_iter = data.get('fp_account_ids').split(',')
                        for name in gl_iter:
                            name = name.strip()
                            # Allow the same accounts as in the interface
                            gl_dom = [('type', '!=', 'view'), ('is_analytic_addicted', '=', True), ('active', '=', 't'), ('code', '=', name), ('user_type_code', 'in', ['expense', 'income'])]
                            gl_ids = acc_obj.search(cr, uid, gl_dom, limit=1, context=context)
                            if gl_ids:
                                gl_list.append(gl_ids[0])
                            else:
                                raise Exception(_('Import error for account "%s" : G/L Account "%s" not found or not of type Income or Expense') % (data.get('name'), name))
                        data['fp_account_ids'] = [(6, 0, gl_list)]
                    else:
                        data['fp_account_ids'] = [(6, 0, [])]

                # Destinations
                dest_cc_tuple_list = []
                if import_brw.model_list_selection == 'destinations':
                    context['from_import_menu'] = True
                    data['category'] = 'DEST'
                    # Parent Analytic Account
                    if data.get('parent_id'):
                        if data['parent_id'] not in parent_ok_cache:
                            parent_id = acc_analytic_obj.browse(cr, uid, data['parent_id'], fields_to_fetch=['type', 'category'], context=context)
                            parent_type = parent_id.type or ''
                            parent_category = parent_id.category or ''
                            if parent_type == 'view' and parent_category == 'DEST':
                                parent_ok_cache[data['parent_id']] = True
                        if not parent_ok_cache.get(data['parent_id']):
                            raise Exception(_('The Parent Analytic Account must be a View type Destination.'))
                    # Type
                    if data['type'] not in ['normal', 'view']:
                        raise Exception(_('The Type must be either "Normal" or "View".'))
                    # Cost Centers
                    dest_cc_list = []
                    if data.get('dest_cc_link_ids'):
                        if data.get('allow_all_cc'):
                            raise Exception(_("Please either list the Cost Centers to allow, or allow all Cost Centers."))
                        split_char = ';'
                        if split_char not in data.get('dest_cc_link_ids'):
                            split_char = ','
                        for cost_center in data.get('dest_cc_link_ids').split(split_char):
                            cc = cost_center.strip()
                            if cc not in cost_centers_cache:
                                cc_dom = [('category', '=', 'OC'), ('type', '=', 'normal'), ('code', '=', cc)]
                                cost_centers_cache[cc] = impobj.search(cr, uid, cc_dom, order='id', limit=1, context=context)
                            cc_ids = cost_centers_cache.get(cc)
                            if cc_ids:
                                dest_cc_list.append(cc_ids[0])
                            else:
                                raise Exception(_('Cost Center "%s" not found.') % cc)
                    self._handle_dest_cc_dates(cr, uid, data, dest_cc_list, dest_cc_tuple_list, context=context)
                    # Accounts
                    if data.get('destination_ids'):  # "destinations_ids" corresponds to G/L accounts...
                        acc_list = []
                        split_char = ';'
                        if split_char not in data.get('destination_ids'):
                            split_char = ','
                        for account in data.get('destination_ids').split(split_char):
                            acc = account.strip()
                            if acc not in gl_account_cache:
                                acc_dom = [('type', '!=', 'view'), ('is_analytic_addicted', '=', True), ('code', '=', acc)]
                                gl_account_cache[acc] = acc_obj.search(cr, uid, acc_dom, order='id', limit=1, context=context)
                            acc_ids = gl_account_cache.get(acc)
                            if acc_ids:
                                acc_list.append(acc_ids[0])
                            else:
                                raise Exception(_("Account code \"%s\" doesn't exist or isn't allowed.") % acc)
                        data['destination_ids'] = [(6, 0, acc_list)]
                    else:
                        data['destination_ids'] = [(6, 0, [])]
                    # if the code matches with an existing destination: update it
                    if data.get('code'):
                        ids_to_update = impobj.search(cr, uid, [('category', '=', 'DEST'), ('code', '=', data['code'])],
                                                      limit=1, context=context)
                        if ids_to_update:
                            # in case of empty columns on non-required fields, existing values should be deleted
                            if 'date' not in data:
                                data['date'] = False
                            if 'allow_all_cc' not in data:
                                data['allow_all_cc'] = False
                            if 'destination_ids' not in data:
                                data['destination_ids'] = [(6, 0, [])]
                            elif data['destination_ids'][0][2]:
                                # accounts already linked to the destination:
                                # - if they don't appear in the new list: will be automatically de-activated
                                # - if they appear in the list: must be re-activated if they are currently disabled
                                link_ids = acc_dest_obj.search(cr, uid,
                                                               [('account_id', 'in', data['destination_ids'][0][2]),
                                                                ('destination_id', '=', ids_to_update[0]),
                                                                ('disabled', '=', True)], context=context)
                                if link_ids:
                                    acc_dest_obj.write(cr, uid, link_ids, {'disabled': False}, context=context)

                # Cost Centers
                if import_brw.model_list_selection == 'cost_centers':
                    ids_to_update = acc_analytic_obj.search(cr, uid, [('code', '=ilike', data.get('code')), ('category', '=', 'OC')])
                    context['from_import_menu'] = True
                    data['category'] = 'OC'
                    # Parent Analytic Account
                    if data.get('parent_id'):
                        parent_id = acc_analytic_obj.browse(cr, uid, data['parent_id'],
                                                            fields_to_fetch=['type', 'category'], context=context)
                        parent_type = parent_id.type or ''
                        parent_category = parent_id.category or ''
                        if parent_type != 'view' or parent_category != 'OC':
                            raise Exception(_('The Parent Analytic Account must be a View type Cost Center.'))

                # Free 1
                if import_brw.model_list_selection == 'free1':
                    context['from_import_menu'] = True
                    data['category'] = 'FREE1'
                    # Parent Analytic Account
                    if data.get('parent_id'):
                        parent_id = acc_analytic_obj.browse(cr, uid, data['parent_id'],
                                                            fields_to_fetch=['type', 'category'], context=context)
                        parent_type = parent_id.type or ''
                        parent_category = parent_id.category or ''
                        if parent_type != 'view' or parent_category != 'FREE1':
                            raise Exception(_('The Parent Analytic Account must be a View type Free 1 account.'))

                # Free 2
                if import_brw.model_list_selection == 'free2':
                    context['from_import_menu'] = True
                    data['category'] = 'FREE2'
                    # Parent Analytic Account
                    if data.get('parent_id'):
                        parent_id = acc_analytic_obj.browse(cr, uid, data['parent_id'],
                                                            fields_to_fetch=['type', 'category'], context=context)
                        parent_type = parent_id.type or ''
                        parent_category = parent_id.category or ''
                        if parent_type != 'view' or parent_category != 'FREE2':
                            raise Exception(_('The Parent Analytic Account must be a View type Free 2 account.'))

                if import_brw.model_list_selection == 'record_rules':
                    if not data.get('groups'):
                        data['groups'] = [(6, 0, [])]

                    ids_to_update = self.pool.get('ir.rule').search(cr, uid, [('name', '=', data.get('name')), ('model_id', '=', data.get('model_id'))], context=context)
                    if len(ids_to_update) > 1:
                        raise Exception('%d records found for rule=%s, model=%s' % (len(ids_to_update), data.get('name'), data.get('model_id')))

                if import_brw.model_list_selection == 'button_access_rules':
                    if not data.get('group_ids'):
                        data['group_ids'] = [(6, 0, [])]

                if import_brw.model_list_selection == 'window_actions':
                    if not data.get('groups_id'):
                        data['groups_id'] = [(6, 0, [])]

                data.update(forced_values)

                id_created = False
                if data.get('comment') == '[DELETE]':
                    impobj.unlink(cr, uid, ids_to_update, context=context)
                    nb_lines_deleted += len(ids_to_update)
                elif ids_to_update:
                    if 'standard_price' in data:
                        del data['standard_price']
                    if import_brw.model_list_selection == 'product_list_update' and 'name' in data:
                        del data['name']
                    impobj.write(cr, uid, ids_to_update, data, context=context)
                    nb_update_success += 1
                    processed.append((row_index+1, line_data))
                else:
                    context['from_import_menu']=  True
                    if import_brw.model_list_selection == 'supplier_catalogue_update':
                        if data.get('product_id') and data['product_id'] not in forbid_creation_of:
                            line_created = impobj.create(cr, uid, data, context=context)
                            lines_already_updated.append(line_created)
                    else:
                        id_created = impobj.create(cr, uid, data, context=context)
                    nb_succes += 1
                    processed.append((row_index+1, line_data))
                    if allow_partial:
                        cr.commit()
                # For Dest CC Links: create, update or delete the links if necessary
                if import_brw.model_list_selection == 'destinations':
                    if isinstance(ids_to_update, (int, long)):
                        ids_to_update = [ids_to_update]
                    if not dest_cc_tuple_list and ids_to_update:
                        # UC1: Dest CC Link column empty => delete all current Dest/CC combinations attached to the Dest
                        old_dcl_ids = dest_cc_link_obj.search(cr, uid, [('dest_id', 'in', ids_to_update)], order='NO_ORDER', context=context)
                        if old_dcl_ids:
                            dest_cc_link_obj.unlink(cr, uid, old_dcl_ids, context=context)
                    else:
                        # UC2: new dest
                        if id_created:
                            for cc, active_date, inactive_date in dest_cc_tuple_list:
                                dest_cc_link_obj.create(cr, uid, {'cc_id': cc, 'dest_id': id_created,
                                                                  'active_from': active_date, 'inactive_from': inactive_date},
                                                        context=context)
                        elif ids_to_update:
                            for dest_id in ids_to_update:
                                dest = acc_analytic_obj.browse(cr, uid, dest_id, fields_to_fetch=['dest_cc_link_ids'], context=context)
                                current_cc_ids = [dest_cc_link.cc_id.id for dest_cc_link in dest.dest_cc_link_ids]
                                new_cc_ids = []
                                for cc, active_date, inactive_date in dest_cc_tuple_list:
                                    new_cc_ids.append(cc)
                                    # UC3: new combinations in existing Destinations
                                    if cc not in current_cc_ids:
                                        dest_cc_link_obj.create(cr, uid, {'cc_id': cc, 'dest_id': dest_id,
                                                                          'active_from': active_date, 'inactive_from': inactive_date},
                                                                context=context)
                                    else:
                                        # UC4: combinations to be updated with new dates
                                        dcl_ids = dest_cc_link_obj.search(cr, uid,
                                                                          [('dest_id', '=', dest_id), ('cc_id', '=', cc)],
                                                                          limit=1, context=context)
                                        if dcl_ids:
                                            dest_cc_link = dest_cc_link_obj.read(cr, uid, dcl_ids[0],
                                                                                 ['active_from', 'inactive_from'], context=context)
                                            if dest_cc_link['active_from']:
                                                current_active_dt = datetime.strptime(dest_cc_link['active_from'], "%Y-%m-%d")
                                            else:
                                                current_active_dt = False
                                            if dest_cc_link['inactive_from']:
                                                current_inactive_dt = datetime.strptime(dest_cc_link['inactive_from'], "%Y-%m-%d")
                                            else:
                                                current_inactive_dt = False
                                            if (current_active_dt != active_date) or (current_inactive_dt != inactive_date):
                                                dest_cc_link_obj.write(cr, uid, dest_cc_link['id'],
                                                                       {'active_from': active_date, 'inactive_from': inactive_date},
                                                                       context=context)
                                # UC5: combinations to be deleted in existing Destinations
                                cc_to_be_deleted = [c for c in current_cc_ids if c not in new_cc_ids]
                                if cc_to_be_deleted:
                                    dcl_to_be_deleted = dest_cc_link_obj.search(cr, uid,
                                                                                [('dest_id', '=', dest_id), ('cc_id', 'in', cc_to_be_deleted)],
                                                                                order='NO_ORDER', context=context)
                                    dest_cc_link_obj.unlink(cr, uid, dcl_to_be_deleted, context=context)
            except (osv.except_osv, orm.except_orm) , e:
                logging.getLogger('import data').info('Error %s' % e.value)
                if raise_on_error:
                    raise Exception('Line %s, %s' % (row_index+2, e.value))
                cr.rollback()
                save_error(e.value, row_index)
                nb_error += 1
                rejected.append((row_index+1, line_data, e.value))
            except Exception, e:
                logging.getLogger('import data').info('Error %s' % tools.ustr(e))
                if raise_on_error:
                    raise Exception('Line %s: %s' % (row_index+2, tools.ustr(e)))
                cr.rollback()
                save_error(tools.ustr(e), row_index)
                nb_error += 1
                rejected.append((row_index+1, line_data, tools.ustr(e)))
            else:
                nb_imported_lines += 1

            self.write(cr, uid, [import_brw.id], {'total_lines_imported': nb_imported_lines}, context=context)

        for last in last_empty_lines:
            # do not display warning for the last empty lines
            del(import_warnings[last])

        warn_msg = ''
        for line_number in sorted(import_warnings.keys()):
            warnings = import_warnings[line_number]
            for warn in warnings:
                warn_msg += _('Line %s: %s') % (line_number, warn)
                if not warn_msg.endswith('\n'):
                    warn_msg += '\n'

        err_msg = ''
        for line_number in sorted(import_errors.keys()):
            errors = import_errors[line_number]
            for err in errors:
                err_msg += _('Line %s: %s') % (line_number, err)
                if not err_msg.endswith('\n'):
                    err_msg += '\n'

        if err_msg and not allow_partial:
            cr.rollback()

        info_msg = _('''Processing of file completed in %s second(s)!
- Total lines to import: %s
- Total lines %s: %s %s
- Total lines updated: %s
- Total lines created: %s
- Total lines deleted: %s
- Total lines with errors: %s %s
%s
        ''') % (
            str(round(time.time() - start_time, 1)),
            import_brw.total_lines_to_import-1,
            err_msg and _('without errors') or _('imported'),
            nb_imported_lines,
            warn_msg and _('(%s line(s) with warning - see warning messages below)') % (
                len(import_warnings.keys()) or '',
            ),
            nb_update_success,
            nb_succes,
            nb_lines_deleted,
            err_msg and len(import_errors.keys()) or 0,
            err_msg and _('(see error messages below)'),
            err_msg and not allow_partial and _("no data will be imported until all the error messages are corrected") or '',
        )

        self.write(cr, uid, [import_brw.id], {
            'error_message': err_msg,
            'show_error': err_msg and True or False,
            'warning_message': warn_msg,
            'show_warning': warn_msg and True or False,
            'info_message': info_msg,
            'state': 'done',
            'end_date': time.strftime('%Y-%m-%d %H:%M:%S'),
        }, context=context)

        if import_data_obj.post_load_hook.get(impobj._name):
            import_data_obj.post_load_hook[impobj._name](impobj, cr, uid)

        if impobj == 'product.product':
            # Clear the cache
            self._cache[dbname] = {}
            prod_nomenclature_obj._cache[dbname] = {}


        if allow_partial:
            cr.commit()

        return (processed, rejected, [tu[0] for tu in headers])

msf_import_export()

class account_analytic_account(osv.osv):
    _inherit = 'account.analytic.account'

    def auto_import_destination(self, cr, uid, file_to_import, context=None):
        processed = []
        rejected = []
        headers = []

        import_obj = self.pool.get('msf.import.export')
        import_id = import_obj.create(cr, uid, {
            'model_list_selection': 'destinations',
            'import_file': base64.encodestring(open(file_to_import, 'r').read()),
        }, context=context)
        processed, rejected, headers = import_obj.import_xml(cr, uid, [import_id], context=context)
        return processed, rejected, headers

account_analytic_account()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
