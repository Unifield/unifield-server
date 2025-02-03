# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
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
    "name" : "Export Files in Excel Format",
    "version" : "0.1",
    "description" : "This module enables to export file in xls format",
    "author" : "MSF - TeMPO Consulting",
    "category" : "Sale",
    "depends" : ["sale", "purchase","specific_rules"],
    "init_xml" : [],
    "update_xml" : [
        'msf_export_report.xml',
        'wizard/po_follow_up_view.xml',
        'wizard/wizard_pick_import.xml',
        'po_follow_up_menu.xml',
        'report/po_follow_up_report.xml',
        'wizard/supplier_performance_wizard_view.xml',
        'report/supplier_performance_report_view.xml',
        'wizard/wizard_out_import.xml',
    ],
    "demo_xml" : [],
    "test": [],
    "installable": True,
    "active": False
}
