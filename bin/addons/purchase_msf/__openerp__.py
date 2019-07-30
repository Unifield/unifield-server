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
    'name': 'Purchase Management modified by MSF',
    'version': '0.1',
    'category': 'Generic Modules/Sales & Purchases',
    'description': """
    Purchase module is for generating a purchase order for purchase of goods from a supplier.
    A supplier invoice is created for the particular order placed
    Dashboard for purchase management that includes:
    * Current Purchase Orders
    * Draft Purchase Orders
    * Graph for quantity and amount per month    

    """,
    'author': 'MSF, TeMPO Consulting',
    'developer': 'pam',
    'website': 'unifield.org',
    'depends': ['purchase','msf_partner'],
    'init_xml' : [ ],
    'demo_xml' : [ ],
    'test': [
    ],
    'update_xml' : [
        'security/ir.model.access.csv',
    ],
    'installable': True,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
