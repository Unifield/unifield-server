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

    # Note: some domains are defined directly inside the method _search_restricted_area (account_override/account.py)

    # REGISTER LINES
    'register_lines': [
        ('type', '!=', 'view'),
        ('is_not_hq_correctible', '!=', True),
        '!', ('code', '=like', '8%'),  # US-791 exclude 8 accounts
        '!', ('code', '=like', '9%'),  # US-791 exclude 9 accounts
        '|', ('type', '!=', 'liquidity'), ('user_type_code', '!=', 'cash'), # Do not allow Liquidity / Cash accounts
        '|', ('type', '!=', 'other'), ('user_type_code', '!=', 'stock'), # Do not allow Regular / Stock accounts
        '|', ('user_type_code', '!=', 'expense'), ('user_type.report_type', '!=', 'none'), # Disallow extra-accounting expenses accounts
    ],
    # CASH RETURN - ADVANCE LINES
    'cash_return': [
        ('type', '!=', 'view'),
        ('type_for_register', '!=', 'donation'),
        '|', '|', '|',
        ('user_type_code', 'in', ['income', 'expense']),
        '&', ('type', '=', 'receivable'), ('user_type_code', 'in', ['receivables', 'cash']),
        '&', ('type', '=', 'other'), ('user_type_code', '=', 'cash'),
        '&', ('type', '=', 'payable'), ('user_type_code', '=', 'payables'),
        ('user_type_report_type', '!=', 'none'),
        ('is_not_hq_correctible', '=', False),
    ],
    # HEADER OF:
    #+ Supplier Invoice
    #+ Direct Invoice
    #+ Supplier refund
    #+ Intersection Supplier Invoice
    #+ Intersection Supplier Refund
    'in_invoice': [
        ('type', '!=', 'view'),
        # Either Payable/Payables or Payable/Tax or Regular/Debt or Regular/Cash or Regular/Income accounts
        '|',
        '&', ('type', '=', 'payable'), ('user_type_code', 'in', ['payables', 'tax']),
        '&', ('type', '=', 'other'), ('user_type_code', 'in', ['debt', 'cash', 'income']),
        ('type_for_register', 'not in', ['donation', 'advance', 'transfer', 'transfer_same']),
    ],
    # HEADER OF:
    #+ Stock Transfer Voucher
    #+ Stock Transfer Refund
    #+ Customer Refund
    #+ Debit Notes
    'out_invoice': [
        ('type', '!=', 'view'),
        # Either Receivable/Receivables or Receivable/Cash or Regular/Cash or Regular/Income accounts
        '|', '&', ('type', '=', 'receivable'), ('user_type_code', 'in', ['receivables','cash']),
        '&', ('type', '=', 'other'), ('user_type_code', 'in', ['cash', 'income']),
        ('type_for_register', 'not in', ['advance', 'transfer', 'transfer_same']),
    ],
    # HEADER OF donation
    'donation_header': [
        ('type', '!=', 'view'),
        ('user_type_code', '=', 'payables'),
        ('type', '=', 'payable'),
        ('type_for_register', '=', 'donation'),
    ],
    # LINES OF:
    #+ Supplier invoice
    #+ Direct invoice
    #+ Supplier refund
    #+ Intersection supplier invoice
    #+ Intersection supplier refund
    #+ Stock transfer voucher
    #+ Stock transfer refund
    #+ Customer refund
    #+ Debit notes
    'invoice_lines': [
        ('type', 'not in', ['view', 'liquidity']), # Do not allow liquidity accounts
        ('is_not_hq_correctible', '!=', True),
        ('type_for_register', '!=', 'donation'),
        '|', ('type', '!=', 'other'), ('user_type_code', '!=', 'stock'), # Do not allow Regular / Stock accounts
        '|', ('user_type_code', '!=', 'expense'), ('user_type.report_type', '!=', 'none'), # Disallow extra-accounting expenses accounts
        ('type_for_register', 'not in', ['advance', 'transfer', 'transfer_same']),
    ],
    # LINES OF donation
    'donation_lines': [
        ('type', '!=', 'view'),
        ('type', '=', 'other'),
        ('user_type_code', '=', 'expense'),
        ('user_type.report_type', '=', 'none'), # Only extra-accounting expenses
        ('type_for_register', '=', 'donation'),
    ],
    # Commitment voucher lines
    'commitment_lines': [
        ('type', '!=', 'view'),
        ('user_type_code', '=', 'expense'),
        '|', ('user_type_code', '!=', 'expense'), ('user_type.report_type', '!=', 'none'), # To only use Expense extra-accounting accounts
    ],
    # HEADER OF Intermission Voucher IN/OUT
    'intermission_header': [
        ('is_intermission_counterpart', '=', True),
    ],
    # LINES OF intermission vouchers
    'intermission_lines': [
        ('type', '!=', 'view'),
        ('is_not_hq_correctible', '=', False),
        ('user_type_code', 'in', ['expense', 'income', 'receivables']),
        ('user_type.report_type', '!=', 'none'), # To only use Expense extra-accounting accounts
        ('type_for_register', 'not in', ['advance', 'transfer', 'transfer_same']),
    ],
    # RECURRING MODELS
    'recurring_lines': [
        ('type', '!=', 'view'),
        ('is_not_hq_correctible', '=', False),
        '|',
        '|', '&', ('user_type_code', '=', 'receivables'), ('type', '=', 'receivable'), '&', ('user_type_code', '=', 'expense'), ('user_type.report_type', '!=', 'none'),  # Receivable/Receivable allowed + expense accounts (without extra-accounting) allowed
        '&', ('user_type_code', '=', 'asset'), ('type', '=', 'other'),  # US-10090 Allow Type "Asset" and Internal Type "Regular"
    ],

    # ACCRUALS - expense lines
    # WARNING: keep in mind that the AD button is always displayed in the Accrual Expense Lines, so if the following
    # domain is modified, this may have to be adapted.
    'accruals': [
        ('type', '!=', 'view'),
        ('is_not_hq_correctible', '=', False),
        ('user_type_code', '=', 'expense'),
        '|', ('user_type_code', '!=', 'expense'), ('user_type.report_type', '!=', 'none'), # Do not allow extra-expense accounts
    ],
    # ACCRUALS - accrual account
    'accruals_accrual': [
        ('type', '!=', 'view'),
        ('is_not_hq_correctible', '=', False),
        ('accrual_account', '=', True),
    ],
    # HQ ENTRIES
    # /!\ The accounts allowed at import are different from the ones allowed for correction
    'hq_lines_import': [
        ('type', '!=', 'view'),
        '|', ('user_type_code', '!=', 'expense'), ('user_type.report_type', '!=', 'none'),  # Exclude extra-accounting expense accounts
        ('type_for_register', '!=', 'donation'),
        #('is_not_hq_correctible', '=', False), # UF-2312: not possibleto add this domain because WE SHOULD ALLOW "Not HQ Correctible" account during the import
    ],
    'hq_lines_correction': [
        ('type', '!=', 'view'),
        ('type_for_register', '!=', 'donation'),
        ('is_not_hq_correctible', '=', False),
        '|',
        ('user_type.code', '=', 'income'),
        '&', ('user_type.code', '=', 'expense'), ('user_type.report_type', '!=', 'none'),  # Exclude extra-accounting expense accounts
        # note : filter_active isn't set to True here as that would prevent to "Change Account" to an account
        # currently inactive but active at the date of the entry
    ],
    # MANUEL JOURNAL ENTRIES
    'account_move_lines': [
        ('type', 'not in', ['view', 'consolidation', 'closed']),
        ('filter_active', '=', True),
        '!', ('code', '=like', '8%'),  # US-791 exclude 8 accounts
        '!', ('code', '=like', '9%'),  # US-791 exclude 9 accounts
        '|', ('type', '!=', 'liquidity'), ('user_type_code', '!=', 'cash'), # Do not allow Liquidity / Cash accounts
        ('is_not_hq_correctible', '=', False),
    ],
    # FINANCING CONTRACT - REPORTING LINES
    'contract_reporting_lines': [
        ('account_id.user_type_code', 'in', ['income', 'expense']),
        ('account_id.user_type_report_type', '!=', 'none'),
    ],
    # PARTNER - DONATION DEFAULT ACCOUNT
    'partner_donation': [
        ('type', '!=', 'view'),
        ('type', '=', 'payable'),
        ('user_type_code', '=', 'payables'),
        ('type_for_register', '=', 'donation'),
    ],
    # PARTNER - PAYABLE DEFAULT ACCOUNT
    'partner_payable': [
        ('type', '!=', 'view'),
        ('type', 'in', ['payable','other']),
        ('user_type_code', 'in', ['payables', 'tax','cash']),
        ('type_for_register', '!=', 'donation'),
    ],
    # PARTNER - RECEIVABLE DEFAULT ACCOUNT
    'partner_receivable': [
        ('type', '!=', 'view'),
        # Either Receivable accounts or Regular / Cash accounts
        '|', ('type', '=', 'receivable'), '&', ('type', '=', 'other'), ('user_type_code', '=', 'cash'),
    ],
    # PRODUCT - DONATION ACCOUNT
    'product_donation': [
        ('type', '!=', 'view'),
        ('user_type_code', '=', 'expense'),
        ('type_for_register', '=', 'donation'),
    ],
    # PRODUCT CATEGORY - DONATION ACCOUNT
    'product_category_donation': [
        ('type', '!=', 'view'),
        ('user_type_code', '=', 'expense'),
        ('type_for_register', '=', 'donation'),
    ],
    # JOURNALS
    'journals': [
        ('type', '!=', 'view'),
        ('user_type_code', '=', 'cash'),
        ('type', '=', 'liquidity'),
    ],
    # CORRECTION WIZARD LINES
    'correction_wizard': [
        ('type', '!=', 'view'),
        ('is_not_hq_correctible', '=', False), # Do not allow user to select accounts with "Not HQ correctible" set to True
        '!', ('code', '=like', '8%'),  # UTP-1187 exclude 8/9 accounts
        '!', ('code', '=like', '9%'),  # UTP-1187 exclude 8/9 accounts
        ('code', 'not in', ['10100', '10200', '10210']),  # UTP-1187 exclude liquidity / cash (10100, 10200, 10210) accounts
        ('is_not_hq_correctible', '!=', True)  # UTP-1187 exclude the "Prevent correction on account codes" attribute set to "True" accounts
    ],
}

from . import res_company
from . import res_currency
from . import res_partner
from . import period
from . import account
from . import invoice
from . import product
from . import account_move_line
from . import account_analytic_line
from . import account_bank_statement
from . import report
from . import wizard
from . import finance_export
from . import account_invoice_sync
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
