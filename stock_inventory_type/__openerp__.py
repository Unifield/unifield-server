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
    "name" : "Stock Adjustment/Move Report",
    "version" : "1.0",
    "author" : "TeMPO Consulting, MSF",
    "category": "Inventory Control",
    "description": """
        This module aims to help you to determine the type \
    of your inventory adjustment and to search stock move \
    by type of adjustment.
    """,
    "website": "http://unifield.msf.org",
    "init_xml": [
    ],
    "depends" : [
        "stock",
        "reason_types_moves",
    ],
    "update_xml": [
        "stock_view.xml",
        "stock_data.xml",
        "security/ir.model.access.csv",
    ],
    "demo_xml": [
    ],
    "test": [
        "test/adjustment_type.yml",
    ],
    "installable": True,
    "active": False,
}
