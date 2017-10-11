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
    "name": "Order Types",
    "version": "1.0",
    "depends": [
        "sale", 
        "purchase", 
        "msf_partner",
        "msf_order_date", 
        "stock",
        "product_expiry",
        "purchase_double_validation",
        "purchase_override"],
    "author": "TeMPO Consulting, MSF",
    "website": "",
    "category": "Sales & Purchase",
    "description": """
    This module aims at differentiating orders. The goal is to split orders into several types that
    will be used for the mapping of different workflows.
    """,
    "init_xml": [
    ],
    'update_xml': [
        'order_types_report.xml',
        'wizard/stock_certificate_picking_view.xml',
        'wizard/stock_print_certificate_view.xml',
        'wizard/stock_picking_not_available_view.xml',
        'stock_view.xml',
        'order_types_data.xml',
    ],
    'demo_xml': [
    ],
    'test': [
    ],
    'installable': True,
    'active': False,
    #    'certificate': 'certificate',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
