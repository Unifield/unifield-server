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

from report import report_sxw
import datetime


class bank_reconciliation(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(bank_reconciliation, self).__init__(cr, uid, name, context=context)
        self.cr = cr
        self.uid = uid
        self.context = context
        self.localcontext.update({
            'get_amount_pending_cheque': self.get_amount_pending_cheque,
            'getNow': self.get_now,
        })

    def get_amount_pending_cheque(self, obj):
        '''
        Returns the amount of unreconciled cheques linked to the Bank journal selected
        and for the same period and the previous ones
        '''
        amount = 0
        aj_obj = self.pool.get('account.journal')
        abs_obj = self.pool.get('account.bank.statement')

        aj_args = [
            ('type', '=', 'cheque'),
            ('bank_journal_id', '=', obj.journal_id.id)
        ]
        aj_ids = aj_obj.search(self.cr, self.uid, aj_args, context=self.context)
        account_ids = []
        for journal in aj_obj.browse(self.cr, self.uid, aj_ids, context=self.context):
            account_ids += [journal.default_debit_account_id.id, journal.default_credit_account_id.id]

        period_ids = self.pool.get('account.period').\
            search(self.cr, self.uid, [('date_start', '<=', obj.period_id.date_start)])
        abs_args = [
            ('period_id', 'in', period_ids),
            ('journal_id', 'in', aj_ids),
        ]

        ids = abs_obj.search(self.cr, self.uid, abs_args, context=self.context)

        amvl_obj = self.pool.get('account.move.line')
        amvl_ids = amvl_obj.search(self.cr, self.uid, [('statement_id', 'in', ids), ('is_reconciled', '=', False),
                                                       ('account_id', 'in', account_ids)], context=self.context)
        # amount in booking currency
        for line in amvl_obj.read(self.cr, self.uid, amvl_ids, ['debit_currency', 'credit_currency'], context=self.context):
            amount += line['credit_currency']
            amount -= line['debit_currency']
        return amount

    def get_now(self, show_datetime=False):
        date_tools_obj = self.pool.get('date.tools')
        res = datetime.datetime.now()
        return date_tools_obj.datetime2orm(res) if show_datetime \
            else date_tools_obj.date2orm(res.date())


report_sxw.report_sxw('report.bank.reconciliation', 'account.bank.statement', 'addons/register_accounting/report/bank_reconciliation.rml', parser=bank_reconciliation)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
