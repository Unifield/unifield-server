# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 MSF, TeMPO Consulting
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

{
    "name" : "MSF Financing Module",
    "version" : "1.0",
    "author" : "MSF, TeMPO Consulting",
    "description" : """
    Finance Extension using analytic and account modules
    """,
    "website": "http://unifield.msf.org",
    # account_voucher: need it to change account_voucher object. Note that account_voucher is the dependance of account_payment which is in depandancy of register_accounting.
    # account_msf: was deleted because of a dependance loop. But don't know why account_msf was in dependancy of account_override module (now finance one)
    "depends" : ["analytic_override", "account_override", "purchase_msf"],
    "category" : "Generic Modules/Accounting",
    "init_xml" : [],
    "demo_xml" : [],
    "update_xml" : [
        'board_account_view.xml',
        'account_view.xml',
        'account_analytic_line_view.xml',
        'account_sequence.xml',
        'wizard/account_report_partner_balance_tree_view.xml', # uf-1715
        'wizard/fo_follow_up_finance_wizard_view.xml',
        'cash_request_data.xml',
        'cash_request_view.xml',
        'wizard/account_report_employee_balance_tree_view.xml',  # US-6392
    ],
    'test': [],
    'installable': True,
    'active': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
