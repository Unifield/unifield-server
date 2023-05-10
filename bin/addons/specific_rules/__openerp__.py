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
    "name" : "Specific Rules",
    "version" : "0.1",
    "author" : "MSF, TeMPO Consulting",
    "developer": "pam",
    "category" : "Generic Modules/Inventory Control",
    # depends on specific_locations because of view_picking_out_form -> stock_moves>form>location_id>quarantine domain
    # depends on reason_types_moves because of view_picking_form -> stock_moves>form>location_id>domain restriction
    "depends" : ["sale", "purchase", "stock", "procurement_cycle", "specific_locations", "reason_types_moves", "stock_override", "procurement_request"],
    "init_xml" : [],
    "demo_xml" : [],
    "description": """
    Specific Management Rules
    """,
    'update_xml': ['security/ir.model.access.csv',
                   'specific_rules_view.xml',
                   'stock_view.xml',
                   'report/report_stock_inventory_view.xml',
                   'unconsistent_stock_report_view.xml',
                   'stock_sequence.xml',
                   ],
    'installable': True,
}
