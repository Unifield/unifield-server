#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Olivier DOSSMANN
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
    "name" : "Accounting Corrections",
    "version" : "1.0",
    "description" : """
        Permits some corrections from Journal Items.
    """,
    "author" : "TeMPO Consulting, MSF",
    'website': 'http://tempo-consulting.fr',
    "category" : "Tools",
    # As account_msf was included in account_override, msf_partner and register_accounting, we just need register accounting
    # Register_accounting depends on finance, and finance on account_override and account_override on account. So account and finance module are not needed as dependancies.
    "depends" : ["base", 'res_currency_functional', 'analytic_distribution', 'account_journal', 'register_accounting'],
    "init_xml" : [],
    "update_xml" : [
        'account_view.xml',
        'account_wizard_view.xml',
    ],
    "demo_xml" : [],
    "test": [
    ],
    "installable": True,
    "active": False
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
