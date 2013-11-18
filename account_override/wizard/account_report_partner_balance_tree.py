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
    _description = 'Print Account Partner Balance Tree'
    _columns = {
        'uid': fields.many2one('res.users', 'Uid', invisible=True),
        'account_type': fields.char('Account type', size=16),
        'account_type_display': fields.boolean('Display account type ?', invisible=True),
        'partner_name': fields.char('Partner', size=168),
        'debit': fields.float('Debit', digits_compute=dp.get_precision('Account')),
        'credit': fields.float('Credit', digits_compute=dp.get_precision('Account')),
        'balance': fields.float('Balance', digits_compute=dp.get_precision('Account')),
    }
    
    _order = "uid, account_type, partner_name"
    
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
        print 'DATA', data
        self._delete_previous_data(cr, uid, context=context)
        
        obj_move = self.pool.get('account.move.line')
        where = obj_move._query_get(cr, uid, obj='l', context=data['form'].get('used_context',{}))
        
        result_selection = data['form'].get('result_selection', '')
        if (result_selection == 'customer'):
            account_type = "('receivable')"
        elif (result_selection == 'supplier'):
            account_type = "('payable')"
        else:
            account_type = "('payable', 'receivable')"
        print 'account type', account_type
        
        move_state = "('draft','posted')"
        if data['form'].get('target_move', 'all') == 'posted':
            move_state = "('posted')"
        print move_state
        
        # inspired from account_report_balance.py
        cr.execute(
            "SELECT p.ref as partner_ref,l.account_id as account_id," \
            " ac.type as account_type, ac.name AS account_name," \
            " ac.code AS account_code,p.name as partner_name," \
            " sum(debit) AS debit, sum(credit) AS credit, " \
                    "CASE WHEN sum(debit) > sum(credit) " \
                        "THEN sum(debit) - sum(credit) " \
                        "ELSE 0 " \
                    "END AS sdebit, " \
                    "CASE WHEN sum(debit) < sum(credit) " \
                        "THEN sum(credit) - sum(debit) " \
                        "ELSE 0 " \
                    "END AS scredit" \
                    #~ "END AS scredit, " \
                    #~ "(SELECT sum(debit-credit) " \
                        #~ "FROM account_move_line l " \
                        #~ "WHERE partner_id = p.id " \
                            #~ "AND " + where + " " \
                            #~ "AND blocked = TRUE " \
                    #~ ") AS enlitige " \
            " FROM account_move_line l LEFT JOIN res_partner p ON (l.partner_id=p.id) " \
            " JOIN account_account ac ON (l.account_id = ac.id)" \
            " JOIN account_move am ON (am.id = l.move_id)" \
            " WHERE ac.type IN " + account_type + "" \
            " AND am.state IN " + move_state + ""\
            " AND " + where + "" \
            " GROUP BY p.id,ac.type,p.ref,p.name,l.account_id,ac.name,ac.code" \
            " ORDER BY l.account_id,p.name")
        res = cr.dictfetchall()

        if data['form'].get('display_partner', '') == 'non-zero_balance':
            full_account = [r for r in res if r['sdebit'] > 0 or r['scredit'] > 0]
        else:
            full_account = [r for r in res]
            
        for r in full_account:
            if not r.get('partner_name', False):
                r.update({'partner_name': _('Unknown Partner')})
            print r
            # TODO: fonctional currency 2 to output currency
            vals = {
                'uid': uid,
                'partner_name': r['partner_name'],
                'debit': r['debit'],
                'credit': r['credit'],
                'balance': r['debit'] - r['credit'],
                'account_type': r['account_type'],
                # display account type then 'Receivable' and 'Payable' are chosen together
                'account_type_display': result_selection not in ('customer', 'receivable'),
            }
            print vals
            self.create(cr, uid, vals, context=context)
account_partner_balance_tree()


class wizard_account_partner_balance_tree(osv.osv_memory):
    """
        This wizard will provide the partner balance report by periods, between any two dates.
    """
    _inherit = 'account.common.partner.report'
    _name = 'wizard.account.partner.balance.tree'
    _description = 'Print Account Partner Balance Tree'
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
            'name': 'Partner Balance' + account_type,
            'res_model': 'account.partner.balance.tree',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'ref': 'view_account_partner_balance_tree',
            'domain': [('uid', '=', uid)],
        }
   
    def export(self, cr, uid, ids, context=None):
        return {}

    #~ def _print_report(self, cr, uid, ids, data, context=None):
        #~ if context is None:
            #~ context = {}
        #~ data = self.pre_print_report(cr, uid, ids, data, context=context)
        #~ data['form'].update(self.read(cr, uid, ids, ['display_partner'])[0])
        #~ return {
            #~ 'type': 'ir.actions.report.xml',
            #~ 'report_name': 'account.partner.balance',
            #~ 'datas': data,
    #~ }

wizard_account_partner_balance_tree()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
