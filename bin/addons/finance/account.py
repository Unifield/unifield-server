#-*- coding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 TeMPO Consulting, MSF. All Rights Reserved
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
from tools.translate import _


class account_account(osv.osv):
    _name = "account.account"
    _inherit = "account.account"

    def _get_is_analytic_addicted(self, cr, uid, ids, field_name, arg, context=None):
        """
        An account is dependant on analytic distribution in these cases:
        - the account is expense (user_type_code == 'expense')

        Some exclusive cases can be add in the system if you configure your company:
        - either you also take all income account (user_type_code == 'income')
        - or you take accounts that are income + 7xx (account code begins with 7)
        """
        # Some checks
        if context is None:
            context = {}
        res = {}
        company_account_active = False
        company = self.pool.get('res.users').browse(cr, uid, uid).company_id
        if company and company.additional_allocation:
            company_account_active = company.additional_allocation
        company_account = 7 # User for accounts that begins by "7"
        # Prepare result
        for account in self.read(cr, uid, ids, ['user_type_code', 'code'], context=context):
            account_id = account.get('id', False)
            user_type = account.get('user_type_code', False)
            code = account.get('code')
            res[account_id] = self.is_analytic_addicted(cr, uid, user_type, code, company_account, company_account_active)
        return res

    def is_analytic_addicted(self, cr, uid, user_type, code, company_account, company_account_active):
        res = False
        if not user_type:
            return res
        if user_type == 'expense':
            res = True
        elif user_type == 'income':
            if not company_account_active:
                res = True
            elif company_account_active and code.startswith(str(company_account)):
                res = True
        return res

    def _search_is_analytic_addicted(self, cr, uid, ids, field_name, args, context=None):
        """
        Search analytic addicted accounts regarding same criteria as those from _get_is_analytic_addicted method.
        """
        # Checks
        if context is None:
            context = {}
        arg = []
        company_account_active = False
        company = self.pool.get('res.users').browse(cr, uid, uid).company_id
        if company and company.additional_allocation:
            company_account_active = company.additional_allocation
        company_account = "7"
        for x in args:
            if x[0] == 'is_analytic_addicted' and ((x[1] in ['=', 'is'] and x[2] is True) or (x[1] in ['!=', 'is not', 'not'] and x[2] is False)):
                arg.append(('|'))
                arg.append(('user_type.code', '=', 'expense'))
                if company_account_active:
                    arg.append(('&'))
                arg.append(('user_type.code', '=', 'income'))
                if company_account_active:
                    arg.append(('code', '=like', '%s%%' % company_account))
            elif x[0] == 'is_analytic_addicted' and ((x[1] in ['=', 'is'] and x[2] is False) or (x[1] in ['!=', 'is not', 'not'] and x[2] is True)):
                arg.append(('user_type.code', '!=', 'expense'))
                if company_account_active:
                    arg.append(('|'))
                    arg.append(('user_type.code', '!=', 'income'))
                    arg.append(('code', 'not like', '%s%%' % company_account))
                else:
                    arg.append(('user_type.code', '!=', 'income'))
            elif x[0] != 'is_analytic_addicted':
                arg.append(x)
            else:
                raise osv.except_osv(_('Error'), _('Operation not implemented!'))
        return arg

    def _get_accounts_from_company(self, cr, uid, ids, context=None):
        return self.pool.get('account.account').search(cr, uid, [('user_type.code', '=', 'income')], context=context)

    _columns = {
        'is_analytic_addicted': fields.function(
            _get_is_analytic_addicted, fnct_search=_search_is_analytic_addicted,
            method=True, type='boolean', string='Analytic-a-holic?', readonly=True,
            help="Is this account addicted on analytic distribution?",
            store={'res.company': (_get_accounts_from_company, ['additional_allocation'], 10),
                   'account.account': (lambda self, cr, uid, ids, c={}: ids, ['user_type_code', 'code'], 10)}),
    }

account_account()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
