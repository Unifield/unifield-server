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

class account_statement_from_invoice_lines(osv.osv_memory):
    _name = 'account.statement.from.invoice.lines'
    _description = 'Generate Entries by Statement from Invoices'
    _inherit = 'account.statement.from.invoice.lines'

account_statement_from_invoice_lines()

class account_statement_from_invoice(osv.osv_memory):
    _name = 'account.statement.from.invoice'
    _description = 'Generate Entries by Statement from Invoices'
    _inherit = 'account.statement.from.invoice'

account_statement_from_invoice()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
