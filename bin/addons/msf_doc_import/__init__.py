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

from tools.translate import _

# max number of lines to import per file
MAX_LINES_NB = 300
GENERIC_MESSAGE = _("""
        IMPORTANT : The first line will be ignored by the system.
        The file should be in XML 2003 format.

The columns should be in this values: """)
# Authorized analytic journal in Accounting import
ACCOUNTING_IMPORT_JOURNALS = [
    'intermission',
    'correction',
    'hr',
    'migration',
    'sale',  # US-70/3
]
PRODUCT_LIST_TYPE = [('list', 'List'), ('sublist', 'Sublist')]


import tender
import purchase_order
import sale_order
import initial_stock_inventory
import stock_cost_reevaluation
import product_list
import composition_kit
import check_line
import wizard
import import_tools
import composition_kit
import account
import stock_picking
import replenishment_rules
import product_list
import product_mass_update
import supplier_catalogue
import report
import msf_import_export
