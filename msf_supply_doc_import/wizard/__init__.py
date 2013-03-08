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

# if you update a file in PO_COLUMNS_HEADER_FOR_INTEGRATION, check also NEW_COLUMNS_HEADER, you also need to modify the method export_po_integration, get_po_row_values and get_po_header_row_values.
# in PO_COLUMNS_HEADER_FOR_INTEGRATION, you have all the importable columns possible
PO_COLUMNS_HEADER_FOR_INTEGRATION=[
('Line*', 'number'), ('Product Code*', 'string'), ('Product Description', 'string'), ('Quantity*', 'number'), ('UoM*', 'string'), ('Price*', 'number'), ('Delivery Request Date', 'date'),
('Delivery Confirmed Date*', 'date'), ('Order Reference*', 'string'), ('Delivery Confirmed Date (PO)*', 'date'),
('Comment', 'string'), ('Supplier Reference', 'string'), ('Origin', 'string'), ('Notes', 'string'), ('Est. Transport Lead Time', 'number'), ('Transport Mode', 'string'), 
('Destination Partner', 'string'), ('Destination Address', 'string'), ('Invoicing Address', 'string'), ('Arrival Date in the country', 'date'),
('Incoterm', 'string'), ('Notes (PO)', 'string')]

PO_COLUMNS_FOR_INTEGRATION = [x for (x, y) in PO_COLUMNS_HEADER_FOR_INTEGRATION]

# if you update a file in NEW_COLUMNS_HEADER, you also need to modify the method export_po_integration, get_po_row_values and get_po_header_row_values.
# in NEW_COLUMNS_HEADER, you choose which columns you want to actually import (it is filtered on what you want if you compare with PO_COLUMNS_HEADER_FOR_INTEGRATION)
NEW_COLUMNS_HEADER = [
('Line*', 'number'), ('Product Code*', 'string'), ('Product Description', 'string'), ('Quantity*', 'number'), ('UoM*', 'string'), ('Price*', 'number'), ('Delivery Request Date', 'date'),
('Delivery Confirmed Date*', 'date'),('Origin', 'string'), ('Comment', 'string'), ('Notes', 'string'), ('Supplier Reference', 'string'), ('Incoterm', 'string')]


import wizard_import_po
import stock_partial_picking