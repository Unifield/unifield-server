# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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

PO_COLUMNS_HEADER_FOR_IMPORT=[
(_('Product Code'), 'string'), (_('Product Description'), 'string'), (_('Quantity'), 'number'), (_('UoM'), 'string'), (_('Price'), 'number'), 
(_('Delivery requested date'), 'string'), (_('Currency'), 'string'), (_('Comment'), 'string')]
PO_LINE_COLUMNS_FOR_IMPORT = [x for (x, y) in PO_COLUMNS_HEADER_FOR_IMPORT]

FO_COLUMNS_HEADER_FOR_IMPORT=[
(_('Product Code'), 'string'), (_('Product Description'), 'string'), (_('Quantity'), 'number'), (_('UoM'), 'string'), (_('Price'), 'number'), 
(_('Delivery requested date'), 'string'), (_('Currency'), 'string'), (_('Comment'), 'string')]
FO_LINE_COLUMNS_FOR_IMPORT = [x for (x, y) in FO_COLUMNS_HEADER_FOR_IMPORT]

IR_COLUMNS_HEADER_FOR_IMPORT=[
(_('Product Code'), 'string'), (_('Product Description'), 'string'), (_('Quantity'), 'number'), (_('Cost Price'), 'number'), (_('UoM'), 'string'), 
(_('Currency'), 'string'), (_('Comment'), 'string')]
IR_COLUMNS_FOR_IMPORT = [x for (x, y) in IR_COLUMNS_HEADER_FOR_IMPORT]

TENDER_COLUMNS_HEADER_FOR_IMPORT=[
(_('Product Code'), 'string'), (_('Product Description'), 'string'), (_('Quantity'), 'number'), (_('UoM'), 'string'), 
(_('Price'), 'number'), (_('Delivery Requested Date'), 'DateTime')]
TENDER_COLUMNS_FOR_IMPORT = [x for (x, y) in TENDER_COLUMNS_HEADER_FOR_IMPORT]

import wizard_import_po_line
import wizard_import_fo_line
import wizard_import_ir_line
import wiz_common_import
import wizard_import_tender_line
