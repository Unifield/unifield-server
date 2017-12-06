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
    "name" : "Analytic Distribution on Purchase Order",
    "version" : "1.0",
    "description" : "This permits to have analytic distribution wizard on a Purchase Order",
    "author" : "TeMPO Consulting, MSF",
    "category" : "Tools",
    "depends" : ["base", "account_journal", "analytic_distribution", "purchase_override", "stock", "res_currency_functional"],
    "init_xml" : [],
    "update_xml" : [
        "account_commitment_view.xml",
    ],
    "demo_xml" : [],
    "test": [
    ],
    "installable": True,
    "active": False
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
