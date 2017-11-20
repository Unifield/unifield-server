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
    "name" : "Products & Pricelists modified by MSF",
    "version" : "0.1",
    "author" : "MSF, TeMPO Consulting",
    "developer": "pam",
    "category" : "Generic Modules/Inventory Control",
    "description": """
    This is the base module for managing products and pricelists in OpenERP.

    Products support variants, different pricing methods, suppliers
    information, make to stock/order, different unit of measures,
    packaging and properties.

    Pricelists support:
    * Multiple-level of discount (by product, category, quantities)
    * Compute price based on different criteria:
        * Other pricelist,
        * Cost price,
        * List price,
        * Supplier price, ...
    Pricelists preferences by product and/or partners.

    Print product labels with barcode.
    """,
    "depends" : ["product","stock_override", "msf_instance","sale", "purchase", "order_nomenclature"],
    "init_xml": [
        "asset_type_data.xml",
    ],
    'test': [
    ],
    'update_xml': [
        'product_asset_view.xml',
        'security/ir.model.access.csv',
        'asset_sequence.xml',
        'wizard/stock_partial_move_view.xml',
        'product_asset_report.xml',
    ],
    'installable': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
