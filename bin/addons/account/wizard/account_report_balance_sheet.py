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

    def _get_def_reserve_account(self, cr, uid, context=None):
        chart_id = self._get_account(cr, uid, context=context)
        res = self.onchange_chart_id(cr, uid, [], chart_id, context=context)
        if not res:
            return False
        return res['value']['reserve_account_id']

    _columns = {
        'export_format': fields.selection([('xls', 'Excel'), ('pdf', 'PDF')], string="Export format", required=True),
        'reserve_account_id': fields.many2one('account.account', 'Reserve & Profit/Loss Account',
                                      required=True,
                                      help='This Account is used for transfering Profit/Loss ' \
                                           '(Profit: Amount will be added, Loss: Amount will be duducted), ' \
                                           'which is calculated from Profilt & Loss Report',
                                      #domain = [('type','=','payable')]),
                                      domain = ['|',('type','=','payable'),'&',('type','=','other'),('user_type_code','=','equity')]),
        'instance_ids': fields.many2many('msf.instance', 'account_report_general_ledger_instance_rel', 'instance_id', 'argl_id', 'Proprietary Instances'),
    }

    _defaults={
        'export_format': 'pdf',
        'journal_ids': [],
        'reserve_account_id': _get_def_reserve_account,
    }

    def onchange_chart_id(self, cr, uid, ids, chart_id, context=None):
        if not chart_id:
            return {}
        account = self.pool.get('account.account').browse(cr, uid, chart_id , context=context)
        if not account.company_id.property_reserve_and_surplus_account:
            return {'value': {'reserve_account_id': False}}
        return {'value': {'reserve_account_id': account.company_id.property_reserve_and_surplus_account.id}}


    def _print_report(self, cr, uid, ids, data, context=None):
        if context is None:
            context = {}
        update_fields = [
            'export_format',
            'reserve_account_id',
            'instance_ids',
        ]
        data['form'].update(self.read(cr, uid, ids, update_fields)[0])
        if not data['form']['reserve_account_id']:
            raise osv.except_osv(_('Warning'),_('Please define the Reserve and Profit/Loss account for current user company !'))
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
