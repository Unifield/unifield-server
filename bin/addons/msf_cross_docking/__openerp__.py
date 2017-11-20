# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF
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
    'name': 'MSF Cross Docking Management',
    'version': '1.0',
    'category': 'Stock',
    'author': 'MSF, TeMPO Consulting',
    'developer': 'Matthieu Choplin',
    'depends': ['purchase_msf', 'delivery_mechanism', 'stock', 'purchase_override', 'unifield_setup'],
    'description': '''
Cross Docking Management.
We enable the user to change the stock location (on input and output) to "cross docking":
- on the purchase order (see tab delivery and invoicing)
- on the incoming shipment (in the wizard when you click on "process", you can change the destination location)
- on the delivery orders, packing, prepacking (we add a button to change the source location)
- if you create a sale order with the option "make to order", the associated purchase order that you obtain when
you run the scheduler will have the option cross docking pre selected.
''',
    'init_xml': [],
    'update_xml': [
        'cross_docking_view.xml',
        'data/msf_cross_docking_data.xml',
    ],
    'test': [
    ],
    'installable': True,
    'active': False,
    #    'certificate': 'certificate',
}
