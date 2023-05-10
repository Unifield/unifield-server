# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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
    "name" : "Inventory Management",
    "version" : "1.1",
    "author" : "OpenERP SA",
    "description" : """OpenERP Inventory Management module can manage multi-warehouses, multi and structured stock locations.
Thanks to the double entry management, the inventory controlling is powerful and flexible:
* Moves history and planning,
* Different inventory methods (FIFO, LIFO, ...)
* Stock valuation (standard or average price, ...)
* Robustness faced with Inventory differences
* Automatic reordering rules (stock level, JIT, ...)
* Bar code supported
* Rapid detection of mistakes through double entry system
* Traceability (upstream/downstream, production lots, serial number, ...)
* Dashboard for warehouse that includes:
    * Products to receive in delay (date < = today)
    * Procurement in exception
    * Graph : Number of Receive products vs planned (bar graph on week par day)
    * Graph : Number of Delivery products vs planned (bar graph on week par day)
    """,
    "website" : "http://www.openerp.com",
    "depends" : ["product", "account"],
    "category" : "Generic Modules/Inventory Control",
    "init_xml" : [],
    "demo_xml" : ["stock_demo.xml"],
    "update_xml" : [
        "security/stock_security.xml",
        "security/ir.model.access.csv",
        "stock_data.xml",
        "wizard/stock_move_view.xml",
        "wizard/stock_change_product_qty_view.xml",
        "wizard/stock_partial_move_view.xml",
        "wizard/stock_fill_inventory_view.xml",
        "wizard/stock_invoice_onshipping_view.xml",
        "wizard/stock_inventory_merge_view.xml",
        "wizard/stock_location_product_view.xml",
        "wizard/stock_splitinto_view.xml",
        "wizard/stock_inventory_line_split_view.xml",
        "stock_workflow.xml",
        "stock_incoterms.xml",
        "stock_view.xml",
        "stock_report.xml",
        "stock_sequence.xml",
        "product_data.xml",
        "product_view.xml",
        "partner_view.xml",
        "report/report_stock_move_view.xml",
        "report/report_stock_view.xml",
        "report/unreserved_stock_report.xml",
        "board_warehouse_view.xml",
        "physical_inventory_view.xml",
        "physical_inventory_data.xml",
        "report/physical_inventory_view.xml",
        "wizard/physical_inventory_select_products_view.xml",
        "wizard/physical_inventory_generate_counting_sheet_view.xml",
        "wizard/physical_inventory_import_view.xml",
        'wizard/manage_expired_stock.xml',
        "wizard/reserved_products_wizard_view.xml",
        "report/reserved_products_report_view.xml",
        "reserved_products_view.xml",
        "wizard/stock_reception_wizard_view.xml",
        "report/stock_reception_report_view.xml",
        "report/stock_expired_damaged_report_view.xml",
        "report/products_situation_report_view.xml",
        "wizard/stock_delivery_wizard_view.xml",
        "report/stock_delivery_report_view.xml",
        "report/closed_physical_inventory_report.xml",
        "wizard/loan_certificate_wizard.xml",
    ],
    'installable': True,
    'active': False,
    'certificate': '0055421559965',
}
