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
    "name": "Transport management",
    "version": "1.0",
    "depends": [
        "sale",
        "purchase",
        "stock",
        "product_attributes",
        "product_asset",
        "product_nomenclature",
        "tender_flow",
        "purchase_followup",
        "sales_followup",
        "supplier_catalogue",
        "procurement_request",
        "procurement",
        "mission_stock",
    ],
    "author": "TeMPO Consulting, MSF",
    "website": "",
    "category": "Useability",
    "description": """
    This module aims at redefining the dashboards and menus for more useability.
    """,
    "init_xml": [
    ],
    'update_xml': [
        "menu/main_menu.xml",
        "menu/supply_config_menu.xml",
        "menu/purchase_menu.xml",
        "menu/warehouse_menu.xml",
        "menu/partner_menu.xml",
        "menu/sale_menu.xml",
        "menu/hidden_menu.xml",
        "menu/accounting_menu.xml",

        "view/sale_view.xml",
        "view/shop_view.xml",

        "dashboard/board_purchase_view.xml",
        "dashboard/board_sale_view.xml",
        "dashboard/board_warehouse_view.xml",

        "view/signature_view.xml",
        'wizard/signature_follow_up_search_wizard.xml',
    ],
    'demo_xml': [
    ],
    'test': [
    ],
    'installable': True,
    'active': False,
}
