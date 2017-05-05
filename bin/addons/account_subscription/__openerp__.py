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
    "name": "Recurring Entries for MSF",
    "version": "1.0",
    "depends": ["analytic_distribution"],
    "author" : "MSF, TeMPO Consulting",
    "category": "General/Standard",
    "description": """
    This module adds analytic distribution and period checks to
    the standard behavior of recurring entries.
    Period checks are done in account_period_closing_level module.
    
    """,
    "init_xml": [],
    'update_xml': [
        'account_model_view.xml'
    ],
    "test": [
    ],
    'demo_xml': [],
    'installable': True,
    'active': False,
#    'certificate': 'certificate',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
