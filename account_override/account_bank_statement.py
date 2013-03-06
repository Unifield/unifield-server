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

class account_bank_statement(osv.osv):
    _name = 'account.bank.statement'
    _inherit = 'account.bank.statement'

    _columns = {
        'prev_reg_id': fields.many2one('account.bank.statement', string="Previous register", required=False, readonly=True, 
            help="This fields give the previous register from which this one is linked."),
        'next_reg_id': fields.one2many('account.bank.statement', 'prev_reg_id', string="Next register", readonly=True, 
            help="This fields give the next register if exists."),
    }

account_bank_statement()

class account_bank_statement_line(osv.osv):
    _name = 'account.bank.statement.line'
    _inherit = 'account.bank.statement.line'

    _columns = {
        'ref': fields.char('Reference', size=50), # UF-1613 - add reference field from 32 to 50 chars
    }

account_bank_statement_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
