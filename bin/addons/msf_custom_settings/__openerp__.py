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
    'name': 'MSF Custom Settings',
    'version': '1.0',
    'category': 'Stock',
    'author': 'MSF, TeMPO Consulting',
    'developer': 'Matthieu Choplin',
    'depends': ['msf_outgoing',
                'delivery_mechanism',
                'sale',
                'purchase',
                'stock',
                'consumption_calculation',
                'msf_cross_docking',
                'procurement',
                'product',
                'msf_doc_import',
                'msf_supply_doc_export',
                'tender_flow',
                ],
    'description': '''
    ''',
    'init_xml': [],
    'update_xml': [
        'view/stock_view.xml',
        'view/delivery_mecanism_view.xml',
        'view/batch_view.xml',
        'view/physical_inventories_view.xml',
        'view/last_product_invetories_view.xml',
        'view/warehouse_view.xml',
        'view/uom_categories_view.xml',
        'view/units_of_measure_view.xml',
        'view/pack_types_view.xml',
    ],
    'test': [
    ],
    'installable': True,
    'active': False,
    #    'certificate': 'certificate',
}
