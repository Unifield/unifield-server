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

import pooler
import tools

from osv import fields
from osv import osv, orm
from tools.translate import _

from tempfile import TemporaryFile
from lxml import etree
from lxml.etree import XMLSyntaxError

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
        domain_type = None
        if 'domain_type' in context:
            domain_type = context['domain_type']
        result_list = [(key, _(value['name'])) for key, value in MODEL_DICT.items() if value['domain_type'] == domain_type]
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
        model_obj = self.pool.get(model)

        fields_get_dict = {}  # keep fields_get result in cache
        fields_get_dict[model] = model_obj.fields_get(cr, uid, context=context)

        for field_index, field in enumerate(field_list):
            res = {'tech_name': field}
            if selection and field in MODEL_DATA_DICT[selection]['required_field_list']:
                res['required'] = True
            child_field, child_model = self.get_child_field(cr, uid, field, model,
                                                            fields_get_dict, context=context)
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
                _("%s selected (%s) doesn't match with the one you are trying to import. Please check following header fields: %s." % (
                    _('Product list') if wiz.model_list_selection == 'product_list_update' else _('Supplier catalogue'),
                    wiz.product_list_id.name if wiz.model_list_selection == 'product_list_update' else wiz.supplier_catalogue_id.name,
                    ', '.join([self.get_displayable_name(cr, uid, parent_model, x, context=context) for x in id_check[wiz.model_list_selection].keys()]).strip(' ,')
                ))
            )

        if len(fields_gotten) != len(fields_needed_name):
            raise osv.except_osv(_('Info'), _('Header info fields must be the following: %s' % ', '.join(fields_needed_name).strip(', ')))
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
        fields_get_dict[model] = model_obj.fields_get(cr, uid, context=context)
        if len(field_list) != len(header_columns):
            raise osv.except_osv(_('Info'), _('The number of column is not same ' \
                                              'than expected (get %s, expected %s). Check your import file and ' \
                                              'the Object to import/export.') % (len(header_columns), len(field_list)))

        for field_index, field in enumerate(field_list):
            child_field, child_model = self.get_child_field(cr, uid, field, model,
                                                            fields_get_dict, context=context)
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

            if column_name.upper() != header_columns[field_index].upper():
                missing_columns.append(_('Column %s: get \'%s\' expected \'%s\'.')
                                       % (self.excel_col(field_index+1), header_columns[field_index], column_name))
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

    def import_xml(self, cr, uid, ids, context=None):
        """Create a thread to import the data after import checking
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        self.check_import(cr, uid, ids, context=context)

        res = (False, False, False)
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

            res = self.bg_import(cr.dbname, uid, wiz, expected_headers, rows, context)
            # thread = threading.Thread(
            #     target=self.bg_import,
            #     args=(cr.dbname, uid, wiz, expected_headers, rows, context),
            # )
            # thread.start()
            # # for now we don't want background but foreground
            # # in case background is needed, just set a value to wait time
            # wait_time = None
            # thread.join(wait_time)
        return res

    def bg_import(self, dbname, uid, import_brw, headers, rows, context=None):
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
        cr = pooler.get_db(dbname).cursor()
        model = MODEL_DICT[import_brw.model_list_selection]['model']
        impobj = self.pool.get(model)

        import_data_obj = self.pool.get('import_data')
        prod_nomenclature_obj = self.pool.get('product.nomenclature')

        # Manage errors
        import_errors = {}

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
        for row_index, row in enumerate(rows):
            res, errors, line_data = self.check_error_and_format_row(import_brw.id, row, headers, context=context)
            if all(not x for x in line_data):
                save_warnings(
                    _('Line seemed empty, so this line was ignored')
                )
                continue
            if res < 0:
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
                                logging.getLogger('import data').info(
                                    'Error %s'% (msg, ))
                                cr.rollback()
                                error = "Line %s, row: %s, %s" % (i, n, msg, )
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
                        elif fields_def[points[0]]['type'] == 'many2many' and line_data[n]:
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
                    ids_to_update = impobj.search(cr, uid, [('msfid', '=',
                                                             data['msfid'])], order='NO_ORDER')
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
                        impobj.create(cr, uid, data, context=context)
                    nb_succes += 1
                    processed.append((row_index+1, line_data))
            except (osv.except_osv, orm.except_orm) , e:
                logging.getLogger('import data').info('Error %s' % e.value)
                cr.rollback()
                save_error(e.value, row_index)
                nb_error += 1
                rejected.append((row_index+1, line_data, e.value))
            except Exception, e:
                cr.rollback()
                logging.getLogger('import data').info('Error %s' % e)
                save_error(e, row_index)
                nb_error += 1
                rejected.append((row_index+1, line_data, e))
            else:
                nb_imported_lines += 1

            self.write(cr, uid, [import_brw.id], {'total_lines_imported': nb_imported_lines}, context=context)

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

        if err_msg:
            cr.rollback()

        info_msg = _('''Processing of file completed in %s second(s)!
- Total lines to import: %s
- Total lines %s: %s %s
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
            nb_lines_deleted,
            err_msg and len(import_errors.keys()) or 0,
            err_msg and _('(see error messages below)'),
            err_msg and _("no data will be imported until all the error messages are corrected") or '',
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


        cr.commit()
        cr.close()

        return (processed, rejected, [tu[0] for tu in headers])

msf_import_export()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
