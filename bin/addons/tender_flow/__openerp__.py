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
    "name" : "Tender and Request for quotation flow",
    "version" : "0.1",
    "author" : "MSF, TeMPO Consulting",
    "developer": "pam",
    "category" : "Generic Modules/Inventory Control",
    "depends" : ["sale", "purchase", "stock",
                 "partner_modification", "sourcing",
                 "msf_order_date", "supplier_catalogue",],
    "init_xml" : [],
    "demo_xml" : [],
    "description": """
    Add sourcing specification
    """,
    'update_xml': [
        'security/ir.model.access.csv',
        'tender_flow_sequence.xml',
        'tender_flow_view.xml',
        'tender_flow_workflow.xml',
        'report/purchase_report_view.xml',
        'board_purchase_view.xml',
        'tender_flow_report.xml',
        'audittrail_data_tender.yml',
        'tender_flow_data.xml',
    ],
    'installable': True,
}
