#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Olivier DOSSMANN
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

class product_product(osv.osv):
    _name = 'product.product'
    _inherit = 'product.product'

    _columns = {
        'donation_expense_account': fields.many2one('account.account', "Donation Account"),
    }

product_product()

class product_category(osv.osv):
    _name = 'product.category'
    _inherit = 'product.category'

    _columns = {
        'donation_expense_account': fields.many2one('account.account', "Donation Account"),
    }

product_category()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
