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
    "name": "MSF Delete Button",
    "version": "1.0",
    "depends": [
                "stock",
                "purchase",
                "tender_flow",
                "procurement_request",
                "useability_dashboard_and_menu",
                ],
    "author": "MSF, TeMPO Consulting",
    "website": "",
    "category": "Specific Modules",
    "description": """
        Hide delete buttons according to the state.
    """,
    "init_xml": [
    ],
    'update_xml': ['view/picking_view.xml',
                   'view/purchase_view.xml',
                   'view/sale_view.xml',
                   'view/tender_view.xml',
                   'view/product_view.xml',
                   'view/shortcut_data.xml',
                   ],
    'demo_xml': [
    ],
    'test': [
             ],
    'installable': True,
    'active': False,
}

