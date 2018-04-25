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
        "account_period_closing_level",
        # As register_accounting has account_override and purchase_override dependancies, no need to add them after that
        #"purchase_override",
        "sale",
        "stock_override",
        "msf_order_date",
        "purchase_compare_rfq",
        "purchase_msf",
        "product_asset",
        "order_nomenclature",
        "product_nomenclature",
        "order_types",
        "res_currency_functional",
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
        "security/ir.model.access.csv",
        "report.xml",
        "usability.xml",
        "user_access_configurator_view.xml",
        "unifield_version_view.xml",
        'view/group_view.xml',
        'view/email_configuration_view.xml',
        "data/patches.xml",
        'view/deleted_object_view.xml',
        "view/boad_accounting_view.xml",
        'view/communication_config.xml',
        'view/open_update_view.xml',
    ],
    "demo_xml": [
    ],
    "function": [
        ('user.access.configurator', 'do_update_after_module_install'),
        ('patch.scripts', 'launch_patch_scripts'),
        #        ('ir.model.data', 'us_254_fix_reconcile'),
        #        ('ir.model.data', 'us_268_fix_seq'),
    ],
    # add this to function to apply patch13 AND REMOVE export_import_lang FROM depends ('ir.model.data', 'patch13_install_export_import_lang')],
    "test": [
    ],
    "installable": True,
    "active": False,
}
