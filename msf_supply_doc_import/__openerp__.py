# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF, Smile. All Rights Reserved
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
    "name" : "Import Files in Excel Format",
    "version" : "0.1",
    "description" : "This module enables to import file in xls format",
    "author" : "MSF - TeMPO Consulting - Smile",
    "category" : "Sale",
    "depends" : ["sale", "purchase", "tender_flow", "msf_supply_doc_export", "spreadsheet_xml"],
    "init_xml" : [],
    "update_xml" : [
        'view/sale_order_import_lines_view.xml',
        'view/internal_request_import_line_view.xml',
        'view/tender_import_line_view.xml',
        'view/purchase_order_import_line_view.xml',
        
        'data/msf_supply_doc_import_data.xml',
    ],
    "demo_xml" : [],
    "test": [],
    "installable": True,
    "active": False
}
