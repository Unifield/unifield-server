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
    "name" : "Account reconciliation wizard",
    "version" : "0.1",
    "description" : "Default reconciliation wizard adaptation for MSF",
    "author" : "MSF, TeMPO Consulting",
    "category" : "Accounting",
    "depends" : ["base", "finance", "res_currency_functional", "register_accounting", "msf_homere_interface"], # register_accounting for third parties and partner_txt field in account_move_line
    #+ res_currency_functional for credit_currency and debit_currency fields (and to redefine some functions)
    #+ account_override module add 'is_addendum_line' attribute that permits to avoid corrections on this kind of line.
    "init_xml" : [
    ],
    "update_xml" : [
        "wizard/account_reconcile_view.xml",
    ],
    "demo_xml" : [],
    "test": [],
    "installable": True,
    "active": False
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
