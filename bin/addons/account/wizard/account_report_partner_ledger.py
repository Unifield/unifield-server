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
import pooler
from tools.translate import _

class account_partner_ledger(osv.osv_memory):
    """
    This wizard will provide the partner Ledger report by periods, between any two dates.
    """
    _name = 'account.partner.ledger'
    _inherit = 'account.common.partner.report'
    _description = 'Account Partner Ledger'

    _columns = {
        'initial_balance': fields.boolean('Include initial balances',
                                    help='It adds initial balance row on report which display previous sum amount of debit/credit/balance'),
        'reconcil': fields.boolean('Include Reconciled Entries', help='Consider reconciled entries'),
        'page_split': fields.boolean('One Partner Per Page', help='Display Ledger Report with One partner per page'),
        'partner_ids': fields.many2many('res.partner', 'account_partner_ledger_partner_rel', 'wizard_id', 'partner_id',
                                        string='Partners', help='Display the report for specific partners only'),
        'only_active_partners': fields.boolean('Only active partners', help='Display the report for active partners only'),
        'instance_ids': fields.many2many('msf.instance', 'account_partner_ledger_instance_rel', 'wizard_id', 'instance_id',
                                        string='Proprietary Instances', help='Display the report for specific proprietary instances only'),
        'account_ids': fields.many2many('account.account', 'account_partner_ledger_account_rel', 'wizard_id', 'account_id',
                                        string='Accounts', help='Display the report for specific accounts only'),
        'amount_currency': fields.boolean("With Currency", help="It adds the currency column if the currency is different then the company currency"),
        'tax': fields.boolean('Exclude tax', help="Exclude tax accounts from process"),
    }

    _defaults = {
       'reconcil': True,
       'initial_balance': False,
       'page_split': False,
       'result_selection': 'supplier',  # UF-1715: 'Payable Accounts' by default instead of 'Receivable'
       'account_domain': "[('type', 'in', ['payable'])]",
       'only_active_partners': False,
       'tax': False, # UFTP-312: Add an exclude tax account possibility
       'fiscalyear_id': False,
    }

    def onchange_fiscalyear(self, cr, uid, ids, fiscalyear_id, context=None):
        """
        If a FY is selected:
        resets the selected periods, and adapts the domain so that the selectable periods are inside the chosen FY.
        If no FY is selected: unticks the "Initial Balance" tickbox.
        """
        if context is None:
            context = {}
        res = {}
        if fiscalyear_id:
            res['domain'] = {'period_from': [('fiscalyear_id', '=', fiscalyear_id)],
                             'period_to': [('fiscalyear_id', '=', fiscalyear_id)],
                             }
            res['value'] = {'period_from': False, 'period_to': False, }
        else:
            res['domain'] = {'period_from': [], 'period_to': [], }
            res['value'] = {'initial_balance': False, }
        return res

    def _check_dates_fy_consistency(self, cr, uid, data, context):
        """
        Raises a warning if the chosen dates aren't inside the selected period.
        """
        if data['form']['fiscalyear_id'] and data['form']['filter'] == 'filter_date':
            fy_obj = pooler.get_pool(cr.dbname).get('account.fiscalyear')
            fy = fy_obj.browse(cr, uid, data['form']['fiscalyear_id'], context=context, fields_to_fetch=['date_start', 'date_stop'])
            if data['form']['date_from'] < fy.date_start or data['form']['date_to'] > fy.date_stop:
                raise osv.except_osv(_('Warning !'), _('Only dates of the selected Fiscal Year can be chosen.'))

    def _print_report(self, cr, uid, ids, data, context=None):
        if context is None:
            context = {}
        data = self.pre_print_report(cr, uid, ids, data, context=context)
        data['form'].update(self.read(cr, uid, ids, ['initial_balance', 'reconcil', 'page_split', 'amount_currency',
                                                     'tax', 'partner_ids', 'only_active_partners', 'instance_ids',
                                                     'account_ids'])[0])
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

account_partner_ledger()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
