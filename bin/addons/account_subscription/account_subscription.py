#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
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
from osv import fields, osv
from tools.translate import _

class account_subscription(osv.osv):
    _name = "account.subscription"
    _inherit = "account.subscription"

    _columns = {
        'period_nbr': fields.integer('Repeat', required=True, help="This field will determine how often entries will be generated: if the period type is 'month' and the repeat '2' then entries will be generated every 2 months"),
    }

    _defaults = {
        'period_total': 0,
    }

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if 'period_nbr' in vals and vals['period_nbr'] < 1:
            raise osv.except_osv(_('Warning'), _('The value in the field "Repeat" must be greater than 0!'))
        return super(account_subscription, self).create(cr, uid, vals, context)

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if context is None:
            context = {}
        if 'period_nbr' in vals and vals['period_nbr'] < 1:
            raise osv.except_osv(_('Warning'), _('The value in the field "Repeat" must be greater than 0!'))
        return super(account_subscription, self).write(cr, uid, ids, vals, context)

    def copy(self, cr, uid, acc_sub_id, default=None, context=None):
        """
        Account Subscription duplication: don't copy the link with subscription lines
        """
        if context is None:
            context = {}
        if default is None:
            default = {}
        default.update({
            'lines_id': [],
        })
        return super(account_subscription, self).copy(cr, uid, acc_sub_id, default, context=context)


account_subscription()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
