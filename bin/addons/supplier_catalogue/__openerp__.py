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
    "name" : "Supplier Catalogue",
    "version" : "1.0",
    "author" : "TeMPO Consulting,MSF",
    "description" : """
    Add management of supplier catalogue
    """,
    "website": "http://unifield.msf.org",
    "depends" : ["product", "purchase", 
                 "product_nomenclature",
                 "partner_modification",
                 "msf_partner",],
    "category" : "Generic Modules/Supplier Catalogue",
    "init_xml" : [],
    "demo_xml" : [],
    "update_xml" : [
        "supplier_catalogue_view.xml",
        "product_view.xml",
        "partner_view.xml",
        "supplier_catalogue_data.xml",
        "wizard/catalogue_import_lines_view.xml",
        "wizard/catalogue_export_lines_view.xml",
        "supplier_catalogue_report.xml",
        "security/ir.model.access.csv",
        "wizard/catalogue_update_lines_ranking_wizard_view.xml",
    ],
    'installable': True,
    'active': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
