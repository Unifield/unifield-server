# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF
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
{
    "name" : "MSF Modules",
    "version" : "1.0",
    "author" : "TeMPO Consulting, MSF",
    "category": "Others",
    "description": """
        Modules for Unifield
    """,
    "website": "http://unifield.msf.org",
    "init_xml": [
        "data.xml",
    ],
    "depends" : [
        "msf_audittrail",
        "msf_tools",
        "base_report_designer",
        "msf_partner",
        "analytic_distribution",
        "register_accounting",
        "analytic_distribution",
        "account_period_closing_level",
        "account_activable",
        "purchase_override",
        "sale_override",
        "stock_override",
        "msf_order_date",
        "purchase_compare_rfq",
        "purchase_msf",
        "product_asset",
        "order_nomenclature",
        "product_nomenclature",
        "order_types",
        "res_currency_functional",
        "account_msf",
        "account_corrections",
        "order_line_number",
        "sourcing",
        "stock_move_tracking",
        "stock_batch_recall",
        "procurement_cycle",
        "procurement_auto",
        "product_list",
        "product_attributes",
        "procurement_report",
        "msf_printed_documents",
        "procurement_request",
        "import_data",
        "sales_followup",
        "purchase_followup",
        "financing_contract",
        "object_query",
        "stock_forecast",
        "partner_modification",
        "specific_locations",
        "reason_types_moves",
        "specific_rules",
        "msf_outgoing", # doit être installé après specific_rules
        "tender_flow",
        "consumption_calculation",
        "threshold_value",
        "account_hq_entries",
        "msf_config_locations",
        "service_purchasing",
        "account_reconciliation",
        "vat_management",
        "analytic_distribution_supply",
        "account_mcdb",
        "out_step",
        "delivery_mechanism",
        "transport_mgmt",
        "documents_done",
        "msf_budget",
        "account_subscription",
        "msf_homere_interface",
        "kit",
        "msf_accrual",
        "purchase_allocation_report",
        "supplier_catalogue",
        "msf_cross_docking",
        "mission_stock",
        "msf_instance",
        "return_claim",
        "msf_processes",
        "useability_dashboard_and_menu",
        "msf_custom_settings",
        "delete_button",
        "spreadsheet_xml",
        "msf_supply_doc_export",
        "msf_doc_import",
        "mission_stock_cron",
        "report_webkit_override",
        "export_import_lang",
        "msf_button_access_rights",
        "msf_field_access_rights",
        "vertical_integration",
        "msf_currency_revaluation",
    ],
    "update_xml": [
        "report.xml",
        "purchase_double_validation_workflow.xml",
        "usability.xml",
        "user_access_configurator_view.xml",
        'view/group_view.xml',
    ],
    "demo_xml": [
    ],
    "function": [('user.access.configurator', 'do_update_after_module_install')],
# add this to function to apply patch13 AND REMOVE export_import_lang FROM depends ('ir.model.data', 'patch13_install_export_import_lang')],
    "test": [
        'test/unique_fields_views.yml',
        'test/inherited_views.yml',
        'test/user_rights.yml',
# the tests below are for the module msf_doc_import (written here because they need the translation)
#        'test/data.yml',
#        'test/fr_import_ir.yml',
#        'test/fr_import_po.yml',
#        'test/fr_import_so.yml',
#        'test/fr_import_tender.yml',
    ],
    "installable": True,
    "active": False,
}
