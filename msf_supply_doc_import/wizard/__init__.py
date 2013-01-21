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

# if you update a file in PO_COLUMNS_FOR_INTEGRATION, you also need to modify the method export_po_integration.
PO_COLUMNS_FOR_INTEGRATION=[
'Order Reference', 'Line', 'Product Code', 'Quantity', 'UoM', 'Price', 'Currency', 'Comment', 'Supplier Reference',
'Delivery Confirmed Date', 'Est. Transport Lead Time', 'Transport Mode', 'Arrival Date in the country', 'Incoterm', 'Destination Partner',
'Destination Address', 'Notes']

import wizard_import_po
