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

from tools.translate import _

ORDER_PRIORITY = [
    ('emergency', 'Emergency'),
    ('normal', 'Normal'),
    ('priority', 'Priority'),
]

ORDER_CATEGORY = [
    ('medical', 'Medical'),
    ('log', 'Logistic'),
    ('service', 'Service'),
    ('transport', 'Transport'),
    ('other', 'Other'),
]

PURCHASE_ORDER_LINE_STATE_SELECTION = [
    ('draft', 'Draft'),
    ('validated_n', 'Validated-n'),
    ('validated', 'Validated'),
    ('sourced_sy', 'Sourced-sy'),
    ('sourced_v', 'Sourced-v'),
    ('sourced_n', 'Sourced-n'),
    ('confirmed', 'Confirmed'),
    ('done', 'Closed'),
    ('cancel', 'Cancelled'),
    ('cancel_r', 'Cancelled-r'),
]

PURCHASE_ORDER_LINE_DISPLAY_STATE_SELECTION = PURCHASE_ORDER_LINE_STATE_SELECTION + [
    ('resourced_v', 'Resourced-v'),
    ('resourced_pv', 'Resourced-pv'),
    ('resourced_s', 'Resourced-s'),
    ('resourced_c', 'Resourced-c'),
    ('resourced_d', 'Resourced-d'),
]

PURCHASE_ORDER_STATE_SELECTION = [
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

ORDER_TYPES_SELECTION = [
    ('regular', _('Regular')),
    ('donation_exp', _('Donation before expiry')),
    ('donation_st', _('Standard donation')),
    ('loan', _('Loan')),
    ('in_kind', _('In Kind Donation')),
    ('purchase_list', _('Purchase List')),
    ('direct', _('Direct Purchase Order')),
]


import purchase_order
import purchase_order_line
import purchase_workflow
import stock
import wizard
import report
import company
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

