#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2018 TeMPO Consulting, MSF. All Rights Reserved
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

from osv import osv
import tools
from tools.translate import _


class update_link(osv.osv):
    """
    NOTE: this class is in msf_profile because it uses classes defined in modules loaded before this one
    """
    _name = 'update.link'
    _description = 'Handling of the Links to Updates Sent and Received'

    def _open_update_list(self, cr, uid, ids, model='', type='received', context=None):
        """
        Returns the Update Received or Sent View with the SD ref of the selected entry already filled in.
        :param model: String, name of the model of the selected entry (ex: 'account.move.line').
        :param type: String. If 'received', will open the Update Received View. Else will open the Update Sent View.
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        active_ids = context.get('active_ids', [])  # to detect if the user has selected several entries
        if len(ids) != 1 or len(active_ids) > 1:
            raise osv.except_osv(_('Error'),
                                 _('This feature can only be used with one entry selected.'))
        if model and isinstance(model, basestring):
            context.update({'search_default_model': model})
            ir_model_obj = self.pool.get('ir.model.data')
            ir_model_data_ids = ir_model_obj.search(cr, uid, [('module', '=', 'sd'),
                                                              ('model', '=', model),
                                                              ('res_id', '=', ids[0])], limit=1, context=context)
            sdref = False
            if ir_model_data_ids:
                sdref = ir_model_obj.browse(cr, uid, ir_model_data_ids[0], fields_to_fetch=['name'],
                                            context=context).name
            if sdref:
                context.update({'search_default_sdref': sdref})
                context.update({'search_default_current': 0})  # "Not Run" filter
        tree_view = type == 'received' and 'update_received_tree_view' or 'sync_client_update_to_send_tree_view'
        view_id = ir_model_obj.get_object_reference(cr, uid, 'sync_client', tree_view)
        view_id = view_id and view_id[1] or False
        search_view = type == 'received' and 'update_received_search_view' or 'update_sent_search_view'
        search_view_id = ir_model_obj.get_object_reference(cr, uid, 'sync_client', search_view)
        search_view_id = search_view_id and search_view_id[1] or False
        res_model = type == 'received' and 'sync.client.update_received' or 'sync.client.update_to_send'
        return {
            'name': type == 'received' and _('Update Received Monitor') or _('Update Sent Monitor'),
            'type': 'ir.actions.act_window',
            'res_model': res_model,
            'view_type': 'form',
            'view_mode': 'tree,form',
            'view_id': [view_id],
            'search_view_id': [search_view_id],
            'context': context,
            'domain': [],
            'target': 'current',
        }

    def open_update_received(self, cr, uid, ids, context=None):
        """
        Opens the Updates Received View with the SD ref of the selected entry already filled in
        """
        return self._open_update_list(cr, uid, ids, model=self._name, type='received', context=context)

    def open_update_sent(self, cr, uid, ids, context=None):
        """
        Opens the Updates Sent View with the SD ref of the selected entry already filled in
        """
        return self._open_update_list(cr, uid, ids, model=self._name, type='sent', context=context)

update_link()


class account_move_line(osv.osv):
    _name = 'account.move.line'
    _inherit = ['account.move.line', 'update.link']

account_move_line()


class account_analytic_line(osv.osv):
    _name = 'account.analytic.line'
    _inherit = ['account.analytic.line', 'update.link']

account_analytic_line()


class account_move(osv.osv):
    _name = 'account.move'
    _inherit = ['account.move', 'update.link']

account_move()


class res_partner(osv.osv):
    _name = 'res.partner'
    _inherit = ['res.partner', 'update.link']

res_partner()


class account_bank_statement(osv.osv):
    _name = 'account.bank.statement'
    _inherit = ['account.bank.statement', 'update.link']

account_bank_statement()


class account_bank_statement_line(osv.osv):
    _name = 'account.bank.statement.line'
    _inherit = ['account.bank.statement.line', 'update.link']

account_bank_statement_line()


class hq_entries(osv.osv):
    _name = 'hq.entries'
    _inherit = ['hq.entries', 'update.link']

hq_entries()


class msf_budget(osv.osv):
    _name = 'msf.budget'
    _inherit = ['msf.budget', 'update.link']

msf_budget()


class cash_request(osv.osv):
    _name = 'cash.request'
    _inherit = ['cash.request', 'update.link']

cash_request()


class account_account(osv.osv):
    _name = 'account.account'
    _inherit = ['account.account', 'update.link']

account_account()


class account_analytic_account(osv.osv):
    _name = 'account.analytic.account'
    _inherit = ['account.analytic.account', 'update.link']

account_analytic_account()


class account_journal(osv.osv):
    _name = 'account.journal'
    _inherit = ['account.journal', 'update.link']

account_journal()


class account_analytic_journal(osv.osv):
    _name = 'account.analytic.journal'
    _inherit = ['account.analytic.journal', 'update.link']

account_analytic_journal()


class account_fiscalyear(osv.osv):
    _name = 'account.fiscalyear'
    _inherit = ['account.fiscalyear', 'update.link']

account_fiscalyear()


class account_period(osv.osv):
    _name = 'account.period'
    _inherit = ['account.period', 'update.link']

account_period()


class account_period_state(osv.osv):
    _name = 'account.period.state'
    _inherit = ['account.period.state', 'update.link']

account_period_state()


class account_fiscalyear_state(osv.osv):
    _name = 'account.fiscalyear.state'
    _inherit = ['account.fiscalyear.state', 'update.link']

account_fiscalyear_state()


class res_currency(osv.osv):
    _name = 'res.currency'
    _inherit = ['res.currency', 'update.link']

res_currency()


class res_currency_table(osv.osv):
    _name = 'res.currency.table'
    _inherit = ['res.currency.table', 'update.link']

res_currency_table()


class hr_employee(osv.osv):
    _name = 'hr.employee'
    _inherit = ['hr.employee', 'update.link']

hr_employee()


class financing_contract_contract(osv.osv):
    _name = 'financing.contract.contract'
    _inherit = ['financing.contract.contract', 'update.link']

financing_contract_contract()


class product_product(osv.osv):
    _name = 'product.product'
    _inherit = ['product.product', 'update.link']

product_product()


class account_tax(osv.osv):
    _name = 'account.tax'
    _inherit = ['account.tax', 'update.link']

account_tax()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
