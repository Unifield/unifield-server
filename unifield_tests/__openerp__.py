#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Olivier DOSSMANN
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
    "name" : "Unifield Unit Tests",
    "version" : "0.1",
    "description" : "This module adds unit test for Unifield modules",
    "author" : "TeMPO Consulting, MSF",
    "category" : "Tests",
    "depends" : [],
    "init_xml" : [
        'master_data/010_accounts.yml',
        'master_data/020_partners.yml',
        'master_data/030_journals.yml',
        'master_data/040_analytic.yml',
        'master_data/050_product_nomenclatures.yml',
        'master_data/060_product_categories.yml',
        'master_data/070_products.yml',
        'master_data/080_locations.yml',
    ],
    "update_xml" : [],
    "demo_xml" : [],
    "test": [],
    "installable": True,
    "active": False
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
