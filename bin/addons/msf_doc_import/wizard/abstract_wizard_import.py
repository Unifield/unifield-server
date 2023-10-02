# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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

import base64
import string

from mx import DateTime

from osv import osv
from osv import fields
from tools.translate import _

from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML


class UnifieldImportException(Exception):
    pass


class ImportHeader(object):
    """
    Class used to export Header template.
    """
    type_ok = ['String', 'Number', 'DateTime', 'Boolean', 'Float']

    def __new__(cls, name, ftype='String', size=70, tech_name=None, required=False):
        """
        Initialize a header column for template export.
        :param name: Name of the field
        :param ftype: Type of the field
        :param size: Displayed size on Excel file
        :param tech_name: Technical name of the field to compute
        :param required: Is the field should be set or not ?
        """
        if ftype not in ImportHeader.type_ok:
            err_msg = _('''Defined type of header \'%s\' is not in the list of possible type: %s - Please contact
your support team and give us this message.
            ''') % (
                name, ', '.join(t for t in ImportHeader.type_ok)
            )
            raise osv.except_osv(
                _('Error'),
                err_msg,
            )

        return _(name), ftype, size, tech_name, required

    @classmethod
    def get_date_from_str(cls, date_value):
        """
        Try to construct a date from a string and return a formatted string date
        :param date_value: String value to compute
        :return: A datetime instance or False
        """
        # US:2527: accept only one format, reject other
        accepted_date_format = [
            '%d/%m/%Y',
        ]

        d = False
        for dformat in accepted_date_format:
            try:
                d = DateTime.strptime(date_value, dformat)
                d = d.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                continue

        return d

    @classmethod
    def check_value(cls, header, value, vtype, context=None):
        """
        Check the value of the column according to header
        :param header: Header used to check if value is required or not
        :param value: Value to check
        :param vtype: Type of the data given
        :return: A tuple with the result of the check, the formatted value and the error message if any
        """
        if not value and header[4]:
            return (-1, value, _('The column \'%s\' is required') % header[0])
        elif not value:
            return (0, value, None)
        elif header[1] == 'String':
            if vtype == 'str':
                return (0, value, None)
            else:
                try:
                    return (0, str(value), None)
                except Exception as e:
                    return (-1, value, e)
        elif header[1] == 'DateTime':
            if vtype == 'datetime':
                return (0, value, None)
            elif vtype == 'str':
                d = ImportHeader.get_date_from_str(value)
                if d:
                    return (0, d, None)
                else:
                    return (-1, value, _('The date format was not correct. The expected date should be > 01/01/1900 in this format DD/MM/YYYY.'))
            else:
                return (-1, value, _('The date format was not correct. The expected date should be > 01/01/1900 in this format DD/MM/YYYY.'))
        elif header[1] == 'Integer':
            if vtype == 'number':
                return (0, value, None)
            else:
                try:
                    return (0, int(value), None)
                except Exception as e:
                    return (-1, value, e)
        elif header[1] == 'Float':
            if vtype == 'number':
                return (0, value, None)
            else:
                try:
                    if isinstance(value, basestring):
                        value = value.rstrip().replace(',', '.')
                    return (0, float(value), None)
                except Exception as e:
                    return (-1, value, e)
        elif header[1] == 'Boolean':
            if isinstance(value, bool):
                pass
            elif value.upper() in ('T', 'TRUE', '1'):
                value = True
            else:
                value = False
        elif header[1] == 'Number':
            if vtype =='int':
                try:
                    return (0, int(value), None)
                except Exception as e:
                    return (-1, value, e)

        return (0, value, None)


class abstract_wizard_import(osv.osv_memory):
    _name = 'abstract.wizard.import'
    _description = 'Generic import wizard'
    _auto = False
    _order = 'start_date'

    def _get_progression(self, cr, uid, ids, field_name, args, context=None):
        """
        Return the percentage of progression
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}

        for wiz in self.browse(cr, uid, ids, context=context):
            if wiz.state == 'done':
                res[wiz.id] = 100.00
            elif wiz.state == 'draft':
                res[wiz.id] = 0.00
            else:
                res[wiz.id] = float(wiz.total_lines_imported) / float(wiz.total_lines_to_import) * 100

        return res

    _columns = {
        'model_name': fields.char(
            size=64,
            string='Model to import',
            required=True,
            readonly=True,
        ),
        'parent_model_name': fields.char(
            size=64,
            string='Model of the parent',
            readonly=True,
            help="To go back to the parent when the window is closed",
        ),
        'parent_record_id': fields.integer(
            string='ID of the parent record',
            readonly=True,
        ),
        'template_file': fields.binary(
            string='Template file',
            readonly=True,
        ),
        'template_filename': fields.char(
            size=64,
            string='Template filename',
            readonly=True,
        ),
        'import_file': fields.binary(
            string='File to import',
        ),
        'info_message': fields.text(
            string='Information',
            readonly=True,
        ),
        'error_message': fields.text(
            string='Errors',
            readonly=True,
        ),
        'show_error': fields.boolean(
            string='Show error message ?',
            readonly=True,
        ),
        'warning_message': fields.text(
            string='Warnings',
            readonly=True,
        ),
        'show_warning': fields.boolean(
            string='Show warning message ?',
            readonly=True,
        ),
        'total_lines_to_import': fields.integer(
            string='# of lines to import',
            readonly=True,
        ),
        'total_lines_imported': fields.integer(
            string='# of lines imported',
            readonly=True,
        ),
        'progression': fields.function(
            _get_progression,
            method=True,
            type='float',
            digits=(16, 2),
            string='Progression',
            store=False,
            readonly=False,
        ),
        'state': fields.selection(
            selection=[
                ('draft', 'Not started'),
                ('progress', 'In progress'),
                ('done', 'Done'),
            ],
            string='State',
            readonly=True,
        ),
        'start_date': fields.datetime(
            string='Start date',
            readonly=True,
        ),
        'end_date': fields.datetime(
            string='End date',
            readonly=True,
        ),
    }

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        """
        Return default values for some fields
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param fields: Technical name of the fields on which system must put a default value
        :param context: Context of the call
        :return: A dictionary with field names as keys
        """
        res = super(abstract_wizard_import, self).default_get(cr, uid, fields, context=context, from_web=from_web)
        res.update({
            'total_lines_to_import': 0,
            'total_lines_imported': 0,
            'state': 'draft',
            'info_message': _('Select a file to import and click on \'Run import\' button.'),
        })
        return res

    def update(self, cr, uid, ids, context=None):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': ids[0],
            'view_type': 'form',
            'view_mode': 'form,tree',
            'target': 'keep_same', # Just to keep reload of the page
            'context': context,
        }

    def exists(self, cr, uid, ids, context=None):
        if self._name != 'abstract.wizard.import':
            return super(abstract_wizard_import, self).exists(cr, uid, ids, context=context)
        return False

    def _get_template_file_data(self, context=None):
        """
        Return values for the import template file report generation
        """
        return {
            'model': self._name,
            'model_name': self._description,
            'header_columns': [],
        }

    def copy(self, cr, uid, old_id, defaults=None, context=None):
        """
        Don't allow copy method
        """
        raise osv.except_osv(
            _('Not allowed'),
            _('You cannot duplicate a %s document!') % self._description,
        )

    def download_template_file(self, cr, uid, ids, context=None):
        """
        Download the template file
        """
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'wizard.import.generic.template',
            'datas': self._get_template_file_data(context=context),
        }

    def run_import(self, cr, uid, ids, context=None):
        raise osv.except_osv(
            _('Error'),
            _('No \'run_import\' action is defined for the object \'%s\'!') % self._name,
        )

    def check_utf8_encoding(self, import_file, base='base64'):
        """
        Check if the given file is an good UTF-8 file
        """
        if base == 'base64':
            import_file = base64.decodestring(import_file)

        try:
            import_file.decode('utf-8')
            return True
        except UnicodeError:
            return False

    def read_file(self, wizard_brw, context=None):
        """
        Open the Spreadsheet XML file
        :param wizard_brw: browse_record of an import wizard
        :return: An iterator on the rows of the file
        """
        if not wizard_brw.import_file:
            raise osv.except_osv(
                _('Error'),
                _('No file to import. Please select a file or download the template file and fill it.'),
            )

        if wizard_brw.state != 'draft':
            raise osv.except_osv(
                _('Error'),
                _('Import can be run only on draft wizard.'),
            )

        if not self.check_utf8_encoding(wizard_brw.import_file):
            raise osv.except_osv(
                _('Error'),
                _('The given file seems not to be encoding in UTF-8. Please check the encoding of the file and re-try.')
            )

        file_obj = SpreadsheetXML(xmlstring=base64.decodestring(wizard_brw.import_file))

        file_obj.getNbRows()
        # iterator on rows
        try:
            res = file_obj.getRows(), file_obj.getNbRows()
            return res
        except TypeError as e:
            raise osv.except_osv(
                _('Error'),
                _('An error occurs during the reading of the file. Please contact an administrator and give him the import file and this error: %s') % e,
            )

    def check_headers(self, headers_row, headers_title, context=None):
        """
        Check if the header in the first row of the file are the same as the expected headers
        :param headers_row: Row that contains the header on the Excel file
        :param headers_title: List of expected headers
        :return: True or raise an error
        """
        if len(headers_row) != len(headers_title):
            raise osv.except_osv(
                _('Error'),
                _('The number of columns in the Excel file (%s) is different than the expected number '\
                  'of columns (%s).\nColumns should be in this order: %s') % (
                    len(headers_row),
                    len(headers_title),
                    '\n * '.join(h[0] for h in headers_title),
                ),
            )

        errors = []
        headers_title_up = [_(x[0]).upper() for x in headers_title]
        headers_row_up = [_(headers_row[i].data).upper() for i in range(0, len(headers_row))]
        for h_index, h in enumerate(headers_title_up):
            if h not in headers_row_up:
                errors.append(
                    _('The column \'%s\' is not present in the file.') % _(headers_title[h_index][0])
                )
            elif headers_row_up[h_index] != h:
                errors.append(
                    _('The column \'%s\' of the Excel file should be \'%s\', not \'%s\'.') % (
                        string.uppercase[h_index],
                        _(headers_title[h_index][0]),
                        _(headers_row[h_index]),
                    )
                )
        if errors:
            raise osv.except_osv(
                _('Error'),
                '\n'.join(err for err in errors),
            )

        return True

    def check_error_and_format_row(self, wizard_id, row, headers, context=None):
        """
        Check if the required cells are set and if this the data are well formatted
        :param wizard_id: ID of the import wizard
        :param row: Row of the Excel file
        :param headers: Required headers
        :return: True
        """
        try:
            line_content = row.cells
        except ValueError:
            return (-1, _('Line is empty'))

        if len(line_content) > len(headers):
            return (-1, _('Number of columns (%s) in the line are larger than expected (%s).') % (
                len(line_content), len(headers)
            ), [])

        # if the last comlumn(s) is(are) empty, line_content do not contain
        # this column: len(line_content) is equal to len(headers) - number of
        # empty columns at the end
        if len(line_content) < len(headers):
            # add None instead of the missing column
            line_content += [None for x in range((len(headers) - len(line_content)))]

        data = []
        errors = []
        for col_index, col_value in enumerate(line_content):
            if col_value is None:
                data.append(None)
                continue
            # Check data values according to expected type
            chk_res = ImportHeader.check_value(headers[col_index], col_value.data, col_value.type, context=context)
            data.append(chk_res[1])
            if chk_res[0] < 0:
                errors.append(chk_res[2])

        return (len(errors) and -1 or 0, errors, data)

    def get_product_by_default_code(self, cr, uid, default_code, context=None):
        """
        Return the ID of the product.product related to the default_code parameter
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param default_code: Code of the product to find
        :param context: Context of the call
        :return: The ID of the product.product
        """
        p_obj = self.pool.get('product.product')
        p_ids = p_obj.search(cr, uid, [('default_code', '=ilike', default_code)], limit=1, order='NO_ORDER', context=context)
        if not p_ids:
            raise UnifieldImportException(_('No product found for the code \'%s\'') % default_code)

        return p_ids[0]


abstract_wizard_import()
