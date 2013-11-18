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

class account_partner_balance_tree(osv.osv_memory):
    """
        This wizard will provide the partner balance report by periods, between any two dates.
    """
    _inherit = 'account.common.partner.report'
    _name = 'account.partner.balance.tree'
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
        res = super(account_partner_balance_tree, self).default_get(cr, uid, fields, context=context)
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
        data = self._get_data(cr, uid, ids, context=context)
        print data
        obj_move = self.pool.get('account.move.line')
        where = obj_move._query_get(cr, uid, obj='l', context=data['form'].get('used_context',{}))
        
        result_selection = data['form'].get('result_selection', '')
        if (result_selection == 'customer'):
            account_type = ('receivable',)
        elif (result_selection == 'supplier'):
            account_type = ('payable',)
        else:
            account_type = ('payable', 'receivable')
        
        move_state = ('draft','posted')
        if data['form'].get('target_mode', '') == 'posted':
            move_state = ('posted')
        
        cr.execute(
            "SELECT p.ref,l.account_id,ac.name AS account_name,ac.code AS code,p.name, sum(debit) AS debit, sum(credit) AS credit, " \
                    "CASE WHEN sum(debit) > sum(credit) " \
                        "THEN sum(debit) - sum(credit) " \
                        "ELSE 0 " \
                    "END AS sdebit, " \
                    "CASE WHEN sum(debit) < sum(credit) " \
                        "THEN sum(credit) - sum(debit) " \
                        "ELSE 0 " \
                    "END AS scredit, " \
                    "(SELECT sum(debit-credit) " \
                        "FROM account_move_line l " \
                        "WHERE partner_id = p.id " \
                            "AND " + where + " " \
                            "AND blocked = TRUE " \
                    ") AS enlitige " \
            "FROM account_move_line l LEFT JOIN res_partner p ON (l.partner_id=p.id) " \
            "JOIN account_account ac ON (l.account_id = ac.id) " \
            "JOIN account_move am ON (am.id = l.move_id) " \
            "WHERE ac.type IN (%s) " \
            "AND am.state IN (%s)" \
            "AND " + where + "" \
            "GROUP BY p.id, p.ref, p.name,l.account_id,ac.name,ac.code " \
            "ORDER BY l.account_id,p.name",
            (",".join(account_type), ",".join(move_state)))
        res = cr.dictfetchall()

        if data['form'].get('display_partner', '') == 'non-zero_balance':
            full_account = [r for r in res if r['sdebit'] > 0 or r['scredit'] > 0]
        else:
            full_account = [r for r in res]
            
        for rec in full_account:
            if not rec.get('name', False):
                rec.update({'name': _('Unknown Partner')})
        ## We will now compute Total
        #subtotal_row = self._add_subtotal(full_account)
        
        return {}
   
    def export(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
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

account_partner_balance_tree()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
