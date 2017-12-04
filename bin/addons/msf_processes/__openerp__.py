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
    "name" : "MSF Processes",
    "version" : "1.0",
    "author" : "TeMPO Consulting, MSF",
    "category": "Others",
    "description": """
        Process
    """,
    "website": "http://unifield.msf.org",
    "init_xml": [],
    "depends" : ["account",
                 "procurement",
                 "sale",
                 "purchase",
                 "tender_flow",
                 "stock",
                 "msf_outgoing",
                 "analytic_distribution",
                 ],
    "update_xml": [# see process_dependencies.xmind for detail about dependencies
                   "process/ship_process.xml", #1
                   "process/draft_ship_process.xml", #2
                   "process/ppl_process.xml", #3
                   "process/picking_process.xml", #4
                   "process/outgoing_process.xml", #5
                   "process/incoming_process.xml", #6
                   "process/rfq_process.xml", #7
                   "process/supplier_invoice_process.xml", #8
                   "process/purchase_process.xml", #9
                   "process/tender_process.xml", #10
                   "process/sale_process.xml", #12
                   ],
    "demo_xml": [],
    "test": [],
    "installable": True,
    "active": False,
}
