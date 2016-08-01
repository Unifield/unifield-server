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

from osv import osv
from tools.translate import _

from msf_doc_import.wizard.abstract_wizard_import import ImportHeader
from msf_doc_import.wizard.abstract_wizard_import import UnifieldImportException


def get_import_batch_headers():
    return [
         ImportHeader(name=_('Name'), ftype='String', size=80, tech_name='name'),
         ImportHeader(name=_('Product Code'), ftype='String', size=80, tech_name='product_id'),
         ImportHeader(name=_('Product Description'), ftype='String', size=120),
         ImportHeader(name=_('Life Date'), ftype='DateTime', size=60, tech_name='life_date'),
         ImportHeader(name=_('Type'), ftype='String', size=80, tech_name='type'),
    ]


class wizard_import_batch(osv.osv):
    _name = 'wizard.import.batch'
    _description = 'Import batch numbers'
    _inherit = 'abstract.wizard.import'
    _auto = True

    _defaults = {
        'model_name': 'stock.production.lot',
        'template_filename': 'Import_batch_number_tpl.csv',
    }

    def _get_template_file_data(self):
        """
        Return values for the import template file report generation
        """
        return {
            'model': 'stock.production.lot',
            'model_name': _('Batch numbers'),
            'header_columns': get_import_batch_headers(),
        }

    def run_import(self, cr, uid, ids, context=None):
        """
        Make checks on file to import and run the import in background.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of ID of wizard.import.patch on which import should be made
        :param context: Context of the call
        :return: True
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        expected_headers = get_import_batch_headers()

        for wiz in self.browse(cr, uid, ids, context=context):
            rows = self.read_file(wiz)

            head = rows.next()
            self.check_headers(head, expected_headers)

            self.bg_import(cr, uid, wiz, expected_headers, rows, context=context)

        return True

    def bg_import(self, cr, uid, import_brw, headers, rows, context=None):
        """
        Run the import of lines in background
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param import_brw: browse_record of a wizard.import.batch
        :param headers: List of expected headers
        :param rows: Iterator on file rows
        :param context: Context of the call
        :return: True
        """
        if context is None:
            context = {}

        # Get header list and information
        header_index_by_name = {}
        for i, h in enumerate(headers):
            header_index_by_name[h[3]] = i

        def get_cell(field):
            return line_data[header_index_by_name[field]]

        # Manage errors
        import_errors = {}
        def save_error(errors):
            if not isinstance(errors, list):
                errors = [errors]
            import_errors.setdefault(row_index+1, [])
            import_errors[row_index+1].extend(errors)

        for row_index, row in enumerate(rows):
            res, errors, line_data = self.check_error_and_format_row(import_brw.id, row, headers)
            if res < 0:
                save_error(errors)
                continue

            # Product
            product_id = None
            try:
                product_id = self.get_product_by_default_code(cr, uid, get_cell('product_id'), context=context)
            except UnifieldImportException as e:
                save_error(e.message)

            # Batch number type
            batch_type = get_cell('type')
            if batch_type.upper() not in (_('Standard').upper(), _('Internal').upper()):
                save_error(
                    _('The Type of the batch number should be \'Standard\' or \'Internal\''),
                )

        print import_errors

        return True


wizard_import_batch()
