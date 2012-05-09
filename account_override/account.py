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

from osv import osv
from osv import fields

class account_account(osv.osv):
    _name = "account.account"
    _inherit = "account.account"

    _columns = {
        'type_for_register': fields.selection([('none', 'None'), ('transfer', 'Transfer'), ('transfer_same','Transfer (same currency)'), 
            ('advance', 'Cash Advance'), ('payroll', 'Third party required - Payroll')], string="Type for Third Parties", required=True,
            help="""This permit to give a type to this account that impact registers. In fact this will link an account with a type of element 
            that could be attached. For an example make the account to be a transfer type will display only registers to the user in the Cash Register 
            when he add a new register line.
            """),
    }

    _defaults = {
        'type_for_register': lambda *a: 'none',
    }

account_account()

class account_move(osv.osv):
    _inherit = 'account.move'

    _columns = {
        'name': fields.char('Entry Sequence', size=64, required=True),
        'statement_line_ids': fields.many2many('account.bank.statement.line', 'account_bank_statement_line_move_rel', 'statement_id', 'move_id', 
            string="Statement lines", help="This field give all statement lines linked to this move."),
    }

account_move()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
