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

# if you update a file in PO_COLUMNS_HEADER_FOR_INTEGRATION, check also NEW_COLUMNS_HEADER, you also need to modify the method export_po_integration, get_po_row_values and get_po_header_row_values.
# in PO_COLUMNS_HEADER_FOR_INTEGRATION, you have all the importable columns possible
PO_COLUMNS_HEADER_FOR_INTEGRATION = [
    (_('Line'), 'number'),
    (_('Ext. Ref.'), 'string'),
    (_('Product Code'), 'string'),
    (_('Product Description'), 'string'),
    (_('Product Qty*'), 'number'),
    (_('Product UoM*'), 'string'),
    (_('Price Unit*'), 'number'),
    (_('Currency*'), 'string'),
    (_('Origin*'), 'string'),
    (_('Delivery Reqd Date'), 'date'),
    (_('Delivery Confd Date*'), 'date'),
    (_('Nomen Name'), 'string'),
    (_('Nomen Group'), 'string'),
    (_('Nomen Family'), 'string'),
    (_('Comment'), 'string'),
    (_('Notes'), 'string'),
    (_('Project Ref.*'), 'string'),
]

PO_COLUMNS_FOR_INTEGRATION = [x for (x, y) in PO_COLUMNS_HEADER_FOR_INTEGRATION]

# if you update a file in NEW_COLUMNS_HEADER, you also need to modify the method export_po_integration, get_po_row_values and get_po_header_row_values.
# in NEW_COLUMNS_HEADER, you choose which columns you want to actually import (it is filtered on what you want if you compare with PO_COLUMNS_HEADER_FOR_INTEGRATION)
NEW_COLUMNS_HEADER = [
    ('Line', 'number'), ('Product Code', 'string'), ('Product Description', 'string'), ('Quantity', 'number'), ('UoM', 'string'), ('Price', 'number'), ('Requested Delivery Date', 'date'),
    ('Confirmed Delivery Date', 'date'),('Origin', 'string'), ('Comment', 'string'), ('Notes', 'string'), ('Supplier Reference', 'string'), ('Incoterm', 'string')]

#Important NOTE: I didn't set the fields of type date with the attribute 'date' (2nd part of the tuple) because for Excel, when a date is empty, the field becomes '1899-30-12' as default. So I set 'string' instead for the fields date.
RFQ_COLUMNS_HEADER_FOR_IMPORT = [
    (_('Line Number'), 'number'), (_('Product Code'), 'string'), (_('Product Description'), 'string'), (_('Quantity'), 'number'), (_('UoM'), 'string'), (_('Price'), 'number'),
    (_('Requested Delivery Date'), 'date'), (_('Confirmed Delivery Date'), 'date'), (_('Currency'), 'string'), (_('Comment'), 'string'), (_('State'), 'string'),
]
RFQ_LINE_COLUMNS_FOR_IMPORT = [x for (x, y) in RFQ_COLUMNS_HEADER_FOR_IMPORT]

PO_COLUMNS_HEADER_FOR_IMPORT=[
    (_('Line Number'), 'number'), (_('Product Code'), 'string'), (_('Product Description'), 'string'), (_('Quantity'), 'number'), (_('UoM'), 'string'), (_('Price'), 'number'), (_('Requested Delivery Date'), 'date'), (_('Currency'), 'string'), (_('Comment'), 'string'), (_('Justification Code'), 'string'), (_('Justification Coordination'), 'string'), (_('HQ Remarks'), 'string'), (_('Justification Y/N'), 'string'), (_('Cold chain type'), 'string'), (_('Dangerous Good Type'), 'string'), (_('Controlled Substance Type'), 'string'), (_('State'), 'string')]
PO_LINE_COLUMNS_FOR_IMPORT = [x for (x, y) in PO_COLUMNS_HEADER_FOR_IMPORT]

FO_COLUMNS_HEADER_FOR_IMPORT=[
    (_('fo_import_product_code'), 'string'), (_('fo_import_product_description'), 'string'), (_('fo_import_qty'), 'number'), (_('fo_import_uom'), 'string'),
    (_('fo_import_price'), 'number'), (_('fo_import_drd'), 'date'), (_('fo_import_currency'), 'string'), (_('fo_import_comment'), 'string'), (_('State'), 'string')]
FO_LINE_COLUMNS_FOR_IMPORT = [x for (x, y) in FO_COLUMNS_HEADER_FOR_IMPORT]

INT_COLUMNS_HEADER_FOR_IMPORT = [
    (_('Product Code'), 'string'), (_('Product Description'), 'string'), (_('Quantity'), 'number'), (_('UoM'), 'string'), (_('Kit'), 'string'),
    (_('Asset'), 'string'), (_('Batch Number'), 'string'), (_('Expiry Date'), 'DateTime'), (_('Source Location'), 'string'), (_('Destination Location'), 'string')]
INT_LINE_COLUMNS_FOR_IMPORT = [x for (x, y) in INT_COLUMNS_HEADER_FOR_IMPORT]

IN_COLUMNS_HEADER_FOR_IMPORT = [
    (_('Product Code'), 'string'), (_('Product Description'), 'string'), (_('Quantity'), 'number'), (_('UoM'), 'string'), (_('Kit'), 'string'),
    (_('Asset'), 'string'), (_('Batch Number'), 'string'), (_('Expiry Date'), 'DateTime'), (_('Source Location'), 'string'), (_('Destination Location'), 'string')]
IN_LINE_COLUMNS_FOR_IMPORT = [x for (x, y) in IN_COLUMNS_HEADER_FOR_IMPORT]

OUT_COLUMNS_HEADER_FOR_IMPORT = [
    (_('Product Code'), 'string'), (_('Product Description'), 'string'), (_('Quantity'), 'number'), (_('UoM'), 'string'), (_('Kit'), 'string'),
    (_('Asset'), 'string'), (_('Batch Number'), 'string'), (_('Expiry Date'), 'DateTime'), (_('Source Location'), 'string'), (_('Destination Location'), 'string')]
OUT_LINE_COLUMNS_FOR_IMPORT = [x for (x, y) in OUT_COLUMNS_HEADER_FOR_IMPORT]

IR_COLUMNS_HEADER_FOR_IMPORT=[
    (_('Product Code'), 'string'), (_('Product Description'), 'string'), (_('Quantity'), 'number'), (_('Cost Price'), 'number'), (_('UoM'), 'string'),
    (_('Currency'), 'string'), (_('Comment'), 'string'), (_('State'), 'string')]
IR_COLUMNS_FOR_IMPORT = [x for (x, y) in IR_COLUMNS_HEADER_FOR_IMPORT]

TENDER_COLUMNS_HEADER_FOR_IMPORT=[
    (_('Product Code'), 'string'), (_('Product Description'), 'string'), (_('Quantity'), 'number'), (_('UoM'), 'string'),
    (_('Unit Price'), 'number'), (_('Unit Price (Comparison Currency)'), 'number'), (_('Delivery Requested Date'), 'DateTime')]
TENDER_COLUMNS_FOR_IMPORT = [x for (x, y) in TENDER_COLUMNS_HEADER_FOR_IMPORT]

AUTO_SUPPLY_COLUMNS_HEADER_FOR_IMPORT = [
    (_('Product Code'), 'string'), (_('Product Description'), 'string'), (_('UoM'), 'string'), (_('Qty'), 'number')]
AUTO_SUPPLY_LINE_COLUMNS_FOR_IMPORT = [x for (x,y) in AUTO_SUPPLY_COLUMNS_HEADER_FOR_IMPORT]

ORDER_CYCLE_COLUMNS_HEADER_FOR_IMPORT = [
    (_('Product Code'), 'string'), (_('Product Description'), 'string'), (_('UoM'), 'string'), (_('Safety stock'), 'number')]
ORDER_CYCLE_LINE_COLUMNS_FOR_IMPORT = [x for (x,y) in ORDER_CYCLE_COLUMNS_HEADER_FOR_IMPORT]

THRESHOLD_COLUMNS_HEADER_FOR_IMPORT = [
    (_('Product Code'), 'string'), (_('Product Description'), 'string'), (_('UoM'), 'string'), (_('Product Qty'), 'number'), (_('Threshold value'), 'number')]
THRESHOLD_LINE_COLUMNS_FOR_IMPORT = [x for (x,y) in THRESHOLD_COLUMNS_HEADER_FOR_IMPORT]

STOCK_WAREHOUSE_ORDERPOINT_COLUMNS_HEADER_FOR_IMPORT = [
    (_('Product Code'), 'string'), (_('Product Description'), 'string'), (_('UoM'), 'string'), (_('Product Min Qty'), 'number'), (_('Product Max Qty'), 'number'), (_('Qty Multiple'), 'number'), ]
STOCK_WAREHOUSE_ORDERPOINT_LINE_COLUMNS_FOR_IMPORT = [x for (x,y) in STOCK_WAREHOUSE_ORDERPOINT_COLUMNS_HEADER_FOR_IMPORT]

PRODUCT_LIST_COLUMNS_HEADER_FOR_IMPORT = [
    (_('Product Code'), 'string'), (_('Product Description'), 'string'), (_('Comment'), 'string')]
PRODUCT_LIST_COLUMNS_FOR_IMPORT = [x for (x,y) in PRODUCT_LIST_COLUMNS_HEADER_FOR_IMPORT]

COLUMNS_HEADER_FOR_PRODUCT_LINE_IMPORT = [
    (_('Product Code'), 'string')]
COLUMNS_FOR_PRODUCT_LINE_IMPORT = [x for (x, y) in COLUMNS_HEADER_FOR_PRODUCT_LINE_IMPORT]

ACCOUNT_INVOICE_COLUMNS_HEADER_FOR_IMPORT = [
    ('Description', 'string'), ('Account', 'string'), ('Quantity', 'number'), ('Unit Price', 'number'), ('Destination', 'string'), ('Cost Center', 'string'), ('Funding Pool', 'string')]
ACCOUNT_INVOICE_COLUMNS_FOR_IMPORT = [x for (x,y) in ACCOUNT_INVOICE_COLUMNS_HEADER_FOR_IMPORT]

# if you update a file in NEW_COLUMNS_HEADER, you also need to modify the method export_po_integration, get_po_row_values and get_po_header_row_values.
# in NEW_COLUMNS_HEADER, you choose which columns you want to actually import (it is filtered on what you want if you compare with PO_COLUMNS_HEADER_FOR_INTEGRATION)

SUPPLIER_CATALOG_COLUMNS_HEADER_FOR_IMPORT = [
    (_('Product Code'), 'string'),
    (_('Product Description'), 'string'),
    (_('Supplier Code'), 'string'),
    (_('UoM'), 'string'),
    (_('Min. Qty'), 'number'),
    (_('Unit Price'), 'number',),
    (_('SoQ Rounding'), 'number'),
    (_('Min. Order Qty.'), 'number'),
    (_('Comment'), 'string'),
]
SUPPLIER_CATALOG_COLUMNS_FOR_IMPORT = [x for (x,y) in SUPPLIER_CATALOG_COLUMNS_HEADER_FOR_IMPORT]

PPL_COLUMNS_LINES_HEADERS_FOR_IMPORT = [
    (_('ppl_import_update_item'), 'number'), (_('ppl_import_update_code'), 'string'), (_('ppl_import_update_description'), 'string'),
    (_('ppl_import_update_comment'), 'string'), (_('ppl_import_update_tot_qty'), 'string'), (_('ppl_import_update_batch'), 'string'),
    (_('ppl_import_update_expiry'), 'date'), (_('ppl_import_update_kc'), 'string'), (_('ppl_import_update_dg'), 'string'),
    (_('ppl_import_update_cs'), 'string'), (_('ppl_import_update_packed'), 'number'), (_('ppl_import_update_from_p'), 'number'),
    (_('ppl_import_update_to_p'), 'number'), (_('ppl_import_update_weight'), 'number'), (_('ppl_import_update_size'), 'number'),
    (_('ppl_import_update_pack_t'), 'string')
]
PPL_COLUMNS_LINES_FOR_IMPORT = [x for (x,y) in PPL_COLUMNS_LINES_HEADERS_FOR_IMPORT]

from . import wizard_import_po
from . import wizard_import_po_line
from . import wizard_import_invoice_line
from . import wizard_import_fo_line
from . import wizard_import_ir_line
from . import wizard_import_picking_line
from . import wiz_common_import
from . import wizard_import_tender_line
from . import wizard_delete_lines
from . import wizard_cancel_lines
from . import wizard_import_product_list
from . import wizard_import_product_line
from . import wizard_import_supplier_catalogue
from . import wizard_po_simulation_screen
from . import wizard_in_simulation_screen
from . import wizard_import_ppl_to_create_ship
from . import wizard_return_from_unit_import

from . import abstract_wizard_import
from . import wizard_import_batch
from . import wizard_import_ad_line
