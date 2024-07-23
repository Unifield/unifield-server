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

from tools.translate import _

from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetCreator
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML

from msf_doc_import import GENERIC_MESSAGE
from msf_doc_import.wizard import SUPPLIER_CATALOG_COLUMNS_HEADER_FOR_IMPORT as sup_cat_columns_header
from msf_doc_import.wizard import SUPPLIER_CATALOG_COLUMNS_FOR_IMPORT as sup_cat_columns
from msf_doc_import.msf_import_export_conf import MODEL_DATA_DICT
from datetime import datetime


class supplier_catalogue(osv.osv):
    _inherit = 'supplier.catalogue'

    def auto_import(self, cr, uid, file_path, context=None):
        '''
        Method called in case of automated import
        Tools > Automated import 
        '''
        if context is None:
            context = {}

        def get_well_formed_date(content):
            if not content:
                return False
            elif isinstance(content, datetime):
                return content.strftime('%Y-%m-%d')
            elif isinstance(content, str):
                return content.strip()
            return False

        xmlstring = open(file_path, 'rb').read()
        file_obj = SpreadsheetXML(xmlstring=xmlstring)

        displayable = {}
        for field in ['name', 'partner_id', 'currency_id', 'period_from',  'period_to']:
            displayable[field] = MODEL_DATA_DICT['supplier_catalogue_update'].get('custom_field_name', {}).get(field) or \
                self.pool.get('msf.import.export').get_displayable_name(cr, uid, 'supplier.catalogue', field, context=context)

        data = {}
        for index, row in enumerate(file_obj.getRows()):
            if index > len(MODEL_DATA_DICT['supplier_catalogue_update'].get('header_info')) -1 :
                break
            if row.cells[0].data == displayable['name']:
                data['name'] = row.cells[1].data
            elif row.cells[0].data == displayable['partner_id']:
                partner_id = self.pool.get('res.partner').search(cr, uid, [('name', '=', row.cells[1].data)], context=context)
                data['partner_id'] = partner_id[0] if partner_id else False
            elif row.cells[0].data == displayable['currency_id']:
                currency_id = self.pool.get('res.currency').search(cr, uid, [('name', '=', row.cells[1].data)], context=context)
                data['currency_id'] = currency_id[0] if currency_id else False
            elif row.cells[0].data == displayable['period_from']:
                data['period_from'] = get_well_formed_date(row.cells[1].data)
            elif row.cells[0].data == displayable['period_to']:
                data['period_to'] = get_well_formed_date(row.cells[1].data)

        catalogue_id = False
        if data.get('name') and data.get('partner_id'):
            catalogue_id = self.search(cr, uid, [('name', '=', data['name']), ('partner_id', '=', data['partner_id'])], context=context)
        else:
            raise osv.except_osv(_('Error'), ('Given partner not found'))
        if not catalogue_id:
            catalogue_id = self.create(cr, uid, data, context=context)
            catalogue_id = [catalogue_id]
            self.button_confirm(cr, uid, catalogue_id, context=context)
            cr.commit()
        else:
            self.write(cr, uid, catalogue_id, {'period_from': data['period_from'], 'period_to': data.get('period_to', False)}, context=context)

        res = (False, False, False)
        if catalogue_id:
            wiz_id = self.pool.get('msf.import.export').create(cr, uid, {
                'model_list_selection': 'supplier_catalogue_update',
                'supplier_catalogue_id': catalogue_id[0],
                'import_file': base64.b64encode(xmlstring),
            }, context=context)

            res = self.pool.get('msf.import.export').import_xml(cr, uid, wiz_id, context=context)

        return res


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

        if isinstance(ids, int):
            ids = [ids]

        context['active_id'] = ids[0]

        columns_header = [(_(f[0]), f[1]) for f in sup_cat_columns_header]

        default_template = SpreadsheetCreator('Template of import', columns_header, [])
        template_file = base64.b64encode(default_template.get_xml(default_filters=['decode.utf8']))

        export_id = wiz_obj.create(cr, uid, {
            'file': template_file,
            'filename_template': _('Supplier Catalogue template.xls'),
            'message': """%s %s""" % (
                _(GENERIC_MESSAGE),
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
