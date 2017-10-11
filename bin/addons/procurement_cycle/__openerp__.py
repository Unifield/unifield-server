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
    "name": "Procurement Order Cycle",
    "version": "1.0",
    "depends": ["base",
                "procurement",
                "stock",
                "consumption_calculation",
                "stock_schedule",
                "sale",
                "purchase",
                "product_expiry",
                "purchase_double_validation",
                "reason_types_moves",
                ],
    "author": "TeMPO Consulting, MSF",
    "website": "",
    "category": "Warehouse & Stock",
    "description": """
        This module aims to add a new replenishment policies with
        fixed dates and variable quantities.
        
        BE CAREFUL: THIS MODULE WAS CREATED DURING THE DEVELOPMENT
        OF THE STOCK REPLENISHMENT MODULE IN ITERATION 1. DON'T FORGET
        TO CHANGE BEHAVIOUR OF THIS MODULE IF YOUR CHANGE THE LOGIC OF THIS 
        NEW MODULE
    """,
    "init_xml": [
    ],
    'update_xml': [
        'procurement_view.xml',
        'procurement_data.xml',
        'wizard/schedulers_all_view.xml',
        'security/ir.model.access.csv',
    ],
    'demo_xml': [
    ],
    'test': [
    ],
    'installable': True,
    'active': False,
    #    'certificate': 'certificate',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
