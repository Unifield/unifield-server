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
from decimal_precision import get_precision
from time import strftime

class hr_payroll(osv.osv):
    _name = 'hr.payroll.msf'
    _description = 'Payroll'

    _columns = {
        'date': fields.date(string='Date', required=True),
        'account_id': fields.many2one('account.account', string="Account", required=True),
        'period_id': fields.many2one('account.period', string="Period", required=True),
        'employee_id': fields.many2one('hr.employee', string="Employee"),
        'partner_id': fields.many2one('res.partner', string="Partner"),
        'journal_id': fields.many2one('account.journal', string="Journal"),
        'employee_id_number': fields.char(string='Employee ID', size=255),
        'name': fields.char(string='Description', size=255),
        'ref': fields.char(string='Reference', size=255),
        'amount': fields.float(string='Amount', digits_compute=get_precision('Account')),
        'currency_id': fields.many2one('res.currency', string="Currency", required=True),
        'state': fields.selection([('draft', 'Draft'), ('valid', 'Validated')], string="State", required=True),
    }

    _order = 'employee_id, date desc'

    _defaults = {
        'date': lambda *a: strftime('%Y-%d-%m'),
        'state': lambda *a: 'draft',
    }

hr_payroll()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
