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
# Authorized journals in Accounting import
ACCOUNTING_IMPORT_JOURNALS = [
    'intermission',
    'correction_manual',
    'hr',
    'migration',
    'sale',  # US-70/3
]

PRODUCT_LIST_TYPE = [('list', 'List'), ('sublist', 'Sublist')]

PPL_IMPORT_FOR_UPDATE_MESSAGE = _("""        The file should be in XML 2003 format.
For the main header, the first 8 lines of the column 1 must have these values: Reference, Date, Requester Ref, \
Our Ref, FO Date, Packing Date, RTS Date, Transport Mode. And the line 1 of the column 4 and 7 \
must have these values: Shipper, Consignee.
There should also be a blank line between the main header and the lines header.
The lines columns at the line 10 should be in this values:""")

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
import product_list
import supplier_catalogue
import report
import msf_import_export
import msf_import_export_conf
