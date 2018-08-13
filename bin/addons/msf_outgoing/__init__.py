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

INTEGRITY_STATUS_SELECTION = [('empty', ''),
                              ('ok', 'Ok'),
                              ('negative', 'Negative Value'),
                              # picking
                              ('missing_lot', 'Batch Number is Missing'),
                              ('missing_date', 'Expiry Date is Missing'),
                              ('no_lot_needed', 'No Batch Number/Expiry Date Needed'),
                              ('wrong_lot_type', 'Wrong Batch Number Type'),
                              ('wrong_lot_type_need_internal', 'Need Expiry Date (Internal) not Batch Number (Standard)'),
                              ('wrong_lot_type_need_standard', 'Need Batch Number (Standard) not Expiry Date (Internal)'),
                              ('empty_picking', 'Empty Picking Ticket'),
                              # return ppl
                              ('return_qty_too_much', 'Too much quantity selected'),
                              # ppl1
                              ('missing_1', 'The first sequence must start with 1'),
                              ('to_smaller_than_from', 'To value must be greater or equal to From value'),
                              ('overlap', 'The sequence overlaps previous one'),
                              ('gap', 'A gap exist in the sequence'),
                              # ppl2
                              ('missing_weight', 'Weight is Missing'),
                              # create shipment
                              ('too_many_packs', 'Too many packs selected'),
                              # return from shipment
                              ('seq_out_of_range', 'Selected Sequence is out of range'),
                              # substitute kit
                              ('not_available', 'Not Available'),
                              ('must_be_greater_than_0', 'Quantity must be greater than 0.0'),
                              ('missing_asset', 'Asset is Missing'),
                              ('no_asset_needed', 'No Asset Needed'),
                              # assign kit
                              ('greater_than_available', 'Assigned qty must be smaller or equal to available qty'),
                              ('greater_than_required', 'Assigned qty must be smaller or equal to required qty'),
                              # pol dekitting
                              ('price_must_be_greater_than_0', 'Unit Price must be greater than 0.0'),
                              # claims
                              ('missing_src_location', 'Src Location is missing'),
                              ('not_exist_in_picking', 'Does not exist in selected IN/OUT'),
                              ]

PACK_INTEGRITY_STATUS_SELECTION = [
    ('empty', ''),
    ('ok', 'Ok'),
    ('missing_1', 'The first sequence must start with 1'),
    ('to_smaller_than_from', 'To value must be greater or equal to From value'),
    ('overlap', 'The sequence overlaps previous one'),
    ('gap', 'A gap exist in the sequence'),
    ('bad_qty_int', 'The quantity per pack must be an integer for this UoM'),
    ('bad_qty_rounded', 'The quantity per pack must be a multiple of UoM\'s rounding'),
]
import msf_outgoing
import wizard
import report


