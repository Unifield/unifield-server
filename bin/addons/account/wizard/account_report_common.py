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

import time
from lxml import etree

from osv import fields, osv
from tools.translate import _

class account_common_report(osv.osv_memory):
    _inherit = "wizard.template.form"  # to be able to store the wizard values
    _name = "account.common.report"
    _description = "Account Common Report"

    def _get_is_report_cross_fy(self, cr, uid, ids, field_names, args,
                                context=None):
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long)):
            ids = [ids]
        for id in ids:
            res[id] = context and context.get('report_cross_fy', False) or False
        return res

    _columns = {
        'chart_account_id': fields.many2one('account.account', 'Chart of account', help='Select Charts of Accounts', domain = [('parent_id','=',False)]),
        'fiscalyear_id': fields.many2one('account.fiscalyear', 'Fiscal year', help='Keep empty for all open fiscal year'),
        'filter': fields.selection([('filter_no', 'No Filters'), ('filter_date', 'Date'), ('filter_period', 'Periods')], "Filter by", required=True),
        'period_from': fields.many2one('account.period', 'Start period'),
        'period_to': fields.many2one('account.period', 'End period'),
        'journal_ids': fields.many2many('account.journal', 'account_common_journal_rel', 'account_id', 'journal_id', 'Journals'),
        'date_from': fields.date("Start Date"),
        'date_to': fields.date("End Date"),
        'target_move': fields.selection([('posted', 'All Posted Entries'),
                                         ('all', 'All Entries'),
                                         ], 'Target Moves', required=True),
        'is_report_cross_fy': fields.function(_get_is_report_cross_fy, type='boolean', method=True, string='Is report cross FY'),
        'rev_journal_ids': fields.boolean('Exclude journal selection'),
        'rev_account_ids': fields.boolean('Exclude account selection'),
    }

    def _get_account(self, cr, uid, context=None):
        accounts = self.pool.get('account.account').search(cr, uid, [('parent_id', '=', False)], limit=1)
        return accounts and accounts[0] or False

    def _get_fiscalyear(self, cr, uid, context=None):
        if context and context.get('report_cross_fy', False):
            return False

        now = time.strftime('%Y-%m-%d')
        fiscalyears = self.pool.get('account.fiscalyear').search(cr, uid, [
            ('date_start', '<', now),
            ('date_stop', '>', now)
        ], limit=1 )
        return fiscalyears and fiscalyears[0] or False

    def _get_default_is_report_cross_fy(self, cr, uid, context=None):
        return context and context.get('report_cross_fy', False) or False

    def _get_all_journal(self, cr, uid, context=None):
        return self.pool.get('account.journal').search(cr, uid ,[])

    _defaults = {
        'fiscalyear_id': _get_fiscalyear,
        'journal_ids': _get_all_journal,
        'filter': 'filter_no',
        'chart_account_id': _get_account,
        'target_move': 'posted',
        'is_report_cross_fy': _get_default_is_report_cross_fy,
        'rev_journal_ids': False,
        'rev_account_ids': False,
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        res = super(account_common_report, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=False)
        if context.get('active_model', False) == 'account.account' and view_id:
            doc = etree.XML(res['arch'])
            nodes = doc.xpath("//field[@name='chart_account_id']")
            for node in nodes:
                node.set('readonly', '1')
                node.set('help', 'If you print the report from Account list/form view it will not consider Charts of account')
            res['arch'] = etree.tostring(doc)
        return res

    def onchange_filter(self, cr, uid, ids, filter='filter_no', fiscalyear_id=False, context=None):
        res = {}
        if filter == 'filter_no':
            res['value'] = {'period_from': False, 'period_to': False, 'date_from': False ,'date_to': False}
        if filter in ('filter_date', 'filter_date_doc', ):
            # Since US-1643 don't fill in the date fields automatically
            res['value'] = {'period_from': False, 'period_to': False}
        if filter == 'filter_period':
            res['value'] = {'date_from': False, 'date_to': False}
            if fiscalyear_id:
                res['value'].update(self.pool.get('account.fiscalyear')._get_normal_period_from_to(cr, uid, fiscalyear_id, context))
        return res

    def _build_contexts(self, cr, uid, ids, data, context=None):
        if context is None:
            context = {}
        result = {}
        result['fiscalyear'] = 'fiscalyear_id' in data['form'] and data['form']['fiscalyear_id'] or False
        result['journal_ids'] = 'journal_ids' in data['form'] and data['form']['journal_ids'] or False
        result['chart_account_id'] = 'chart_account_id' in data['form'] and data['form']['chart_account_id'] or False
        if data['form']['filter'] == 'filter_date':
            result['date_from'] = data['form']['date_from']
            result['date_to'] = data['form']['date_to']
        elif data['form']['filter'] == 'filter_date_doc':
            result['date_fromto_docdate'] = True
            result['date_from'] = data['form']['date_from']
            result['date_to'] = data['form']['date_to']
        elif data['form']['filter'] == 'filter_period':
            if not data['form']['period_from'] or not data['form']['period_to']:
                raise osv.except_osv(_('Error'),_('Select a starting and an ending period'))
            result['period_from'] = data['form']['period_from']
            result['period_to'] = data['form']['period_to']
        return result

    def _print_report(self, cr, uid, ids, data, context=None):
        raise (_('Error'), _('not implemented'))

    def check_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        data = {}
        data['keep_open'] = 1
        data['ids'] = context.get('active_ids', [])
        data['model'] = context.get('active_model', 'ir.ui.menu')
        data['form'] = self.read(cr, uid, ids, ['date_from',  'date_to',  'fiscalyear_id', 'journal_ids', 'period_from',
                                                'period_to',  'filter',  'chart_account_id', 'target_move',
                                                'rev_journal_ids', 'rev_account_ids'])[0]
        used_context = self._build_contexts(cr, uid, ids, data, context=context)
        data['form']['periods'] = used_context.get('periods', False) and used_context['periods'] or []
        data['form']['used_context'] = used_context
        return self._print_report(cr, uid, ids, data, context=context)

account_common_report()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
