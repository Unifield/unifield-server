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
    "name": "Account Period for MSF",
    "version": "1.0",
    "depends": ["account_subscription"],
    "author" : "MSF, TeMPO Consulting",
    "developer": "Matthieu Dietrich",
    "category": "General/Standard",
    "description": """
    This module adds states to the fiscal years and accounting periods,
    with a new wizard to create tem automatically.
    
    """,
    "init_xml": [],
    'update_xml': [
        'account_period_closing_level_view.xml',
        'wizard/account_period_create_view.xml',
        'wizard/year_end_closing.xml',
        'account_year_end_closing.xml',
    ],
    "test": [
    ],
    'demo_xml': [
        'test/account_period_demo.xml'
    ],
    'installable': True,
    'active': False,
    #    'certificate': 'certificate',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
