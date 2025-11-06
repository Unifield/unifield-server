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
        "service_purchasing",
        "purchase_override",
        "res_currency_functional",
        "product_nomenclature",
        "msf_outgoing",
        "msf_partner",
        "msf_order_date",
    ],
    "author": "TeMPO Consulting, MSF",
    "website": "",
    "category": "Sales & Purchase",
    "description": """
    This module aims at implementing the transport cost in Purchase and Sale orders.
    """,
    "init_xml": [
    ],
    'update_xml': [
        'purchase_view.xml',
        'sale_view.xml',
        'product_view.xml',
        'stock_view.xml',
        'transport_data.xml',
        'transport_view.xml',
        'report/intl_transport_view.xml',
        'report/local_transport_view.xml',
        'security/ir.model.access.csv',
    ],
    'demo_xml': [
    ],
    'test': [
    ],
    'installable': True,
    'active': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
