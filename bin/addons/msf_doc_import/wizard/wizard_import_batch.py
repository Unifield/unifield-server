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


IMPORT_BATCH_HEADERS = [
     ImportHeader(name=_('Name'), type='String', size=80),
     ImportHeader(name=_('Product Code'), type='String', size=80),
     ImportHeader(name=_('Product Description'), type='String', size=120),
     ImportHeader(name=_('Life Date'), type='Date', size=60),
     ImportHeader(name=_('Type'), type='String', size=80),
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
            'header_columns': IMPORT_BATCH_HEADERS,
        }

wizard_import_batch()
