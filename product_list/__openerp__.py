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
    "name": "Product Lists and Sub-Lists",
    "version": "1.0",
    "depends": ["base", "product", "stock"],
    "author": "TeMPO Consulting, MSF",
    "website": "",
    "category": "Stock & Warehouse",
    "description": """
    This module aims to add a feature to allow users to predefine
    a list of products.
    """,
    "init_xml": [
    ],
    'update_xml': [
        'product_list_view.xml',
        'wizard/list_export_view.xml',
        'wizard/list_import_view.xml',
        'wizard/product_to_list_view.xml',
        'product_list_report.xml',
        'security/ir.model.access.csv',
    ],
    'demo_xml': [
    ],
    'test': [
        'test/data.yml',
        'test/import_list.yml',
    ],
    'installable': True,
    'active': False,
#    'certificate': 'certificate',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: