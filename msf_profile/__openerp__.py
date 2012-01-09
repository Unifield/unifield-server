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
        "base_report_designer",
        "msf_partner",
        "register_accounting",
        "analytic_distribution",
        "account_period_closing_level",
        "account_activable",
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
        "financing_contract",
        "object_query",
        "stock_forecast",
        "partner_modification",
        "account_invoice_split",
        "account_msf",
        "specific_locations",
        "reason_types_moves",
        "specific_rules",
        "msf_outgoing", # doit être installé après specific_rules
        "tender_flow",
        "consumption_calculation",
        "threshold_value",
        "analytic_distribution_invoice",
        "service_purchasing",
        "account_reconciliation",
        "vat_management",
        "analytic_distribution_supply",
        "account_mcdb",
        "out_step",
        "delivery_mechanism",
        "msf_tools",
        "transport_mgmt",
        "documents_done",
        "msf_budget",
    ],
    "update_xml": [
        "report.xml",
        "purchase_double_validation_workflow.xml",
    ],
    "demo_xml": [
    ],
    "test": [
        'test/unique_fields_views.yml',
        'test/inherited_views.yml',
    ],
    "installable": True,
    "active": False,
}
