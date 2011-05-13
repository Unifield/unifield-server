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
    ],
    "depends" : [
        "msf_partner",
        "procurement_list",
        "register_accounting",
        "stock_inventory_type",
        "analytic_plan_tree",
        "account_period_closing_level",
        "account_activable",  
        "msf_order_date",
        "purchase_compare_rfq",
        "account_budget_definition",
        "purchase_msf",
	    "product_asset",
	    "order_nomenclature",
	    "product_nomenclature",
        "order_types",
        "res_currency_functional",
	    "sourcing",
        "stock_move_tracking",
        "stock_batch_recall",
        "procurement_cycle",
        "procurement_auto",
        "product_attributes",
        "procurement_report",
    ],
    "update_xml": [
    ],
    "demo_xml": [
    ],
    "test": [
        'test/inherited_views.yml',
    ],
    "installable": True,
    "active": False,
}
