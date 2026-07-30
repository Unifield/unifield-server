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
    "name" : "Kit",
    "version" : "0.1",
    "author" : "MSF pam",
    "category" : "Kit capabilities",
    "description": """
        Add Kit management capabilities. Composition List, theorical composition, kitting, de-kitting.
        """,
    'website': 'http://www.unifield.org',
    'init_xml': [],
    "depends" : ["stock", "sale", "purchase", "product_nomenclature","product_asset",
                 "purchase_double_validation", "specific_rules", "supplier_catalogue"],
    'update_xml': [
        'kit_view.xml',
        'kit_creation_view.xml',
        'kit_sequence.xml',
        'kit_report.xml',
        'wizard/substitute_view.xml',
        'wizard/confirm_view.xml',
        'wizard/kit_selection_view.xml',
        'wizard/kit_selection_sale_view.xml',
        'wizard/modify_expiry_date_view.xml',
        'wizard/process_to_consume_view.xml',
        'wizard/assign_to_kit_view.xml',
        'security/ir.model.access.csv',
        'wizard/split_move_view.xml',
        'wizard/kit_mass_import_view.xml',
        'report/kit_mass_import_export_view.xml',
        'report/kitting_order_report.xml',
        'report/tkc_kcl_comparison_report_view.xml'
    ],
    "demo_xml": [],
    'test': [
    ],
    'installable': True,
}
