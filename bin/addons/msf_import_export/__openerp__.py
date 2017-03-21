# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2017 MSF, TeMPO Consulting
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
    "name": "MSF Import Export",
    "version": "1.0",
    "depends": ["base",
                "product",
                ],
    "author": "MSF, TeMPO Consulting",
    "website": "",
    "category": "Specific Modules",
    "description": """
        Interface for import/export
    """,
    "init_xml": [
    ],
    'update_xml': [
        'views/msf_import_export_view.xml',
    ],
    'demo_xml': [
    ],
    'test': [# tests should be performed in base classes to avoid cyclic dependencies
    ],
    'installable': True,
    'active': False,
}

