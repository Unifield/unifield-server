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
#    You should have received a..wizard.wizard_import_batch import IMPORT_BATCH_HEADERS copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import base64
import logging

from osv import osv
from osv import fields
from tools.translate import _


def check_utf8_encoding(file_to_check, base='base64'):
    """
    Check if the given file is an good UTF-8 file
    """
    if base == 'base64':
        file_to_check = base64.decodestring(file_to_check)

    try:
        file_to_check.decode('utf-8')
        return True
    except UnicodeError:
        return False


class ImportHeader(object):
    """
    Class used to export Header template.
    """
    type_ok = ['String', 'Number', 'DateTime']

    def __new__(self, name, type='String', size=70):
        """
        Initialize a header column for template export.
        :param name: Name of the field
        :param ftype: Type of the field
        :param size: Displayed size on Excel file
        """
        self.fld_name = name
        self.fld_type = type
        self.fld_size = size

        if self.fld_type not in ImportHeader.type_ok:
            err_msg = '''Defined type of header \'%s\' is not in the list of possible type: %s - Please contact
your support team and give us this message.
            ''' % (
                self.fld_name, ', '.join(t for t in ImportHeader.type_ok)
            )
            raise osv.except_osv(
                _('Error'),
                err_msg,
            )

        return (self.fld_name, self.fld_type, self.fld_size)


class abstract_wizard_import(osv.osv):
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
                res[wiz.id] = 1.00
            elif wiz.state == 'draft':
                res[wiz.id] = 0.00
            else:
                res[wiz.id] = float(wiz.total_lines_imported) / float(wiz.total_lines_to_import)

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
        'error_message': fields.text(
            string='Error',
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
            digits=(16,2),
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

    _defaults = {
        'total_lines_to_import': 0,
        'total_lines_imported': 0,
        'state': 'draft',
    }

    def exists(self, cr, uid, ids, context=None):
        if self._name != 'abstract.wizard.import':
            return super(abstract_wizard_import, self).exists(cr, uid, ids, context=context)
        return False

    def onchange_import_file(self, cr, uid, ids, import_file, context=None):
        """
        When the file to import is changed, check if the file is encoding in UTF-8
        """
        res = {}

        if import_file:
            if not check_utf8_encoding(import_file):
                res.update({
                    'warning': {
                        'title': _('Bad encoding'),
                        'message': _('The given file is not encoding in UTF-8. Please verify its encoding before retry'),
                    },
                    'values': {
                        'import_file': False,
                    },
                })

        return res

    def _get_template_file_data(self):
        """
        Return values for the import template file report generation
        """
        return {
            'model': self._name,
            'model_name': self._description,
            'header_columns': [],
        }

    def download_template_file(self, cr, uid, ids, context=None):
        """
        Download the template file
        """
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'wizard.import.generic.template',
            'datas': self._get_template_file_data(),
        }

    def copy(self, cr, uid, old_id, defaults=None, context=None):
        """
        Don't allow copy method
        """
        raise osv.except_osv(
            _('Not allowed'),
            _('You cannot duplicate a %s document!') % self._description,
        )

abstract_wizard_import()
