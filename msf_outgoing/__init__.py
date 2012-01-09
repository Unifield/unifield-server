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
                              ('missing_lot', 'Production Lot/Expiry Date is Missing'),
                              ('no_lot_needed', 'No Production Lot/Expiry Date Needed'),
                              ('wrong_lot_type', 'Wrong Production Lot Type'),
                              ('wrong_lot_type_need_internal', 'Need Expiry Date (Internal) not Production Lot (Standard)'),
                              ('wrong_lot_type_need_standard', 'Need Production Lot (Standard) not Expiry Date (Internal)'),
                              ('empty_picking', 'Empty Picking Ticket'),
                              ]

import msf_outgoing
import wizard
import report

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
