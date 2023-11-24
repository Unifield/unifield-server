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

    def _get_fake(self, cr, uid, ids, name, args, context=None):
        res = {}
        if not ids:
            return res
        if isinstance(ids, int):
            ids = [ids]
        for id in ids:
            res[id] = False
        return res

    _columns = {
        'initial_balance': fields.boolean("Include initial balances",
                                          help='It adds initial balance row on report which display previous sum amount of debit/credit/balance'),
        'is_initial_balance_available': fields.function(_get_fake, method=True, type='boolean', string="Is initial balance filter available ?"),
        'amount_currency': fields.boolean("With Currency", help="It adds the currency column if the currency is different then the company currency"),
        'sortby': fields.selection([('sort_date', 'Posting Date'),
                                    ('sort_third_party', 'Third Party'),
                                    ('sort_currency', 'Currency'),
                                    ('sort_reconcile', 'Reconcile Number')], 'Sort by', required=True),
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
        'amount_currency': True,
        'sortby': 'sort_date',
        'initial_balance': False,
        'export_format': 'pdf',
        'journal_ids': _get_journals,  # exclude extra-accounting journals from this report (IKD, ODX)
        'account_type': 'all',
        'reconciled': 'empty',
        'is_initial_balance_available': False,  # as no FY selection, not available by default US-926 point 7)
        'display_account': 'bal_movement',  # by default only result with JIs
    }

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        if context is None:
            context = {}
        context['report_cross_fy'] = True
        res = super(account_report_general_ledger, self).default_get(cr, uid, fields, context=context, from_web=from_web)
        # get company default currency
        user = self.pool.get('res.users').browse(cr, uid, [uid], context=context)
        if user and user[0] and user[0].company_id:
            res['output_currency'] = user[0].company_id.currency_id.id
        return res

    def onchange_fiscalyear(self, cr, uid, ids, fiscalyear=False, context=None):
        res = {
            'value': {
                'is_initial_balance_available': fiscalyear or False,
            },
        }
        return res

    def onchange_filter(self, cr, uid, ids, fiscalyear_id=False, context=None):
        res = super(account_report_general_ledger, self).onchange_filter(cr,
                                                                         uid, ids, fiscalyear_id=fiscalyear_id, context=context)
        if res is None:
            res = {}
        if not 'value' in res:
            res['value'] = {
                'is_initial_balance_available': fiscalyear_id or False,
            }
        else:
            res['value']['is_initial_balance_available'] = \
                fiscalyear_id or False
        return res

    def onchange_filter_date(self, cr, uid, ids, filter, fiscalyear_id,
                             date_from, date_to, period_from, period_to, context=None):
        # US-822: initial balance available if FY/01/01 included in the
        # date selection (posting date of initial balance)
        # AND if only one FY included in the selection
        # as we can't sum both balances and aggregated balances of period 0
        res = {}
        ib_available = fiscalyear_id or False
        if ib_available and filter and filter != 'filter_no':
            fy_rec = self.pool.get('account.fiscalyear').browse(cr, uid,
                                                                fiscalyear_id, context=context)
            if filter in ('filter_date_doc', 'filter_date', ):
                ib_available = date_from and date_from == fy_rec.date_start
            elif filter in 'filter_period':
                if not period_from or not period_to:
                    ib_available = False
                else:
                    period_from_rec = self.pool.get('account.period').browse(cr,
                                                                             uid,  period_from, context=context)
                    period_to_rec = self.pool.get('account.period').browse(cr,
                                                                           uid,  period_to, context=context)
                    ib_available = \
                        period_from_rec.date_start == fy_rec.date_start \
                        and period_to_rec.date_stop <= fy_rec.date_stop

        res['value'] = {'is_initial_balance_available': ib_available, }
        return res

    def remove_journals(self, cr, uid, ids, context=None):
        if ids:
            self.write(cr, uid, ids, { 'journal_ids': [(6, 0, [])] },
                       context=context)
        return {}

    def _print_report(self, cr, uid, ids, data, context=None):
        if not ids:
            return
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}
        if data.get('form', {}).get('export_format') == 'xls':
            report_name = 'account.general.ledger_xls'
        else:
            report_name = 'account.general.ledger_landscape'

        background_id = self.pool.get('memory.background.report').create(cr, uid, {
            'report_name': report_name,
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 3

        return {
            'type': 'ir.actions.report.xml',
            'report_name': report_name,
            #'datas': {'ids': ids, 'target_filename': filename, 'context': context},
            'datas': {'ids': ids, 'context': context},
            'context': context,
        }

    def _init_data(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        data = {'form': self.read(cr, uid, ids[0], [], context=context)}
        data['model'] = context.get('active_model')
        data = self.pre_print_report(cr, uid, ids, data, context=context)
        data['form']['report_mode'] = 'gl'  # general ledger mode

        # US-822: safe initial balance check box
        rec = self.browse(cr, uid, ids[0], fields_to_fetch=['filter', 'fiscalyear_id', 'date_from', 'date_to', 'period_from', 'period_to'], context=context)
        ofd_res = self.onchange_filter_date(cr, uid, [ids[0]],
                                            rec.filter, rec.fiscalyear_id.id,
                                            rec.date_from, rec.date_to,
                                            rec.period_from.id, rec.period_to.id, context=context)
        if ofd_res and 'value' in ofd_res \
                and not ofd_res['value'].get('is_initial_balance_available', True):
            # initial balance not applicable
            # (check onchange_filter_date comments)
            data['form']['initial_balance'] = False

        if not data['form']['fiscalyear_id']:# GTK client problem onchange does not consider in save record
            data['form']['initial_balance'] = False

        if data['form']['journal_ids']:
            default_journals = self._get_journals(cr, uid, context=context)
            if default_journals:
                if set(default_journals) == set(data['form']['journal_ids']):
                    data['form']['all_journals'] = True

        return data
account_report_general_ledger()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
