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

from osv import fields, osv

class account_partner_ledger(osv.osv_memory):
    """
    This wizard will provide the partner Ledger report by periods, between any two dates.
    """
    _name = 'account.partner.ledger'
    _inherit = 'account.common.partner.report'
    _description = 'Account Partner Ledger'

    _columns = {
        'reconciled': fields.selection([
                        ('empty', ''),
                        ('yes', 'Yes'),
                        ('no', 'No'),
                    ], string='Reconciled'),
        'page_split': fields.boolean('One Partner Per Page', help='Display Ledger Report with One partner per page (PDF version only)'),
        'partner_ids': fields.many2many('res.partner', 'account_partner_ledger_partner_rel', 'wizard_id', 'partner_id',
                                        string='Partners', help='Display the report for specific partners only'),
        'only_active_partners': fields.boolean('Only active partners', help='Display the report for active partners only'),
        'instance_ids': fields.many2many('msf.instance', 'account_partner_ledger_instance_rel', 'wizard_id', 'instance_id',
                                         string='Proprietary Instances', help='Display the report for specific proprietary instances only'),
        'account_ids': fields.many2many('account.account', 'account_partner_ledger_account_rel', 'wizard_id', 'account_id',
                                        string='Accounts', help='Display the report for specific accounts only'),
        'tax': fields.boolean('Exclude tax', help="Exclude tax accounts from process"),
        'display_partner': fields.selection([('non-zero_balance', 'With balance is not equal to 0'),
                                             ('all', 'All Partners')], string='Display Partners'),
    }

    _defaults = {
       'reconciled': 'empty',
       'page_split': False,
       'result_selection': 'customer_supplier',
       'account_domain': "[('type', 'in', ['payable', 'receivable'])]",
       'only_active_partners': False,
       'tax': False, # UFTP-312: Add an exclude tax account possibility
       'fiscalyear_id': False,
       'display_partner': 'non-zero_balance',
    }

    def _print_report(self, cr, uid, ids, data, context=None):
        if context is None:
            context = {}
        data = self.pre_print_report(cr, uid, ids, data, context=context)
        data['form'].update(self.read(cr, uid, ids, ['reconciled', 'page_split', 'tax', 'partner_ids',
                                                     'only_active_partners', 'instance_ids', 'account_ids',
                                                     'display_partner'])[0])
        self._check_dates_fy_consistency(cr, uid, data, context)
        if data['form']['page_split']:
            return {
                'type': 'ir.actions.report.xml',
                'report_name': 'account.third_party_ledger',
                'datas': data,
            }
        return {
            'type': 'ir.actions.report.xml',
                'report_name': 'account.third_party_ledger_other',
                'datas': data,
        }

    def print_report_xls(self, cr, uid, ids, data, context=None):
        if context is None:
            context = {}
        data = {}
        data['keep_open'] = 1
        data['ids'] = context.get('active_ids', [])
        data['model'] = context.get('active_model', 'ir.ui.menu')
        data['form'] = self.read(cr, uid, ids, ['date_from',  'date_to',  'fiscalyear_id', 'journal_ids', 'period_from', 'period_to',  'filter',  'chart_account_id', 'target_move'])[0]
        used_context = self._build_contexts(cr, uid, ids, data, context=context)
        data['form']['periods'] = used_context.get('periods', False) and used_context['periods'] or []
        data['form']['used_context'] = used_context

        data = self.pre_print_report(cr, uid, ids, data, context=context)
        data['form'].update(self.read(cr, uid, ids, ['reconciled', 'page_split', 'tax', 'partner_ids',
                                                     'only_active_partners', 'instance_ids', 'account_ids',
                                                     'display_partner'])[0])
        self._check_dates_fy_consistency(cr, uid, data, context)
        return {
            'type': 'ir.actions.report.xml',
                'report_name': 'account.third_party_ledger_xls',
                'datas': data,
        }

account_partner_ledger()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
