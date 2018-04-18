# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting
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
    "name" : "Stock override",
    "version" : "1.0",
    "author" : "MSF, TeMPO Consulting",
    "description" : """
    Add hook to stock class and wizard
    """,
    "website": "http://unifield.msf.org",
    "depends" : ["stock", "reason_types_moves"],
    "category" : "Generic Modules/Inventory Control",
    "init_xml" : [],
    "demo_xml" : [],
    "update_xml" : [
        "stock_data.xml",
        "stock_view.xml",
        "stock_workflow.xml",
        "procurement_view.xml",
        "destruction_report.xml",
        "stock_report.xml",
        "report/report_destruction_location_view.xml",
        "report/report_stock_move_view.xml",
        "wizard/stock_analyze_view_view.xml",
        "security/ir.model.access.csv",
        "wizard/stock_partial_move_view.xml",
        "wizard/change_dest_location_view.xml",
        "wizard/stock_card_view.xml",
    ],
    'installable': True,
    'active': False,
}
