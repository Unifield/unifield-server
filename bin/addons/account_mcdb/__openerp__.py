#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
    "name" : "Multi-Criteria Data Browser",
    "version" : "0.1",
    "description" : "Ease data searching in Analytic Journal Items and Journal Items",
    "author" : "TeMPO Consulting, MSF",
    "category" : "Accounting",
    "depends" : ["account", "register_accounting", "res_currency_tables", "analytic_distribution", "report_webkit", "msf_instance"],
    "init_xml" : [],
    "update_xml" : [
        'wizard/output_currency_for_export_view.xml',
        'account_period_state_view.xml',
        'account_mcdb_view.xml',
        'account_view.xml',
        'account_mcdb_export_view.xml',
        'account_mcdb_report.xml',
        'account_mcdb_data.xml',
        "sync_query_view.xml",
    ],
    "demo_xml" : [],
    "test": [],
    "installable": True,
    "active": False
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
