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
from tools.translate import _

import time

class account_bs_report(osv.osv_memory):
    """
    This wizard will provide the account balance sheet report by periods, between any two dates.
    """
    _name = 'account.bs.report'
    _inherit = "account.common.account.report"
    _description = 'Account Balance Sheet Report'

    _columns = {
        'export_format': fields.selection([('xls', 'Excel'), ('pdf', 'PDF')], string="Export format", required=True),
        'instance_ids': fields.many2many('msf.instance', 'account_report_general_ledger_instance_rel', 'instance_id', 'argl_id', 'Proprietary Instances'),
    }

    _defaults={
        'export_format': 'pdf',
        'journal_ids': [],
    }

    def _check(self, cr, uid, context=None, data=None):
        # US-227/2bis: check cpy year closing B/S account are set
        cpy_rec = self.pool.get('res.users').browse(cr, uid, [uid],
            context=context)[0].company_id
        bs_accounts_ko = []
        if not cpy_rec.ye_pl_pos_debit_account:
            bs_accounts_ko.append(_('Debit Account for P&L>0 (B/S account)'))
        if not cpy_rec.ye_pl_ne_credit_account:
            bs_accounts_ko.append(_('Credit Account P&L<0 (B/S account)'))
        if bs_accounts_ko:
            raise osv.except_osv(_('Warning'),
                _('You must set following company account(s)'
                    ' to use this report: %s') % (', '.join(bs_accounts_ko), ))

        if data and 'form' in data:
            data['form'].update({
                'bs_debit_account_id': cpy_rec.ye_pl_pos_debit_account.id,
                'bs_credit_account_id': cpy_rec.ye_pl_ne_credit_account.id,
            })

    def _print_report(self, cr, uid, ids, data, context=None):
        if context is None:
            context = {}
        self._check(cr, uid, context=context, data=data)

        update_fields = [
            'export_format',
            'instance_ids',
        ]

        data['form'].update(self.read(cr, uid, ids, update_fields)[0])
        data = self.pre_print_report(cr, uid, ids, data, context=context)
        instance = self.pool.get('ir.sequence')._get_instance(cr, uid)
        data['target_filename'] = _('Balance Sheet_%s_%s') % (instance, time.strftime('%Y%m%d'))

        if data['form']['export_format'] \
           and data['form']['export_format'] == 'xls':
            # US-227: excel version
            return {
                'type': 'ir.actions.report.xml',
                'report_name': 'account.balance.sheet_xls',
                'datas': data,
            }

        # PDF version (portrait version 'account.balancesheet' not used now)
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'account.balancesheet.horizontal',
            'datas': data,
        }

account_bs_report()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
