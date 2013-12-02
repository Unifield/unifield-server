#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
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

ACCOUNT_RESTRICTED_AREA = {
    # REGISTER LINES
    'register_lines': [
        ('type', '!=', 'view'),
        ('is_not_hq_correctible', '!=', True),
        '|', ('type', '!=', 'liquidity'), ('user_type_code', '!=', 'cash'), # Do not allow Liquidity / Cash accounts
        '|', ('type', '!=', 'regular'), ('user_type_code', '!=', 'stock'), # Do not allow Regular / Stock accounts
    ]
}

import res_currency
import account
import invoice
import account_voucher
import account_move_line
import account_analytic_line
import account_bank_statement
import report
import wizard

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
