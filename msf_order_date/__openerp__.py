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
    "name": "MSF Order dates",
    "version": "1.0",
    "depends": [
                "base",
                "sale",
                "purchase",
                "account",
                "stock_override",
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
    ],
    'demo_xml': [
    ],
    'test': [
        'test/create_data.yml',
        'test/purchase_dates.yml',
        'test/sale_dates.yml',
    ],
    'installable': True,
    'active': False,
#    'certificate': 'certificate',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
