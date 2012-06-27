# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF, Smile
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
    'name': 'MSF Custom Settings',
    'version': '1.0',
    'category': 'Stock',
    'author': 'MSF, TeMPO Consulting, Smile',
    'developer': 'Matthieu Choplin',
    'depends': ['base'],
    'description': '''
    ''',
    'init_xml': [],
    'update_xml': [
        'view/base.xml',
        'view/picking_in_view.xml',
        'view/purchase_view.xml',
        'view/sale_view.xml',
    ],
    'test': [
    ],
    'installable': True,
    'active': False,
#    'certificate': 'certificate',
}
