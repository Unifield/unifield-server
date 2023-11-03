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

from tools.translate import _

MODEL_DICT = {
    # SUPPLY
    'products': {
        'name': 'Products',
        'domain_type': 'supply',
        'model': 'product.product',
        'partial': True,
    },
    'product_nomenclature': {
        'name': 'Product Nomenclature',
        'domain_type': 'supply',
        'model': 'product.nomenclature',
        'partial': True,
    },
    'product_category': {
        'name': 'Product Categories',
        'domain_type': 'supply',
        'model': 'product.category',
        'domain': [('msfid', '!=', False)],
        'partial': True,
    },
    'product_list': {
        'name': 'Products Lists',
        'domain_type': 'supply',
        'model': 'product.list',
        'partial': True,
    },
    'product_list_line': {
        'name': 'Products Lists Lines',
        'domain_type': 'supply',
        'model': 'product.list.line',
        'partial': True,
    },
    'product_list_update': {
        'name': 'Products Lists Update',
        'domain_type': 'supply',
        'model': 'product.list.line',
        'partial': True,
    },
    'suppliers': {
        'name': 'Suppliers',
        'domain_type': 'supply',
        'model': 'res.partner',
        'domain': [('supplier', '=', True)],
        'partial': True,
    },
    'supplier_catalogues': {
        'name': 'Supplier Catalogues',
        'domain_type': 'supply',
        'model': 'supplier.catalogue',
        'partial': True,
    },
    'supplier_catalogues_lines': {
        'name': 'Supplier Catalogue Lines',
        'domain_type': 'supply',
        'model': 'supplier.catalogue.line',
        'partial': True,
    },
    'supplier_catalogue_update': {
        'name': 'Supplier Catalogue Update',
        'domain_type': 'supply',
        'model': 'supplier.catalogue.line',
        'partial': True,
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
    'funding_pools': {
        'name': 'Funding Pools',
        'domain_type': 'finance',
        'model': 'account.analytic.account',
        'domain': [('category', '=', 'FUNDING'), ('parent_id', '!=', False)]
    },
    'destinations': {
        'name': 'Destinations',
        'domain_type': 'finance',
        'model': 'account.analytic.account',
        'domain': [('category', '=', 'DEST'), ('parent_id', '!=', False)]
    },
    'cost_centers': {
        'name': _('Cost Center Creation Mapping'),
        'domain_type': 'finance',
        'model': 'account.analytic.account',
        'domain': [('category', '=', 'OC'), ('parent_id', '!=', False)],
        'partial': False
    },
    'cost_centers_update': {
        'name': _('Cost Center Updates'),
        'domain_type': 'finance',
        'model': 'account.analytic.account',
        'domain': [('category', '=', 'OC'), ('parent_id', '!=', False)],
        'partial': False
    },
    'free1': {
        'name': 'Free 1',
        'domain_type': 'finance',
        'model': 'account.analytic.account',
        'domain': [('category', '=', 'FREE1'), ('parent_id', '!=', False)]
    },
    'free2': {
        'name': 'Free 2',
        'domain_type': 'finance',
        'model': 'account.analytic.account',
        'domain': [('category', '=', 'FREE2'), ('parent_id', '!=', False)]
    },
    'analytic_journals': {
        'name': 'Analytic Journals',
        'domain_type': 'finance',
        'model': 'account.analytic.journal'
    },
    'employees': {
        'name': 'Employees',
        'domain_type': 'finance',
        'model': 'hr.employee'
    },
    'hq_entries': {
        'name': 'HQ Entries',
        'domain_type': 'finance',
        'model': 'hq.entries'
    },
    'currency_rate': {
        'name': 'Currencies Rates',
        'domain_type': 'finance',
        'model': 'res.currency.rate'
    },
    'budget': {
        'name': 'Budget',
        'domain_type': 'finance',
        'model': 'msf.budget'
    },


    # NON FUNCTIONNAL
    'user_groups': {
        'name': 'User Groups',
        'domain_type': 'non_functionnal',
        'model': 'res.groups'
    },
    'user_access': {
        'name': 'User Access',
        'domain_type': 'non_functionnal',
        'lang': 'en_MF',
        'model': 'user.access.configurator'
    },
    'record_rules': {
        'name': 'Record Rules',
        'domain_type': 'non_functionnal',
        'lang': 'en_MF',
        'model': 'ir.rule'
    },
    'access_control_list': {
        'name': 'Access Controls List',
        'domain_type': 'non_functionnal',
        'model': 'ir.model.access',
        'lang': 'en_MF',
        'domain': [('from_system', '=', False), ('model_id.model_exists', '=', True)],
    },
    'access_control_list_empty': {
        'name': 'Objects without ACL',
        'domain_type': 'non_functionnal',
        'model': 'ir.model.access.empty',
        'lang': 'en_MF',
        'domain': [('model_id.osv_memory', '=', False), ('model_id.model_exists','=', True)],
    },
    'field_access_rules': {
        'name': 'Field Access Rules',
        'domain_type': 'non_functionnal',
        'lang': 'en_MF',
        'model': 'msf_field_access_rights.field_access_rule'
    },
    'field_access_rule_lines': {
        'name': 'Field Access Rule Lines',
        'domain_type': 'non_functionnal',
        'lang': 'en_MF',
        'model': 'msf_field_access_rights.field_access_rule_line'
    },
    'button_access_rules': {
        'name': 'Button Access Rules',
        'domain_type': 'non_functionnal',
        'lang': 'en_MF',
        'model': 'msf_button_access_rights.button_access_rule',
    },
    'window_actions': {
        'name': 'Window Actions',
        'domain_type': 'non_functionnal',
        'model': 'ir.actions.act_window',
        'lang': 'en_MF',
        'domain': [('res_model', '!=', 'audittrail.log.line')],
    },
}

MODEL_DATA_DICT = {
    # SUPPLY
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
            'justification_code_id.code',
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
            'parent_id.msfid',
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
            'asset_bs_account_id',
            'asset_bs_depreciation_account_id',
            'asset_pl_account_id',
            'family_id.msfid',
        ],
        'required_field_list': [
            'name',
            'family_id.msfid',
        ],
    },
    'product_list_update': {
        'header_info': [
            'type',
            'ref',
            'name',
            'description',
            'standard_list_ok',
            'order_list_print_ok',
            'warehouse_id',
            'location_id',
        ],
        'header_list': [
            'name.default_code',
            'name.name',
            'comment',
        ],
        'required_field_list': [
            'name.default_code',
        ],
        'ignore_field': [
            'name.name',
        ],
        'custom_field_name': {
            'name.default_code': 'Product Code',
            'ref': 'Ref',
            'order_list_print_ok': 'Order List print',
        },
    },
    'product_list': {
        'header_list': [
            'name',
            'type',
            'creator',
            'ref',
        ],
        'required_field_list': [
            'name',
            'type',
            'creator',
        ],
    },
    'product_list_line': {
        'header_list': [
            'list_id.name',
            'name.default_code',
            'name',
            'comment',
        ],
        'required_field_list': [
            'list_id.name',
            'name.default_code',
        ],
        'ignore_field': [
            'name'
        ],
    },
    'suppliers': {
        'header_list': [
            'address.type',
            'address.city',
            'address.name',
            'address.street',
            'address.zip',
            'address.phone',
            'address.country_id.name',
            'address.email',
            'property_account_payable.code',
            'property_account_receivable.code',
            'name',
            'lang',
            'partner_type',
            'customer',
            'supplier',
            'property_product_pricelist_purchase.currency_id',
            'property_product_pricelist.currency_id',
        ],
        'required_field_list': [
            'property_account_payable.code',
            'property_account_receivable.code',
            'name',
        ],
    },
    'supplier_catalogues': {
        'header_list': [
            'name',
            'period_from',
            'period_to',
            'currency_id.name',
            'partner_id.name',
        ],
        'required_field_list': [
            'name',
            'currency_id.name',
            'partner_id.name',
        ],
    },
    'supplier_catalogues_lines': {
        'header_list': [
            'catalogue_id.name',
            'product_id.default_code',
            'product_id.name',
            'line_uom_id.name',
            'min_qty',
            'unit_price',
            'rounding',
            'min_order_qty',
            'comment',
        ],
        'required_field_list': [
            'catalogue_id.name',
            'product_id.default_code',
            'line_uom_id.name',
            'min_qty',
            'unit_price',
        ],
        'ignore_field': [
            'product_id.name',
        ],
    },
    'supplier_catalogue_update': {
        'header_info': [
            'name',
            'partner_id',
            'currency_id',
            'period_from',
            'period_to',
        ],
        'header_list': [
            'product_id.default_code',
            'product_id.name',
            'product_code',
            'line_uom_id.name',
            'min_qty',
            'unit_price',
            'rounding',
            'min_order_qty',
            'comment',
        ],
        'required_field_list': [
            'product_id.default_code',
            'line_uom_id.name',
            'min_qty',
            'unit_price',
        ],
        'ignore_field': [
            'product_id.name',
        ],
        'custom_field_name': {
            'partner_id': 'Partner Name',
            'product_id.default_code': 'Product Code',
            'product_id.name': 'Product Description',
            'line_uom_id.name': 'UoM',
            'min_order_qty': 'Min. Order Qty.',
        },
    },

    # FINANCE
    'gl_accounts': {
        'header_list': [
            'user_type.name',
            'accrual_account',
            'activation_date',
            'code',
            'default_destination_id.id',
            'inactivation_date',
            'type',
            'name',
            'note',
            'type_for_register',
            'reconcile',
            'parent_id.code',
            'is_not_hq_correctible',
            'shrink_entries_for_hq',
            'currency_revaluation',
        ],
        'required_field_list': [
            'user_type.name',
            'activation_date',
            'code',
            'type',
            'name',
            'type_for_register',
        ],
    },
    'gl_journals': {
        'header_list': [
            'code',
            'currency.name',
            'default_credit_account_id.code',
            'default_debit_account_id.code',
            'name',
            'type',
            'analytic_journal_id.name',
        ],
        'required_field_list': [
            'code',
            'name',
            'type',
            'analytic_journal_id.name',
        ],
    },
    'funding_pools': {
        'header_list': [
            'code',
            'name',
            'parent_id.code',
            'type',
            'date_start',
            'date',  # "inactive from"
            'cost_center_ids',
            'tuple_destination_account_ids',
            'instance_id.code',
            'allow_all_cc_with_fp',
            'fp_account_ids',
        ],
        'required_field_list': [
            'name',
            'code',
            'parent_id.code',
            'date_start',
        ],
    },
    'cost_centers': {
        'header_list': [
            'code',
            'name',
            'parent_id.code',
            'type',
            'date_start',
            'date',  # "inactive from"
            'top_prop_instance',
            'is_target_cc_instance_ids',
            'top_cc_instance_ids',
            'po_fo_cc_instance_ids',
        ],
        'required_field_list': [
            'name',
            'code',
            'parent_id.code',
            'date_start',
        ],
    },
    'cost_centers_update': {
        'header_list': [
            'code',
            'name',
            'parent_id.code',
            'type',
            'date_start',
            'date',  # "inactive from"
            'top_prop_instance',
            'is_target_cc_instance_ids',
            'top_cc_instance_ids',
            'po_fo_cc_instance_ids',
        ],
        'required_field_list': [
            'code',
        ],
    },
    'destinations': {
        'header_list': [
            'code',
            'name',
            'parent_id.code',
            'type',
            'date_start',
            'date',  # "inactive from"
            'dest_cc_link_ids',
            'dest_cc_link_active_from',
            'dest_cc_link_inactive_from',
            'destination_ids',
            'allow_all_cc',
        ],
        'required_field_list': [
            'name',
            'code',
            'parent_id.code',
            'type',
            'date_start',
        ],
    },
    'free1': {
        'header_list': [
            'name',
            'code',
            'parent_id.code',
            'type',
            'date_start',
            'date',  # "inactive from"
        ],
        'required_field_list': [
            'name',
            'code',
            'parent_id.code',
            'date_start',
        ],
    },
    'free2': {
        'header_list': [
            'name',
            'code',
            'parent_id.code',
            'type',
            'date_start',
            'date',  # "inactive from"
        ],
        'required_field_list': [
            'name',
            'code',
            'parent_id.code',
            'date_start',
        ],
    },
    'analytic_journals': {
        'header_list': [
            'active',
            'code',
            'name',
            'type',
        ],
        'required_field_list': [
            'code',
            'name',
            'type',
        ],
    },
    'employees': {
        'header_list': [
            'name',
            'identification_id',
            'active',
            'contract_end_date',
        ],
        'required_field_list': [
            'name',
            'identification_id',
        ],
        'hide_export': True,
    },
    'hq_entries': {
        'header_list': [
            'name',
            'ref',
            'document_date',
            'date',
            'account_id',
            'partner_txt',
            'amount',
            'currency_id.name',
            'destination_id',
            'cost_center_id',
            'analytic_id',
            'free_1_id',
            'free_2_id',
        ],
        'required_field_list': [
            'name',
            'account_id',
            'currency_id.name',
            'destination_id',
            'analytic_id',
        ],
        'csv_button': True,
        'hide_export': True,
    },
    'currency_rate': {
        'header_list': [
            'name',
            'currency_id.name',
            'rate',
        ],
        'required_field_list': [
            'name',
            'rate',
            'currency_id.name',
        ],
    },
    'budget': {
        'header_list': [],
        'required_field_list': [],
        'csv_button': True,
        'hide_export': True,
    },


    # NON FUNCTIONNAL
    'user_groups': {
        'header_list': [
            'name',
        ],
        'required_field_list': [
            'name',
        ],
    },
    'user_access': {
        'header_list': [
        ],
        'required_field_list': [
        ],
        'hide_download_template': True,
        'hide_download_3_entries': True,
    },
    'record_rules': {
        'header_list': [
            'name',
            'model_id.model',
            'groups',
            'domain_force',
            'perm_read',
            'perm_create',
            'perm_unlink',
            'perm_write',
        ],
        'required_field_list': [
            'model_id.model',
            'name',
        ],
    },
    'access_control_list': {
        'header_list': [
            'name',
            'group_id.name',
            'perm_create',
            'perm_unlink',
            'perm_read',
            'perm_write',
            'model_id.id',
        ],
        'required_field_list': [
            'name',
            'model_id.id',
        ],
    },
    'access_control_list_empty': {
        'header_list': [
            'name',
            'group_id.name',
            'perm_create',
            'perm_unlink',
            'perm_read',
            'perm_write',
            'model_id.id',
        ],
        'required_field_list': [],
        'hide_download_template': True,
        'hide_download_3_entries': True,
        'display_file_import': False,
    },
    'field_access_rules': {
        'header_list': [
            'active',
            'comment',
            'domain_text',
            'group_ids',
            'instance_level',
            'name',
            'model_id.model',
            'status',
        ],
        'required_field_list': [
            'instance_level',
            'model_id.model',
            'name',
        ],
    },
    'field_access_rule_lines': {
        'header_list': [
            'field_access_rule.name',
            'field.id',
            'field.name',
            'field.field_description',
            'write_access',
        ],
        'required_field_list': [
            'field_access_rule.name',
            'field.id',
        ],
        'ignore_field': [
            'field.field_description',
            'field.name',
        ],
    },
    'button_access_rules': {
        'header_list': [
            'name',
            'label',
            'active',
            'comment',
            'id',
            'group_ids',
            'model_id.model',
            'view_id.name',
            'bar_type',
            'create_date',
        ],
        'required_field_list': [
            'id',
        ],
        'ignore_field': [
            'name',
            'label',
            'model_id.model',
            'view_id.name',
            'create_date',
        ],
    },
    'window_actions': {
        'header_list': [
            'name',
            'res_model',
            'view_type',
            'view_id.name',
            'groups_id',
            'id',
        ],
        'required_field_list': [
            'id',
        ],
        'ignore_field': [
            'name',
            'res_model',
            'view_type',
            'view_id.name',
        ]
    },
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
