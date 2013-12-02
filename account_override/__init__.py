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
    ],
    # HEADER OF:
    #+ Supplier Invoice
    #+ Direct Invoice
    #+ Supplier refund
    'in_invoice': [
        ('type', '!=', 'view'),
        ('type', '=', 'payable'),
        ('type_for_register', '!=', 'donation'),
    ],
    # HEADER OF:
    #+ Stock Transfer Voucher
    #+ Customer Refund
    #+ Debit Notes
    'out_invoice': [
        ('type', '!=', 'view'),
        ('type', '!=', 'receivable'),
    ],
    # HEADER OF donation
    'donation_header': [
        ('type', '!=', 'view'),
        ('type_for_register', '=', 'donation'),
    ],
    # LINES OF:
    #+ Supplier invoice
    #+ Direct invoice
    #+ Supplier refund
    #+ Stock transfer voucher
    #+ Customer refund
    #+ Debit notes
    'invoice_lines': [
        ('type', '!=', 'view'),
        ('is_not_hq_correctible', '!=', True),
        '|', ('type', '!=', 'liquidity'), ('user_type_code', '!=', 'cash'), # Do not allow Liquidity / Cash accounts
        '|', ('type', '!=', 'regular'), ('user_type_code', '!=', 'stock'), # Do not allow Regular / Stock accounts
    ],
    # LINES OF donation
    'donation_lines': [
        ('type', '!=', 'view'),
        ('user_type_code', '=', 'expense'),
        ('report_type', '=', 'none'), # To only use Expense extra-accounting accounts
    ],
    # HEADER OF Intermission Voucher IN/OUT
    'intermission_header': [
        ('is_intermission_counterpart', '=', True),
    ],
    # LINES OF intermission vouchers
    'intermission_lines': [
        ('type', '!=', 'view'),
        ('is_not_hq_correctible', '=', False),
    ],
    # RECURRING MODELS
    'recurring_lines': [
        ('type', '!=', 'view'),
        ('is_not_hq_correctible', '=', False),
    ],
    # ACCRUALS
    'accruals': [
        ('type', '!=', 'view'),
        ('is_not_hq_correctible', '=', False),
    ],
    # PAYROLLS
    'payroll_lines': [
        ('type', '!=', 'view'),
        ('is_not_hq_correctible', '=', False),
    ],
    # HQ ENTRIES
    'hq_lines': [
        ('type', '!=', 'view'),
        ('user_type_code', '=', 'expense'), 
        ('user_type.report_type', '!=', 'none'), # Exclude non-extra accounting expense accounts
    ],
    # MANUEL JOURNAL ENTRIES
    'account_move_lines': [
        '|', ('type', '!=', 'liquidity'), ('user_type_code', '!=', 'cash'), # Do not allow Liquidity / Cash accounts
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
