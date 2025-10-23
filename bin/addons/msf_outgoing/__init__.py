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

PACK_INTEGRITY_STATUS_SELECTION = [
    ('empty', ''),
    ('ok', _('Ok')),
    ('missing_1', _('The first sequence must start with 1')),
    ('to_smaller_than_from', _('To value must be greater or equal to From value')),
    ('overlap', _('The sequence overlaps previous one')),
    ('gap', _('A gap exists in the sequence: previous sequence is missing')),
]
INTEGRITY_STATUS_SELECTION = [
    ('negative', _('Negative Value')),
    # picking
    ('missing_lot', _('Batch Number is Missing')),
    ('missing_date', _('Expiry Date is Missing')),
    ('no_lot_needed', _('No Batch Number/Expiry Date Needed')),
    ('wrong_lot_type', _('Wrong Batch Number Type')),
    ('wrong_lot_type_need_internal', _('Need Expiry Date (Internal) not Batch Number (Standard)')),
    ('wrong_lot_type_need_standard', _('Need Batch Number (Standard) not Expiry Date (Internal)')),
    ('lot_not_linked_to_prod', _('BN is linked to another product')),
    ('empty_picking', _('Empty Picking Ticket')),
    # return ppl
    ('return_qty_too_much', _('Too much quantity selected')),
    # ppl2
    ('missing_weight', _('Weight is Missing')),
    # create shipment
    ('too_many_packs', _('Too many packs selected')),
    # return from shipment
    ('seq_out_of_range', _('Selected Sequence is out of range')),
    # substitute kit
    ('not_available', _('Not Available')),
    ('must_be_greater_than_0', _('Quantity must be greater than 0.0')),
    ('missing_asset', _('Asset is Missing')),
    ('no_asset_needed', _('No Asset Needed')),
    # assign kit
    ('greater_than_available', _('Assigned qty must be smaller or equal to available qty')),
    ('greater_than_required', _('Assigned qty must be smaller or equal to required qty')),
    # pol dekitting
    ('price_must_be_greater_than_0', _('Unit Price must be greater than 0.0')),
    # claims
    ('missing_src_location', _('Src Location is missing')),
    ('not_exist_in_picking', _('Prod/BN/ED not available in the IN/OUT')),
] + PACK_INTEGRITY_STATUS_SELECTION

from . import msf_outgoing
from . import wizard
from . import report


