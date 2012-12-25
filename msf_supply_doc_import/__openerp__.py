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
    "name": "Import Files in Excel Format",
    "version": "0.1",
    "description": "This module enables to import file in xls format",
    "author": "MSF - TeMPO Consulting",
    "category": "Sale",
    "depends": ["sale", "purchase", "tender_flow", "msf_supply_doc_export", "spreadsheet_xml"],
    "init_xml": [],
    "update_xml": [
        'view/sale_order_import_lines_view.xml',
        'view/internal_request_import_line_view.xml',
        'view/tender_import_line_view.xml',
        'view/purchase_order_import_line_view.xml',
        'view/initial_stock_inventory_line_view.xml',
        'view/stock_cost_reevaluation_view.xml',
        'view/product_list_view.xml',
        'view/composition_kit_import_line_view.xml',
        'data/msf_supply_doc_import_data.xml',
        'data/inactive_categ.xml',
        'workflow/purchase_workflow.xml',
        'workflow/sale_workflow.xml',
        'workflow/tender_flow_workflow.xml',
        'workflow/procurement_request_workflow.xml',
    ],
    "demo_xml": [],
    "test": [
        'test/data.yml',
        'test/import_po.yml',
        'test/import_so.yml',
        'test/import_rfq.yml',
        'test/import_ir.yml',
        'test/import_tender.yml',
        'test/import_composition_kit.yml',
        'test/import_real_average_consumption.yml',
        'test/import_monthly_consumption.yml',
    ],
    "installable": True,
    "active": False
}
