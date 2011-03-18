#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution    
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    Author: Tempo Consulting (<http://www.tempo-consulting.fr/>), MSF
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

{
    "name" : "Cash Register",
    "version" : "1.0",
    "description" : """
        This module aims to add Cash Register Attributes for Sprint 1 in Unifield project for MSF.
    """,
    "author" : "Tempo Consulting",
    'website': 'http://tempo-consulting.fr',
    "category" : "Tools",
    "depends" : ["base", "account", "hr", "account_payment"],
    "init_xml" : [],
    "update_xml" : [
        'security/ir.model.access.csv',
        'account_view.xml',
        'account_bank_statement_workflow.xml',
        'wizard/wizard_closing_cashbox.xml',
        'wizard/wizard_cashbox_write_off.xml',
        'wizard/wizard_temp_posting.xml',
        'wizard/wizard_hard_posting.xml',
        'account_cash_statement_sequence.xml',
    ],
    "demo_xml" : [],
    "test": [
        'test/account_cash_statement.yml',
        'test/account_bank_statement.yml',
        'test/account_cheque_register.yml',
        'test/cash_and_bank_transfers.yml',
    ],
    "installable": True,
    "active": False
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
