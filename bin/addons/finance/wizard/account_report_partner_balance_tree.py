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
            'Account type'),  # not used since US-3873
        'partner_id': fields.many2one('res.partner', 'Partner', invisible=True),
        'name': fields.char('Partner', size=168),  # partner name
        'partner_ref': fields.char('Partner Ref', size=64 ),
        'debit': fields.float('Debit', digits_compute=dp.get_precision('Account')),
        'credit': fields.float('Credit', digits_compute=dp.get_precision('Account')),
        'balance': fields.float('Balance', digits_compute=dp.get_precision('Account')),
        'ib_debit': fields.float('Initial Balance Debit', digits_compute=dp.get_precision('Account')),  # not used since US-3873
        'ib_credit': fields.float('Initial Balance Credit', digits_compute=dp.get_precision('Account')),  # not used since US-3873
        'ib_balance': fields.float('IB Balance', digits_compute=dp.get_precision('Account')),  # not used since US-3873
    }

    _order = "name, partner_id"

    def __init__(self, pool, cr):
        super(account_partner_balance_tree, self).__init__(pool, cr)
        self.total_debit_credit_balance = {}
        self.move_line_ids = {}

    def _execute_query_partners(self, cr, uid, data):
        """
        Returns a list of dicts, each containing data for one partner
        """
        obj_move = self.pool.get('account.move.line')
        used_context = data['form'].get('used_context', {})

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

        fiscalyear_id = data['form'].get('fiscalyear_id', False)
        if not fiscalyear_id:
            # by default all FY taken into account
            used_context.update({'all_fiscalyear': True})

        where = obj_move._query_get(cr, uid, obj='l', context=used_context) or ''

        # reconciliation filter
        reconcile_filter = data['form'].get('reconciled', '')
        if reconcile_filter == 'yes':
            self.RECONCILE_REQUEST = "AND l.reconcile_id IS NOT NULL"
        elif reconcile_filter == 'no':
            self.RECONCILE_REQUEST = "AND l.reconcile_id IS NULL AND ac.reconcile='t'"  # reconcilable entries not reconciled
        else:  # 'empty'
            self.RECONCILE_REQUEST = ""

        # proprietary instances filter
        self.INSTANCE_REQUEST = ''
        instance_ids = data['form'].get('instance_ids', False)
        if instance_ids:
            self.INSTANCE_REQUEST = " AND l.instance_id in(%s)" % (",".join(map(str, instance_ids)))

        # UFTP-312: take tax exclusion in account if user asked for it
        self.TAX_REQUEST = ''
        if data['form'].get('tax', False):
            self.TAX_REQUEST = "AND at.code != 'tax'"

        self.PARTNER_REQUEST = 'AND l.partner_id IS NOT NULL'
        if data['form'].get('partner_ids', False):  # some partners are specifically selected
            partner_ids = data['form']['partner_ids']
            if len(partner_ids) == 1:
                self.PARTNER_REQUEST = 'AND p.id = %s' % partner_ids[0]
            else:
                self.PARTNER_REQUEST = 'AND p.id IN %s' % (tuple(partner_ids),)
        elif data['form'].get('only_active_partners'):  # check if we should include only active partners
            self.PARTNER_REQUEST = "AND p.active = 't'"

        self.ACCOUNT_REQUEST = ''
        if data['form'].get('account_ids', False):  # some accounts are specifically selected
            self.ACCOUNT_REQUEST = " AND ac.id IN (%s)" % (",".join(map(str, data['form']['account_ids'])))

        where = where and 'AND %s' % where or ''
        query = """SELECT p.id as partner_id, p.ref as partner_ref, p.name as partner_name,
            COALESCE(sum(debit),0) AS debit, COALESCE(sum(credit), 0) AS credit,
            CASE WHEN sum(debit) > sum(credit) THEN sum(debit) - sum(credit) ELSE 0 END AS sdebit,
            CASE WHEN sum(debit) < sum(credit) THEN sum(credit) - sum(debit) ELSE 0 END AS scredit
            FROM account_move_line l INNER JOIN res_partner p ON (l.partner_id=p.id)
            JOIN account_account ac ON (l.account_id = ac.id)
            JOIN account_move am ON (am.id = l.move_id)
            JOIN account_account_type at ON (ac.user_type = at.id)
            WHERE ac.type IN %s
            AND am.state IN %s
            %s %s %s %s %s %s
            GROUP BY p.id, p.ref, p.name
            ORDER BY p.name;""" % (account_type, move_state,  # not_a_user_entry
                                   where, self.INSTANCE_REQUEST, self.TAX_REQUEST,
                                   self.PARTNER_REQUEST, self.ACCOUNT_REQUEST,
                                   self.RECONCILE_REQUEST)
        cr.execute(query)
        res = cr.dictfetchall()

        if data['form'].get('display_partner', '') == 'non-zero_balance':
            res2 = [r for r in res if r['sdebit'] > 0 or r['scredit'] > 0]
        else:  # with_movements or all
            res2 = [r for r in res]
        return res2

    def _execute_query_selected_partner_move_line_ids(self, cr, uid, partner_id, data):
        # if this method is re-called with the same arguments don't recompute the result
        if not self.move_line_ids or partner_id != self.move_line_ids['partner_id'] or data != self.move_line_ids['data']:
            obj_move = self.pool.get('account.move.line')
            where = obj_move._query_get(cr, uid, obj='l', context=data['form'].get('used_context', {})) or ''

            result_selection = data['form'].get('result_selection', '')
            if result_selection == 'customer':
                account_type = "('receivable')"
            elif result_selection == 'supplier':
                account_type = "('payable')"
            else:
                account_type = "('payable', 'receivable')"

            move_state = "('draft','posted')"
            if data['form'].get('target_move', 'all') == 'posted':
                move_state = "('posted')"

            query = "SELECT l.id FROM account_move_line l" \
                " JOIN account_account ac ON (l.account_id = ac.id)" \
                " JOIN account_move am ON (am.id = l.move_id)" \
                " JOIN account_account_type at ON (ac.user_type = at.id) WHERE "
            if partner_id:
                query += "l.partner_id = " + str(partner_id) + "" \
                    " AND ac.type IN " + account_type + "" \
                    " AND am.state IN " + move_state + ""
            else:
                query += "ac.type IN " + account_type + "" \
                         " AND am.state IN " + move_state + ""
            # UFTP-312: Filtering regarding tax account (if user asked it)
            if data['form'].get('tax', False):
                query += " AND at.code != 'tax' "

            reconcile_filter = data['form'].get('reconciled', '')
            if reconcile_filter == 'yes':
                query += " AND l.reconcile_id IS NOT NULL"
            elif reconcile_filter == 'no':
                query += " AND l.reconcile_id IS NULL AND ac.reconcile='t'"  # reconcilable entries not reconciled

            if data['form'].get('instance_ids', False):
                query += " AND l.instance_id in(%s)" % (",".join(map(str, data['form']['instance_ids'])))
            if data['form'].get('account_ids', False):  # some accounts are specifically selected
                query += " AND ac.id IN (%s)" % (",".join(map(str, data['form']['account_ids'])))
            if where:
                query += " AND " + where + ""

            cr.execute(query)
            res = cr.fetchall()
            if res:
                res2 = []
                for r in res:
                    res2.append(r[0])
                self.move_line_ids['res'] = res2
            else:
                self.move_line_ids['res'] = False
            self.move_line_ids['partner_id'] = partner_id
            self.move_line_ids['data'] = data
        return self.move_line_ids['res']

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

        res = self._execute_query_partners(cr, uid, data)

        p_seen = {}  # store every partner handled
        for r in res:
            debit = r['debit']
            credit = r['credit']
            if r['partner_id'] not in p_seen:
                p_seen[r['partner_id']] = {}
                p_seen[r['partner_id']]['name'] = r['partner_name']
                p_seen[r['partner_id']]['partner_ref'] = r['partner_ref']
            vals = {
                'uid': uid,
                'build_ts': data['build_ts'],
                'partner_id': r['partner_id'],
                'name': r['partner_name'],
                'partner_ref': r['partner_ref'],
                'debit': debit,
                'credit': credit,
                'balance': debit - credit,
            }
            self.create(cr, uid, vals, context=context)

        # if "Display Partners: All partners" has been selected, add the partners without movements
        # ONLY IF NO specific partner has been selected
        if data['form'].get('display_partner', '') == 'all' and not data['form'].get('partner_ids', False):
            # create entries at zero for partners where no result was found
            active_selection = data['form'].get('only_active_partners') and ('t',) or ('t', 'f')
            other_partners_sql_end = ""
            other_partners_sql_end_params = []
            if p_seen:
                # exclude partners already found if any
                other_partners_sql_end = " AND id NOT IN %s "
                other_partners_sql_end_params.append(tuple(p_seen.keys()))
            other_partners_sql = """
                        SELECT id, ref, name 
                        FROM res_partner
                        WHERE active IN %s 
                        AND name != 'To be defined' """ + other_partners_sql_end + """ ;
                        """
            other_partners_params = (active_selection,) + tuple(other_partners_sql_end_params)
            cr.execute(other_partners_sql, other_partners_params) # not_a_user_entry
            other_partners = cr.dictfetchall()
            for partner in other_partners:
                vals = {
                    'uid': uid,
                    'build_ts': data['build_ts'],
                    'partner_id': partner['id'],
                    'name': partner['name'],
                    'partner_ref': partner['ref'] or '',
                    'debit': 0.0,
                    'credit': 0.0,
                    'balance': 0.0,
                }
                self.create(cr, uid, vals, context=context)

    def open_journal_items(self, cr, uid, ids, context=None):
        # get related partner
        res = {}
        if context is None:
            context = {}
        if ids:
            if isinstance(ids, (int, long)):
                ids = [ids]
            r = self.read(cr, uid, ids, ['partner_id'], context=context)
            if r and r[0] and r[0]['partner_id']:
                if context and 'data' in context and 'form' in context['data']:
                    move_line_ids = self._execute_query_selected_partner_move_line_ids(
                        cr, uid,
                        r[0]['partner_id'][0],
                        context['data'])
                    if move_line_ids:
                        new_context = {}
                        if context:
                            ctx_key_2copy = ('lang', 'tz', 'department_id', 'client', 'name')
                            for k in ctx_key_2copy:
                                if k in context:
                                    new_context[k] = context[k]
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
        if not res:
            raise osv.except_osv(_('Warning !'), _('No Journal Items to show.'))
        return res

    def get_partner_data(self, cr, uid, data, context=None):
        """
        Gets the "account_partner_balance_trees" which have just been created
        """
        domain = [
            ('uid', '=', uid),
            ('build_ts', '=', data['build_ts']),
        ]
        ids = self.search(cr, uid, domain, context=context, order='name, id')
        if ids:
            if isinstance(ids, (int, long)):
                ids = [ids]
            return self.browse(cr, uid, ids, context=context)
        return []

    def get_partner_account_move_lines_data(self, cr, uid, partner_id, data, context=None):
        ids = self._execute_query_selected_partner_move_line_ids(cr, uid, partner_id, data)
        if ids:
            if isinstance(ids, (int, long)):
                ids = [ids]
            sql = """SELECT a.code as account, SUM(aml.debit) as deb, SUM(aml.credit) as cred, SUM(debit) - SUM(credit) as total
                    FROM account_move_line as aml, account_account as a
                    WHERE aml.id in %s
                    AND aml.account_id = a.id
                    GROUP BY a.code"""
            cr.execute(sql, (tuple(ids), ))
            res = cr.dictfetchall()
            return res
        return []

    def get_lines_per_currency(self, cr, uid, partner_id, data, account_code):
        """
        Returns a list of dicts, each containing the subtotal per currency for the given partner and account
        """
        res = []
        if partner_id and data and account_code:
            # the subtotal lines for the selected partner must be limited to the ids corresponding to
            # the criteria selected in the wizard
            ids = self._execute_query_selected_partner_move_line_ids(cr, uid, partner_id, data)
            if ids:
                sql = """SELECT c.name as currency_booking,
                        SUM(aml.debit_currency) as debit_booking, SUM(aml.credit_currency) as credit_booking, 
                        SUM(debit_currency) - SUM(credit_currency) as total_booking,
                        SUM(aml.debit) - SUM(aml.credit) as total_functional
                        FROM account_move_line AS aml
                        INNER JOIN account_account AS a ON aml.account_id = a.id
                        INNER JOIN res_currency AS c ON aml.currency_id = c.id
                        WHERE aml.id in %s
                        AND a.code = %s
                        GROUP BY a.code, c.name
                        ORDER BY c.name;"""
                cr.execute(sql, (tuple(ids), account_code))
                res = cr.dictfetchall()
        return res

    def get_partners_total_debit_credit_balance(self, cr, uid, data):
        """Compute all partners total debit/credit from self data
        return total_debit, total_credit (tuple)
        """
        # recalculate the result only if the criteria have changed
        if not self.total_debit_credit_balance or data != self.total_debit_credit_balance['data']:
            query = """SELECT sum(debit) AS debit, sum(credit) AS credit, sum(balance) as balance
                       FROM account_partner_balance_tree
                       WHERE uid = %s
                       AND build_ts = %s;
                       """
            cr.execute(query, (uid, data['build_ts']))
            res = cr.dictfetchall()
            self.total_debit_credit_balance['data'] = data
            self.total_debit_credit_balance['res'] = res[0]['debit'], res[0]['credit'], res[0]['balance']
        return self.total_debit_credit_balance['res']


account_partner_balance_tree()


class wizard_account_partner_balance_tree(osv.osv_memory):
    """
        This wizard will provide the partner balance report by periods, between any two dates.
    """
    _inherit = 'account.common.partner.report'
    _name = 'wizard.account.partner.balance.tree'
    _description = 'Print Account Partner Balance View'

    _columns = {
        'display_partner': fields.selection([('all', 'All Partners'),
                                             ('with_movements', 'With movements'),
                                             ('non-zero_balance', 'With balance is not equal to 0')],
                                            string='Display Partners', required=True),
        'instance_ids': fields.many2many('msf.instance', 'account_report_general_ledger_instance_rel', 'instance_id', 'argl_id', 'Proprietary Instances'),
        'tax': fields.boolean('Exclude tax', help="Exclude tax accounts from process"),
        'partner_ids': fields.many2many('res.partner', 'account_partner_balance_partner_rel', 'wizard_id', 'partner_id',
                                        string='Partners', help='Display the report for specific partners only'),
        'only_active_partners': fields.boolean('Only active partners', help='Display the report for active partners only'),
        'account_ids': fields.many2many('account.account', 'account_partner_balance_account_rel', 'wizard_id', 'account_id',
                                        string='Accounts', help='Display the report for specific accounts only'),
        'reconciled': fields.selection([
            ('empty', ''),
            ('yes', 'Yes'),
            ('no', 'No'),
        ], string='Reconciled'),
    }

    def _get_journals(self, cr, uid, context=None):
        """exclude extra-accounting journals from this report (IKD, ODX)."""
        domain = [('type', 'not in', ['inkind', 'extra'])]
        return self.pool.get('account.journal').search(cr, uid, domain, context=context)

    _defaults = {
        'display_partner': 'with_movements',
        'result_selection': 'customer_supplier',
        'account_domain': "[('type', 'in', ['payable', 'receivable'])]",
        'journal_ids': _get_journals,
        'tax': False,
        'only_active_partners': False,
        'reconciled': 'empty',
        'fiscalyear_id': False,
    }

    def _get_data(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        data = {}
        data['keep_open'] = 1
        data['ids'] = context.get('active_ids', [])
        data['model'] = context.get('active_model', 'ir.ui.menu')
        data['build_ts'] = datetime.datetime.now().strftime(self.pool.get('date.tools').get_db_datetime_format(cr, uid, context=context))
        data['form'] = self.read(cr, uid, ids, ['date_from',  'date_to',  'fiscalyear_id', 'journal_ids', 'period_from',
                                                'period_to',  'filter',  'chart_account_id', 'target_move', 'display_partner',
                                                'instance_ids', 'tax', 'partner_ids',
                                                'only_active_partners', 'account_ids', 'reconciled'])[0]
        if data['form']['journal_ids']:
            default_journals = self._get_journals(cr, uid, context=context)
            if default_journals:
                if len(default_journals) == len(data['form']['journal_ids']):
                    data['form']['all_journals'] = True
        used_context = self._build_contexts(cr, uid, ids, data, context=context)
        data['form']['periods'] = used_context.get('periods', False) and used_context['periods'] or []
        data['form']['used_context'] = used_context

        data = self.pre_print_report(cr, uid, ids, data, context=context)
        return data

    def show(self, cr, buid, ids, context=None):
        uid = hasattr(buid, 'realUid') and buid.realUid or buid
        data = self._get_data(cr, uid, ids, context=context)
        self.pool.get('account.partner.balance.tree').build_data(cr,
                                                                 uid, data,
                                                                 context=context)
        self._check_dates_fy_consistency(cr, uid, data, context)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Partner Balance'),
            'res_model': 'account.partner.balance.tree',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'keep_open': 1,
            'ref': 'view_account_partner_balance_tree',
            'domain': [
                ('uid', '=', uid),
                ('build_ts', '=', data['build_ts']),
            ],
            'context': context,
        }

    def print_pdf(self, cr, buid, ids, context=None):
        if context is None:
            context = {}
        uid = hasattr(buid, 'realUid') and buid.realUid or buid
        data = self._get_data(cr, uid, ids, context=context)
        self._check_dates_fy_consistency(cr, uid, data, context)
        self.pool.get('account.partner.balance.tree').build_data(cr, uid, data, context=context)
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'account.partner.balance',
            'datas': data,
        }

    def print_xls(self, cr, buid, ids, context=None):
        if context is None:
            context = {}
        uid = hasattr(buid, 'realUid') and buid.realUid or buid
        data = self._get_data(cr, uid, ids, context=context)
        self._check_dates_fy_consistency(cr, uid, data, context)
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
