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
    "name" : "MSF Locations configuration",
    "version" : "1.0",
    "author" : "TeMPO Consulting/MSF",
    "description" : """
    Allow users with specific rights to configure
    optionnal stock locations
    """,
    "website": "http://unifield.msf.org",
    "category" : "Generic Modules/Warehouse",
    "depends" : [
        'stock',
        'product_nomenclature',
        'msf_outgoing',
        'stock_override',
        'msf_cross_docking',
    ],
    "init_xml" : [
    ],
    "update_xml" : [
        'stock_configuration_view.xml',
        'msf_location_data.xml',
        'installer/configurable_location_view.xml',
    ],
    "demo_xml" : [
    ],
    'test': [
    ],
    'installable': True,
    'active': False,
}
