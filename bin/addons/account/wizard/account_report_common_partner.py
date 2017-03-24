# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

class account_common_partner_report(osv.osv_memory):
    _name = 'account.common.partner.report'
    _description = 'Account Common Partner Report'
    _inherit = "account.common.report"
    _columns = {
        'result_selection': fields.selection([('customer','Receivable Accounts'),
                                              ('supplier','Payable Accounts'),
                                              ('customer_supplier','Receivable and Payable Accounts')],
                                              "Partner's", required=True),
        'account_domain': fields.char('Account domain', size=250, required=False),
    }

    _defaults = {
        'result_selection': 'customer',
    }

    def onchange_result_selection_or_tax(self, cr, uid, ids, result_selection, exclude_tax, context=None):
        """
        Adapt the domain of the account according to the selections made by the user
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
        if exclude_tax:
            account_domain.append(('user_type_code', '!=', 'tax'))
        res['value'] = {'account_domain': '%s' % account_domain}
        return res

    def pre_print_report(self, cr, uid, ids, data, context=None):
        if context is None:
            context = {}
        data['form'].update(self.read(cr, uid, ids, ['result_selection'], context=context)[0])
        return data

account_common_partner_report()

#vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: