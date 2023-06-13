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
from base import currency_date
from tools.translate import _
from . import ACCOUNT_RESTRICTED_AREA


class res_company(osv.osv):
    _name = 'res.company'
    _inherit = 'res.company'

    def _get_currency_date_type(self, cr, uid, ids, name, args, context=None):
        """
        Returns the type of date used for functional amount computation in this instance
        """
        res = {}
        for c_id in ids:
            res[c_id] = currency_date.get_date_type(self, cr) == 'document' and _('Document Date') or _('Posting Date')
        return res

    def _get_currency_date_beginning(self, cr, uid, ids, name, args, context=None):
        """
        Returns the date from when the functional amount computation is based on the document date, if applicable
        """
        res = {}
        for c_id in ids:
            res[c_id] = currency_date.get_date_type(self, cr) == 'document' and currency_date.BEGINNING or False
        return res

    _columns = {
        'import_invoice_default_account': fields.many2one('account.account', string="Re-billing Inter-section account",
                                                          help="Default account for an import invoice on a Debit note"),
        'intermission_default_counterpart': fields.many2one('account.account', string="Intermission counterpart",
                                                            help="Default account used for partner in Intermission Voucher IN/OUT"),
        'additional_allocation': fields.boolean('Additional allocation condition?', help="If you check this attribute, analytic allocation will be required for income accounts with an account code starting with \"7\"; if unchecked, the analytic allocation will be required for all income accounts."),
        'revaluation_default_account': fields.many2one('account.account', string="Revaluation account",
                                                       help="Default account used for revaluation"),
        'currency_date_type': fields.function(_get_currency_date_type, method=True, type='char',
                                              string='Date Type Used', store=False, readonly=1),
        'currency_date_beginning': fields.function(_get_currency_date_beginning, method=True, type='date',
                                                   string='Since', store=False, readonly=1),
        'cheque_debit_account_id': fields.many2one('account.account', 'Cheque Default Debit Account',
                                                   domain=ACCOUNT_RESTRICTED_AREA['journals']),
        'cheque_credit_account_id': fields.many2one('account.account', 'Cheque Default Credit Account',
                                                    domain=ACCOUNT_RESTRICTED_AREA['journals']),
        'bank_debit_account_id': fields.many2one('account.account', 'Bank Default Debit Account',
                                                 domain=ACCOUNT_RESTRICTED_AREA['journals']),
        'bank_credit_account_id': fields.many2one('account.account', 'Bank Default Credit Account',
                                                  domain=ACCOUNT_RESTRICTED_AREA['journals']),
        'cash_debit_account_id': fields.many2one('account.account', 'Cash Default Debit Account',
                                                 domain=ACCOUNT_RESTRICTED_AREA['journals']),
        'cash_credit_account_id': fields.many2one('account.account', 'Cash Default Credit Account',
                                                  domain=ACCOUNT_RESTRICTED_AREA['journals']),
        'has_move_regular_bs_to_0': fields.boolean("Move regular B/S account to 0"),
        'has_book_pl_results': fields.boolean("Book the P&L results"),
        'display_hq_system_accounts_buttons': fields.boolean("Display HQ system accounts mapping?", help="Display HQ system accounts on JI and AJI list views"),
    }

    _defaults = {
        'has_move_regular_bs_to_0': False,
        'has_book_pl_results': False,
        'display_hq_system_accounts_buttons': False,
    }


res_company()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
