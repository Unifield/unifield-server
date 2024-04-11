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
    "name" : "MSF Partners",
    "version" : "1.0",
    "author" : "TeMPO Consulting, MSF",
    "category": "Others",
    "description": """
        This modules aims to differentiate Internal/External partners
        It also aims to create a new type of partner: Manufacturer
    """,
    "website": "http://unifield.msf.org",
    "init_xml": [
    ],
    "depends" : [
        "base",
        "product",
        "partner_modification",
    ],
    "update_xml": [
        "partner_view.xml",
        "product_view.xml",
        "wizard/sol_pol_intermission_section_validation_view.xml",
    ],
    "demo_xml": [
        "partner_demo.xml",
    ],
    "test": [
    ],
    "installable": True,
    "active": False,
}
