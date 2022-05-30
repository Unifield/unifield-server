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
    "name": "Fx Tables Management",
    "version": "1.0",
    "depends": ["res_currency_functional", "base"],
    "category": "General/Standard",
    "description": """
    This module aims to have other subsets of currencies, and have them available
    for financing contracts and budgets.
    
    """,
    "init_xml": [
    ],
    'update_xml': [
        'security/ir.model.access.csv',
        'res_currency_view.xml',
        'res_currency_table_report.xml',
        'wizard/wizard_report_rates_table_view.xml',
        'wizard/wizard_report_currency_table_view.xml',
    ],
    'test': [
    ],
    'demo_xml': [],
    'installable': True,
    'active': False,
    #    'certificate': 'certificate',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
