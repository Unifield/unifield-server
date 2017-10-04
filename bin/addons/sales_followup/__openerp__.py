# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF
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
    "name" : "Sales Follow-Up",
    "version" : "1.0",
    "author" : "TeMPO Consulting, MSF",
    "category": "Others",
    "description": """
        Add wizard to allow users to have
        an overview of all related 
        documents to a sale order.
    """,
    "website": "http://unifield.msf.org",
    "init_xml": [
    ],
    "depends" : [
        "sale",
        "stock",
        "purchase",
        "msf_order_date",
        "purchase_double_validation",
        "procurement",
        "tender_flow",
    ],
    "update_xml": [
        "sale_followup_view.xml",
        "report/sale_follow_up_report.xml",
        "report/ir_follow_up_location_report.xml",
        "report/ir_track_changes_report.xml",
        "wizard/sale_followup_multi_wizard_view.xml",
        "wizard/ir_followup_location_wizard_view.xml",
        "wizard/ir_track_changes_wizard_view.xml",
    ],
    "demo_xml": [
    ],
    "test": [
    ],
    "installable": True,
    "active": False,
}
