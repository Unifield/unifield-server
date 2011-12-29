# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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
    "name" : "Analytic Account for MSF",
    "version": "1.1",
    "author" : "MSF - TeMPO Consulting",
    "category" : "Generic Modules/Projects & Services",
    "depends" : ["analytic", "account", "account_override", "account_budget"],
    "description": """Module for defining analytic accounting object and commitment voucher.
    """,
    "init_xml" : [
        'data/analytic_account_data.xml',
    ],
    "update_xml": [
        'security/ir.model.access.csv',
        'analytic_account_view.xml',
        'analytic_line_view.xml',
        'wizard/account_analytic_chart_view.xml',
        'analytic_distribution_wizard_view.xml',
        'account_commitment_workflow.xml',
        'account_commitment_sequence.xml',
        'account_commitment_view.xml',
    ],
    'test': [
        'test/analytic_account_activable.yml',
    ],
    'demo_xml': [
    ],
    'installable': True,
    'active': False,
#    'certificate': 'certificate',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
