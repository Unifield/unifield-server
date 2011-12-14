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
    "name": "Batch Recall",
    "version": "1.0",
    "depends": ["base", "stock_move_tracking", "product_expiry", "specific_rules"],
    "author": "TeMPO Consulting, MSF",
    "website": "",
    "category": "Warehouse",
    "description": """
    This module adds a wizard to see a specific product/bacth/expired date
    in stock.
    It also modifies the stock inventory view to add expired date.
    """,
    "init_xml": [
    ],
    'update_xml': [
        'stock_view.xml',
        'security/ir.model.access.csv',
    ],
    'demo_xml': [
    ],
    'installable': True,
    'active': False,
#    'certificate': 'certificate',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: