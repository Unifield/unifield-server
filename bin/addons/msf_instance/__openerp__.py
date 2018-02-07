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
    "name" : "MSF Proprietary Instance",
    "version": "1.1",
    "author" : "MSF, TeMPO Consulting",
    "developer": "Matthieu Dietrich",
    "category" : "Generic Modules/Projects & Services",
    # Old account_msf was included in some modules as account_override and msf_partner and register accounting. So we include register_accounting module as last needed depandancy
    "depends" : ["register_accounting", "res_currency_functional"],
    "description": """Module for defining proprietary instances, their informations
    """,
    "init_xml" : [],
    "update_xml": [
        'msf_instance_installer_view.xml',
        'security/ir.model.access.csv',
        'msf_instance_view.xml',
        'msf_instance_company_configuration.xml',
        'wizard/wizard_add_cost_centers_view.xml',
        'wizard/account_chart_view.xml',
        'wizard/account_analytic_chart_view.xml',
        'data/remote_backup.xml',
    ],
    "additional_xml": [
        'data/instance_data.xml',
    ],
    'demo_xml': [
    ],
    'installable': True,
    'active': False,
#    'certificate': 'certificate',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
