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

from osv import fields
from osv import osv
from tools.translate import _
from tempfile import TemporaryFile
from lxml import etree
from lxml.etree import XMLSyntaxError

MODEL_DICT = {
    # SUPPLY
    'products': {
        'name': 'Products',
        'domain_type': 'supply',
        'model': 'product.product',
    },
    'product_nomenclature': {
        'name': 'Product Nomenclature',
        'domain_type': 'supply',
        'model': 'product.nomenclature',
    },
    'product_category': {
        'name': 'Product Categories',
        'domain_type': 'supply',
        'model': 'product.categories',
    },
    'suppliers': {
        'name': 'Suppliers',
        'domain_type': 'supply',
        'model': 'res.partner',
        'domain': [('supplier', '=', True)],
    },
    'supplier_catalogues': {
        'name': 'Supplier Catalogues',
        'domain_type': 'supply',
        'model': 'supplier.catalogue.line',
    },


    # FINANCE
    'gl_accounts': {
        'name': 'GL Accounts',
        'domain_type': 'finance',
        'model': 'account.account'
    },
    'gl_journals': {
        'name': 'GL Journals',
        'domain_type': 'finance',
        'model': 'account.journal'
    },
    'analytic_account': {
        'name': 'Analytic Accounts',
        'domain_type': 'finance',
        'model': 'analytic.account'
    },


    # NON FUNCTIONNAL
    'user_groups': {
        'name': 'User Groups',
        'domain_type': 'non_functionnal',
        'model': 'res.groups'
    },
    'record_rules': {
        'name': 'Record Rules',
        'domain_type': 'non_functionnal',
        'model': 'ir.rule'
    },
}

MODEL_DATA_DICT = {
    'product.product': {
        'field_list': [
            'default_code',
            'name',
            'xmlid_code',
            'old_code',
            'type',
            'transport_ok',
            'subtype',
            'asset_type_id.name',
            'procure_method',
            'supply_method',
            'standard_price',
            'volume',
            'weight',
            'international_status.name',
            'state.name',
            'active',
            'perishable',
            'batch_management',
            'uom_id.name',
            'uom_po_id.name',
            'nomen_manda_0.name',
            'nomen_manda_1.name',
            'nomen_manda_2.name',
            'nomen_manda_3.name',
            'life_time',
            'use_time',
            'short_shelf_life',
            'alert_time',
            'heat_sensitive_item.code',
            'cold_chain',
            'sterilized',
            'single_use',
            'narcotic',
            'justification_code_id.id',
            'controlled_substance',
            'closed_article',
            'restricted_country',
            'country_restriction',
            'dangerous_goods',
            'un_code',
            'criticism',
            'abc_class',
            'product_catalog_path',
            'description',
            'description2',
            'description_sale',
            'description_purchase',
            'procure_delay',
            'property_account_income.code',
            'property_account_expense.code',
        ],
        'required_field_list': [
            'name',
            'internationnal_status.name'
            'nomen_manda_0.name',
            'nomen_manda_1.name',
            'nomen_manda_2.name',
            'nomen_manda_3.name',
        ],
        'hide_export_all_entries': True,
    },
    'product.nomenclature': {
        'field_list': [
            'level',
            'name',
            'type',
            'parent_id',
            'msfid'
        ],
        'required_field_list': [
            'level',
            'name',
        ],
        'hide_export_3_entries': True,
        'hide_export_all_entries': True,
    },
    'product.category': {
        'field_list': [
        ],
        'required_field_list': [
        ],
    },
    'account.account': {
        'field_list': [],
    },
    'account.journal': {
        'field_list': [],
    },
    'analytic.account': {
        'field_list': [],
    },
    'res.groups': {
        'field_list': [],
    },
    'ir.rule': {
        'field_list': [],
    },
}


class msf_import_export(osv.osv_memory):
    _name = 'msf.import.export'
    _description = 'MSF Import Export'


    def _model_selection_get(self, cr, uid, context=None, domain_type=None):
        '''return a selection of the model of domain_type
        '''
        if context is None:
            context = {}
        result_list = [(key, value['name']) for key, value in MODEL_DICT.items() if value['domain_type'] == domain_type]
        return sorted(result_list, key=lambda a: a[1])

    _columns = {
        'display_file_import': fields.boolean('File Import'),
        'display_file_export': fields.boolean('File Export'),
        'domain_type': fields.selection([
            ('', ''),
            ('supply', 'Supply'),
            ('finance', 'Finance'),
            ('non_functionnal', 'Non-Functionnal')
            ], 'Type', required=True,
            help='Type of object to import/export'),
        'model_list_selection': fields.selection(_model_selection_get, 'Object to Import/Export', required=True),
        'binary_file': fields.binary('File to import .xml'),
        'hide_export_3_entries': fields.boolean('Hide export 3 entries button'),
        'hide_export_all_entries': fields.boolean('Hide export all entries button'),
        'display_test_import_button': fields.boolean('Display test import button'),
    }

    _default = {
        'display_file_import': lambda *a: False,
        'display_file_export': lambda *a: False,
        'hide_export_3_entries': lambda *a: False,
        'hide_export_all_entries': lambda *a: False,
        'display_test_import_button': lambda *a: False,
    }

    def domain_type_change(self, cr, uid, obj_id, position, field_type, domain_type, model_list_selection, context=None):
        if context is None:
            context = {}

        result = {'value': {}}
        if position == 0 and domain_type:
            selection = self._model_selection_get(cr, uid, context=context, domain_type=domain_type)
            result['value']['model_list_selection'] = selection
            result['value']['display_file_import'] = False
            result['value']['display_file_export'] = False
        elif position == 1 and model_list_selection:
            result['value']['display_file_import'] = True
            result['value']['display_file_export'] = True
            model = MODEL_DICT.get(model_list_selection) and MODEL_DICT[model_list_selection]['model']
            if model and model in MODEL_DATA_DICT:
                hide_3 = MODEL_DATA_DICT[model].get('hide_export_3_entries', False)
                result['value']['hide_export_3_entries'] = hide_3
                hide_all = MODEL_DATA_DICT[model].get('hide_export_all_entries', False)
                result['value']['hide_export_all_entries'] = hide_all
            else:
                result['value']['hide_export_3_entries'] = False
                result['value']['hide_export_all_entries'] = False
        return result

    def file_change(self, cr, uid, obj_id, binary_file, context=None):
        if context is None:
            context = {}
        result = {
                'value': {
                    'display_test_import_button': False,
                }
        }
        if binary_file:
            result['value']['display_test_import_button'] = True
        return result

    def check_xml_syntax(self, cr, uid, xml_string, context=None):
        '''Try to parse the xml file and raise if there is an error
        '''
        try:
            file_dom = etree.fromstring(xml_string)
        except XMLSyntaxError as e:
            raise osv.except_osv(_('Error'), _('File structure is incorrect, '
                'please correct. You may generate a template with the File '
                'export functionality.'))

    def test_import(self, cr, uid, ids, context=None):
        '''check file structure is correct
        '''
        obj = self.read(cr, uid, ids[0])
        fileobj = TemporaryFile('w+')
        if not obj['binary_file']:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))
        try:
            xml_string = base64.decodestring(obj['binary_file'])
            self.check_xml_syntax(cr, uid, xml_string, context=context)
        finally:
            fileobj.close()

        # check that the required column are present
        # XXX to be written

        # check all column present in the file exists in the database
        # XXX to be written

        raise osv.except_osv(_('Info'), _('File structure is correct.'))

msf_import_export()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
