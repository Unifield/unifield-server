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
from tools.translate import _
import decimal_precision as dp
import datetime
from datetime import timedelta

class account_partner_balance_tree(osv.osv):
    _name = 'account.partner.balance.tree'
    _description = 'Print Account Partner Balance View'
    _columns = {
        'uid': fields.many2one('res.users', 'Uid', invisible=True),
        'build_ts': fields.datetime('Build timestamp', invisible=True),
        'account_type': fields.selection([
                ('payable', 'Payable'),
                ('receivable', 'Receivable')
            ],
            'Account type'),
        'partner_id': fields.many2one('res.partner', 'Partner', invisible=True),
        'name': fields.char('Partner', size=168),  # partner name
        'partner_ref': fields.char('Partner Ref', size=64 ),
        'debit': fields.float('Debit', digits_compute=dp.get_precision('Account')),
        'credit': fields.float('Credit', digits_compute=dp.get_precision('Account')),
        'balance': fields.float('Balance', digits_compute=dp.get_precision('Account')),
    }

    _order = "account_type, partner_id"

    def _execute_query_partners(self, cr, uid, data):
        """
        return res, account_type, move_state
        """
        obj_move = self.pool.get('account.move.line')
        where = obj_move._query_get(cr, uid, obj='l', context=data['form'].get('used_context',{}))

        result_selection = data['form'].get('result_selection', '')
        if (result_selection == 'customer'):
            account_type = "('receivable')"
        elif (result_selection == 'supplier'):
            account_type = "('payable')"
        else:
            account_type = "('payable', 'receivable')"

        move_state = "('draft','posted')"
        if data['form'].get('target_move', 'all') == 'posted':
            move_state = "('posted')"

        # proprietary instances filter
        instance_ids = data['form']['instance_ids']
        if instance_ids:
            # we add instance filter in 'where'
            if where:
                where += " AND "
            where += "l.instance_id in(%s)" % (",".join(map(str, instance_ids)))

        # UFTP-312: take tax exclusion in account if user asked for it
        TAX_REQUEST = ' '
        if data['form'].get('tax', False):
            TAX_REQUEST = "AND at.code != 'tax'"

        # inspired from account_report_balance.py report query
        # but group only per 'account type'/'partner'
        query = "SELECT ac.type as account_type," \
        " p.id as partner_id, p.ref as partner_ref, p.name as partner_name," \
        " sum(debit) AS debit, sum(credit) AS credit," \
        " CASE WHEN sum(debit) > sum(credit) THEN sum(debit) - sum(credit) ELSE 0 END AS sdebit," \
        " CASE WHEN sum(debit) < sum(credit) THEN sum(credit) - sum(debit) ELSE 0 END AS scredit" \
        " FROM account_move_line l LEFT JOIN res_partner p ON (l.partner_id=p.id)" \
        " JOIN account_account ac ON (l.account_id = ac.id)" \
        " JOIN account_move am ON (am.id = l.move_id)" \
        " JOIN account_account_type at ON (ac.user_type = at.id)" \
        " WHERE ac.type IN " + account_type + "" \
        " AND am.state IN " + move_state + "" \
        " AND " + where + "" \
        " " + TAX_REQUEST + " " \
        " GROUP BY ac.type,p.id,p.ref,p.name" \
        " ORDER BY ac.type,p.name"
        cr.execute(query)
        res = cr.dictfetchall()
        if data['form'].get('display_partner', '') == 'non-zero_balance':
            res2 = [r for r in res if r['sdebit'] > 0 or r['scredit'] > 0]
        else:
            res2 = [r for r in res]
        return res2, account_type, move_state

    def _execute_query_selected_partner_move_line_ids(self, cr, uid, account_type, partner_id, data):
        obj_move = self.pool.get('account.move.line')
        where = obj_move._query_get(cr, uid, obj='l', context=data['form'].get('used_context',{}))

        move_state = "('draft','posted')"
        if data['form'].get('target_move', 'all') == 'posted':
            move_state = "('posted')"

        query = "SELECT l.id FROM account_move_line l" \
        " JOIN account_account ac ON (l.account_id = ac.id)" \
        " JOIN account_move am ON (am.id = l.move_id)" \
        " JOIN account_account_type at ON (ac.user_type = at.id) WHERE "
        if partner_id:
            query += "l.partner_id = " + str(partner_id) + "" \
            " AND ac.type = '" + account_type + "'" \
            " AND am.state IN " + move_state + ""
        else:
            query += "ac.type = '" + account_type + "'" \
            " AND am.state IN " + move_state + ""
        # UFTP-312: Filtering regarding tax account (if user asked it)
        if data['form'].get('tax', False):
            query += " AND at.code != 'tax' "

        if where:
            query += " AND " + where + ""

        cr.execute(query)
        res = cr.fetchall()
        if res:
            res2 = []
            for r in res:
                res2.append(r[0])
            return res2
        else:
            return False

    def _delete_previous_data(self, cr, uid, context=None):
        """ delete older user request than 15 days"""
        dt = datetime.datetime.now() - timedelta(days=15)
        dt_orm = dt.strftime(self.pool.get('date.tools').get_db_datetime_format(cr, uid, context=context))
        domain = [
            ('uid', '=', uid),
            ('build_ts', '<', dt_orm),
        ]
        ids = self.search(cr, uid, domain, context=context)
        if ids:
            if isinstance(ids, (int, long)):
                ids = [ids]
            self.unlink(cr, uid, ids, context=context)

    def build_data(self, cr, uid, data, context=None):
        """
        data
        {'model': 'ir.ui.menu', 'ids': [494], 'build_ts': build_timestamp,
         'form': {
            'output_currency': 1,
            'display_partner': 'non-zero_balance', 'chart_account_id': 1,
            'result_selection': 'customer', 'date_from': False,
            'period_to': False,
            'journal_ids': [16, 9, 10, 11, 12, 13, 14, 6, 7, 17, 18, 20, 15, 5, 1, 2, 3, 4, 8, 19],
            'used_context': {
                'chart_account_id': 1,
                'journal_ids': [16, 9, 10, 11, 12, 13, 14, 6, 7, 17, 18, 20, 15, 5, 1, 2, 3, 4, 8, 19],
                'fiscalyear': 1},
            'filter': 'filter_no', 'period_from': False,
            'fiscalyear_id': 1, 'periods': [], 'date_to': False, 'id': 1, 'target_move': 'posted'
         }
        }
        """
        if context is None:
            context = {}
        context['data'] = data
        self._delete_previous_data(cr, uid, context=context)

        comp_currency_id = self._get_company_currency(cr, uid, context=context)
        output_currency_id = data['form'].get('output_currency', comp_currency_id)

        res = self._execute_query_partners(cr, uid, data)

        for r in res[0]:
            if not r.get('partner_name', False):
                r.update({'partner_name': _('Unknown Partner')})
            vals = {
                'uid': uid,
                'build_ts': data['build_ts'],
                'account_type': r['account_type'].lower(),
                'partner_id': r['partner_id'],
                'name': r['partner_name'],
                'partner_ref': r['partner_ref'],
                'debit': self._currency_conv(cr, uid, r['debit'], comp_currency_id, output_currency_id),
                'credit': self._currency_conv(cr, uid, r['credit'], comp_currency_id, output_currency_id),
                'balance': self._currency_conv(cr, uid, r['debit'] - r['credit'], comp_currency_id, output_currency_id),
            }
            self.create(cr, uid, vals, context=context)

    def open_journal_items(self, cr, uid, ids, context=None):
        # get related partner
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long)):
            ids = [ids]
        r = self.read(cr, uid, ids, ['account_type', 'partner_id'], context=context)
        if r and r[0] and r[0]['partner_id']:
            if context and 'data' in context and 'form' in context['data']:
                move_line_ids = self._execute_query_selected_partner_move_line_ids(
                                                cr, uid,
                                                r[0]['account_type'].lower(),
                                                r[0]['partner_id'][0],
                                                context['data'])
                if move_line_ids:
                    new_context = {}
                    if context:
                        ctx_key_2copy = ('lang', 'tz', 'department_id', 'client', 'name')
                        for k in ctx_key_2copy:
                            if k in context:
                                new_context[k] = context[k]
                        comp_currency_id = self._get_company_currency(cr, uid, context=context)
                        output_currency_id = context['data']['form'].get('output_currency', comp_currency_id)
                        if comp_currency_id and output_currency_id \
                            and comp_currency_id != output_currency_id:
                            # output currency in action context
                            new_context['output_currency_id'] = output_currency_id
                    view_id = self.pool.get('ir.model.data').get_object_reference(
                                cr, uid, 'finance',
                                'view_account_partner_balance_tree_move_line_tree')[1]
                    res = {
                        'name': 'Journal Items',
                        'type': 'ir.actions.act_window',
                        'res_model': 'account.move.line',
                        'view_mode': 'tree,form',
                        'view_type': 'form',
                        'domain': [('id','in',tuple(move_line_ids))],
                        'context': new_context,
                    }
                    if view_id:
                        res['view_id'] = [view_id]
                return res
        return res

    def _get_company_currency(self, cr, uid, context=None):
        res = False
        user = self.pool.get('res.users').browse(cr, uid, [uid], context=context)
        if user and user[0] and user[0].company_id:
            res = user[0].company_id.currency_id.id
        if not res:
            raise osv.except_osv(_('Error !'), _('Company has no default currency'))
        return res

    def _currency_conv(self, cr, uid, amount,
                       comp_currency_id, output_currency_id,
                       date=False):
        if not amount or amount == 0.:
            return 0.
        if not comp_currency_id or not output_currency_id \
            or comp_currency_id == output_currency_id:
            # unset currencies or ouput currency == company currency
            return amount
        if date:
            context={'date': date}
        else:
            context=None
        amount = self.pool.get('res.currency').compute(cr, uid,
                                                comp_currency_id,
                                                output_currency_id,
                                                amount,
                                                context=context)
        if not amount:
            amount = 0.
        return amount

    def get_partner_data(self, cr, uid, account_types, data, context=None):
        """ browse with account_type filter 'payable' or 'receivable'"""
        domain = [
            ('uid', '=', uid),
            ('build_ts', '=', data['build_ts']),
        ]
        if account_types:
            domain += [('account_type', 'in', account_types)]
        ids = self.search(cr, uid, domain, context=context)
        if ids:
            if isinstance(ids, (int, long)):
                ids = [ids]
            return self.browse(cr, uid, ids, context=context)
        return []

    def get_partner_account_move_lines_data(self, cr, uid, account_type, partner_id, data, context=None):
        ids = self._execute_query_selected_partner_move_line_ids(cr, uid,
                                                        account_type,
                                                        partner_id,
                                                        data)
        if ids:
            if isinstance(ids, (int, long)):
                ids = [ids]
            sql = """SELECT a.code as account, SUM(aml.debit) as deb, SUM(aml.credit) as cred, ABS(SUM(debit) - SUM(credit)) as total
                    FROM account_move_line as aml, account_account as a
                    WHERE aml.id in %s
                    AND aml.account_id = a.id
                    GROUP BY a.code"""
            cr.execute(sql, (tuple(ids), ))
            res = cr.dictfetchall()
            return res
        return []

    def get_partners_total_debit_credit_balance_by_account_type(self, cr, uid, account_type, data):
        """Compute all partners total debit/credit from self data
        for given account_types (tuple) payable/receivable or both
        return total_debit, total_credit (tuple)
        """
        query = "SELECT" \
        " sum(debit) AS debit, sum(credit) AS credit, sum(balance) as balance" \
        " FROM account_partner_balance_tree" \
        " WHERE account_type IN ('" + account_type + "')" \
        " AND uid = " + str(uid) + "" \
        " AND build_ts='" + data['build_ts'] + "'"
        cr.execute(query)
        res = cr.dictfetchall()
        return res[0]['debit'], res[0]['credit'], res[0]['balance']
account_partner_balance_tree()


class wizard_account_partner_balance_tree(osv.osv_memory):
    """
        This wizard will provide the partner balance report by periods, between any two dates.
    """
    _inherit = 'account.common.partner.report'
    _name = 'wizard.account.partner.balance.tree'
    _description = 'Print Account Partner Balance View'
    _columns = {
        'display_partner': fields.selection([('non-zero_balance',
                                             'With balance is not equal to 0'),
                                             ('all', 'All Partners')]
                                            ,'Display Partners'),
        'output_currency': fields.many2one('res.currency', 'Output Currency', required=True),
        'instance_ids': fields.many2many('msf.instance', 'account_report_general_ledger_instance_rel', 'instance_id', 'argl_id', 'Proprietary Instances'),
        'tax': fields.boolean('Exclude tax', help="Exclude tax accounts from process"),
    }

    def _get_journals(self, cr, uid, context=None):
        """exclude extra-accounting journals from this report (IKD, ODX)."""
        domain = [('type', 'not in', ['inkind', 'extra'])]
        return self.pool.get('account.journal').search(cr, uid, domain, context=context)

    _defaults = {
        'display_partner': 'non-zero_balance',
        'result_selection': 'supplier',
        'journal_ids': _get_journals,
        'tax': False,
    }

    def default_get(self, cr, uid, fields, context=None):
        res = super(wizard_account_partner_balance_tree, self).default_get(cr, uid, fields, context=context)
        # get company default currency
        user = self.pool.get('res.users').browse(cr, uid, [uid], context=context)
        if user and user[0] and user[0].company_id:
            res['output_currency'] = user[0].company_id.currency_id.id
        return res

    def _get_data(self, cr, uid, ids, context=None):
        """return data, account_type (tuple)"""
        if context is None:
            context = {}

        data = {}
        data['ids'] = context.get('active_ids', [])
        data['model'] = context.get('active_model', 'ir.ui.menu')
        data['build_ts'] = datetime.datetime.now().strftime(self.pool.get('date.tools').get_db_datetime_format(cr, uid, context=context))
        data['form'] = self.read(cr, uid, ids, ['date_from',  'date_to',  'fiscalyear_id', 'journal_ids', 'period_from', 'period_to',  'filter',  'chart_account_id', 'target_move', 'display_partner', 'output_currency', 'instance_ids', 'tax'])[0]
        if data['form']['journal_ids']:
            default_journals = self._get_journals(cr, uid, context=context)
            if default_journals:
                if len(default_journals) == len(data['form']['journal_ids']):
                    data['form']['all_journals'] = True
        used_context = self._build_contexts(cr, uid, ids, data, context=context)
        data['form']['periods'] = used_context.get('periods', False) and used_context['periods'] or []
        data['form']['used_context'] = used_context

        data = self.pre_print_report(cr, uid, ids, data, context=context)

        result_selection = data['form'].get('result_selection', '')
        if (result_selection == 'customer'):
            account_type = 'Receivable'
        elif (result_selection == 'supplier'):
            account_type = 'Payable'
        else:
            account_type = 'Receivable and Payable'
        return data, account_type

    def show(self, cr, uid, ids, context=None):
        data, account_type = self._get_data(cr, uid, ids, context=context)
        self.pool.get('account.partner.balance.tree').build_data(cr,
                                                        uid, data,
                                                        context=context)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Partner Balance ' + account_type,
            'res_model': 'account.partner.balance.tree',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'ref': 'view_account_partner_balance_tree',
            'domain': [
                ('uid', '=', uid),
                ('build_ts', '=', data['build_ts']),
            ],
            'context': context,
        }

    def print_pdf(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        data, account_type = self._get_data(cr, uid, ids, context=context)
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'account.partner.balance',
            'datas': data,
        }

    def print_xls(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        data, account_type = self._get_data(cr, uid, ids, context=context)
        self.pool.get('account.partner.balance.tree').build_data(cr,
                                                        uid, data,
                                                        context=context)
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'account.partner.balance.tree_xls',
            'datas': data,
        }

    def remove_journals(self, cr, uid, ids, context=None):
        if ids:
            self.write(cr, uid, ids, { 'journal_ids': [(6, 0, [])] },
                       context=context)
        return {}

wizard_account_partner_balance_tree()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
