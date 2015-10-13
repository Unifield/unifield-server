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

class account_report_general_ledger(osv.osv_memory):
    _inherit = "account.common.account.report"
    _name = "account.report.general.ledger"
    _description = "General Ledger Report"

    _columns = {
        'initial_balance': fields.boolean("Include initial balances",
            help='It adds initial balance row on report which display previous sum amount of debit/credit/balance'),
        'amount_currency': fields.boolean("With Currency", help="It adds the currency column if the currency is different then the company currency"),
        'sortby': fields.selection([('sort_date', 'Date'), ('sort_journal_partner', 'Journal & Partner')], 'Sort By', required=True),
        'output_currency': fields.many2one('res.currency', 'Output Currency', required=True),
        'instance_ids': fields.many2many('msf.instance', 'account_report_general_ledger_instance_rel', 'instance_id', 'argl_id', 'Proprietary Instances'),
        #'export_format': fields.selection([('xls', 'Excel'), ('csv', 'CSV'), ('pdf', 'PDF')], string="Export format", required=True),
        'export_format': fields.selection([('xls', 'Excel'), ('pdf', 'PDF')], string="Export format", required=True),

        # us-334: General ledger report improvements
        'account_type': fields.selection([
            ('all', 'All'),
            ('pl','Profit & Loss'),
            ('bl','Balance Sheet'),
        ], 'B/S / P&L account', required=True),

        'unreconciled': fields.boolean("Unreconciled",
            help="filter will apply only on the B/S accounts except for the non reconciliable account like 10100 and 10200 which will never be displayed per details"),

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
        """exclude extra-accounting journals from this report (IKD, ODX)."""
        domain = [('type', 'not in', ['inkind', 'extra'])]
        return self.pool.get('account.journal').search(cr, uid, domain, context=context)
    
    _defaults = {
        'amount_currency': True,
        'sortby': 'sort_date',
        'initial_balance': False,
        'export_format': 'pdf',
        'journal_ids': _get_journals,  # exclude extra-accounting journals from this report (IKD, ODX)
        'account_type': 'all',
        'unreconciled': False,
    }
    
    def default_get(self, cr, uid, fields, context=None):
        res = super(account_report_general_ledger, self).default_get(cr, uid, fields, context=context)
        # get company default currency
        user = self.pool.get('res.users').browse(cr, uid, [uid], context=context)
        if user and user[0] and user[0].company_id:
            res['output_currency'] = user[0].company_id.currency_id.id
        return res

    def onchange_fiscalyear(self, cr, uid, ids, fiscalyear=False, context=None):
        res = {}
        if not fiscalyear:
            res['value'] = {'initial_balance': False}
        return res
        
    def remove_journals(self, cr, uid, ids, context=None):
        if ids:
            self.write(cr, uid, ids, { 'journal_ids': [(6, 0, [])] },
                       context=context)
        return {}

    def _print_report(self, cr, uid, ids, data, context=None):
        if context is None:
            context = {}
        data = self.pre_print_report(cr, uid, ids, data, context=context)
        data['form']['report_mode'] = 'gl'  # general ledger mode

        form_fields = [ 'landscape',  'initial_balance', 'amount_currency',
            'sortby', 'output_currency', 'instance_ids', 'export_format',
            'account_type', 'display_account_view', 'display_details',
            'unreconciled', 'account_ids',
        ]

        data['form'].update(self.read(cr, uid, ids, form_fields)[0])
        if not data['form']['fiscalyear_id']:# GTK client problem onchange does not consider in save record
            data['form'].update({'initial_balance': False})
        if data['form']['journal_ids']:
            default_journals = self._get_journals(cr, uid, context=context)
            if default_journals:
                if len(default_journals) == len(data['form']['journal_ids']):
                    data['form']['all_journals'] = True

        if data['form']['export_format'] \
           and data['form']['export_format'] == 'xls':
            return { 
                'type': 'ir.actions.report.xml',
                'report_name': 'account.general.ledger_xls',
                'datas': data,
            }
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'account.general.ledger_landscape',
            'datas': data,
            }

        
account_report_general_ledger()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
