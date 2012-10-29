# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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
    'name': 'MSF Product Attributes',
    'version': '1.0',
    'category': 'Generic Modules',
    'author': 'MSF, TeMPO consulting',
    'developer': 'Matthieu Dietrich',
    'description': """
        This module displays more fields for future sprints in the Products form view.
    """,
    'depends': ['product_expiry', 'product_manufacturer', 'sale', 'product_list', 'purchase'],
    'data': ['product_sequence.xml'],
    'init_xml': [
        'security/ir.model.access.csv',
        'data/product_section_code.xml',
        'data/product_supply_source.xml',
        'data/product_justification_code.xml',
    ],
    'update_xml': [
        'product_attributes_view.xml',
    ],
    'demo_xml': [
        'product_remove_demo.xml',
    ],
    'installable': True,
    'active': False,
#    'certificate': 'certificate',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
