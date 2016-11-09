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
    "name" : "MSF Chart Of Account",
    "version" : "0.1",
    "description" : "This permits to have a chart of account for Unifield Project at MSF",
    "author" : "TeMPO Consulting, MSF",
    "category" : "Localisation/Account Charts",
    # As register_accounting has finance as dependancy which have account_override as dependancy (in which account_activable have been included): no need of account_activable
    "depends" : ["base", "register_accounting", "account_journal", "msf_instance"],
    "init_xml": [],
    "update_xml" : [
        "data/account.xml",
        "data/account_data.xml",
        "msf_chart_of_account_installer.xml",
    ],
    "demo_xml" : [],
    "test": [],
    "installable": True,
    "active": False
}


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
