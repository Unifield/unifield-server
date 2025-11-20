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
    "name": "Unifield Setup",
    "version": "1.0",
    "depends": [
        "base",
        "base_setup",
        "product",
        "product_attributes",
        "base_setup",
        "hr",
        "account",
        "purchase",
        "sale",
        "purchase_double_validation",
    ],
    "author": "TeMPO Consulting, MSF",
    "website": "http://www.unifield.org",
    "category": "General",
    "description": """
    This module aims at implementing the configuration of a Unifield instance.
    """,
    "init_xml": [
    ],
    'update_xml': [
        "setup_data.xml",
        "unifield_setup_data.xml",
        # Installer views
        "installer/project_addresses_view.xml",
        "installer/project_lead_time_view.xml",
        "installer/delivery_process_view.xml",
        "installer/allocation_setup_view.xml",
        "installer/sales_price_view.xml",
        "installer/restrictive_country_view.xml",
        "installer/field_orders_view.xml",
        "installer/lang_setup_view.xml",
        "installer/currency_setup_view.xml",
        "installer/fixed_asset_view.xml",
        "installer/payroll_view.xml",
        "installer/commitment_import_view.xml",
        "installer/vat_setup_view.xml",
        "installer/previous_fy_dates_setup_view.xml",
        "installer/customer_commitment_voucher.xml",
        "installer/transport_view.xml",
        # Security and access rights
        "security/ir.model.access.csv",
        "view/product_view.xml",
    ],
    'demo_xml': [
    ],
    'test': [
    ],
    'installable': True,
    'active': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
