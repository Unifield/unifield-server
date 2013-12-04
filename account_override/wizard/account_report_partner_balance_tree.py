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

class account_partner_balance_tree(osv.osv):
    _name = 'account.partner.balance.tree'
    _description = 'Print Account Partner Balance View'
    _columns = {
        'uid': fields.many2one('res.users', 'Uid', invisible=True),
        'row_type': fields.integer('Row type', invisible=True),
        'account_type': fields.char('Account type', size=16),
        'account_type_display': fields.boolean('Display account type ?', invisible=True),
        'partner_id': fields.many2one('res.partner', 'Partner', invisible=True),
        'account_id': fields.many2one('account.account', 'Account', invisible=True),
        'name': fields.char('Partner', size=168),
        'debit': fields.float('Debit', digits_compute=dp.get_precision('Account')),
        'credit': fields.float('Credit', digits_compute=dp.get_precision('Account')),
        'balance': fields.float('Balance', digits_compute=dp.get_precision('Account')),
    }
    
    _order = "uid, account_type, partner_id, row_type"
    
    def _execute_query_aggregate(self, cr, uid, data):
        """
        return res, account_type, move_state
        """
        obj_move = self.pool.get('account.move.line')
        where = obj_move._query_get(cr, uid, obj='l', context=data['form'].get('used_context',{}))
        print '_execute_query_aggregate where', where
         
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
    
        # inspired from account_report_balance.py report query
        query = "SELECT ac.type as account_type," \
        " p.id as partner_id, p.ref as partner_ref, p.name as partner_name," \
        " sum(debit) AS debit, sum(credit) AS credit," \
        " CASE WHEN sum(debit) > sum(credit) THEN sum(debit) - sum(credit) ELSE 0 END AS sdebit," \
        " CASE WHEN sum(debit) < sum(credit) THEN sum(credit) - sum(debit) ELSE 0 END AS scredit" \
        " FROM account_move_line l LEFT JOIN res_partner p ON (l.partner_id=p.id)" \
        " JOIN account_account ac ON (l.account_id = ac.id)" \
        " JOIN account_move am ON (am.id = l.move_id)" \
        " WHERE ac.type IN " + account_type + "" \
        " AND am.state IN " + move_state + "" \
        " AND " + where + "" \
        " GROUP BY ac.type,p.id,p.ref,p.name" \
        " ORDER BY ac.type,p.name"
        print query
        cr.execute(query)
        res = cr.dictfetchall()
        print 'RES rows', len(res)
        print res
        if data['form'].get('display_partner', '') == 'non-zero_balance':
            res2 = [r for r in res if r['sdebit'] > 0 or r['scredit'] > 0]
        else:
            res2 = [r for r in res]
        return res2, account_type, move_state
        
    def _execute_query_selected_partner_move_line_ids(self, cr, uid, partner_id, data):
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
    
        query = "SELECT l.id" \
        " FROM account_move_line l" \
        " JOIN account_account ac ON (l.account_id = ac.id)" \
        " JOIN account_move am ON (am.id = l.move_id)" \
        " WHERE l.partner_id = " + str(partner_id) + "" \
        " AND ac.type IN " + account_type + "" \
        " AND am.state IN " + move_state + "" \
        " AND " + where + ""
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
        ids = self.search(cr, uid, [('uid', '=', uid)], context=context)
        if ids:
            if isinstance(ids, (int, long)):
                ids = [ids]
            self.unlink(cr, uid, ids, context=context)
    
    def build_data(self, cr, uid, data, context=None):
        """
        data
        {'model': 'ir.ui.menu', 'ids': [494], 
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

        res, account_type, move_state = self._execute_query_aggregate(cr, uid, data)
        # TODO
        return {}
        
        if account_type and account_type == "('payable', 'receivable')":
            account_type_display = True
        else:
            account_type_display = False
        print 'account_partner_balance_tree account_type_display', account_type, account_type_display
        prev = {
            'partner_id': False,
            'partner_name': False,
            'account_type': False,
        }
        sub_total = {
            'debit': 0.,
            'credit': 0.,
        }
        for r in res:
            if not r.get('partner_name', False):
                r.update({'partner_name': _('Unknown Partner')})
            if not prev['partner_id'] and not prev['account_type']:
                prev['partner_id'] = r['partner_id']
                prev['partner_name'] = r['partner_name']
                prev['account_type'] = r['account_type']
            
            vals = {
                'uid': uid,
                'row_type': 2,
                'account_type': r['account_type'].capitalize(),
                # display account type then 'Receivable' and 'Payable' are chosen together
                'account_type_display': account_type_display,
                'partner_id': r['partner_id'],
                'account_id': r['account_id'],
                'name': r['account_name'],
                'debit': self._currency_conv(cr, uid, r['debit'], comp_currency_id, output_currency_id),
                'credit': self._currency_conv(cr, uid, r['credit'], comp_currency_id, output_currency_id),
                'balance': self._currency_conv(cr, uid, r['debit'] - r['credit'], comp_currency_id, output_currency_id),
            }
            print 'line', vals
            
            if prev['partner_id'] == r['partner_id'] and prev['account_type'] == r['account_type']:
                sub_total['credit'] += r['credit']
                sub_total['debit'] += r['debit']
            else:
                sub_vals = {
                    'uid': uid,
                    'row_type': 1,
                    'account_type': prev['account_type'].capitalize(),
                    # display account type then 'Receivable' and 'Payable' are chosen together
                    'account_type_display': account_type_display,
                    'partner_id': prev['partner_id'],
                    'account_id': False,
                    'name': prev['partner_name'],
                    'debit': self._currency_conv(cr, uid, sub_total['debit'], comp_currency_id, output_currency_id),
                    'credit': self._currency_conv(cr, uid, sub_total['credit'], comp_currency_id, output_currency_id),
                    'balance': self._currency_conv(cr, uid, sub_total['debit'] - sub_total['credit'], comp_currency_id, output_currency_id),
                }
                print 'subvals ', sub_vals
                self.create(cr, uid, sub_vals, context=context)
                prev['partner_id'] = r['partner_id']
                prev['partner_name'] = r['partner_name']
                prev['account_type'] = r['account_type']
                sub_total['debit'] = r['debit']
                sub_total['credit'] = r['credit']
                
            self.create(cr, uid, vals, context=context)
        sub_vals = {
            'uid': uid,
            'row_type': 1,
            'account_type': prev['account_type'].capitalize(),
            # display account type then 'Receivable' and 'Payable' are chosen together
            'account_type_display': account_type_display,
            'partner_id': prev['partner_id'],
            'account_id': False,
            'name': prev['partner_name'],
            'debit': self._currency_conv(cr, uid, sub_total['debit'], comp_currency_id, output_currency_id),
            'credit': self._currency_conv(cr, uid, sub_total['credit'], comp_currency_id, output_currency_id),
            'balance': self._currency_conv(cr, uid, sub_total['debit'] - sub_total['credit'], comp_currency_id, output_currency_id),
        }
        self.create(cr, uid, sub_vals, context=context)
            
    def open_journal_items(self, cr, uid, ids, context=None):
        # get related partner
        res = {}
        if not ids:
            return res
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
                    res = {
                        "name": "Journal Items",
                        "type": "ir.actions.act_window",
                        "res_model": "account.move.line",
                        "view_mode": "tree,form",
                        "view_type": "form",
                        "domain": [('id','in',tuple(move_line_ids))],
                    }
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
            
    def _currency_conv(self, cr, uid, amount, comp_currency_id, output_currency_id):
        if not amount or amount == 0.:
            return amount
        if not comp_currency_id or not output_currency_id \
            or comp_currency_id == output_currency_id:
            return amount
        amount = self.pool.get('res.currency').compute(cr, uid,
                                                comp_currency_id,
                                                output_currency_id,
                                                amount)
        if not amount:
            amount = 0.
        return amount
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
    }

    _defaults = {
        'display_partner': 'non-zero_balance',
    }
       
    def default_get(self, cr, uid, fields, context=None):
        res = super(wizard_account_partner_balance_tree, self).default_get(cr, uid, fields, context=context)
        # get company default currency
        user = self.pool.get('res.users').browse(cr, uid, [uid], context=context)
        if user and user[0] and user[0].company_id:
            res['output_currency'] = user[0].company_id.currency_id.id
        return res
        
    def _get_data(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        data = {}
        data['ids'] = context.get('active_ids', [])
        data['model'] = context.get('active_model', 'ir.ui.menu')
        data['form'] = self.read(cr, uid, ids, ['date_from',  'date_to',  'fiscalyear_id', 'journal_ids', 'period_from', 'period_to',  'filter',  'chart_account_id', 'target_move'])[0]
        used_context = self._build_contexts(cr, uid, ids, data, context=context)
        data['form']['periods'] = used_context.get('periods', False) and used_context['periods'] or []
        data['form']['used_context'] = used_context
        
        data = self.pre_print_report(cr, uid, ids, data, context=context)
        data['form'].update(self.read(cr, uid, ids, ['display_partner', 'output_currency'], context=context)[0])
        return data
    
    def show(self, cr, uid, ids, context=None):
        data = self._get_data(cr, uid, ids, context=context)
        
        result_selection = data['form'].get('result_selection', '')
        if (result_selection == 'customer'):
            account_type = 'Receivable'
        elif (result_selection == 'supplier'):
            account_type = 'Payable'
        else:
            account_type = 'Receivable and Payable'
        
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
            'domain': [('uid', '=', uid)],
            'context': context,
        }
   
    def export(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        data = self._get_data(cr, uid, ids, context=context)
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'account.partner.balance.tree_xls',
            'datas': data,
        }

wizard_account_partner_balance_tree()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
