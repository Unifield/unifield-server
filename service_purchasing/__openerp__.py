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
    "name" : "Service Purchasing",
    "version" : "0.1",
    "author" : "MSF, TeMPO Consulting",
    "developer": "pam",
    "category" : "Generic Modules/Inventory Control",
    "description": """
        Add the capability for a product to be a service with reception in %UOM
        """,
    'website': 'http://www.unifield.org',
    'init_xml': [],
    "depends" : ["stock", "product_attributes", "purchase_override", "order_types", "msf_outgoing",],
    'update_xml': ['service_purchasing_view.xml',
                   ],
    "demo_xml": [],
    'test': ['test/data.yml',
             'test/service_purchasing.yml',
             'test/service_purchasing-0.yml',
             'test/service_purchasing-1.yml',
             'test/service_purchasing-2.yml',
             'test/service_purchasing-3.yml',
             'test/service_purchasing-4.yml',
             'test/service_purchasing-5.yml',
             'test/service_purchasing-6.yml',
             'test/service_purchasing-7.yml',
             'test/check_stock_move.yml',
             ],
    'installable': True,
}
