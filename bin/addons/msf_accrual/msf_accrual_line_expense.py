# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2022 MSF, TeMPO Consulting.
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

from osv import fields, osv


class msf_accrual_line_expense(osv.osv):
    # this object corresponds to the "lines" of the "msf.accrual.line"
    _name = 'msf.accrual.line.expense'

    _columns = {
        'line_number': fields.integer(string='Line Number'),
        'description': fields.char('Description', size=64, required=True),
        'expense_account_id': fields.many2one('account.account', 'Expense Account', required=True,
                                              domain=[('restricted_area', '=', 'accruals')]),
        'accrual_amount': fields.float('Accrual Amount', required=True),
        'accrual_line_id': fields.many2one('msf.accrual.line', 'Accrual Line', required=True, ondelete='cascade'),
    }

    _order = 'line_number'


msf_accrual_line_expense()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
