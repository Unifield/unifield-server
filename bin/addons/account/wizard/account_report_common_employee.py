# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2022 TeMPO Consulting,MSF
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

from osv import osv, fields


class account_common_employee_report(osv.osv_memory):
    _name = 'account.common.employee.report'
    _description = 'Account Common Employee Report'
    _inherit = "account.common.partner.report"
    _columns = {
        'result_selection': fields.selection([('customer', 'Receivable Accounts'),
                                              ('supplier', 'Payable Accounts'),
                                              ('customer_supplier', 'Receivable and Payable Accounts')],
                                             "Employee's", required=True),
        'account_domain': fields.char('Account domain', size=250, required=False),
    }

    def onchange_result_selection(self, cr, uid, ids, result_selection, context=None):
        """
        Adapts the domain of the account according to the selections made by the user
        Note: directly changing the domain on the many2many field "account_ids" doesn't work in that case so we use the
        invisible field "account_domain" to store the domain and use it in the view...
        """
        if context is None:
            context = {}
        res = {}
        if result_selection == 'supplier':
            account_domain = [('type', 'in', ['payable'])]
        elif result_selection == 'customer':
            account_domain = [('type', 'in', ['receivable'])]
        else:
            account_domain = [('type', 'in', ['payable', 'receivable'])]
        res['value'] = {'account_domain': '%s' % account_domain}
        return res

    def onchange_payment_method(self, cr, uid, ids, payment_method, context=None):
        """
        Exclude expatriate when one method of payment is chosen and only display Nat staff using this method of payment.
        """
        if context is None:
            context = {}
        res = {}
        if payment_method and payment_method != 'blank':
            res['value'] = {'employee_type': 'local'}
        return res

    def onchange_employee_type(self, cr, uid, ids, employee_type, context=None):
        """
        When expatriate is selected set method of payment to blank
        """
        if context is None:
            context = {}
        res = {}
        if not employee_type or employee_type in ('', 'ex'):
            res['value'] = {'payment_method': 'blank'}
        return res

    _defaults = {
        'result_selection': 'customer',
    }


account_common_employee_report()

#vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
