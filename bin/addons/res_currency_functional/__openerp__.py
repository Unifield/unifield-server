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
    "name": "Multi-Currency Management",
    "version": "1.0",
    "depends": ["account_journal", "finance", "analytic_distribution", "purchase", "register_accounting"],
    "category": "General/Standard",
    "description": """
    This module aims to only use a subset of currencies, and have them available
    for each accounting entry.

    """,
    "init_xml": [
        'data/currency_data.xml',
    ],
    'update_xml': [
        'res_currency_functional_view.xml',
        'account_move_line_view.xml',
        'account_bank_statement_view.xml',
    ],
    'test': [
    ],
    'demo_xml': [],
    'installable': True,
    'active': False,
    #    'certificate': 'certificate',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
