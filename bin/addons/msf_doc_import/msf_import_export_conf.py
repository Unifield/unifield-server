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
        'model': 'product.category',
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
        'model': 'account.analytic.account'
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
    'access_control_list': {
        'name': 'Access Control list',
        'domain_type': 'non_functionnal',
        'model': 'ir.model.access'
    },
    'field_access_rules': {
        'name': 'Field Access Rules',
        'domain_type': 'non_functionnal',
        'model': 'msf_field_access_rights.field_access_rule'
    },
    'field_access_rule_lines': {
        'name': 'Field Access Rule Lines',
        'domain_type': 'non_functionnal',
        'model': 'msf_field_access_rights.field_access_rule_line'
    },
    'button_access_rules': {
        'name': 'Button Access Rules',
        'domain_type': 'non_functionnal',
        'model': 'msf_button_access_rights.button_access_rule'
    },
    'window_actions': {
        'name': 'Window Actions',
        'domain_type': 'non_functionnal',
        'model': 'ir.actions.act_window'
    },
}

MODEL_DATA_DICT = {
    'products': {
        'header_list': [
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
            'international_status.name',
            'nomen_manda_0.name',
            'nomen_manda_1.name',
            'nomen_manda_2.name',
            'nomen_manda_3.name',
        ],
        'hide_download_all_entries': True,
    },
    'product_nomenclature': {
        'header_list': [
            'level',
            'name',
            'type',
            'parent_id',
            'msfid',
        ],
        'required_field_list': [
            'level',
            'name',
        ],
        'hide_download_3_entries': True,
        'hide_download_all_entries': True,
    },
    'product_category': {
        'header_list': [
            'type',
            'property_account_expense_categ',
            'property_account_income_categ',
            'name',
            'property_stock_journal',
            'donation_expense_account',
            'family_id',
            'msfid',
        ],
        'required_field_list': [
            'name',
            'family_id',
            'msfid',
        ],
    },
    'suppliers': {
        'header_list': [
            'address.type',
            'address.city',
            'address.name',
            'address.street',
            'address.zip',
            'address.country_id',
            'address.email',
            'property_account_payable',
            'property_account_receivable',
            'name',
            'lang',
            'partner_type',
            'customer',
            'supplier',
            'property_product_pricelist_purchase',
            'property_product_pricelist',
        ],
        'required_field_list': [
            'property_account_payable',
            'property_account_receivable',
            'name',
        ],
    },
    'supplier_catalogues': {
        'header_list': [
            'product_id.code',
            'product_id.name',
            'line_uom_id',
            'min_qty',
            'unit_price',
            'rounding',
            'min_order_qty',
            'comment',
        ],
        'required_field_list': [
            'product_id.code',
            'line_uom_id',
            'min_qty',
            'unit_price',
        ],
    },
    'gl_accounts': {
        'header_list': [
        ],
        'required_field_list': [
        ],
    },
    'gl_journals': {
        'header_list': [
        ],
        'required_field_list': [
        ],
    },
    'analytic_account': {
        'header_list': [
        ],
        'required_field_list': [
        ],
    },
    'user_groups': {
        'header_list': [
        ],
        'required_field_list': [
        ],
    },
    'record_rules': {
        'header_list': [
        ],
        'required_field_list': [
        ],
    },
    'access_control_list': {
        'header_list': [
        ],
        'required_field_list': [
        ],
    },
    'field_access_rules': {
        'header_list': [
        ],
        'required_field_list': [
        ],
    },
    'field_access_rule_lines': {
        'header_list': [
        ],
        'required_field_list': [
        ],
    },
    'button_access_rules': {
        'header_list': [
        ],
        'required_field_list': [
        ],
    },
    'window_actions': {
        'header_list': [
        ],
        'required_field_list': [
        ],
    },
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
