# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
#
#    This 7ogram is free software: you can redistribute it and/or modify
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

import threading
import time

import pooler

from datetime import datetime

from osv import osv
from tools.translate import _

from msf_doc_import.wizard.abstract_wizard_import import ImportHeader
from msf_doc_import.wizard.abstract_wizard_import import UnifieldImportException


def get_import_batch_headers(context=None):
    return [
        ImportHeader(name=_('get_import_batch_headers_name'), ftype='String', size=80, tech_name='name', required=False),
        ImportHeader(name=_('get_import_batch_headers_type'), ftype='String', size=80, tech_name='type', required=True),
        ImportHeader(name=_('get_import_batch_headers_life_date'), ftype='DateTime', size=60, tech_name='life_date', required=True),
        ImportHeader(name=_('get_import_batch_headers_product_code'), ftype='String', size=80, tech_name='product_id', required=True),
        ImportHeader(name=_('get_import_batch_headers_product_desc'), ftype='String', size=120, required=False),
    ]

# Get header list and information
header_index_by_name = {}
for i, h in enumerate(get_import_batch_headers()):
    header_index_by_name[h[3]] = i


def get_cell(line_data, field):
    cell_data = line_data[header_index_by_name[field]]
    if cell_data:
        return cell_data
    return None


class wizard_import_batch(osv.osv_memory):
    _name = 'wizard.import.batch'
    _description = 'Import batch numbers'
    _inherit = 'abstract.wizard.import'
    _auto = True

    _defaults = {
        'model_name': 'stock.production.lot',
        'template_filename': 'Import_batch_number_tpl.csv',
    }

    def _get_template_file_data(self, context=None):
        """
        Return values for the import template file report generation
        """
        return {
            'model': 'stock.production.lot',
            'model_name': _('Batch numbers'),
            'header_columns': get_import_batch_headers(context=context),
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

        if isinstance(ids, int):
            ids = [ids]

        expected_headers = get_import_batch_headers(context=context)

        for wiz in self.browse(cr, uid, ids, context=context):
            rows, nb_rows = self.read_file(wiz, context=context)

            head = next(rows)
            self.check_headers(head, expected_headers, context=context)

            self.write(cr, uid, [wiz.id], {
                'total_lines_to_import': nb_rows,
                'state': 'progress',
                'start_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                'info_message': _('Import in progress, please leave this window open and press the button \'Update\' '
                                  'to show the progression of the import. Otherwise, you can continue to use Unifield'),
            }, context=context)
            wiz.total_lines_to_import = nb_rows

            thread = threading.Thread(
                target=self.bg_import,
                args=(cr.dbname, uid, wiz, expected_headers, rows, context),
            )
            thread.start()

        return True

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

        prodlot_obj = self.pool.get('stock.production.lot')
        product_obj = self.pool.get('product.product')
        sequence_obj = self.pool.get('ir.sequence')
        date_tools = self.pool.get('date.tools')

        if context is None:
            context = {}

        cr = pooler.get_db(dbname).cursor()
        nb_imported_lines = 0

        # Manage errors
        import_errors = {}

        def save_error(errors):
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
        nb_lines_ok = 0
        for row_index, row in enumerate(rows):
            res, errors, line_data = self.check_error_and_format_row(import_brw.id, row, headers, context=context)
            if res < 0:
                save_error(errors)
                continue

            if all(not x for x in line_data):
                save_warnings(
                    _('Line seemed empty, so this line was ignored')
                )
                continue

            # Product
            product_id = None
            try:
                product_id = self.get_product_by_default_code(cr, uid, get_cell(line_data, 'product_id').strip(),
                                                              context=context)
            except UnifieldImportException as e:
                save_error(e)

            # Batch number type
            batch_type = get_cell(line_data, 'type').strip()
            if batch_type.upper() not in (_('Standard').upper(), _('Internal').upper()):
                save_error(
                    _('The type of the batch number should be \'Standard\' or \'Internal\''),
                )
                batch_type = None
            elif batch_type.upper() == _('Standard').upper():
                batch_type = 'standard'
            elif batch_type.upper() == _('Internal').upper():
                batch_type = 'internal'

            # Go to next line if all base data are not set
            if not (product_id and batch_type):
                continue

            # Make consistency checks
            name = get_cell(line_data, 'name').strip()
            life_date = get_cell(line_data, 'life_date')
            try:
                # US-2492: In case we've ended up with a mx.DateTime.DateTime here
                # make it into the string we were expecting.
                if life_date and isinstance(life_date, datetime):
                    life_date = life_date.strftime('%Y-%m-%d %H:%M:%S')
                if life_date and datetime.strptime(life_date, '%Y-%m-%d %H:%M:%S') < datetime(1900, 1, 1, 0, 0, 0):
                    date_format = date_tools.get_date_format(cr, uid, context=context)
                    save_error(
                        _('You cannot create a batch number with an expiry date before %s') % (
                            datetime(1900, 1, 1, 0, 0, 0).strftime(date_format),
                        ),
                    )
                    continue
            except Exception as e:
                save_error(e)

            product_brw = product_obj.read(cr, uid, product_id, ['batch_management', 'perishable'], context=context)

            if not product_brw['batch_management'] and not product_brw['perishable']:
                save_error(
                    _('You cannot create a batch number for a product that is not \'Perishable\''
                      ' nor \'Batch mandatory\'')
                )
                continue
            elif product_brw['batch_management'] and batch_type == 'internal':
                save_error(
                    _('You cannot create an \'Internal\' batch number for a \'Batch mandatory\' product')
                )
                continue
            elif not product_brw['batch_management'] and product_brw['perishable'] and batch_type == 'standard':
                save_error(
                    _('You cannot create a \'Standard\' batch number for a non \'Batch mandatory\' product')
                )
                continue
            elif product_brw['batch_management'] and not name:
                save_error(
                    _('For a \'Standard\' batch number, you have to put a value in the \'Batch Number\' column')
                )
                continue

            # Check no duplicate
            prodlot_domain = [
                ('product_id', '=', product_id),
                ('type', '=', batch_type),
                ('life_date', '=', life_date),
            ]
            if product_brw['batch_management']:
                prodlot_domain.append(('name', '=', name))

            prodlot_id = prodlot_obj.search(cr, uid, prodlot_domain, limit=1, order='NO_ORDER', context=context)
            if prodlot_id:
                save_error(
                    _('A batch number with the same parameters already exists in the system')
                )
                continue

            if batch_type == 'internal':
                if name:
                    save_warnings(
                        _('Name of the batch will be ignored because the batch is \'Internal\' so '
                          'name is created by the system')
                    )
                name = sequence_obj.get(cr, uid, 'stock.lot.serial')

            create_vals = {
                'name': name,
                'product_id': product_id,
                'life_date': life_date,
                'type': batch_type,
            }
            try:
                prodlot_obj.create(cr, uid, create_vals, context=context)
                nb_lines_ok += 1
            except Exception as e:
                save_error(e)
                cr.rollback()

            nb_imported_lines += 1
            self.write(cr, uid, [import_brw.id], {'total_lines_imported': nb_imported_lines}, context=context)

        warn_msg = ''
        for lnum, warnings in import_warnings.items():
            for warn in warnings:
                warn_msg += _('Line %s: %s') % (lnum, warn)
                warn_msg += '\n'

        err_msg = ''
        for lnum, errors in import_errors.items():
            for err in errors:
                err_msg += _('Line %s: %s') % (lnum, err)
                err_msg += '\n'

        if err_msg:
            cr.rollback()

        info_msg = _('''Processing of file completed in %s second(s)!
- Total lines to import: %s
- Total lines %s: %s %s
- Total lines with errors: %s %s
%s
        ''') % (
            str(round(time.time() - start_time, 1)),
            import_brw.total_lines_to_import-1,
            err_msg and _('without errors') or _('imported'),
            nb_lines_ok,
            warn_msg and _('(%s line(s) with warning - see warning messages below)') % (
                len(list(import_warnings.keys())) or '',
            ),
            err_msg and len(list(import_errors.keys())) or 0,
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

        cr.commit()
        cr.close()

        return True

wizard_import_batch()
