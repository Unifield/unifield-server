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
    "name": "MSF Delivery Mechanism",
    "version": "1.0",
    "depends": ["base",
                "sale",
                "purchase",
                "account",
                "stock_override",
                "purchase_override",
                "sale_override",
                "product_asset", # because of asset_id
                "msf_outgoing",
                ],
    "author": "MSF, TeMPO Consulting",
    "website": "",
    "category": "Specific Modules",
    "description": """
        Specify business for Incoming shipment.
    """,
    "init_xml": [
    ],
    'update_xml': ['security/ir.model.access.csv',
                   'delivery_mechanism_view.xml',
                   'wizard/stock_partial_move_view.xml',
                   'wizard/change_product_memory_move_view.xml',
                   'wizard/enter_reason_view.xml',
                   ],
    'demo_xml': [
    ],
    'test': ['test/data.yml',
             'test/product_cost_valuation.yml',
             'test/delivery_mechanism-process-same-qty.yml', #A
             'test/delivery_mechanism-process-less.yml', #B
             'test/delivery_mechanism-process-split-same-qty.yml', #C
             'test/delivery_mechanism-process-split-less.yml', #D
             'test/delivery_mechanism-process-split-less-split-more-on-backorder.yml', #E
             'test/delivery_mechanism-process-change-product-same-qty.yml', #F
             'test/delivery_mechanism-process-change-product-less-qty.yml', #K
             'test/delivery_mechanism-process-split-less-split-more-on-backorder-NO-OUT.yml', # in A
             'test/delivery_mechanism-process-split-less-cancel-backorder-update-out.yml', #G
             'test/delivery_mechanism-process-split-less-cancel-backorder.yml', #H
             'test/delivery_mechanism-process-split-less-cancel-backorder-update-out-NO-OUT.yml', # in B
             'test/delivery_mechanism-process-change-product-same-qty-delete-one-line.yml', #I
             'test/delivery_mechanism-cancel-update-out.yml', #J
             'test/internal_request.yml',
             'test/duplicate-out.yml',
             ],
    'installable': True,
    'active': False,
}

