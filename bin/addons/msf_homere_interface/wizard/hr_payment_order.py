#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2018 TeMPO Consulting, MSF. All Rights Reserved
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

from osv import osv
from osv import fields


class hr_payment_order(osv.osv_memory):
    _name = 'hr.payment.order'
    _description = 'Payment Orders'

    _columns = {
        'payment_method_id': fields.many2one('hr.payment.method', string='Payment Method', required=True),
        'period_id': fields.many2one('account.period', string='Period', required=False, domain="[('number', '!=', 0)]"),
    }


hr_payment_order()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
