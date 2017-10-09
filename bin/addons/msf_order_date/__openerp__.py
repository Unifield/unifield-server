# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting
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
    "name": "MSF Order dates",
    "version": "3.0",
    "depends": ["base",
                "purchase",
                "account",
                "stock_override",
                "sale",
                "purchase_override",
                "partner_modification",
                "msf_tools",
                ],
    "author": "TeMPO Consulting, MSF",
    "website": "",
    "category": "Specific Modules",
    "description": """
        This module aims at defining the dates of orders (purchase and sales orders).
    """,
    "init_xml": [
    ],
    'update_xml': [
        'security/msf_order_date_groups.xml',
        'security/ir.model.access.csv',
        'order_dates_view.xml',
        'wizard/update_lines_view.xml',
    ],
    'demo_xml': [
    ],
    'test': [
    ],
    'installable': True,
    'active': False,
}
