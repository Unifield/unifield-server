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
    "name" : "Sale override",
    "version" : "1.0",
    "author" : "TeMPO Consulting, MSF",
    "category": "Others",
    "description": """
        Add hooks to sale class
    """,
    "website": "http://unifield.msf.org",
    "init_xml": [],
    "depends" : [
        "sale",
        "stock_override",
    ],
    "update_xml": [
        "sale_view.xml",
        "sale_workflow.xml",
        "wizard/split_order_line_view.xml",
        "wizard/order_change_currency_view.xml",
        "sale_sequence.xml",
        "report/sale_report_view.xml",
    ],
    "demo_xml": [
    ],
    "test": [
        "test/data.yml",
        "test/sale_test.yml",
        "test/split_line.yml",
        "test/deactivate_product_valid_fo.yml",
        "test/deactivate_product_validate_fo.yml",
    ],
    "installable": True,
    "active": False,
}
