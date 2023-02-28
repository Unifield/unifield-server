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
    "name" : "Purchase override",
    "version" : "1.0",
    "author" : "TeMPO Consulting, MSF",
    "category": "Others",
    "description": """
        Add hooks to purchase class
    """,
    "website": "http://unifield.msf.org",
    "init_xml": [],
    "depends" : [
        "account_override",
        "purchase",
        "stock_override",
        "stock",
        "purchase_double_validation",
        "reason_types_moves",
        "unifield_setup",
        "msf_tools",
    ],
    "update_xml": [
        "purchase_view.xml",
        "purchase_report.xml",
        "wizard/split_order_line_view.xml",
        "wizard/order_change_currency_view.xml",
        "security/ir.model.access.csv",
        "purchase_sequence.xml",
        "wizard/purchase_order_group_view.xml",
    ],
    "demo_xml": [
    ],
    "test": [
    ],
    "installable": True,
    "active": False,
}
