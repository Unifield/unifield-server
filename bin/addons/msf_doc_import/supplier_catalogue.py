# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
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

from osv import osv
from osv import fields

from tools.translate import _

from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetCreator

from msf_doc_import import GENERIC_MESSAGE
from msf_doc_import.wizard import SUPPLIER_CATALOG_COLUMNS_HEADER_FOR_IMPORT as sup_cat_columns_header
from msf_doc_import.wizard import SUPPLIER_CATALOG_COLUMNS_FOR_IMPORT as sup_cat_columns


class supplier_catalogue(osv.osv):
    _inherit = 'supplier.catalogue'

    def wizard_import_supplier_catalogue_line(self, cr, uid, ids, context=None):
        """
        Open the wizard to import supplier catalogue lines in background with progress bar.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of ID of supplier catalogues on which lines should be imported (only the first one is used)
        :param context: Context of the call
        :return : The action descriptino of the wizard to import lines in supplier catalogue
        """
        wiz_obj = self.pool.get('wizard.import.supplier.catalogue')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        context['active_id'] = ids[0]

        columns_header = [(_(f[0]), f[1]) for f in sup_cat_columns_header]

        default_template = SpreadsheetCreator('Template of import', columns_header, [])
        template_file = base64.encodestring(default_template.get_xml(default_filters=['decode.utf8']))

        export_id = wiz_obj.create(cr, uid, {
            'file': template_file,
            'filename_template': _('Supplier Catalogue template.xls'),
            'message': """%s %s""" % (
                GENERIC_MESSAGE,
                ', '.join([_(f) for f in sup_cat_columns]),
            ),
            'filename': _('Lines Not imported.xls'),
            'catalogue_id': ids[0],
            'state': 'draft',
        }, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': wiz_obj._name,
            'res_id': export_id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'crush',
            'context': context,
        }

supplier_catalogue()
