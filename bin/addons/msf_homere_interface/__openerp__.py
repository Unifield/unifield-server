#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
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
    "name" : "Homere Interface",
    "version" : "0.1",
    "description" : "Homere interface with OpenERP",
    "author" : "MSF - TeMPO Consulting",
    "category" : "Human Resources",
    "depends" : ["base", "finance", "hr", "analytic_distribution", "spreadsheet_xml"],
    "init_xml" : [],
    "update_xml" : [
        'security/ir.model.access.csv',
        'hr_view.xml',
        'hr_payroll_view.xml',
        'hr_payroll_wizard.xml',
    ],
    "demo_xml" : [],
    "test": [],
    "installable": True,
    "active": False
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
