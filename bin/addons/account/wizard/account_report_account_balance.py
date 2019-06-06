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

class account_balance_report(osv.osv_memory):
    _inherit = "account.common.account.report"
    _name = 'account.balance.report'
    _description = 'Trial Balance Report'

    _columns = {
        'initial_balance': fields.boolean("Include initial balances",
            help='It adds initial balance row on report which display previous sum amount of debit/credit/balance'),
        'instance_ids': fields.many2many('msf.instance', 'account_report_general_ledger_instance_rel', 'instance_id', 'argl_id', 'Proprietary Instances'),
        'export_format': fields.selection([('xls', 'Excel'), ('pdf', 'PDF')], string="Export format", required=True),

        # us-334: General ledger report improvements
        'account_type': fields.selection([
            ('all', 'All'),
            ('pl','Profit & Loss'),
            ('bl','Balance Sheet'),
        ], 'B/S / P&L account', required=True),

        'reconciled': fields.selection([
            ('empty', ''),
            ('yes', 'Yes'),
            ('no', 'No'),
        ], "Reconciled",
        help="filter will apply only on the B/S accounts except for the non reconciliable account like 10100 and 10200 which will never be displayed per details"),
        'reconcile_date': fields.date("At"),

        'open_items': fields.many2one('account.period', string='Open Items at', domain=[('state', '!=', 'created')]),
        
        'account_ids': fields.many2many('account.account',
            'account_report_general_ledger_account_account_rel',
            'report_id', 'account_id', 'Accounts'),

        'filter': fields.selection([
            ('filter_no', 'No Filters'),
            ('filter_date_doc', 'Document Date'),
            ('filter_date', 'Posting Date'),
            ('filter_period', 'Periods')
        ], "Filter by", required=True),
    }

    def _get_journals(self, cr, uid, context=None):
        return self.pool.get('account.journal').search(cr, uid, [], context=context)

    _defaults = {
        'initial_balance': False,
        'export_format': 'pdf',
        'account_type': 'all',
        'reconciled': 'empty',
        'journal_ids': _get_journals,
        'display_account': 'bal_movement',  # by default only result with JIs
    }

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        context['report_cross_fy'] = True
        return super(account_balance_report, self).default_get(cr, uid, fields, context=context)

    def remove_journals(self, cr, uid, ids, context=None):
        if ids:
            self.write(cr, uid, ids, { 'journal_ids': [(6, 0, [])] },
                       context=context)
        return {}

    def _print_report(self, cr, uid, ids, data, context=None):
        """data = self.pre_print_report(cr, uid, ids, data, context=context)
        return {'type': 'ir.actions.report.xml', 'report_name': 'account.account.balance', 'datas': data}
        """
        # US-334: General ledger and Trial balance report common parser/templates
        if context is None:
            context = {}
        data = self.pre_print_report(cr, uid, ids, data, context=context)
        data['form']['report_mode'] = 'tb'  # trial balance mode

        data['form']['initial_balance'] = False
        form_fields = [ 'initial_balance', 'instance_ids', 'export_format',
            'account_type', 'account_ids', 'reconciled', 'reconcile_date', 'open_items']
        data['form'].update(self.read(cr, uid, ids, form_fields)[0])

        if not data['form']['fiscalyear_id']:# GTK client problem onchange does not consider in save record
            data['form']['initial_balance'] = False

        if data['form']['journal_ids']:
            default_journals = self._get_journals(cr, uid, context=context)
            if default_journals:
                if set(default_journals) == set(data['form']['journal_ids']):
                    data['form']['all_journals'] = True

        action = {
            'type': 'ir.actions.report.xml',
            'report_name': 'account.general.ledger_landscape_tb',  # PDF
            'datas': data,
        }
        if data['form']['export_format'] \
           and data['form']['export_format'] == 'xls':
            action['report_name'] = 'account.general.ledger_xls'
        return action

account_balance_report()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
