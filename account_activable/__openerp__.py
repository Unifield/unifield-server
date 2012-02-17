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
    "name": "Chart of Accounts for MSF",
    "version": "1.0",
    "depends": ["account", "account_chart"],
    "author" : "MSF, TeMPO Consulting",
    "developer": "Matthieu Dietrich",
    "category": "General/Standard",
    "description": """
    This module changes the view and adds a searchable "Active" attribute.
    
    """,
    "init_xml": [
        'data/account_type.xml',
    ],
    'update_xml': [
        'account_activable_view.xml',
        'wizard/account_chart_activable_view.xml',
    ],
    'test': [
        'test/account_activable.yml'
    ],
    'demo_xml': [],
    'installable': True,
    'active': False,
#    'certificate': 'certificate',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
