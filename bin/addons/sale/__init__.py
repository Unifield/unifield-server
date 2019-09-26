# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

#----------------------------------------------------------
# Init Sales
#----------------------------------------------------------

SALE_ORDER_LINE_STATE_SELECTION = [
    ('draft', 'Draft'),
    ('validated', 'Validated'),
    ('sourced', 'Sourced'),
    ('sourced_v', 'Sourced-v'),
    ('sourced_sy', 'Sourced-sy'),
    ('sourced_n', 'Sourced-n'),
    ('confirmed', 'Confirmed'),
    ('done', 'Closed'),
    ('cancel', 'Cancelled'),
    ('cancel_r', 'Cancelled-r'),
]

SALE_ORDER_LINE_DISPLAY_STATE_SELECTION = SALE_ORDER_LINE_STATE_SELECTION + [
    ('resourced_v', 'Resourced-v'),
    ('resourced_pv', 'Resourced-pv'),
    ('resourced_s', 'Resourced-s'),
    ('resourced_c', 'Resourced-c'),
    ('resourced_d', 'Resourced-d'),
]

SALE_ORDER_STATE_SELECTION = [
    ('draft', 'Draft'),
    ('draft_p', 'Draft-p'),
    ('validated', 'Validated'),
    ('validated_p', 'Validated-p'),
    ('sourced', 'Sourced'),
    ('sourced_p', 'Sourced-p'),
    ('confirmed', 'Confirmed'),
    ('confirmed_p', 'Confirmed-p'),
    ('done', 'Closed'),
    ('cancel', 'Cancelled'),
]


SALE_ORDER_SPLIT_SELECTION = [
    ('original_sale_order', 'Original'),
    ('esc_split_sale_order', '1'), # ESC
    ('stock_split_sale_order', '2'), # from Stock
    ('local_purchase_split_sale_order', '3'), # Local Purchase
]

import sale_order
import stock
import sale_installer
import wizard
import report
import company
import res_partner
import sale_workflow

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
