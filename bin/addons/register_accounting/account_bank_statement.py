#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    All Rigts Reserved
#    Developer: Olivier DOSSMANN
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
from osv import fields
from tools.translate import _
from tools.safe_eval import safe_eval
from tools.misc import _max_amount
from tools.misc import get_fake
from register_tools import _get_third_parties
from register_tools import _set_third_parties
from register_tools import create_cashbox_lines
from register_tools import open_register_view
from base import currency_date
import time
import datetime


def _get_fake(cr, table, ids, *a, **kw):
    ret = {}
    for i in ids:
        ret[i] = False
    return ret

def _search_fake(*a, **kw):
    return []

class hr_employee(osv.osv):
    _name = 'hr.employee'
    _inherit = 'hr.employee'
    _columns = {
        'filter_for_third_party': fields.function(_get_fake, type='char', string="Internal Field", fnct_search=_search_fake, method=False),
        'filter_for_third_party_in_advance_return': fields.function(_get_fake, type='char', string="Internal Field", fnct_search=_search_fake, method=False),
    }
hr_employee()

class res_partner(osv.osv):
    _name = 'res.partner'
    _inherit = 'res.partner'
    def _get_fake(self, cr, table, ids, field_name, arg, context):
        ret = {}
        for i in ids:
            ret[i] = False
        return ret

    def _search_filter_third(self, cr, uid, obj, name, args, context):
        """
        Return only suppliers
        """
        if not context:
            context = {}
        if not args:
            return []
        return [('supplier', '=', True)]

    _columns = {
        'filter_for_third_party': fields.function(_get_fake, type='char', string="Internal Field", fnct_search=_search_fake, method=True), # search is now fake because of UTP-510
        'filter_for_third_party_in_advance_return': fields.function(_get_fake, type='char', string="Internal Field", fnct_search=_search_filter_third, method=True),

    }
res_partner()

class account_journal(osv.osv):
    _name = 'account.journal'
    _inherit = 'account.journal'

    def _get_fake(self, cr, table, ids, field_name, arg, context):
        ret = {}
        for i in ids:
            ret[i] = False
        return ret

    def _search_filter_third(self, cr, uid, obj, name, args, context):
        if not context:
            context = {}
        regline_obj = self.pool.get('account.bank.statement.line')
        dom = [('type', 'in', ['cash', 'bank', 'cheque']), ('is_active', '=', True)]
        if context.get('from', '') == 'regline_view' and context.get('active_id'):
            # get the currency and journal values for the View "Register Lines" accessible from the reg. Actions Menu
            reg_line = regline_obj.browse(cr, uid, context['active_id'], fields_to_fetch=['statement_id'], context=context)
            reg = reg_line and reg_line.statement_id
            if reg and not context.get('curr'):
                context['curr'] = reg.currency and reg.currency.id or False
            if reg and not context.get('journal'):
                context['journal'] = reg.journal_id.id
        if not args or not context.get('curr') or not context.get('journal'):
            return dom
        if args[0][2]:
            t = self.pool.get('account.account').read(cr, uid, args[0][2], ['type_for_register'])
            # UF-1972: Do not display itself for transfer in same currency. If another currency, itself is not shown.
            if t['type_for_register'] == 'transfer_same':
                return dom+[('currency', 'in', [context['curr']]), ('id', 'not in', [context['journal']])]
            elif t['type_for_register'] == 'transfer':
                return dom+[('currency', 'not in', [context['curr']])]
        return dom

    def write(self, cr, uid, ids, vals, context=None):
        # write is not allowed on upper or sibling liquidity journals
        if context is None:
            context = {}
        if not context.get('sync_update_execution') and uid != 1:
            instance = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
            if instance and instance.level != 'section':
                allowed = [x.id for x in instance.child_ids] + [instance.id]
                nids = self.search(cr, uid,[
                    ('id', 'in', ids),
                    ('type', 'in', ['bank', 'cheque', 'cash']),
                    ('instance_id', 'not in', allowed)],
                    context=context)
                if nids:
                    raise osv.except_osv(_('Error'), _("Writing on liquidity journals %s is not allowed") % (", ".join([x['code'] for x in self.read(cr, uid, nids, ['code'], context=context)]), ))

        return super(account_journal, self).write(cr, uid, ids, vals, context)


    _columns = {
        'filter_for_third_party': fields.function(_get_fake, type='char', string="Internal Field", fnct_search=_search_filter_third, method=True),
        'filter_for_third_party_in_advance_return': fields.function(_get_fake, type='char', string="Internal Field",
                                                                    fnct_search=_search_filter_third, method=True),
    }
account_journal()

class account_bank_statement(osv.osv):
    _name = "account.bank.statement"
    _inherit = "account.bank.statement"

    _sql_constraints = [
        ('period_journal_uniq', 'unique (period_id, journal_id)', 'You cannot have a register on the same period and the same journal!')
    ]

    def __init__(self, pool, cr):
        """
        Change some fields that were store=True to field that have store=False:
        - total_entry_encoding
        - balance_end
        """
        super(account_bank_statement, self).__init__(pool, cr)
        if self.pool._store_function.get(self._name, []):
            newstore = []
            for fct in self.pool._store_function[self._name]:
                if fct[1] not in ['balance_end', 'total_entry_encoding']:
                    newstore.append(fct)
            self.pool._store_function[self._name] = newstore
            super(account_bank_statement, self)._columns['total_entry_encoding'].store = False
            super(account_bank_statement, self)._columns['balance_end'].store = False


    def _get_register_id(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Get current register id
        """
        res = {}
        local_instance_id = self.pool.get('res.company')._get_instance_id(cr, uid)

        for st in self.browse(cr, uid, ids, fields_to_fetch=['journal_id'], context=context):
            res[st.id] = {
                'virtual_id': st.id,
                'local_register': st.journal_id.instance_id.id == local_instance_id,
            }
        return res

    def _balance_gap_compute(self, cr, uid, ids, name, attr, context=None):
        """
        Calculate Gap between bank statement balance (balance_end_real) and calculated balance (balance_end)
        """
        res = {}
        for statement in self.browse(cr, uid, ids):
            res[statement.id] = ((statement.balance_end_real or 0.0) - (statement.balance_end or 0.0)) or 0.0
        return res

    _columns = {
        'virtual_id': fields.function(_get_register_id, method=True, store=False, type='integer', string='Id', readonly="1",
                                      help='Virtual Field that take back the id of the Register',  multi="id_local"),
        'local_register': fields.function(_get_register_id, method=True, store=False, type='boolean', string="Is local register", multi="id_local"),
        'closing_balance_frozen': fields.boolean(string="Closing balance freezed?", readonly="1"),
        'closing_balance_frozen_date': fields.date("Closing balance frozen date"),
        'filter_for_third_party': fields.function(_get_fake, type='char', string="Internal Field", fnct_search=_search_fake, method=False),
        'balance_gap': fields.function(_balance_gap_compute, method=True, string='Gap', readonly=True),
        'notes': fields.text('Comments', states={'confirm': [('readonly', True)]}),
        'period_number': fields.related('period_id', 'number', relation='account.period', string="Period number", type="integer", store=True, readonly=True),
        'closing_date': fields.date("Closed On"),
        'responsible_ids': fields.many2many('res.users', 'bank_statement_users_rel', 'statement_id', 'user_id', 'Responsible'),
        'bank_account_number': fields.related('journal_id', 'bank_account_number', type='char',
                                              string='Bank Account Number', store=False, readonly=True),
        'register_closed_by': fields.char('Register Closed by', size=128, states={'confirm': [('readonly', True)]},
                                          help='Name and position of the person who closes the register'),
    }

    def balance_check(self, cr, uid, register_id, journal_type='bank', context=None):
        """
        Check the balance for Registers
        """
        if not context:
            context = {}
        # Disrupt cheque verification
        if journal_type == 'cheque':
            return True
        # Add other verification for cash register
        if journal_type == 'cash':
            if not self._equal_balance(cr, uid, register_id, context):
                raise osv.except_osv(_('Error !'), _('CashBox Balance is not matching with Calculated Balance !'))
        st = self.browse(cr, uid, register_id, context=context)
        balance_end_real = round(st.balance_end_real or 0.0, 2)
        balance_end = round(st.balance_end or 0.0, 2)
        if abs(balance_end_real - balance_end) > 10**-3:
            raise osv.except_osv(_('Error !'),
                                 _('The statement balance is incorrect !\n') +
                                 _('The expected balance (%.2f) is different than the computed one. (%.2f)') % (st.balance_end_real, st.balance_end))
        return True

    def unlink(self, cr, uid, ids, context=None):
        """
        Delete a bank statement is forbidden!
        """
        if context and context.get('from', False) and context.get('from') == "journal_deletion":
            return super(account_bank_statement, self).unlink(cr, uid, ids)
        raise osv.except_osv(_('Warning'), _('Delete a Register is totally forbidden!'))
        return True

    def check_status_condition(self, cr, uid, state, journal_type='bank'):
        """
        Check Status of Register
        """
        return state =='draft' or state == 'open'


    def button_confirm_bank(self, cr, uid, ids, context=None):
        """
        Confirm Bank Statement
        """
        # First verify that all lines are in hard state
        for register in self.browse(cr, uid, ids, context=context):
            for line in register.line_ids:
                if line.state != 'hard':
                    raise osv.except_osv(_('Warning'), _('All entries must be hard posted before closing this Register!'))
        obj_seq = self.pool.get('ir.sequence')
        if context is None:
            context = {}

        for st in self.browse(cr, uid, ids, context=context):
            j_type = st.journal_id.type
#            company_currency_id = st.journal_id.company_id.currency_id.id
            if not self.check_status_condition(cr, uid, st.state, journal_type=j_type):
                continue

            # US-665 Do not permit closing Bank/Cheque Register if previous register is not closed! (confirm state)
            if st.prev_reg_id and st.prev_reg_id.state != 'confirm':
                raise osv.except_osv(_('Error'), _('Please close previous register before closing this one!'))

            # modification of balance_check for cheque registers
            if st.journal_id.type in ['bank', 'cash']:
                self.balance_check(cr, uid, st.id, journal_type=j_type, context=context)
            if (not st.journal_id.default_credit_account_id) \
                    or (not st.journal_id.default_debit_account_id):
                raise osv.except_osv(_('Configuration Error !'),
                                     _('Please verify that an account is defined in the journal.'))

            if not st.name == '/':
                st_number = st.name
            else:
                if st.journal_id.sequence_id:
                    c = {'fiscalyear_id': st.period_id.fiscalyear_id.id}
                    st_number = obj_seq.get_id(cr, uid, st.journal_id.sequence_id.id, context=c)
                else:
                    st_number = obj_seq.get(cr, uid, 'account.bank.statement')

            for line in st.move_line_ids:
                if line.state <> 'valid':
                    raise osv.except_osv(_('Error !'),
                                         _('The account entries lines are not in valid state.'))
            for st_line in st.line_ids:
                if st_line.analytic_account_id:
                    if not st.journal_id.analytic_journal_id:
                        raise osv.except_osv(_('No Analytic Journal !'),_("You have to define an analytic journal on the '%s' journal!") % (st.journal_id.name,))
                if not st_line.amount:
                    continue
            self.write(cr, uid, [st.id], {'name': st_number, 'closing_date': time.strftime("%Y-%m-%d")}, context=context)
            # Verify that the closing balance is frozen
            if not st.closing_balance_frozen and st.journal_id.type in ['bank', 'cash']:
                raise osv.except_osv(_('Error'), _("Please confirm closing balance before closing register named '%s'") % st.name or '')
        # Display the bank confirmation wizard
        title = "Bank"
        if context.get('confirm_from', False) and context.get('confirm_from') == 'cheque':
            title = "Cheque"
        title += " confirmation wizard"
        return {
            'name': title,
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.confirm.bank',
            'target': 'new',
            'view_mode': 'form',
            'view_type': 'form',
            'context':
            {
                'active_id': ids[0],
                'active_ids': ids,
                'statement_id': st.id,
            }
        }

    def button_create_invoice(self, cr, uid, ids, context=None):
        """
        Create a direct invoice
        """
        if context is None:
            context = {}

        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
        self.check_access_rule(cr, real_uid, ids, 'write')

        # Search the customized view we made for Supplier Invoice (for * Register's users)
        currency =  self.read(cr, uid, ids, ['currency'])[0]['currency']
        if isinstance(currency, tuple):
            currency =currency[0]
        i = self.pool.get('wizard.account.invoice').search(cr, uid, [('currency_id','=',currency), ('register_id', '=', ids[0])])
        if not i:
            i = self.pool.get('wizard.account.invoice').create(cr, uid, {'currency_id': currency, 'register_id': ids[0], 'type': 'in_invoice'},
                                                               context={'journal_type': 'purchase', 'type': 'in_invoice', 'doc_type': 'di'})
        return {
            'name': "Supplier Direct Invoice",
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.account.invoice',
            'target': 'new',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': i,
            'context':
            {
                'active_id': ids[0],
                'type': 'in_invoice',
                'doc_type': 'di',
                'journal_type': 'purchase',
                'active_ids': ids,
                'from_wizard_di': 1,
            }
        }

    def button_wiz_import_invoices(self, cr, uid, ids, context=None):
        """
        When pressing 'Pending Payments' button then opening a wizard to select some invoices and add them into the register by changing their states to 'paid'.
        """
        # statement_id is useful for making some line's registration.
        # currency_id is useful to filter invoices in the same currency
        st = self.browse(cr, uid, ids[0], context=context)
        i = self.pool.get('wizard.import.invoice').create(cr, uid, {'statement_id': ids[0] or None, 'currency_id': st.currency.id or None}, context=context)
        # Remember if we come from a cheque register (for adding some fields)
        from_cheque = False
        if st.journal_id.type == 'cheque':
            from_cheque = True
        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
        self.check_access_rule(cr, real_uid, ids, 'write')
        return {
            'name': "Import Invoice",
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.import.invoice',
            'target': 'new',
            'view_mode': 'form,tree',
            'view_type': 'form',
            'res_id': [i],
            'context':
            {
                'active_id': ids[0],
                'active_ids': ids,
                'from_cheque': from_cheque,
                'st_id': st.id,
                'st_period_id': st.period_id and st.period_id.id or False,
            }
        }

    def button_wiz_import_cheques(self, cr, uid, ids, context=None):
        """
        When pressing 'Import Cheques' button then opening a wizard to select some cheques from a register and add them into the present register
        in a temp post state.
        """
        # statement_id is useful for making some line's registration.
        # currency_id is useful to filter cheques in the same currency
        # period_id is useful to filter cheques drawn in the same period
        st = self.browse(cr, uid, ids[0], context=context)
        i = self.pool.get('wizard.import.cheque').create(cr, uid, {'statement_id': ids[0] or None, 'currency_id': st.currency.id or None,
                                                                   'period_id': st.period_id.id}, context=context)
        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
        self.check_access_rule(cr, real_uid, ids, 'write')
        return {
            'name': "Import Cheque",
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.import.cheque',
            'target': 'new',
            'view_mode': 'form,tree',
            'view_type': 'form',
            'res_id': [i],
            'context':
            {
                'active_id': ids[0],
                'active_ids': ids,
            }
        }

    def button_confirm_closing_balance(self, cr, uid, ids, context=None):
        """
        Confirm that the closing balance could not be editable.
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = []

        # check if write is allowed
        user_id = hasattr(uid, 'realUid') and uid.realUid or uid
        for reg in self.browse(cr, uid, ids, context=context):
            # Validate register only if this one is open
            if reg.state == 'open':
                now_orm = self.pool.get('date.tools').date2orm(
                    datetime.datetime.now().date())
                res_id = self.write(cr, user_id, [reg.id], {
                    'closing_balance_frozen': True,
                    'closing_balance_frozen_date': now_orm,
                }, context=context)
                res.append(res_id)

            else:
                # question: is it possible to click on the button if the register state != 'open' ?
                # check user access
                self.write(cr, user_id, [reg.id], {'closing_balance_frozen': reg.closing_balance_frozen}, context=context)

            # Create next starting balance for cash registers
            if reg.journal_id.type == 'cash':
                create_cashbox_lines(self, cr, uid, reg.id, context=context)
            # For bank statement, give balance_end
            elif reg.journal_id.type == 'bank':
                # Verify that another bank statement exists.
                st_prev_ids = self.search(cr, uid, [('prev_reg_id', '=', reg.id)], context=context)
                if len(st_prev_ids) > 1:
                    raise osv.except_osv(_('Error'), _('A problem occurred: More than one register have this one as previous register!'))
                if st_prev_ids:
                    self.write(cr, uid, st_prev_ids, {'balance_start': reg.balance_end_real}, context=context)
        return res

    def button_cancel_closing_balance_confirmation(self, cr, uid, ids, context=None):
        """
        Resets the confirmation of the register month-end balance, which makes it re-editable. Note that the starting
        balance of the reg. N+1 is not updated (this will be done at next closing balance confirmation of the reg. N).
        """
        if context is None:
            context = {}
        for reg in self.browse(cr, uid, ids, fields_to_fetch=['state'], context=context):
            # action performed only if the register is still open
            if reg.state == 'open':
                self.write(cr, uid, [reg.id], {'closing_balance_frozen': False,
                                               'closing_balance_frozen_date': False,
                                               }, context=context)
        return True

    def button_confirm_closing_bank_balance(self, cr, uid, ids, context=None):
        """
        Verify bank statement balance before closing it.
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for reg in self.browse(cr, uid, ids):
            # Verify that the closing balance (balance_end_real) correspond to the calculated balance (balance_end)
            # NB: UTP-187 reveals that some difference appears between balance_end_real and balance_end. These fields are float. And balance_end_real is calculated. In python this imply some difference.
            # Because of fields values with 2 digits, we compare the two fields difference with 0.001 (10**-3)
            if (abs(round(reg.balance_end_real, 2) - round(reg.balance_end, 2))) > 10**-3:
                raise osv.except_osv(_('Warning'), _('Bank statement balance is not equal to Calculated balance.'))
        return self.button_confirm_closing_balance(cr, uid, ids, context=context)

    def button_open_advances(self, cr, uid, ids, context=None):
        """
        Open a list of open advances
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values

        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
        self.check_access_rule(cr, real_uid, ids, 'write')


        date = time.strftime('%Y-%m-%d')
        registers = self.browse(cr, uid, ids, context=context)
        register = registers and registers[0] or False
        if not register:
            raise osv.except_osv(_('Error'), _('Please select a register first.'))
        context.update({'check_advance_reconciled': True})
        domain = [('account_id.type_for_register', '=', 'advance'),
                  ('state', 'in', ['temp', 'hard']),
                  ('reconciled', '=', False),
                  ('amount', '<=', 0.0),
                  ('date', '<=', date)]
        name = _('Open Advances')
        if register.journal_id and register.journal_id.currency:
            # prepare some values
            name += ' - ' + register.journal_id.code + ' - '+ register.journal_id.currency.name
            domain.append(('statement_id.journal_id.currency', '=', register.journal_id.currency.id))
        # Prepare view
        view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'register_accounting', 'view_account_bank_statement_line_tree')
        view_id = view and view[1] or False
        # Prepare search view
        search_view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'register_accounting', 'view_account_bank_statement_line_filter')
        search_view_id = search_view and search_view[1] or False
        context.update({'open_advance': register.id, 'search_default_current_register': True, 'current_register_journal': register.journal_id.id})
        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'res_model': 'account.bank.statement.line',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'view_id': [view_id],
            'search_view_id': search_view_id,
            'domain': domain,
            'context': context,
            'target': 'current',
        }

    def get_register_lines(self, cr, uid, ids, context=None):
        """
        Return all register lines from first given register
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        domain = [('statement_id', '=', ids[0])]
        # Search valid ids
        reg = self.browse(cr, uid, ids[0])
        if reg and reg.journal_id.type in ['bank', 'cash', 'cheque']:
            context.update({
                'journal_type': reg.journal_id.type,
                'from_regline_view': True,
                'register_id': reg.id,
            })
        return {
            'name': reg and reg.name or 'Register Lines',
            'type': 'ir.actions.act_window',
            'res_model': 'account.bank.statement.line',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'context': context,
            'domain': domain,
            'target': 'current',
        }

    def get_analytic_register_lines(self, cr, uid, ids, context=None):
        """
        Return all FP analytic lines attached to register lines from first given register
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Search valid ids
        reg = self.browse(cr, uid, ids[0])
        domain = [('account_id.category', '=', 'FUNDING'), ('move_id.statement_id', 'in', [ids[0]])]
        context.update({'display_fp': True})
        return {
            'name': reg and 'Analytic Entries from ' + reg.name or 'Analytic Entries',
            'type': 'ir.actions.act_window',
            'res_model': 'account.analytic.line',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'context': context,
            'domain': domain,
            'target': 'current',
        }

    def get_statement(self, cr, uid, ids, st_type='bank', context=None):
        """
        Give the search + tree view of account cash statement with a pre-filled instance field
        """
        # Some checks
        if context is None:
            context = {}
        # Prepare some values
        domain = [('journal_id.type', '=', st_type)]
        context.update({
            'journal_type': st_type,
            'search_default_open': 1,
            #'search_default_instance_id': instance_id,
            'active_id': False, # this is to avoid some "No field_values" problem
            'active_ids': False, # idem that active_id
        })
        st_help = "A bank statement is a summary of all financial transactions occurring over a given period of time on a deposit account, a credit card or any other type of financial account. The starting balance will be proposed automatically and the closing balance is to be found on your statement. When you are in the Payment column of a line, you can press F1 to open the reconciliation form."
        tree_module = 'account'
        tree_view = 'view_bank_statement_tree'
        search_module = 'register_accounting'
        search_view = 'view_bank_statement_search'
        name = _('Bank Registers')
        res_module = 'register_accounting'
        res_view = 'inherit_view_bank_statement_form'
        if st_type == 'cheque':
            name = _('Cheque Registers')
            tree_module = 'register_accounting'
            tree_view = 'view_cheque_register_tree'
            search_module = 'register_accounting'
            search_view = 'view_cheque_register_search'
            res_module = 'register_accounting'
            res_view = 'view_cheque_register_form'
            st_help = "A cheque register is a summary of all financial transactions occurring over a given period of time on a cheque account. \
The starting balance will be proposed automatically and the closing balance is to be found on your statement."
        elif st_type == 'cash':
            name = _('Cash Registers')
            tree_module = 'register_accounting'
            tree_view = 'view_cash_statement_tree'
            search_module = 'account'
            search_view = 'view_account_bank_statement_filter'
            res_module = 'register_accounting'
            res_view = 'inherit_view_bank_statement_form2'
            st_help = "A Cash Register allows you to manage cash entries in your cash journals. This feature provides an easy way to follow up cash payments on a daily basis. You can enter the coins that are in your cash box, and then post entries when money comes in or goes out of the cash box."
        # Search views
        tree_view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, tree_module, tree_view)
        tree_view_id = tree_view_id and tree_view_id[1] or False
        search_view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, search_module, search_view)
        search_view_id = search_view_id and search_view_id[1] or False
        res_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, res_module, res_view)
        res_id = res_id and res_id[1] or False
        # Return the search view
        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'res_model': 'account.bank.statement',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'view_id': [tree_view_id],
            'search_view_id': search_view_id,
            'views': [(tree_view_id, 'tree'), (res_id, 'form')],
            'context': context,
            'domain': domain,
            'target': 'current',
            'help': st_help,
        }

    def get_analytic_register_free1_lines(self, cr, uid, ids, context=None):
        """
        Return all FREE1 analytic lines attached to register lines from first given register
        """
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Search valid ids
        reg = self.browse(cr, uid, ids[0])
        domain = [('account_id.category', '=', 'FREE1'), ('move_id.statement_id', 'in', [ids[0]])]
        context.update({'display_fp': False, 'categ': 'FREE1'})
        return {
            'name': reg and 'Free 1 Analytic Entries from ' + reg.name or 'Free 1 Analytic Entries',
            'type': 'ir.actions.act_window',
            'res_model': 'account.analytic.line',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'context': context,
            'domain': domain,
            'target': 'current',
        }

    def get_analytic_register_free2_lines(self, cr, uid, ids, context=None):
        """
        Return all FREE2 analytic lines attached to register lines from first given register
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Search valid ids
        reg = self.browse(cr, uid, ids[0])
        domain = [('account_id.category', '=', 'FREE2'), ('move_id.statement_id', 'in', [ids[0]])]
        context.update({'display_fp': False, 'categ': 'FREE2'})
        return {
            'name': reg and 'Free 2 Analytic Entries from ' + reg.name or 'Free 2 Analytic Entries',
            'type': 'ir.actions.act_window',
            'res_model': 'account.analytic.line',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'context': context,
            'domain': domain,
            'target': 'current',
        }

    def get_pending_cheque_ids(self, cr, uid, register_ids, account_ids, min_posting_date, aml_ids=None, context=None):
        """
        Returns a list containing the ids of the JIs matching the following criteria:
        - if aml_ids is given: having their ids in this list, else booked in the register(s) and in the account(s) in
          parameters (note that registers don't exist at HQ level)
        - either not reconciled or reconciled partially or totally with at least one reconciliation leg having a
          posting date later than the min_posting_date in parameter
        """
        if context is None:
            context = {}
        aml_obj = self.pool.get('account.move.line')
        if aml_ids is None:
            aml_ids = aml_obj.search(cr, uid, [('statement_id', 'in', register_ids),
                                               ('account_id', 'in', account_ids), ],
                                     order='date DESC', context=context)
        if not aml_ids:
            return []
        cr.execute('''select l1.id from account_move_line l1
                 left join account_move_line l2 on l2.date > %s and (l2.reconcile_id = l1.reconcile_id or l2.reconcile_partial_id = l1.reconcile_partial_id)
                 where l1.id in %s
                 and coalesce(l2.is_addendum_line, 'f') = 'f'
                 group by l1.id
                 having (l1.reconcile_id is null and l1.reconcile_partial_id is null) or count(l2) > 0
                ''', (min_posting_date, tuple(aml_ids)))
        return [x[0] for x in cr.fetchall()]

    def open_register(self, cr, uid, reg_id, cash_opening_balance=None, context=None):
        """
        Opens the register and updates the related XML_ID
        """
        if context is None:
            context = {}
        reg = self.browse(cr, uid, reg_id, fields_to_fetch=['period_id', 'journal_id'], context=context)
        if reg.period_id.state in ['field-closed', 'mission-closed', 'done']:
            raise osv.except_osv(_('Error'),
                                 _('The associated period is closed.'))
        if reg.journal_id.type == 'cash':
            self.do_button_open_cash(cr, uid, [reg_id], opening_balance=cash_opening_balance, context=context)
        else:
            self.write(cr, uid, [reg_id], {'state': 'open', 'name': reg.journal_id.name})
        # The update of xml_id must be done when opening the register
        # --> set the value of xml_id based on the period as period is no more editable
        self.update_xml_id_register(cr, uid, reg_id, context)
        return True

    def button_open_cash_register(self, cr, uid, ids, context=None):
        return self.button_open_register(cr, uid, ids, context=context)

    def button_open_cheque_register(self, cr, uid, ids, context=None):
        return self.button_open_register(cr, uid, ids, context=context)

    def button_open_bank_register(self, cr, uid, ids, context=None):
        return self.button_open_register(cr, uid, ids, context=context)

    def button_open_register(self, cr, uid, ids, context=None):
        """
        Opens the "Register Opening Confirmation" wizard if it is the first register of the journal,
        else opens the register directly.
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = False
        wiz_reg_opening_obj = self.pool.get('wizard.register.opening.confirmation')
        if ids:
            reg = self.browse(cr, uid, ids[0], fields_to_fetch=['prev_reg_id', 'journal_id'], context=context)
            if not reg.prev_reg_id:
                wiz_id = wiz_reg_opening_obj.create(cr, uid, {'register_id': ids[0]}, context=context)
                return {'name': _('Open Register Confirmation'),
                        'type': 'ir.actions.act_window',
                        'res_model': 'wizard.register.opening.confirmation',
                        'target': 'new',
                        'view_mode': 'form',
                        'view_type': 'form',
                        'res_id': [wiz_id],
                        'context': context,
                        }
            else:
                computed_balance = 0.0
                if reg.journal_id.type == 'cash':
                    computed_balance = self._get_starting_balance(cr, uid, [ids[0]], context=context)[ids[0]].get('balance_start', 0.0)
                return self.open_register(cr, uid, ids[0], cash_opening_balance=computed_balance, context=context)
        return res

account_bank_statement()


class account_bank_statement_line(osv.osv):
    _name = "account.bank.statement.line"
    _inherit = "account.bank.statement.line"

    _order = 'sequence_for_order desc, sequence_for_reference desc, document_date desc, date desc, id desc'


    def check_access_rule(self, cr, uid, ids, operation, context=None):
        if operation == 'create':
            real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
        else:
            real_uid = uid

        return super(account_bank_statement_line, self).check_access_rule(cr, real_uid, ids, operation, context=context)

    def _get_state(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Return account_bank_statement_line state in order to know if the bank statement line is in :
        - draft
        - temp posting
        - hard posting
        - unknown if an error occurred or anything else (for an example the move have a new state)
        """
        res = {}
        # Optimization: Use SQL request instead of a browse to improve result generation for cases where you have a lot of line (30+)
        sql = """
            SELECT
                absl.id,
                CASE
                    WHEN absl.direct_invoice = 'f' AND am.state IS NULL THEN 'draft'
                    WHEN absl.direct_invoice = 'f' AND am.state = 'draft' THEN 'temp'
                    WHEN absl.direct_invoice = 'f' AND am.state = 'posted' THEN 'hard'
                    WHEN absl.direct_invoice = 't' THEN absl.direct_state
                    ELSE 'unknown'
                END AS absl_state
            FROM account_bank_statement_line AS absl
                LEFT JOIN account_bank_statement_line_move_rel AS abslm ON abslm.move_id = absl.id
                LEFT JOIN account_move AS am ON abslm.statement_id = am.id
            WHERE absl.id IN %s
            ORDER BY absl.id;"""
        cr.execute(sql, (tuple(ids),))
        tmp_res = cr.fetchall()
        if tmp_res:
            res = dict(tmp_res)
        return res

    def _get_amount(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Get the amount from amount_in and amount_on
        """
        # Variable initialisation
        default_amount = 0.0
        res = {}
        # Browse account bank statement lines
        for absl in self.browse(cr, uid, ids, context=context):
            # amount is positive so he should be in amount_in
            if absl.amount > 0 and field_name == "amount_in":
                res[absl.id] = abs(absl.amount)
            # amount is negative, it should be in amount_out
            elif absl.amount < 0 and field_name == "amount_out":
                res[absl.id] = abs(absl.amount)
            # if no result, we display 0.0 (default amount)
            else:
                res[absl.id] = default_amount
        return res

    def _search_state(self, cr, uid, obj, name, args, context=None):
        """
        Search elements by state :
        - draft
        - temp
        """
        # Test how many arguments we have
        if not len(args):
            return []

        # We just support = and in operators
        if args[0][1] not in ['=', 'in']:
            raise osv.except_osv(_('Warning'), _('This filter is not implemented yet!'))
        # Case where we search draft lines
        sql_draft = """
            SELECT st.id FROM account_bank_statement_line st
            LEFT JOIN account_bank_statement_line_move_rel rel ON rel.move_id = st.id
            WHERE rel.move_id is null
            """
        sql_temp = """SELECT st.id FROM account_bank_statement_line st
            LEFT JOIN account_bank_statement_line_move_rel rel ON rel.move_id = st.id
            LEFT JOIN account_move m ON m.id = rel.statement_id
            WHERE m.state = 'draft'
            """
        sql_hard = """SELECT st.id FROM account_bank_statement_line st
            LEFT JOIN account_bank_statement_line_move_rel rel ON rel.move_id = st.id
            LEFT JOIN account_move m ON m.id = rel.statement_id
            WHERE m.state = 'posted'
            """
        ids = []
        filterok = False
        if args[0][1] == '=' and args[0][2] == 'draft' or 'draft' in args[0][2]:
            sql = sql_draft
            cr.execute(sql)
            ids += [x[0] for x in cr.fetchall()]
            filterok = True
        # Case where we search temp lines
        if args[0][1] == '=' and args[0][2] == 'temp' or 'temp' in args[0][2]:
            sql = sql_temp
            cr.execute(sql)
            ids += [x[0] for x in cr.fetchall()]
            filterok = True
        if args[0][1] == '=' and args[0][2] == 'hard' or 'hard' in args[0][2]:
            sql = sql_hard
            cr.execute(sql)
            ids += [x[0] for x in cr.fetchall()]
            filterok = True

        # Case with IN

# If args[0][1] == 'in', so create a SQL request like this:
# SELECT st.id
# FROM account_bank_statement_line st
#     LEFT JOIN account_bank_statement_line_move_rel rel ON rel.move_id = st.id
#     LEFT JOIN account_move am ON am.id = rel.statement_id
# WHERE (rel.statement_id is null OR am.state != 'posted')
# ORDER BY st.id;

        # Non expected case
        if not filterok:
            raise osv.except_osv(_('Warning'), _('This filter is not implemented yet!'))
        return [('id', 'in', ids)]

    def _get_reconciled_state(self, cr, uid, ids, field_name=None, args=None, context=None):
        """
        Give the state of reconciliation for the account bank statement line
        """
        # Prepare some values
        res = {}
        # browse account bank statement lines
        for absl in self.browse(cr, uid, ids):
            # browse each move and move lines
            if absl.move_ids and absl.state == 'hard':
                res[absl.id] = False
                for move in absl.move_ids:
                    for move_line in move.line_id:
                        # Result is True if the account is reconciliable and a reconcile_id exists
                        if move_line.account_id.reconcile and move_line.reconcile_id:
                            res[absl.id] = True
                            break
            else:
                res[absl.id] = False
        return res

    def _search_reconciled(self, cr, uid, obj, name, args, context=None):
        """
        Search all lines that are reconciled or not
        If 'check_advance_reconciled' is in context, restrict the search to the accounts having the type "Advance".
        Use case:
        - advance booked on the account 13000 - Operating advances in a CHEQUE register
        - advance line reconciled
        - the register line should be seen as reconciled even if the other leg of the JE
          (on the account 10210 - Outstanding Cheques) is still reconcilable.
        """
        # Test how many arguments we have
        if not len(args):
            return []
        if context is None:
            context = {}
        # We just support "=" case
        if args[0][1] not in ['=', 'in']:
            raise osv.except_osv(_('Warning'), _('This filter is not implemented yet!'))
        # Search statement lines that have move lines and which moves are posted
        check_advance_reconciled = ''
        if context.get('check_advance_reconciled', False):
            check_advance_reconciled = " AND ac.type_for_register = 'advance' "
        if args[0][2] == True:
            sql_posted_moves = """
                SELECT st.id FROM account_bank_statement_line st
                    LEFT JOIN account_bank_statement_line_move_rel rel ON rel.move_id = st.id
                    LEFT JOIN account_move move ON rel.statement_id = move.id
                    LEFT JOIN account_move_line line ON line.move_id = move.id
                    LEFT JOIN account_account ac ON ac.id = line.account_id
                WHERE rel.move_id is not null AND move.state = 'posted'
                      %(check_advance_reconciled)s
                GROUP BY st.id HAVING COUNT(reconcile_id IS NULL AND ac.reconcile='t' OR NULL)=0;
            """
        else:
            sql_posted_moves = """
                SELECT st.id FROM account_bank_statement_line st
                    LEFT JOIN account_bank_statement_line_move_rel rel ON rel.move_id = st.id
                    LEFT JOIN account_move move ON rel.statement_id = move.id
                    LEFT JOIN account_move_line line ON line.move_id = move.id
                    LEFT JOIN account_account ac ON ac.id = line.account_id
                WHERE
                    rel.move_id is null OR move.state != 'posted' OR 
                    (line.reconcile_id IS NULL AND ac.reconcile='t' 
                     %(check_advance_reconciled)s );
            """
        sql_posted_moves = sql_posted_moves % {'check_advance_reconciled': check_advance_reconciled}
        cr.execute(sql_posted_moves) # not_a_user_entry
        return [('id', 'in', [x[0] for x in cr.fetchall()])]

    def _search_amount(self, cr, uid, obj, name, args, context=None):
        """
        Search all lines that have this amount
        """
        # Test how many arguments we have
        if not len(args):
            return []
        # Search statement lines that have amount corresponding to what expected
        operator = args[0][1]
        args2 = args[0][2]
        if name == 'amount_out':
            args2 = "-%s" % (args[0][2])
            if args[0][1] == '<=':
                operator = '>='
            elif args[0][1] == '>=':
                operator = '<='
        return [('amount', operator, args2)]

    def _get_number_imported_invoice(self, cr, uid, ids, field_name=None, args=None, context=None):
        ret = {}
        for i in self.read(cr, uid, ids, ['imported_invoice_line_ids']):
            ret[i['id']] = len(i['imported_invoice_line_ids'])
        return ret

    def _get_down_payment_state(self, cr, uid, ids, field_name=None, args=None, context=None):
        """
        Verify down payment eligibility:
         - account should be a down_payment type for register
         - amount should be negative
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        sql = """
            SELECT absl.id, CASE WHEN a.type_for_register = 'down_payment' THEN true ELSE false END AS res
            FROM account_bank_statement_line AS absl, account_account AS a
            WHERE absl.account_id = a.id
            AND absl.id IN %s
            ORDER BY absl.id;
        """
        cr.execute(sql, (tuple(ids),))
        tmp_res = cr.fetchall()
        if not tmp_res:
            return res
        return dict(tmp_res)

    def _get_transfer_with_change_state(self, cr, uid, ids, field_name=None, args=None, context=None):
        """
        If account is a transfer with change, then True. Otherwise False.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        sql = """
        SELECT absl.id, a.type_for_register
        FROM account_bank_statement_line AS absl, account_account AS a
        WHERE absl.account_id = a.id
        AND absl.id IN %s
        ORDER BY absl.id;
        """
        cr.execute(sql, (tuple(ids),))
        # Browse elements
        #+ If type_for_register is transfer, True. Otherwise False.
        for line in cr.fetchall():
            res[line[0]] = line[1] == 'transfer'
        return res

    def _get_sequence(self, cr, uid, ids, field_name=None, args=None, context=None):
        """
        Get default sequence number: "" (no char).
        If moves, get first one's name.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for line in self.browse(cr, uid, ids):
            res[line.id] = {
                'sequence_for_reference': '',
                'sequence_for_order': line.id
            }
            if len(line.move_ids) > 0:
                res[line.id] = {
                    'sequence_for_reference': line.move_ids[0].name,
                    'sequence_for_order': 0
                }
            else:
                # UFTP-201: If there is no move linked to this reg line, get the current value of ref
                res[line.id] = {
                    'sequence_for_reference': line.sequence_for_reference,
                    'sequence_for_order': not line.sequence_for_reference and line.id or 0
                }

        return res

    def _get_bank_statement_line_ids(self, cr, uid, ids, context=None):
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        result = []
        for move in self.pool.get('account.move').browse(cr, uid, ids, context=context):
            if move.statement_line_ids:
                for statement in move.statement_line_ids:
                    result.append(statement.id)
        return result

    def _get_move_ids(self, cr, uid, ids, context=None):
        """
        Get all account move linked to the given register, those from analytic lines correction included!
        """
        # Some verifications
        if not context:
            context = {}
        res = set()
        for absl in self.browse(cr, uid, ids, context=context):
            if absl.move_ids:
                # Default ones (direct link to register lines)
                for m in absl.move_ids:
                    res.add(m.id)
                    # Fetch reversal and correction moves
                    # UTP-1055: delete lines that fetch reconciled lines so that cash advance return don't give all lines in the Full Report
                    for ml in m.line_id:
                        other_ml_ids = self.pool.get('account.move.line').search(cr, uid, ['|', ('reversal_line_id', '=', ml.id), ('corrected_line_id', '=', ml.id)], context=context)
                        if other_ml_ids:
                            for el in self.pool.get('account.move.line').read(cr, uid, other_ml_ids, ['move_id'], context=context):
                                if el.get('move_id', False) and el.get('move_id')[0]:
                                    res.add(el['move_id'][0])
            # Those from pending payments (imported_invoice_line_ids are move_line)
            if absl.imported_invoice_line_ids:
                for ml in absl.imported_invoice_line_ids:
                    res.add(ml.move_id.id)
            # UTP-1039: Show the search loop for direct invoice
            if absl.invoice_id and (absl.direct_invoice or absl.cash_return_move_line_id):
                # BKLG-60: reg line from advance return: display invoice(s) AJIs too
                res.add(absl.invoice_id.move_id.id)
            elif not absl.invoice_id and absl.direct_invoice:
                # US-512:
                # above case UTP-1039 was ok for temp posted direct invoice
                # hard posted direct invoice regline case (and sync P1->C1)
                if absl.direct_invoice_move_id:
                    res.add(absl.direct_invoice_move_id.id)
            # advance closed by a SI in project => in upper inst. invoice_id is empty: use advance_invoice_move_id
            elif not absl.invoice_id and absl.advance_invoice_move_id:
                res.add(absl.advance_invoice_move_id.id)
        return list(res)

    def _get_fp_analytic_lines(self, cr, uid, ids, field_name=None, args=None, context=None):
        """
        Get all analytic lines linked to the given register lines
        """

        if not context:
            context = {}

        res = {}
        aal_obj = self.pool.get('account.analytic.line')
        for absl in self.browse(cr, uid, ids, context=context):
            # UTP-1055: In case of Cash Advance register line, we don't need to see all other advance lines allocation (analytic lines). So we keep only analytic lines with the same "name" than register line
            aal_ids = self.pool.get('account.analytic.line').search(cr, uid, [('move_id.move_id', 'in', self._get_move_ids(cr, uid, [absl.id], context=context)), ('account_id.category', '=', 'FUNDING'), ('name', '=ilike', '%%%s' % absl.name)])
            # Then retrieve all corrections/reversals from them
            res[absl.id] = aal_obj.get_corrections_history(cr, uid, aal_ids, context=context)
        return res

    def _get_free_analytic_lines(self, cr, uid, ids, field_name=None, args=None, context=None):
        """
        Get analytic lines Free 1 and Free 2 linked to the given register lines
        """
        if not context:
            context = {}
        res = {}
        aal_obj = self.pool.get('account.analytic.line')
        for absl in self.browse(cr, uid, ids, context=context):
            # UTP-1055: In case of Cash Advance register line, we don't need to see all other advance lines allocation (analytic lines).
            # So we keep only analytic lines with the same "name" than register line
            aal_ids = self.pool.get('account.analytic.line').search(cr, uid, [('move_id.move_id', 'in', self._get_move_ids(cr, uid, [absl.id], context=context)),
                                                                              ('account_id.category', 'in', ['FREE1', 'FREE2']), ('name', '=ilike', '%%%s' % absl.name)])
            # Then retrieve all corrections/reversals from them
            res[absl.id] = aal_obj.get_corrections_history(cr, uid, aal_ids, context=context)
        return res

    def _check_red_on_supplier(self, cr, uid, ids, name, arg, context=None):
        result = {}
        for id in ids:
            result[id] = {'red_on_supplier': False}

        for out in self.browse(cr, uid, ids, context=context):
            type_for_register = out.account_id.type_for_register
            if type_for_register in ['advance','transfer_same','down_payment','transfer']:
                if out.partner_id.id is False and out.employee_id.id is False and out.transfer_journal_id.id is False:
                    result[out.id]['red_on_supplier'] = True
        return result

    def _get_number_imported_account_invoices(self, cr, uid, ids, field_name=None, args=None, context=None):
        """
        For each register line, gets the number of real account.invoices imported, even partially.
        Other types of lines imported are ignored.
        """
        res = {}
        if context is None:
            context = {}
        for regline in self.read(cr, uid, ids, ['imported_account_invoice_ids'], context=context):
            res[regline['id']] = len(regline['imported_account_invoice_ids'])
        return res

    def _search_current_register(self, cr, uid, obj, name, args, context=None):
        if context is None:
            context = {}
        if not args or 'current_register_journal' not in context:
            return []
        return [('journal_id', '=', context['current_register_journal'])]

    _columns = {
        'transfer_journal_id': fields.many2one("account.journal", "Journal", ondelete="restrict"),
        'auto_counterpart': fields.boolean('Is/Was linked to a counterpart', readonly=1),
        'counterpart_transfer_st_line_id': fields.many2one('account.bank.statement.line', 'Counterpart line', readonly=1, ondelete='set null'),
        'counterpart_transfer_st_line_sdref': fields.char('St couterpert line sdref', size=128, select=1, readonly=1, help='used by sync, bc draft reg line are not synced'),
        'has_a_counterpart_transfer': fields.boolean('Has a counterpart_transfer', select=1, readonly=1, help="used by sync, bc draft reg line are not synced"),
        'employee_id': fields.many2one("hr.employee", "Employee", ondelete="restrict"),
        'partner_id': fields.many2one('res.partner', 'Partner', ondelete="restrict"),
        'amount_in': fields.function(_get_amount, fnct_search=_search_amount, method=True, string="Amount In", type='float'),
        'amount_out': fields.function(_get_amount, fnct_search=_search_amount, method=True, string="Amount Out", type='float'),
        'state': fields.function(_get_state, fnct_search=_search_state, method=True, string="Status", type='selection', selection=[
            ('draft', 'Draft'), ('temp', 'Temp'), ('hard', 'Hard'), ('unknown', 'Unknown')]),
        'direct_state': fields.char(string="Direct Invoice State", size=8),  # draft, temp, hard. See ticket utp917
        'partner_type': fields.function(_get_third_parties, fnct_inv=_set_third_parties, type='reference', method=True,
                                        string="Third Parties", selection=[('res.partner', 'Partner'), ('account.journal', 'Journal'), ('hr.employee', 'Employee')],
                                        multi="third_parties_key", hide_default_menu=True),
        'partner_type_mandatory': fields.boolean('Third Party Mandatory'),
        'reconciled': fields.function(_get_reconciled_state, fnct_search=_search_reconciled, method=True, string="Amount Reconciled",
                                      type='boolean', store=False),
        # WARNING: Due to UTP-348, store = True for sequence_for_reference field is mandatory! Otherwise this breaks Cheque Inventory report.
        'sequence_for_reference': fields.function(_get_sequence, method=True, string="Sequence", type="char",
                                                  store={
                                                      'account.bank.statement.line': (lambda self, cr, uid, ids, c=None: ids, ['move_ids'], 10),
                                                      'account.move': (_get_bank_statement_line_ids, ['statement_line_ids'], 10)
                                                  }, size=64, multi='_seq_for_ref_order'),
        'sequence_for_order': fields.function(_get_sequence, method=True, string="Sequence (for order)", type="float", store=True, readonly=1, multi='_seq_for_ref_order'),
        'date': fields.date('Posting Date', required=True),
        'document_date': fields.date(string="Document Date", required=True),
        'cheque_number': fields.char(string="Cheque Number", size=120),
        'from_cash_return': fields.boolean(string='Come from a cash return?'),
        'direct_invoice': fields.boolean(string='Direct invoice?'),
        'first_move_line_id': fields.many2one('account.move.line', "Register Move Line"),
        'third_parties': fields.function(_get_third_parties, type='reference', method=True,
                                         string="Third Parties", selection=[('res.partner', 'Partner'), ('account.journal', 'Journal'), ('hr.employee', 'Employee')], help="To use for python code when registering", multi="third_parties_key"),
        'imported_invoice_line_ids': fields.many2many('account.move.line', 'imported_invoice', 'st_line_id', 'move_line_id',
                                                      string="Imported Invoices", required=False, readonly=True),
        'number_imported_invoice': fields.function(_get_number_imported_invoice, method=True, string='Number Invoices', type='integer'),
        # store only account.invoices and ignore other lines imported
        'imported_account_invoice_ids': fields.many2many('account.invoice', 'register_line_imported_account_invoice',
                                                         'regline_id', 'invoice_id', string='Real invoices imported',
                                                         required=False, readonly=True,
                                                         help="The invoices imported, even partially, "
                                                              "either directly into this register "
                                                              "or indirectly via the import of the related cheque."),
        'number_imported_account_invoices': fields.function(_get_number_imported_account_invoices, method=True, type='integer',
                                                            string='Number of real invoices imported', store=False),
        'is_down_payment': fields.function(_get_down_payment_state, method=True, string="Is a down payment line?",
                                           type='boolean', store=False),
        'from_import_cheque_id': fields.many2one('account.move.line', "Cheque Line",
                                                 help="This move line has been taken for create an Import Cheque in a bank statement."),
        'is_transfer_with_change': fields.function(_get_transfer_with_change_state, method=True, string="Is a transfer with change line?",
                                                   type='boolean', store=False),
        'is_current_register': fields.function(get_fake, fnct_search=_search_current_register, method=True,
                                               string="Is this open advance from current register journal?",
                                               type='boolean', store=False),
        'down_payment_id': fields.many2one('purchase.order', "Down payment", readonly=True),
        'transfer_amount': fields.float(string="Amount", help="Amount used for Transfers"),
        'type_for_register': fields.related('account_id','type_for_register', string="Type for register", type='selection', selection=[('none','None'),
                                                                                                                                       ('transfer', 'Internal Transfer'), ('transfer_same', 'Internal Transfer (same currency)'), ('advance', 'Operational Advance'),
                                                                                                                                       ('payroll', 'Third party required - Payroll'), ('down_payment', 'Down payment'), ('donation', 'Donation')] , readonly=True),
        'fp_analytic_lines': fields.function(_get_fp_analytic_lines, type="one2many", obj="account.analytic.line", method=True, string="Analytic lines linked to the given register line(s). Correction(s) included."),
        'free_analytic_lines': fields.function(_get_free_analytic_lines, type="one2many", obj="account.analytic.line", method=True, string="Analytic lines Free 1 and Free 2 linked to the given register line(s). Correction(s) included."),
        'red_on_supplier': fields.function(_check_red_on_supplier, method=True, type="boolean", string="Supplier flag", store=False, readonly=True, multi="m"),
        'journal_id': fields.related('statement_id','journal_id', string="Journal", type='many2one', relation='account.journal', readonly=True),
        'direct_invoice_move_id': fields.many2one('account.move', 'Direct Invoice Move', readonly=True, help="This field have been added to get the move that comes from the direct invoice because after synchronization some lines lost the direct invoice link. And so we can't see which move have been linked to the invoice in case the register line is temp posted."),
        'advance_invoice_move_id': fields.many2one('account.move', 'Account Move of the Invoice used to close the Advance',
                                                   readonly=True,
                                                   help="When a SI is used to close an Advance, the related JE is stored in this field"),
    }

    _defaults = {
        'from_cash_return': lambda *a: 0,
        'direct_invoice': lambda *a: 0,
        'transfer_amount': lambda *a: 0,
        'direct_state': lambda *a: 'draft',
    }

    def return_to_register(self, cr, uid, ids, context=None):
        """
        Return to register from which lines come from
        """
        st_line = self.browse(cr, uid, ids[0])
        if st_line and st_line.statement_id:
            return open_register_view(self, cr, uid, st_line.statement_id.id)
        raise osv.except_osv(_('Warning'), _('You have to select some line to return to a register.'))

    def show_analytic_lines(self, cr, uid, ids, context=None):
        """
        Show analytic lines list linked to the given register line(s)
        """
        # Some verifications
        if not context:
            context = {}
        if not 'active_ids' in context or not context.get('active_ids', False):
            raise osv.except_osv(_('Error'), _('No line selected!'))
        # Use right register line IDS
        ids = context.get('active_ids')
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Fetch move_ids linked to these register lines
        move_ids = self._get_move_ids(cr, uid, ids, context=context)
        # Search valid ids
        domain = [('account_id.category', '=', 'FUNDING'), ('move_id.move_id', 'in', move_ids)]

        # BKLG-60: for cash advance register lines, filtering on new
        # cash_return_move_line_id link field
        absl_brs = self.browse(cr, uid, ids, context=context)
        cash_adv_return_move_line_ids = [
            absl.cash_return_move_line_id.id \
            for absl in absl_brs \
            if not absl.invoice_id and not absl.advance_invoice_move_id and absl.from_cash_return and \
            absl.cash_return_move_line_id
            # NOTE: for imported invoices we let the default behaviour
            # (display of invoice AJIs)
        ]
        if cash_adv_return_move_line_ids:
            domain.append(('move_id', 'in', cash_adv_return_move_line_ids))

        context.update({'display_fp': True}) # to display "Funding Pool" column name instead of "Analytic account"
        return {
            'name': _('Analytic Journal Items'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.analytic.line',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'context': context,
            'domain': domain,
            'target': 'current',
        }


    def unlink_moves(self, cr, uid, ids, context=None):
        """
        If invoice is a Direct Invoice and is in temp state, then delete moves and associated records,
        from the account_bank_statement_line. These are then recreated for the updated invoice line.
        """

        if context is None:
            context = {}

        account_move = self.pool.get('account.move')                    # am
        account_invoice = self.pool.get('account.invoice') #ai
        account_move_line = self.pool.get('account.move.line')          # aml
        analytic_distribution = self.pool.get('analytic.distribution')  # ad
        account_analytic_line = self.pool.get('account.analytic.line')  # aal

        # create a dict to add seqnum to context, keyed by journal id
        seqnums = {}

        for absl in self.browse(cr, uid, ids):
            if absl.state == 'temp' and absl.direct_invoice == True:
                # Find all moves lines linked to this register line
                # first, via the statement
                move_ids = [x.id for x in absl.move_ids]
                if move_ids:
                    am1 = account_move.browse(cr, uid, move_ids)[0]
                    seqnums[am1.journal_id.id] = am1.name
                else:
                    # UFTP-201: If there is no move linked to this reg line, get the current value of ref
                    seqnums[absl.statement_id.journal_id.id] = absl.sequence_for_reference

                # then via the direct invoice
                ai = account_invoice.browse(cr, uid, [absl.invoice_id.id])[0]
                if ai.move_id.id:
                    move_ids.append(ai.move_id.id)
                    seqnums[ai.move_id.journal_id.id] = ai.move_id.name
                    account_invoice.write(cr, uid, [ai.id],{'move_id': False}, context=context)
                else:
                    # UFTP-201: If there is no move linked to this invoice, retrieve the current value
                    if absl.invoice_id.journal_id and absl.invoice_id.journal_id.id: # not needed but just to be sure
                        seqnums[absl.invoice_id.journal_id.id] = absl.invoice_id.internal_number

                # TODO: Needs to be fixed during refactoring. The field move_id on account.analytic.line
                # is actually account_move_line.id, not account_move.id
                move_line_ids = account_move_line.search(cr, uid, [('move_id','in',move_ids)])
                # Find and delete all analytic lines for this move
                ad_ids = []
                aal_ids = []
                for aml in account_move_line.browse(cr, uid, move_line_ids, context=context):
                    if aml.analytic_distribution_id:
                        ad_ids.append(aml.analytic_distribution_id.id)
                for ad in analytic_distribution.browse(cr, uid, ad_ids):
                    if ad.analytic_lines:
                        aal_ids.append(ad.analytic_lines[0].id)

                from_sync = False
                if context.get('sync_update_execution'):
                    from_sync = True
                    del context['sync_update_execution']
                account_analytic_line.unlink(cr, uid, aal_ids, context=context)
                analytic_distribution.unlink(cr, uid, ad_ids, context=context)

                # Save the seqnums and delete the move lines
                context['seqnums'] = seqnums
                account_move.unlink(cr, uid, move_ids, context=context)
                if from_sync:
                    context['sync_update_execution'] = True
        return True


    def create_move_from_st_line(self, cr, uid, st_line, company_currency_id, st_line_number, counterpart_transfer_st_line=False, context=None):
        """
        Create move from the register line
        """
        # @@@override@ account.account_bank_statement.create_move_from_st_line()
        if context is None:
            context = {}
        res_currency_obj = self.pool.get('res.currency')
        account_move_obj = self.pool.get('account.move')
        account_move_line_obj = self.pool.get('account.move.line')
        st = st_line.statement_id

        curr_date = currency_date.get_date(self, cr, st_line.document_date, st_line.date)
        context.update({'currency_date': curr_date})

#        # Prepare partner_type
#        partner_type = False
#        if st_line.third_parties:
#            partner_type = ','.join([str(st_line.third_parties._table_name), str(st_line.third_parties.id)])
        # end of add

        move_id = account_move_obj.create(cr, uid, {
            'journal_id': st.journal_id.id,
            'period_id': st.period_id.id,
            'document_date': st_line.document_date,
            'date': st_line.date,
            'name': st_line_number,
            'ref': st_line.ref or False,
            ## Add partner_type
            #            'partner_type': partner_type or False,
            # end of add
        }, context=context)
        # Optimization on write for this field
        self.write(cr, uid, [st_line.id], {'move_ids': [(4, move_id, False)]}, context=context)

        torec = []
        if st_line.amount < 0:
            account_id = st.journal_id.default_credit_account_id.id
        else:
            account_id = st.journal_id.default_debit_account_id.id

        acc_cur = ((st_line.amount<=0) and st.journal_id.default_debit_account_id) or st_line.account_id
        context.update({
            'res.currency.compute.account': acc_cur,
        })
        amount = res_currency_obj.compute(cr, uid, st.currency.id,
                                          company_currency_id, st_line.amount, context=context)


        counter_part_id = counterpart_transfer_st_line and counterpart_transfer_st_line.get('id') or st_line.auto_counterpart and st_line.counterpart_transfer_st_line_id and st_line.counterpart_transfer_st_line_id.id or False
        counter_part_sdref = counterpart_transfer_st_line and counterpart_transfer_st_line.get('sdref') or False
        val = {
            'name': st_line.name,
            'date': st_line.date,
            'document_date': st_line.document_date,
            'move_id': move_id,
            'partner_id': ((st_line.partner_id) and st_line.partner_id.id) or False,
            # Add employee_id, transfer_journal_id and partner_type support
            'employee_id': ((st_line.employee_id) and st_line.employee_id.id) or False,
            'transfer_journal_id': ((st_line.transfer_journal_id) and st_line.transfer_journal_id.id) or False,
            #            'partner_type': partner_type or False,
            'partner_type_mandatory': st_line.partner_type_mandatory or False,
            'cheque_number': st_line.cheque_number or False,
            # end of add
            'account_id': (st_line.account_id) and st_line.account_id.id,
            'credit': ((amount>0) and amount) or 0.0,
            'debit': ((amount<0) and -amount) or 0.0,
            'statement_id': st.id,
            'journal_id': st.journal_id.id,
            'period_id': st.period_id.id,
            'currency_id': st.currency.id,
            'analytic_account_id': st_line.analytic_account_id and st_line.analytic_account_id.id or False,
            'transfer_amount': st_line.transfer_amount or 0.0,
            'counterpart_transfer_st_line_id': counter_part_id,
            'counterpart_transfer_st_line_sdref': counter_part_sdref,
            'has_a_counterpart_transfer': bool(counter_part_id),
        }

        if st_line.analytic_distribution_id:
            val.update({'analytic_distribution_id': self.pool.get('analytic.distribution').copy(cr, uid,
                                                                                                st_line.analytic_distribution_id.id, {}, context=context) or False})

        if st.currency.id <> company_currency_id:
            amount_cur = res_currency_obj.compute(cr, uid, company_currency_id,
                                                  st.currency.id, amount, context=context)
            val['amount_currency'] = -st_line.amount

        if st_line.account_id and st_line.account_id.currency_id and st_line.account_id.currency_id.id <> company_currency_id:
            val['currency_id'] = st_line.account_id.currency_id.id
            amount_cur = res_currency_obj.compute(cr, uid, company_currency_id,
                                                  st_line.account_id.currency_id.id, amount, context=context)
            val['amount_currency'] = -amount_cur

        # Optimization: check=False for the first move line. Then do it for the second line
        move_line_id = account_move_line_obj.create(cr, uid, val, context=context, check=False)
        torec.append(move_line_id)

        # Fill the secondary amount/currency
        # if currency is not the same than the company
        amount_currency = False
        currency_id = False
        if st.currency.id <> company_currency_id:
            amount_currency = st_line.amount
            currency_id = st.currency.id
        # Add register_line_id variable
        # Optimization: check=True to check all move lines
        first_move_line_id = account_move_line_obj.create(cr, uid, {
            'name': st_line.name,
            'date': st_line.date,
            'document_date': st_line.document_date,
            'move_id': move_id,
            'partner_id': ((st_line.partner_id) and st_line.partner_id.id) or False,
            # Add employee_id and transfer_journal_id support
            'employee_id': ((st_line.employee_id) and st_line.employee_id.id) or False,
            'transfer_journal_id': ((st_line.transfer_journal_id) and st_line.transfer_journal_id.id) or False,
            #            'partner_type': partner_type or False,
            'partner_type_mandatory': st_line.partner_type_mandatory or False,
            'cheque_number': st_line.cheque_number or False,
            # end of add
            'account_id': account_id,
            'credit': ((amount < 0) and -amount) or 0.0,
            'debit': ((amount > 0) and amount) or 0.0,
            'statement_id': st.id,
            'journal_id': st.journal_id.id,
            'period_id': st.period_id.id,
            'amount_currency': amount_currency,
            'currency_id': currency_id,
        }, context=context, check=True)
        torec.append(first_move_line_id)

        # Optimization: do not browse the move to browse move lines. Just read content of created move lines.
        #+ This is because no other move lines should be created in this method for the given account_move object.
        for line in account_move_line_obj.read(cr, uid, torec, ['state', 'name']):
            if line.get('state') <> 'valid':
                raise osv.except_osv(_('Error !'),
                                     _('Journal Item "%s" is not valid') % line.get('name'))
        # @@@end

        # Removed post from original method
        # Optimization on write for this field
        self.write(cr, uid, [st_line.id], {'first_move_line_id': first_move_line_id}, context=context)
        return move_id

    def _update_amount(self, values):
        """
        Update amount in 'values' with the difference between amount_in and amount_out.
        """
        res = values.copy()
        amount = None
        if 'amount_in' not in values and 'amount_out' not in values:
            return res
        if values:
            amount_in = values.get('amount_in', 0.0)
            amount_out = values.get('amount_out', 0.0)
            if amount_out == 0:
                amount = amount_in
            elif amount_in == 0:
                amount = - amount_out
            else:
                raise osv.except_osv(_('Error'), _('Please correct amount fields!'))

            res.update({'amount': amount})
        return res

    def update_employee_analytic_distribution(self, cr, uid, values):
        """
        Update analytic distribution if some expat staff is in values
        """
        # Prepare some values
        res = values.copy()
        # Fetch default funding pool: MSF Private Fund
        try:
            msf_fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
        except ValueError:
            msf_fp_id = 0
        # Check that an employee is given in employee_id or third_parties
        if values.get('employee_id', False) or values.get('partner_type', False):
            # Fetch account (should be mandatory)
            account = self.pool.get('account.account').read(cr, uid, values.get('account_id'), ['user_type_code', 'default_destination_id'])
            is_expense = False
            if account.get('user_type_code', False) == 'expense':
                is_expense = True
            if values.get('employee_id'):
                emp_id = values.get('employee_id')
            else:
                data = values.get('partner_type')
                if not ',' in data:
                    raise osv.except_osv(_('Error'), _('Wrong 3rd parties format!'))
                third = data.split(',')
                # Do not do anything if partner is another object that employee
                if third and third[0] and third[0] != "hr.employee":
                    return res
                emp_id = third and third[1] or False
            employee = self.pool.get('hr.employee').read(cr, uid, int(emp_id), ['destination_id', 'cost_center_id', 'funding_pool_id', 'free1_id', 'free2_id'])
            if is_expense and employee.get('cost_center_id', False):
                # Create a distribution

                # default destination
                destination_id = account.get('default_destination_id', False) and account.get('default_destination_id')[0] or False

                # emp destination
                emp_destination_id = employee.get('destination_id', False) and employee.get('destination_id')[0] or False
                if emp_destination_id:
                    # US-331: use EMP destination
                    # check that the EMP dest is compatible with the account (else use account default dest instead)
                    domain = [
                        ('account_id', '=', values.get('account_id')),
                        ('destination_id', '=', emp_destination_id),
                        ('disabled', '=', False),
                    ]
                    if self.pool.get('account.destination.link').search(cr, uid,
                                                                        domain, limit=1):
                        destination_id = emp_destination_id  # compatible

                cc_id = employee.get('cost_center_id', False) and employee.get('cost_center_id')[0] or False
                fp_id = employee.get('funding_pool_id',False) and employee.get('funding_pool_id')[0] or False
                f1_id = employee.get('free1_id', False) and employee.get('free1_id')[0] or False
                f2_id = employee.get('free2_id', False) and employee.get('free2_id')[0] or False
                if not fp_id:
                    fp_id = msf_fp_id
                distrib_id = self.pool.get('analytic.distribution').create(cr, uid, {})
                statement_id = values.get('statement_id', False)
                st = self.pool.get('account.bank.statement').browse(cr, uid, statement_id)
                currency_id = st.journal_id and st.journal_id.currency and st.journal_id.currency.id or False
                if distrib_id:
                    curr_date = currency_date.get_date(self, cr, values.get('document_date', False), values.get('date', False))
                    common_vals = {
                        'distribution_id': distrib_id,
                        'currency_id': currency_id,
                        'percentage': 100.0,
                        'date': values.get('date', False),
                        'source_date': curr_date,
                        'destination_id': destination_id,
                    }
                    common_vals.update({'analytic_id': cc_id,})
                    self.pool.get('cost.center.distribution.line').create(cr, uid, common_vals)
                    common_vals.update({'analytic_id': fp_id, 'cost_center_id': cc_id,})
                    self.pool.get('funding.pool.distribution.line').create(cr, uid, common_vals)
                    del common_vals['cost_center_id']
                    if f1_id:
                        common_vals.update({'analytic_id': f1_id,})
                        self.pool.get('free.1.distribution.line').create(cr, uid, common_vals)
                    if f2_id:
                        common_vals.update({'analytic_id': f2_id})
                        self.pool.get('free.2.distribution.line').create(cr, uid, common_vals)
                res.update({'analytic_distribution_id': distrib_id})
        return res

    def _verify_dates(self, cr, uid, ids, context=None):
        """
        Verify that the given parameter contains date. Then validate date with regarding register period.
        """
        for st_line in self.browse(cr, uid, ids, context=context):
            # Prepare some values
            register = st_line.statement_id
            account_id = st_line.account_id.id
            date = st_line.date
            period_start = register.period_id.date_start
            period_stop = register.period_id.date_stop
            # Verify that the date is included between period_start and period_stop
            if date < period_start or date > period_stop:
                raise osv.except_osv(_('Error'), _('The date for "%s" is outside the register period!') % (st_line.name,))
            # Verify that the date is useful with default debit or credit account activable date
            #+ (in fact the default debit and credit account have an activation date, and the given account_id too)
            #+ That means default debit and credit account are required for registers !
            register_debit_account_id = register.journal_id.default_debit_account_id.id
            register_credit_account_id = register.journal_id.default_credit_account_id.id
            amount = st_line.amount
            acc_obj = self.pool.get('account.account')
            register_account = None
            if amount > 0:
                register_account = acc_obj.browse(cr, uid, register_debit_account_id, context=context)
            elif amount < 0:
                register_account = acc_obj.browse(cr, uid, register_credit_account_id, context=context)
            if register_account:
                if date < register_account.activation_date or (register_account.inactivation_date and date > register_account.inactivation_date):
                    raise osv.except_osv(_('Error'),
                                         _('Posting date for "%s" is outside the validity period of the default account for this register!') % (st_line.name,))
            if account_id:
                account = acc_obj.browse(cr, uid, account_id, context=context)
                if date < account.activation_date or (account.inactivation_date and date > account.inactivation_date):
                    raise osv.except_osv(_('Error'),
                                         _('Posting date for "%s" is outside the validity period of the selected account for this record!') % (st_line.name,))
        return True

    _constraints = [
        (_verify_dates, "Date is not correct. Verify that it's in the register's period. ", ['date']),
    ]

    def _update_move_from_st_line(self, cr, uid, ids, values=None, context=None):
        """
        Update move lines from given statement lines
        """
        if not values:
            return False
        if context is None:
            context = {}

        acc_move_line_obj = self.pool.get('account.move.line')

        for st_line in self.browse(cr, uid, ids, context=context):
            # Prepare some values
            move_line_values = dict(values)
            # Get first line (from Register account)
            register_line = st_line.first_move_line_id
            # Delete 'from_import_cheque_id' field not to break the account move line write
            if 'from_import_cheque_id' in move_line_values:
                del(move_line_values['from_import_cheque_id'])
            # Delete down_payment value not to be given to account_move_line
            if 'down_payment_id' in move_line_values:
                del(move_line_values['down_payment_id'])
            # Delete analytic distribution from move_line_values because each move line should have its own analytic distribution
            if 'analytic_distribution_id' in move_line_values:
                del(move_line_values['analytic_distribution_id'])
            for to_del in ['counterpart_transfer_st_line_id', 'counterpart_transfer_st_line_sdref', 'has_a_counterpart_transfer']:
                if to_del in move_line_values:
                    del(move_line_values[to_del])
            if register_line:
                # Search second move line
                other_line_id = acc_move_line_obj.search(cr, uid, [('move_id', '=', st_line.move_ids[0].id), ('id', '!=', register_line.id)], context=context)[0]
                other_line = acc_move_line_obj.read(cr, uid, other_line_id, ['account_id', 'analytic_distribution_state'], context=context)
                other_account_id = move_line_values.get('account_id', other_line.get('account_id')[0])
                amount = move_line_values.get('amount', st_line.amount)
                # Search all data for move lines
                register_account_id = st_line.statement_id.journal_id.default_debit_account_id.id
                if amount < 0:
                    register_account_id = st_line.statement_id.journal_id.default_credit_account_id.id
                    register_debit = 0.0
                    register_credit = abs(amount)
                    other_debit = abs(amount)
                    other_credit = 0.0
                else:
                    register_debit = amount
                    register_credit = 0.0
                    other_debit = 0.0
                    other_credit = amount
                # What's about register currency ?
                register_amount_currency = False
                other_amount_currency = False
                currency_id = st_line.statement_id.currency.id
                if st_line.statement_id.currency.id != st_line.statement_id.company_id.currency_id.id:
                    # Prepare value
                    res_currency_obj = self.pool.get('res.currency')
                    # Get date for having a good change rate
                    curr_date = currency_date.get_date(self, cr, move_line_values.get('document_date', st_line.document_date),
                                                       move_line_values.get('date', st_line.date))
                    context.update({'currency_date': curr_date})
                    # Change amount
                    new_amount = res_currency_obj.compute(cr, uid, \
                                                          st_line.statement_id.journal_id.currency.id, st_line.company_id.currency_id.id, abs(amount), round=False, context=context)
                    # Take currency for the move lines
                    currency_id = st_line.statement_id.journal_id.currency.id
                    # Default amount currency
                    register_amount_currency = False
                    if amount < 0:
                        register_amount_currency = -abs(amount)
                        register_debit = 0.0
                        register_credit = new_amount
                        other_debit = new_amount
                        other_credit = 0.0
                    else:
                        register_amount_currency = abs(amount)
                        register_debit = new_amount
                        register_credit = 0.0
                        other_debit = 0.0
                        other_credit = new_amount
                    # Amount currency for "other line" is the opposite of "register line"
                    other_amount_currency = -register_amount_currency
                # Update values for register line
                # FIXME: List fields to take instead of removing fields we don't want
                # TODO: Make a guideline to explain what's to be done when you create a new column in register lines
                for el in ['is_transfer_with_change', 'transfer_amount', 'imported_invoice_line_ids']:
                    if el in move_line_values:
                        del(move_line_values[el])

                for_updates = {
                    'account_id':register_account_id,
                    'debit':register_debit,
                    'credit':register_credit,
                    'amount_currency':register_amount_currency, 'currency_id':currency_id
                }
                if 'ref' in values: # only get this value if it presented in "values"
                    for_updates['reference'] = values.get('ref', False)
                move_line_values.update(for_updates)
                # Write move line object for register line
                #+ Optimization: Do not check line because of account_move.write() method at the end of this method
                acc_move_line_obj.write(cr, uid, [register_line.id], move_line_values, context=context, check=False, update_check=False)
                # Update values for other line
                move_line_values.update({'account_id': other_account_id, 'debit': other_debit, 'credit': other_credit, 'amount_currency': other_amount_currency,
                                         'currency_id': currency_id,})
                if st_line.is_transfer_with_change:
                    move_line_values.update({'is_transfer_with_change': True})
                    if st_line.transfer_amount:
                        move_line_values.update({'transfer_amount': st_line.transfer_amount or 0.0})
                # Write move line object for other line
                # UTP-407: Add new message for temp posted register line if you change account and that it's not valid with analytic distribution
                try:
                    # Optimization: Do not check line because of account_move.write() method at the end of this method
                    acc_move_line_obj.write(cr, uid, [other_line.get('id')], move_line_values, context=context, check=False, update_check=False)
                except osv.except_osv as e:
                    msg = e.value
                    if 'account_id' in values and st_line.state == 'temp' and other_line.get('analytic_distribution_state') == 'invalid':
                        msg = _('The account modification required makes the analytic distribution previously defined invalid; please perform the account modification through the analytic distribution wizard')
                    raise osv.except_osv(e.name, msg)
                # Update analytic distribution lines
                analytic_amount = acc_move_line_obj.read(cr, uid, [other_line.get('id')], ['amount_currency'], context=context)[0].get('amount_currency', False)
                if analytic_amount and st_line.analytic_distribution_id:
                    self.pool.get('analytic.distribution').update_distribution_line_amount(cr, uid, [st_line.analytic_distribution_id.id],
                                                                                           amount=analytic_amount, context=context)
                # Update move
                # first prepare partner_type
                partner_type = False
                if st_line.third_parties:
                    partner_type = ','.join([str(st_line.third_parties._table_name), str(st_line.third_parties.id)])
                # finally write move object
                move_vals = { 'partner_type': partner_type, }
                if 'ref' in values: # only get this value if it presented in "values"
                    move_vals['ref'] = values.get('ref', False)
                if 'date' in move_line_values:  # US-84
                    move_vals.update({'date': move_line_values.get('date')})
                if 'document_date' in move_line_values:
                    move_vals.update({'document_date': move_line_values.get('document_date')})
                if 'cheque_number' in move_line_values:
                    move_vals.update({'cheque_number': move_line_values.get('cheque_number')})
                self.pool.get('account.move').write(cr, uid, [register_line.move_id.id], move_vals, context=context)

                # UTP-1097: If ref is given in "values"
                if 'ref' in values:
                    ref = values.get('ref', False)
                    if not ref and register_line.move_id:
                        # UTP-1097 ref field is cleared (a value to empty/False)
                        # ref of JIs/AJIs is not properly cleared in this case
                        aml_ids = acc_move_line_obj.search(cr, uid,
                                                           [('move_id', '=', register_line.move_id.id), ('ref', '!=', '')],
                                                           context = context)
                        if aml_ids:
                            # note: move line will update its AJIs ref
                            acc_move_line_obj.write(cr, uid, aml_ids,
                                                    {'reference': ''}, context=context)
        return True

    def do_direct_expense(self, cr, uid, st_line, posttype='', context=None):
        """
        If the statement line...
            - is being hardposted
            - has a Partner Third Party being neither Intermission nor Intersection
            - is booked on an income or expense account
        ... this method creates automated entries on partner payable or receivable account (JI), adds them to the
        regline JE, and returns a list of their ids that will have to be reconciled once the JE will be posted.
        """
        if context is None:
            context = {}
        if not st_line:
            return False
        automated_entries_ids = []
        if posttype == 'hard' and st_line.partner_id and st_line.partner_id.partner_type not in ('intermission', 'section') and \
                st_line.account_id.user_type.code in ('expense', 'income') and st_line.direct_invoice is False:
            # Prepare some elements
            move_line_obj = self.pool.get('account.move.line')
            current_date = time.strftime('%Y-%m-%d')
            # Create move lines
            account_id = False
            if st_line.account_id.user_type.code == 'expense':
                account_id = st_line.partner_id.property_account_payable.id or False
            elif st_line.account_id.user_type.code == 'income':
                account_id = st_line.partner_id.property_account_receivable.id or False
            if not account_id:
                raise osv.except_osv(_('Warning'), _('The supplier seems to have an incorrect account. Please contact '
                                                     'an Accounting Administrator to solve this problem.'))
            reg_move = st_line.first_move_line_id and st_line.first_move_line_id.move_id or False
            if not reg_move:
                raise osv.except_osv(_('Warning'),
                                     _('Journal Entry linked to the register line %s not found.') % st_line.sequence_for_reference or '')
            val = {
                'name': st_line.name,
                'date': reg_move.date,
                'document_date': reg_move.document_date,
                'move_id': reg_move.id,
                'partner_id': st_line.partner_id.id or False,
                'partner_type_mandatory': True,
                'account_id': account_id,
                'credit': 0.0,
                'debit': 0.0,
                'statement_id': st_line.statement_id.id,
                'journal_id': reg_move.journal_id.id,
                'period_id': reg_move.period_id.id,
                'currency_id': st_line.statement_id.currency.id,
                'analytic_account_id': st_line.analytic_account_id and st_line.analytic_account_id.id or False
            }
            amount = abs(st_line.amount)
            # update values if we have a different currency that company currency
            if st_line.statement_id.currency.id != st_line.statement_id.company_id.currency_id.id:
                curr_date = currency_date.get_date(self, cr, st_line.document_date, st_line.date)
                context['currency_date'] = curr_date or current_date
                amount = self.pool.get('res.currency').compute(cr, uid, st_line.statement_id.currency.id,
                                                               st_line.statement_id.company_id.currency_id.id, amount, round=False, context=context)
            val.update({'debit': amount, 'credit': 0.0, 'amount_currency': abs(st_line.amount)})
            # Optimization: Add check=False because of next post() for the move
            # (From US-3874: JIs are added to the regline JE to be posted right after the current method is called)
            move_line_debit_id = move_line_obj.create(cr, uid, val, context=context, check=False)
            val.update({'debit': 0.0, 'credit': amount, 'amount_currency': -abs(st_line.amount)})
            move_line_credit_id = move_line_obj.create(cr, uid, val, context=context, check=False)
            # the new JIs created will have to be reconciled after the JE will be posted
            automated_entries_ids.append(move_line_debit_id)
            automated_entries_ids.append(move_line_credit_id)
            # Disable the cash return button on this line
            # Optimization on write() for this field
            self.write(cr, uid, [st_line.id], {'from_cash_return': True}, context=context)
        return automated_entries_ids

    def do_import_invoices_reconciliation(self, cr, uid, st_line, context=None):
        """
        Reconcile line that come from an import invoices wizard in 3 steps :
         - split line into the move
         - post move
         - reconcile lines from the move
        """
        # Some verifications
        if not context:
            context = {}
        if not st_line:
            return False

        # Prepare some values
        absl_obj = self.pool.get('account.bank.statement.line')
        move_line_obj = self.pool.get('account.move.line')
        move_obj = self.pool.get('account.move')

        # Verification if st_line have some imported invoice lines
        if not st_line.imported_invoice_line_ids:
            return False

        total_amount = 0
        for invoice_move_line in st_line.imported_invoice_line_ids:
            total_amount += invoice_move_line.amount_currency

        ## STEP 1 : Split lines
        # Prepate some values
        move_ids = [x.id for x in st_line.move_ids]
        # Search move lines that are attached to move_ids
        move_lines = move_line_obj.search(cr, uid, [('move_id', 'in', move_ids),
                                                    ('id', '!=', st_line.first_move_line_id.id)]) # move lines that have been created AFTER import invoice wizard
        # Add new lines
        amount = abs(st_line.first_move_line_id.amount_currency)
        sign = 1
        if st_line.first_move_line_id.amount_currency > 0:
            sign = -1
        res_ml_ids = []
        process_invoice_move_line_ids = []
        total_payment = True
        diff = st_line.first_move_line_id.amount_currency - total_amount
        nb_imported_inv = len(st_line.imported_invoice_line_ids)
        if nb_imported_inv == 1 and abs(diff) > 0.001:  # 1 single invoice partially imported
            inv_ml = st_line.imported_invoice_line_ids[0]
            if inv_ml:
                ji_description = inv_ml.invoice.number or st_line.first_move_line_id.name or ''
                move_line_obj.write(cr, uid, move_lines, {'name': ji_description}, check=False, update_check=False, context=context)
        elif nb_imported_inv > 1 and abs(diff) > 0.001:
            # multi unpartial payment
            total_payment = False
            # Delete them
            #+ Optimization: As we post the move at the end of this method, no need to check lines after their deletion
            move_line_obj.unlink(cr, uid, move_lines, context=context, check=False)
            for invoice_move_line in sorted(st_line.imported_invoice_line_ids, key=lambda x: abs(x.amount_currency)):
                amount_currency = invoice_move_line.amount_currency

                if invoice_move_line.reconcile_partial_id:
                    amount_currency = 0
                    for line in invoice_move_line.reconcile_partial_id.line_partial_ids:
                        amount_currency += (line.debit_currency or 0.0) - (line.credit_currency or 0.0)
                if abs(amount_currency) <= amount:
                    amount_to_write = sign * abs(amount_currency)
                else:
                    amount_to_write = sign * amount
                # create a new move_line corresponding to this invoice move line
                aml_vals = {
                    'name': invoice_move_line.invoice.number or st_line.first_move_line_id.name or '', # UTP-793 fix
                    'move_id': move_ids[0],
                    'partner_id': invoice_move_line.partner_id.id,
                    'account_id': st_line.account_id.id,
                    'amount_currency': amount_to_write,
                    'statement_id': st_line.statement_id.id,
                    'currency_id': st_line.statement_id.currency.id,
                    'from_import_invoice_ml_id': invoice_move_line.id, # FIXME: add this ONLY IF total amount was paid
                    'date': st_line.date,
                    'document_date': st_line.document_date,
                }
                process_invoice_move_line_ids.append(invoice_move_line.id)
                # Optimization: As we post the move at the end of this method, no need to check creation
                move_line_id = move_line_obj.create(cr, uid, aml_vals, context=context, check=False)
                res_ml_ids.append(move_line_id)

                amount -= abs(amount_to_write)
                if not amount:
                    todo = [x.id for x in st_line.imported_invoice_line_ids if x.id not in process_invoice_move_line_ids]
                    # remove remaining invoice lines
                    if todo:
                        absl_obj.write(cr, uid, [st_line.id], {'imported_invoice_line_ids': [(3, x) for x in todo]}, context=context)
                    break
        # STEP 2 : Post moves
        move_obj.post(cr, uid, move_ids, context=context)

        # STEP 3 : Reconcile
        # UTP-574 Avoid problem of reconciliation for pending payments
        context.update({'pending_payment': True})
        if total_payment:
            move_line_obj.reconcile_partial(cr, uid, move_lines+[x.id for x in st_line.imported_invoice_line_ids], context=context)
        else:
            for ml in move_line_obj.browse(cr, uid, res_ml_ids, context=context):
                # reconcile lines
                move_line_obj.reconcile_partial(cr, uid, [ml.id, ml.from_import_invoice_ml_id.id], context=context)
        return True

    def do_import_cheque_reconciliation(self, cr, uid, st_line, context=None):
        """
        Do a reconciliation of an imported cheque and the current register line
        """
        # Some verifications
        if not context:
            context = {}
        if not st_line:
            return False
        # Prepare some values
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        # Verification if st_line have some imported invoice lines
        if not st_line.from_import_cheque_id:
            return False
        move_obj.post(cr, uid, [st_line.move_ids[0].id], context=context)
        # Search the line that would be reconcile after hard post
        move_line_id = move_line_obj.search(cr, uid, [('move_id', '=', st_line.move_ids[0].id), ('id', '!=', st_line.first_move_line_id.id)],
                                            context=context)
        # Do reconciliation
        move_line_obj.reconcile_partial(cr, uid, [st_line.from_import_cheque_id.id, move_line_id[0]], context=context)
        return True

    def analytic_distribution_is_mandatory(self, cr, uid, line, context=None):
        """
        Verify that no analytic distribution is mandatory. It's not until one of test is true
        """
        # Some verifications
        if not context:
            context = {}
        # Check
        if line.account_id.is_analytic_addicted and not line.analytic_distribution_id:
            return True
        elif line.account_id.is_analytic_addicted and not line.analytic_distribution_id.funding_pool_lines:
            return True
        return False

    def create_down_payment_link(self, cr, uid, absl, context=None):
        """
        Copy down_payment link to right move line
        """
        # browse all bank statement line
        if not absl.is_down_payment:
            return False
        move_ids = [x.id or None for x in absl.move_ids]
        # Search line that have same account for given register line
        line_ids = self.pool.get('account.move.line').search(cr, uid, [('account_id', '=', absl.account_id.id), ('move_id', 'in', move_ids)])
        # Add down_payment link
        self.pool.get('account.move.line').write(cr, uid, line_ids, {'down_payment_id': absl.down_payment_id.id}, update_check=False, check=False)
        return True

    def _check_cheque_number_uniticy(self, cr, uid, statement_id,
                                     cheque_number, context=None):
        if context is None:
            context = {}
        if not context.get('sync_update_execution', False) and\
                cheque_number and statement_id:
            statement_obj = self.pool.get('account.bank.statement')
            statement = statement_obj.read(cr, uid, statement_id, ['journal_id'])
            journal_id = statement['journal_id'][0]
            sql = '''SELECT l.id
                   FROM account_bank_statement_line l
                   LEFT JOIN account_bank_statement s ON l.statement_id = s.id
                   WHERE l.cheque_number=%s
                   AND s.journal_id=%s
            '''
            cr.execute(sql, (cheque_number, journal_id))

            for row in cr.dictfetchall():
                msg = _('This cheque number has already been used')
                raise osv.except_osv(_('Info'), (msg))

    def _check_on_regline_big_amounts(self, cr, uid, ids, context=None):
        """
        Prevents booking amounts IN or OUT having more than 10 digits before the comma, i.e. amounts starting from 10 billions.
        The goal is to avoid losing precision, see e.g.: "%s" % 10000000000.01  # '10000000000.0'
        (and to avoid decimal.InvalidOperation due to huge amounts).
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for regline in self.browse(cr, uid, ids, fields_to_fetch=['amount', 'name'], context=context):
            if _max_amount(regline.amount):
                raise osv.except_osv(_('Error'), _('The amount of the register line "%s" is more than 10 digits with decimals or 12 digits without decimals.') % regline.name)

    def _check_register_open(self, register, action, context=None):
        """
        If out-of-synchro and the register isn't in Open state, raises an error msg containing the "action" forbidden
        """
        if context is None:
            context = {}
        if not context.get('sync_update_execution'):
            if register.state != 'open':
                raise osv.except_osv(_('Warning'), _("You can't %s lines in the register %s (%s) as it isn't Open.") %
                                     (_(action), register.name or '', register.period_id.name))

    def create(self, cr, uid, values, context=None):
        """
        Create a new account bank statement line with values
        """
        if context is None:
            context = {}
        # First update amount
        values = self._update_amount(values=values)
        # Then update expat analytic distribution
        distrib_id = False
        if 'analytic_distribution_id' in values and values.get('analytic_distribution_id') != False:
            distrib_id = values.get('analytic_distribution_id')
        if not distrib_id:
            values = self.update_employee_analytic_distribution(cr, uid,
                                                                values=values)
        self._check_cheque_number_uniticy(cr, uid, values.get('statement_id'),
                                          values.get('cheque_number'), context=context)
        # remove useless spaces, line breaks and non-breaking spaces in the description and ref
        self.pool.get('data.tools').replace_line_breaks_from_vals(values, ['name', 'ref'], replace=['name'])

        # Then create a new bank statement line
        absl = super(account_bank_statement_line, self).create(cr, uid, values, context=context)
        reg = self.browse(cr, uid, absl, context=context).statement_id
        self._check_register_open(reg, "create", context)
        self._check_account_partner_compat(cr, uid, absl, context=context)
        return absl

    def write(self, cr, uid, ids, values, context=None):
        """
        Write some existing account bank statement lines with 'values'.
        """
        if not ids:
            return True

        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        if not values:
            return False
        # Optimization: if only one field to change and that this field is not needed by some other, no impact on them and no change, so we can call the super method.
        #+ We prepare some boolean to test what permit to skip some checks.
        #+ SKIP_WRITE_CHECK is a param in context that permit to directly write thing without any check or changes. Use it with caution.
        one_field = len(values) == 1
        field_match = values.keys()[0] in ['move_ids', 'first_move_line_id', 'from_cash_return', 'name', 'direct_state', 'sequence_for_reference', 'imported_invoice_line_ids']
        skip_check = context.get('skip_write_check', False) and context.get('skip_write_check') == True or False
        if values.get('cheque_number'):
            for line in self.read(cr, uid, ids, ['statement_id', 'cheque_number'], context=context):
                if values.get('cheque_number') !=  line['cheque_number']:
                    self._check_cheque_number_uniticy(cr, uid,
                                                      line['statement_id'][0], values.get('cheque_number'),
                                                      context=context)
        self.pool.get('data.tools').replace_line_breaks_from_vals(values, ['name', 'ref'], replace=['name'])
        if (one_field and field_match) or skip_check:
            return super(account_bank_statement_line, self).write(cr, uid, ids, values, context=context)
        # Prepare some values
        state = self._get_state(cr, uid, ids, context=context).values()[0]
        # Verify that the statement line isn't in hard state
        if state == 'hard':
            if values.get('partner_move_ids') or values.get('partner_move_line_ids') or \
                    values == {'from_cash_return': True} or values.get('analytic_distribution_id', False) or \
                    (values.get('invoice_id', False) and len(values.keys()) == 2 and values.get('from_cash_return')) or \
                    'from_correction' in context or context.get('sync_update_execution', False):
                res = super(account_bank_statement_line, self).write(cr, uid, ids, values, context=context)
                self._check_account_partner_compat(cr, uid, ids, context=context)
                self._check_on_regline_big_amounts(cr, uid, ids, context=context)
                return res
            raise osv.except_osv(_('Warning'), _('You cannot write a hard posted entry.'))
        # First update amount
        values = self._update_amount(values=values)
        # Case where _update_amount return False ! => this imply there is a problem with amount columns
        if not values:
            return False

        # Then update analytic distribution
        res = []
        must_return = False

        # US-836: _update_move_from_st_line is called on temp posted reg line
        # it deletes / creates AJI
        # call _update_move_from_st_line only if values have changed
        to_update_ids = []
        if state == 'temp' and not context.get('sync_update_execution'):
            to_remove= ['from_import_cheque_id', 'down_payment_id', 'imported_invoice_line_ids', 'move_ids']
            keys_to_read = [x for x in values.keys() if x not in to_remove]
            if keys_to_read:
                for x in self.read(cr, uid, ids, keys_to_read, context=context):
                    for k in keys_to_read:
                        if isinstance(x[k], tuple) and x[k]:
                            if x[k][0] != values[k]:
                                to_update_ids.append(x['id'])
                                break
                        elif k == 'partner_type':
                            if not values[k] and x[k].get('selection', '').endswith(','):
                                continue
                            if x[k].get('selection') != values[k]:
                                to_update_ids.append(x['id'])
                                break
                        elif x[k] != values[k]:
                            to_update_ids.append(x['id'])
                            break

        # US-351: fixed the wrong condition
        if 'employee_id' in values or 'partner_type' in values:
            must_return = True
            for line in self.read(cr, uid, ids, ['analytic_distribution_id', 'account_id', 'statement_id', 'first_move_line_id', 'move_ids']):
                account_id = line.get('account_id')[0]
                if not 'account_id' in values:
                    values.update({'account_id': account_id})
                if not 'statement_id' in values:
                    values.update({'statement_id': line.get('statement_id')[0]})

                old_distrib = False
                if line.get('analytic_distribution_id', False):
                    old_distrib = line.get('analytic_distribution_id')[0]

                # US-427: Do not update the AD from Employee/Third party if it comes from sync, only use the one provided by sync
                # US-9752: Keep AD that is applied on the entry when we correct info on the entry in temp state
                if not context.get('sync_update_execution') and state != 'temp':
                    values = self.update_employee_analytic_distribution(cr, uid, values) # this should only be done at local instance

                tmp = super(account_bank_statement_line, self).write(cr, uid, line.get('id'), values, context=context)
                self._check_account_partner_compat(cr, uid, line.get('id'), context=context)
                self._check_on_regline_big_amounts(cr, uid, line.get('id'), context=context)
                res.append(tmp)

                new_distrib = values.get('analytic_distribution_id', False)
                # US-351: Fixed the wrong condition
                if new_distrib and old_distrib != new_distrib and line.get('first_move_line_id', False) and line.get('move_ids', False):
                    first_move_line_id = line.get('first_move_line_id')[0]
                    move_ids = line.get('move_ids')[0]
                    if isinstance(move_ids, (int, long)):
                        move_ids = [move_ids]

                    # US-289: If there is a change in the DA, then populate it to the move line (and thus analytic lines)
                    ml_ids = self.pool.get('account.move.line').search(cr, uid, [('account_id', '=', account_id), ('id', 'not in', [first_move_line_id]), ('move_id', 'in', move_ids)])
                    if ml_ids:
                        # copy distribution
                        new_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, new_distrib, {}, context=context)
                        # write changes - first on account move line WITH account_id from wizard, THEN on register line with given account
                        # US-1343: The account to be updated must the new one, not the old account of the move line!
                        self.pool.get('account.move.line').write(cr, uid, ml_ids, {'analytic_distribution_id': new_distrib_id, 'account_id': values.get('account_id')}, check=False, update_check=False)

        # US-289: The following block is moved down after the employee update, so that the call to _update_move_from_st_line will also update
        # the distribution analytic in case there is a change of this value on the reg line, issued from the new block right above

        # In case of Temp Posting, we also update attached account move lines
        if state == 'temp':
            # method write removes date in value: save it, then restore it
            saveddate = False
            if values.get('date'):
                saveddate = values['date']
            if not context.get('sync_update_execution') and to_update_ids:
                self._update_move_from_st_line(cr, uid, to_update_ids, values, context=context)
            if saveddate:
                values['date'] = saveddate

        if must_return:
            return res
        # Update the bank statement lines with 'values'
        res = super(account_bank_statement_line, self).write(cr, uid, ids, values, context=context)
        self._check_account_partner_compat(cr, uid, ids, context=context)
        self._check_on_regline_big_amounts(cr, uid, ids, context=context)
        # Amount verification regarding Down payments
        for line in self.read(cr, uid, ids, ['is_down_payment', 'down_payment_id']):
            if line.get('is_down_payment', False) and line.get('down_payment_id'):
                if not self.pool.get('wizard.down.payment').check_register_line_and_po(cr, uid, line.get('id'), line.get('down_payment_id')[0], context=context):
                    raise osv.except_osv(_('Warning'), _('An error occurred on down_payment check. Please contact an administrator to resolve this problem.'))
        return res

    def copy(self, cr, uid, absl_id, default=None, context=None):
        """
        Create a copy of given line
        """
        # Some verifications
        if not context:
            context = {}
        if not default:
            default = {}
        # Update vals
        default.update({
            'analytic_account_id': False,
            'analytic_distribution_id': False,
            'direct_invoice': False,
            'first_move_line_id': False,
            'from_cash_return': False,
            'from_import_cheque_id': False,
            'imported_invoice_line_ids': False,
            'cash_register_op_advance_po_id': False,
            'invoice_id': False,
            'move_ids': False,
            'reconciled': False,
            'sequence': False,
            'sequence_for_reference': False,
            'state': 'draft',
            'transfer_amount': False,
            'transfer_currency': False,
            'down_payment_id': False,
            'cash_return_move_line_id': False,  # BKLG-60
            'partner_move_ids': [],
            'partner_move_line_ids': [],
            'advance_invoice_move_id': False,
            'direct_invoice_move_id': False,
            'imported_account_invoice_ids': [],
            'counterpart_transfer_st_line_id': False,
            'counterpart_transfer_st_line_sdref': False,
            'auto_counterpart': False,
            'has_a_counterpart_transfer': False,
        })
        # Copy analytic distribution if exists
        line = self.browse(cr, uid, [absl_id], context=context)[0]
        if line.analytic_distribution_id:
            new_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, line.analytic_distribution_id.id, {}, context=context)
            if new_distrib_id:
                default.update({'analytic_distribution_id': new_distrib_id})
        return super(osv.osv, self).copy(cr, uid, absl_id, default, context=context)

    def update_analytic_lines(self, cr, uid, absl, distrib=False, context=None):
        """
        Update analytic lines for temp posted lines
        """
        # Some verifications
        if not context:
            context = {}
        if not absl:
            return False
        # Prepare some values
        ml_obj = self.pool.get('account.move.line')
        distro_obj = self.pool.get('analytic.distribution')
        if absl.state != 'temp':
            return True
        # Search all moves lines linked to this register line
        move_ids = [x.id for x in absl.move_ids]
        move_line_ids = ml_obj.search(cr, uid, [('move_id', 'in', move_ids)])
        # Renew analytic lines
        for line in ml_obj.read(cr, uid, move_line_ids, ['analytic_distribution_id']):
            if line.get('analytic_distribution_id', False):
                distrib_id = distrib or line.get('analytic_distribution_id')[0] or False
                if not distrib_id:
                    raise osv.except_osv(_('Error'), _('Problem with analytic distribution for this line: %s') % (absl.name or '',))
                new_distrib_id = distro_obj.copy(cr, uid, distrib_id, {})
                # remove old distribution
                distro_obj.unlink(cr, uid, line.get('analytic_distribution_id')[0])
                # Optimization: do not check move lines. This should be done at the end of this method
                ml_obj.write(cr, uid, [line.get('id')], {'analytic_distribution_id': new_distrib_id}, update_check=False, check=False)
        # Optimization: Validate moves so that analytic lines are delete and recreated
        self.pool.get('account.move').validate(cr, uid, move_ids, context=context)
        return True

    def posting(self, cr, uid, ids, postype, context=None):
        """
        Write some statement line into some account move lines with a state that depends on postype.
        """
        if not context:
            context = {}
        if postype not in ('hard', 'temp'):
            raise osv.except_osv(_('Warning'), _('Post type has to be hard or temp'))
        if not len(ids):
            raise osv.except_osv(_('Warning'), _('There is no active_id. Please contact an administrator to resolve the problem.'))
        acc_move_obj = self.pool.get("account.move")

        # low level lock to prevent double posting
        cr.execute('select id from account_bank_statement_line where id in %s for update', (tuple(ids),))

        # browse all statement lines for creating move lines
        absls = self.browse(cr, 1, list(set(ids)), context=context)
        # check the register state only once as it is the same for all lines
        if absls:
            self._check_register_open(absls[0].statement_id, "post", context)
        # handle the lines ordered by sequence_for_order so this order will be kept in the Entry Sequences generated
        for absl in sorted(absls, key=lambda x: x.sequence_for_order):
            if not context.get('from_wizard_di'):
                if absl.statement_id and absl.statement_id.journal_id and absl.statement_id.journal_id.type in ['cheque'] and not absl.cheque_number:
                    raise osv.except_osv(_('Warning'), _('Cheque Number is missing!'))
            if absl.account_id.type_for_register == 'advance' and not absl.ref:
                raise osv.except_osv(_('Warning'), _('Line "%s": Reference is mandatory for operational advance accounts.') % absl.name)
            previous_state = ''.join(absl.state)
            if absl.state == 'draft':
                # US-673: temp posted line generates 2 creation updates
                # if the line is temp posted between the 2 rules, the 1st upd to create the line is not sent
                # update ir_model_data create_date to now(), so the 2 updates will be generated together at the next sync
                cr.execute("""update ir_model_data set create_date=NOW() where
                    model=%s and res_id=%s and module='sd'
                    """, (self._name, absl.id))

            if absl.state == "hard":
                raise osv.except_osv(_('Warning'), _('You can\'t re-post a hard posted entry !'))
            elif absl.state == "temp" and postype == "temp" and absl.direct_invoice == False:
                raise osv.except_osv(_('Warning'), _('You can\'t temp re-post a temp posted entry !'))

            if not absl.direct_invoice:
                # Some checks
                ## Journal presence for transfers cases - because of UF-1982 migration without journals
                if absl.account_id.type_for_register in ['transfer', 'transfer_same'] and not absl.transfer_journal_id:
                    raise osv.except_osv(_('Error'), _('Please give a transfer journal!'))
                ## Employee presence for operational advance
                if absl.account_id.type_for_register == 'advance' and not absl.employee_id:
                    raise osv.except_osv(_('Error'), _('Please give an employee!'))
                ## Analytic distribution presence
                if self.analytic_distribution_is_mandatory(cr, uid, absl, context=context):
                    raise osv.except_osv(_('Error'), _('Analytic distribution is mandatory for this line: %s') % (absl.name or '',))
                # Check analytic distribution validity
                if absl.account_id.is_analytic_addicted and absl.analytic_distribution_state != 'valid':
                    raise osv.except_osv(_('Error'), _('Analytic distribution is not valid for this line: %s') % (absl.name or '',))

                if absl.is_down_payment and not absl.down_payment_id:
                    raise osv.except_osv(_('Error'), _('You need to specify a PO before temp posting the Down Payment!'))

            to_write = {}
            cp_line = False
            cp_line_sdref = False
            if absl.account_id.type_for_register in ['transfer', 'transfer_same'] and \
                    absl.transfer_journal_id and \
                    absl.transfer_journal_id.instance_id.id == absl.instance_id.id and \
                    not absl.auto_counterpart \
                    and absl.state == 'draft':
                instance_id = self.pool.get('res.company')._get_instance_id(cr, uid)
                if instance_id == absl.instance_id.id:
                    if not absl.auto_counterpart:
                        cp_reg = self.pool.get('account.bank.statement').search(cr, uid, [('journal_id', '=', absl.transfer_journal_id.id), ('state', '=', 'open'), ('period_id', '=', absl.statement_id.period_id.id)], context=context)
                        if cp_reg:
                            cp_line = self.create(cr, uid, {
                                'auto_counterpart': True,
                                'counterpart_transfer_st_line_id': absl.id,
                                'has_a_counterpart_transfer': True,
                                'statement_id': cp_reg[0],
                                'transfer_journal_id': absl.statement_id.journal_id.id,
                                'document_date': absl.document_date,
                                'date': absl.date,
                                'name': absl.name,
                                'ref': absl.ref,
                                'account_id': absl.account_id.id,
                                'amount_in': absl.amount_out,
                                'amount_out': absl.amount_in,
                            }, context=context)
                            cp_line_sdref = self.get_sd_ref(cr, uid, cp_line)
                            to_write.update({'has_a_counterpart_transfer': True, 'auto_counterpart': True, 'counterpart_transfer_st_line_id': cp_line, 'counterpart_transfer_st_line_sdref': cp_line_sdref})

            # UF-2281 (linked to UTP-917)
            #+ We need to create move from st line in the given use cases:
            #+  FROM  |  TO  | IS DIRECT INVOICE? | Create move from st line ? |
            #+  draft | temp |         NO         |            YES             |
            #+  draft | hard |         NO         |            YES             |
            #+  temp  | hard |         NO         |            NO              |
            #+  draft | temp |         YES        |            YES             |
            #+  draft | hard |         YES        |            YES             |
            #+  temp  | hard |         YES        |            NO              |
            #+  As temp state is not effective on direct invoice and that previously we just create move when we are in draft and do not want to hard post a direct invoice
            #+  Note that direct invoice moves though temp state and back to draft via code (not user actions).
            #+  Code is duplicated below for clarifty. TODO: fix during refactoring of dirct invoices
            if absl.state == 'draft' and not absl.direct_invoice:
                self.create_move_from_st_line(cr, uid, absl, absl.statement_id.journal_id.company_id.currency_id.id, '/', counterpart_transfer_st_line={'id': cp_line, 'sdref': cp_line_sdref}, context=context)
                # reset absl browse_record cache, because move_ids have been created by create_move_from_st_line
                absl = self.browse(cr, 1, absl.id, context=context)
            if absl.state in ('draft','temp') and absl.direct_invoice and postype != 'hard':
                self.create_move_from_st_line(cr, uid, absl, absl.statement_id.journal_id.company_id.currency_id.id, '/', counterpart_transfer_st_line={'id': cp_line, 'sdref': cp_line_sdref}, context=context)
                # reset absl browse_record cache, because move_ids have been created by create_move_from_st_line
                absl = self.browse(cr, 1, absl.id, context=context)



            if postype == 'temp' and absl.direct_invoice:  #utp-917
                # Optimization on write() for this field
                to_write['direct_state'] = 'temp'
                self.write(cr, uid, [absl.id], to_write, context=context)
                # create the accounting entries
                account_invoice = self.pool.get('account.invoice')
                account_invoice.action_open_invoice(cr, uid, [absl.invoice_id.id], context=context)

                # set the invoice form open back to draft
                #account_invoice = self.pool.get('account.invoice')
                account_invoice.write(cr, uid, [absl.invoice_id.id], {'state':'draft'}, context=context)

                # unpost them
                account_move = self.pool.get('account.move')
                account_move_line = self.pool.get('account.move.line')
                account_move.write(cr, uid, [absl.invoice_id.move_id.id],{'state':'draft'}, context=context)

                account_move_line_ids = account_move_line.search(cr, uid, [('move_id', '=', absl.invoice_id.move_id.id)])
                # Optimizations: Do check=False and update_check=False because it would be done for the same move lines at the end of this loop

                # UTP-1039: Update also the statement_id = absl.statement_id to the new account_move_lines
                account_move_line.write(cr, uid, account_move_line_ids, {'state': 'draft', 'statement_id': absl.statement_id.id}, context=context, check=False, update_check=False)
                # UFTP-376 Make the link between move that correspond to the invoice to the register line
                self.write(cr, uid, [absl.id], {'direct_invoice_move_id': absl.invoice_id.move_id.id}, context=context)
                # link to account_move_reconcile on account_move_line
                account_move_reconcile = self.pool.get('account.move.reconcile')
                for line in account_move_line.read(cr, uid, account_move_line_ids, ['reconcile_id'], context=context):
                    if line.get('reconcile_id', False):
                        account_move_reconcile.unlink(cr, uid, [line.get('reconcile_id')[0]], context=context)

                # update the invoice 'name' (ref)  TODO - does this need to be set to "/" ?
                self.pool.get('account.invoice').read(cr, uid, absl.invoice_id.id, ['number'])['number']

                # Optimization: Do check=True and update_check=True because it was out from previous lines.
                account_move_line.write(cr, uid, account_move_line_ids, {'state': 'draft'}, context=context, check=True, update_check=True)
            elif postype == 'temp' and to_write:
                self.write(cr, uid, [absl.id], to_write, context=context)

            if postype == "hard":
                if absl.imported_invoice_line_ids:
                    # US-518/1.2
                    imported_total_amount = 0

                    for inv_move_line in absl.imported_invoice_line_ids:
                        imported_total_amount += inv_move_line.amount_currency
                    if absl.amount_out - abs(imported_total_amount) > 0.001 or \
                            absl.amount_in - abs(imported_total_amount) > 0.001:
                        raise osv.except_osv(_('Warning'),
                                             _('You can not hard post with an amount greater'
                                               ' than total of imported invoices: Entry %s') % absl.sequence_for_reference or '')

                # Update analytic lines
                if absl.account_id.is_analytic_addicted:
                    self.update_analytic_lines(cr, uid, absl)
                # some verifications
                if self.analytic_distribution_is_mandatory(cr, uid, absl, context=context):
                    vals = self.update_employee_analytic_distribution(cr, uid, {'employee_id': absl.employee_id and absl.employee_id.id or False, 'account_id': absl.account_id.id, 'statement_id': absl.statement_id.id,})
                    if 'analytic_distribution_id' in vals:
                        self.write(cr, uid, [absl.id], {'analytic_distribution_id': vals.get('analytic_distribution_id'),})
                    else:
                        raise osv.except_osv(_('Error'), _('No analytic distribution found!'))
                if absl.is_transfer_with_change:
                    if not absl.transfer_journal_id:
                        raise osv.except_osv(_('Warning'), _('Third party is required in order to hard post a transfer with change register line!'))

                if absl.is_down_payment:
                    self.pool.get('wizard.down.payment').check_register_line_and_po(cr, uid, absl.id, absl.down_payment_id.id, context=context)
                    self.create_down_payment_link(cr, uid, absl, context=context)



                to_write['sequence_for_reference'] = self.pool.get('ir.sequence').get(cr, uid, 'all.registers')
                # Optimization on write() for this field

                self.write(cr, uid, [absl.id], to_write, context=context)
                # Case where this line come from an "Pending Payments" Wizard
                if absl.imported_invoice_line_ids:
                    self.do_import_invoices_reconciliation(cr, uid, absl, context=context)
                elif absl.from_import_cheque_id:
                    self.do_import_cheque_reconciliation(cr, uid, absl, context=context)
                elif absl.direct_invoice:
                    if not absl.invoice_id:
                        raise osv.except_osv(_('Error'), _('This line is linked to an unknown Direct Invoice.'))
                    if absl.statement_id and absl.statement_id.journal_id and absl.statement_id.journal_id.type in ['cheque'] and not absl.cheque_number:
                        raise osv.except_osv(_('Warning'), _('Cheque Number is missing!'))

                    # Hard posting
                    # statement line
                    # Optimization on write() for this field
                    self.write(cr, uid, [absl.id], {'direct_state': 'hard'}, context=context)
                    # invoice. UFTP-312: in case we develop some changes next, we update context to inform we come from hard post
                    context.update({'from_hard_post': True})
                    self.pool.get('account.invoice').write(cr, uid, [absl.invoice_id.id], {'state':'paid'}, context=context)
                    # reconcile lines
                    self.pool.get('account.invoice').action_reconcile_direct_invoice(cr, uid, absl.invoice_id, context=context)
                    # move lines
                    acc_move_obj.write(cr, uid, [x.id for x in absl.move_ids], {'state':'posted'}, context=context)
                    acc_move_obj.write(cr, uid, [absl.invoice_id.move_id.id], {'state':'posted'}, context=context)
                else:
                    # create automated entries if need be: add the JIs to the regline JE and get the JIs to be reconciled
                    automated_entries_ids = self.do_direct_expense(cr, uid, absl, posttype=postype, context=context)
                    # post regline JE
                    acc_move_obj.post(cr, uid, [x.id for x in absl.move_ids], context=context)
                    if automated_entries_ids:
                        # reconcile automated entries together
                        self.pool.get('account.move.line').reconcile_partial(cr, uid, automated_entries_ids, context=context)
                        # store them in the regline as partner_move_line_ids ("Automated Entries")
                        self.write(cr, uid, absl.id, {'partner_move_line_ids': [(6, 0, automated_entries_ids)]}, context=context)

                if previous_state == 'draft':
                    direct_hard_post = True  # UF-2316
                else:
                    direct_hard_post = False

                if absl.counterpart_transfer_st_line_id and absl.counterpart_transfer_st_line_id.state == 'hard':
                    to_rec_ids = self.pool.get('account.move.line').search(cr, uid, [('counterpart_transfer_st_line_id', 'in', [absl.id, absl.counterpart_transfer_st_line_id.id])])
                    if len(to_rec_ids) < 2:
                        raise osv.except_osv(_('Error'), _('An auto booked transfer JI is missing, cannot reconcile the entries.'))
                    self.pool.get('account.move.line').reconcile_partial(cr, uid, to_rec_ids)

                self._set_register_line_audittrail_post_hard_state_log(cr, uid, absl, direct_hard_post, context=context)
        return True

    def _set_register_line_audittrail_post_hard_state_log(self, cr, uid, absl, direct_hard_post, context=None):
        """UF-2269 Timing fix: journal items updated after register line audit
        so we have to audit directly the Hard Poster state"""
        model_name = 'account.bank.statement'
        object_id = self.pool.get('ir.model').search(cr, uid, [('model', '=', model_name)], context=context)
        fct_object_id = self.pool.get('ir.model').search(cr, uid, [('model', '=', 'account.bank.statement.line')], context=context)
        if object_id and fct_object_id:
            audit_line_obj = self.pool.get('audittrail.log.line')
            rule_obj = self.pool.get('audittrail.rule')

            model_id = self.pool.get('ir.model').search(cr, uid,
                                                        [('model', '=', self._name)], context=context)[0]
            # get the rule_id
            rule_ids = rule_obj.search(cr, uid,
                                       [('object_id', '=', model_id)],
                                       context=context)
            rule_id = rule_ids and rule_ids[0] or False
            if not rule_id:
                return
            rule = rule_obj.browse(cr, uid, rule_id, context=context)

            # get state field id
            field_pool = self.pool.get('ir.model.fields')
            field_ids = field_pool.search(cr, uid, [('name', '=', 'state'), ('model_id', '=', fct_object_id)])
            field_id = field_ids and field_ids[0] or False
            if not field_id:
                return
            # get next sequence
            domain = [
                ('model', '=', model_name),
                ('res_id', '=', absl.statement_id.id),
            ]
            if direct_hard_post:
                # for a direct hard post, an audit line with Draft 2 Temp is already created
                # we have to update this line with Draft 2 Hard vs create a new one

                # search the audit line
                domain = [
                    ('field_id', '=', field_id),
                    ('object_id', '=', object_id[0]),
                    ('res_id', '=', absl.statement_id.id),
                    ('fct_object_id', '=', fct_object_id[0]),
                    ('fct_res_id', '=', absl.id),
                    ('method', '=', 'write'),
                    ('new_value', '=', 'temp'),
                ]
                direct_hard_post_audit_line_ids = audit_line_obj.search(cr, uid, domain, context=context)
                if not direct_hard_post_audit_line_ids or len(direct_hard_post_audit_line_ids) != 1:
                    return
            else:
                log_sequence = self.pool.get('audittrail.log.sequence').search(cr, uid, domain)
                if log_sequence:
                    log_seq = self.pool.get('audittrail.log.sequence').browse(cr, uid, log_sequence[0]).sequence
                    # get new id
                    log = log_seq.get_id(code_or_id='id')
                else:
                    log = False
            # set vals
            vals = {
                'rule_id': rule_id,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'new_value': 'hard',
                'new_value_text': 'Hard',
                'new_value_fct': 'Hard',
            }

            if rule and absl.id and rule.field_other_id:
                vals.update({
                    'other_column': self.pool.get(rule.object_id.model).read(cr, uid,
                                                                             absl.id, [rule.field_other_id.name])[rule.field_other_id.name]
                }
                )

            if direct_hard_post:
                # UF-2316
                old_value_vals = {
                    'old_value': 'draft',
                    'old_value_text': 'Draft',
                    'old_value_fct': 'Draft',
                }
            else:
                vals.update({
                    'user_id': uid,
                    'method': 'write',
                    'name': 'state',
                    'object_id': object_id[0],
                    'res_id': absl.statement_id.id,
                    'fct_object_id': fct_object_id[0],
                    'fct_res_id': absl.id,
                    'sub_obj_name': absl.name,
                    'field_description': 'Status',
                    'trans_field_description': 'Status',
                })
                old_value_vals = {
                    'old_value': 'temp',
                    'old_value_text': 'Temp',
                    'old_value_fct': 'Temp',
                }

            vals.update(old_value_vals)
            if field_id:
                vals['field_id'] = field_id

            if direct_hard_post:
                audit_line_obj.write(cr, uid, direct_hard_post_audit_line_ids[0], vals, context=context)
            else:
                if log:
                    vals['log'] = log
                audit_line_obj.create(cr, uid, vals, context=context)

    def button_hard_posting(self, cr, uid, ids, context=None):
        """
        Write some statement line into some account move lines in posted state.
        """
        return self.posting(cr, uid, ids, 'hard', context=context)

    def button_temp_posting(self, cr, uid, ids, context=None):
        """
        Write some statement lines into some account move lines in draft state.
        """
        return self.posting(cr, uid, ids, 'temp', context=context)

    def button_analytic_lines(self, cr, uid, ids, context=None):
        """
        Give analytic lines linked to the given register lines
        """
        if not context:
            context = {}
        # Update context
        context.update({'active_ids': ids})
        # Return result of action named "Analytic Lines" on register lines
        return self.show_analytic_lines(cr, uid, ids, context=context)

    def unlink(self, cr, uid, ids, context=None):
        """
        Permit to delete some account_bank_statement_line. But do some treatments on temp posting lines and do nothing for hard posting lines.
        """
        # We browse all ids
        for st_line in self.browse(cr, uid, ids):
            # if trying to delete a down payment, check that amounts IN won't be higher than remaining amounts OUT on the PO
            if st_line.account_id and st_line.account_id.type_for_register == 'down_payment' and st_line.down_payment_id:
                args = [('down_payment_id', '=', st_line.down_payment_id.id)]
                lines_ids = self.search(cr, uid, args, context=context)
                lines_amount = 0
                # browse all lines of the PO
                for line in self.read(cr, uid, lines_ids, ['id', 'amount'], context=context):
                    if st_line.id != line['id']:
                        lines_amount += line['amount']

                if lines_amount > 0:
                    raise osv.except_osv(_('Error'),
                                         _("You can't delete this line. Amounts IN can't be higher than Amounts OUT for the selected PO."))

            # if the line have a link to a move we have to make some treatments
            if st_line.move_ids:
                # in case of hard posting line : do nothing (because not allowed to change an entry which was posted!
                if st_line.state == "hard":
                    raise osv.except_osv(_('Error'), _('You are not allowed to delete hard posting lines!'))
                else:
                    #US-960: No need to set the check flag to True when unlink a reg line, otherwise it could regenerate wrongly new AJIs!
                    self.pool.get('account.move').unlink(cr, uid, [x.id for x in st_line.move_ids], context=context, check=False)
            # Delete direct invoice if exists
            if st_line.direct_invoice and st_line.invoice_id and not context.get('from_direct_invoice', False):
                # unlink moves and analytic lines before deleting the line
                self.unlink_moves(cr, uid, [st_line.id], context=context)
                self.pool.get('account.invoice').unlink(cr, uid, [st_line.invoice_id.id], {'from_register': True})
            elif st_line.direct_invoice and st_line.direct_invoice_move_id and not context.get('from_direct_invoice', False):
                self.pool.get('account.move').unlink(cr, uid, [st_line.direct_invoice_move_id.id], context=context)
            # If a sequence number had been generated for the register line, keep track of it
            if st_line.sequence_for_reference and not context.get('sync_update_execution', False):
                vals = {
                    'statement_id': st_line.statement_id.id,
                    'sequence': st_line.sequence_for_reference,
                    'instance_id': st_line.instance_id.id,
                }
                self.pool.get('account.bank.statement.line.deleted').create(cr, uid, vals, context=context)
        cp_move_ids = self.pool.get('account.move.line').search(cr, uid, [('counterpart_transfer_st_line_id', 'in', ids)])
        if cp_move_ids:
            self.pool.get('account.move.line').write(cr, uid, {'has_a_counterpart_transfer': False}, context=context)
        cp_st_l_ids = self.search(cr, uid, [('counterpart_transfer_st_line_id', 'in', ids)])
        if cp_st_l_ids:
            self.write(cr, uid, {'has_a_counterpart_transfer': False}, context=context)

        return super(account_bank_statement_line, self).unlink(cr, uid, ids)

    def button_advance(self, cr, uid, ids, context=None):
        """
        Launch a wizard when you press "Advance return" button on a bank statement line in a Cash or Bank Register
        """
        if context is None:
            context = {}
        # Some verifications
        if len(ids) > 1:
            raise osv.except_osv(_('Error'), _('This wizard only accept ONE advance line.'))
        # others verifications
        for st_line in self.browse(cr, uid, ids, context=context):
            # verify that the journal id is a cash, cheque or bank journal
            if not st_line.statement_id or not st_line.statement_id.journal_id or not st_line.statement_id.journal_id.type \
                    or st_line.statement_id.journal_id.type not in ['cash', 'bank', 'cheque']:
                raise osv.except_osv(_('Error'), _("The register journal is not compatible with an advance return."))
            # verify that there is a third party, particularly an employee_id in order to do something
            if not st_line.employee_id:
                raise osv.except_osv(_('Error'), _("The staff field is not filled in. Please complete the third parties field with an employee/staff."))
        # then display the wizard with an active_id = cash_register_id, and giving in the context a number of the bank statement line
        st_obj = self.pool.get('account.bank.statement.line')
        stl = st_obj.browse(cr, uid, ids[0])
        st = stl.statement_id
        if 'open_advance' in context:
            st = self.pool.get('account.bank.statement').browse(cr, uid, context.get('open_advance'), context=context)
        if st and st.state != 'open':
            raise osv.except_osv(_('Error'), _('You cannot do an advance return in a Register which is in another state than "open"!'))
        statement_id = st.id
        amount = self.read(cr, uid, ids[0], ['amount']).get('amount', 0.0)
        if amount >= 0:
            raise osv.except_osv(_('Warning'), _('Please select a line with a filled out "amount out"!'))
        wiz_obj = self.pool.get('wizard.cash.return')
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
            'statement_line_id': ids[0],
            'statement_id': statement_id,
            'amount': amount
        })
        if stl.cash_register_op_advance_po_id:
            context['cash_register_op_advance_po_id'] = stl.cash_register_op_advance_po_id.id
        wiz_id = wiz_obj.create(cr, uid, {'returned_amount': 0.0, 'initial_amount': abs(amount), 'advance_st_line_id': ids[0], \
                                          'currency_id': stl.statement_id.currency.id,
                                          'reference': stl.ref or '', 'journal_id':stl.statement_id.journal_id.id}, context=context)
        if statement_id:
            return {
                'name' : "Advance Return",
                'type' : 'ir.actions.act_window',
                'res_model' :"wizard.cash.return",
                'target': 'new',
                'view_mode': 'form',
                'view_type': 'form',
                'res_id': [wiz_id],
                'context': context,
            }
        else:
            return False

    def button_open_invoices(self, cr, uid, ids, context=None):
        """
        Open invoices linked to the register given register lines.
        To find them, search invoice that move_id is the same as move_line's move_id
        """
        # Checks
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        l = self.read(cr, uid, ids, ['imported_invoice_line_ids'])[0]
        if not l['imported_invoice_line_ids']:
            raise osv.except_osv(_('Error'), _("No related invoice line"))
        # Fetch invoices
        move_ids = []
        for regl in self.browse(cr, uid, ids):
            for ml in regl.imported_invoice_line_ids:
                if ml.move_id:
                    move_ids.append(ml.move_id.id)
        inv_ids = self.pool.get('account.invoice').search(cr, uid, [('move_id', 'in', move_ids)])
        if not inv_ids:
            raise osv.except_osv(_('Error'), _("No related invoice line"))
        # open the generic tree view which can contain different invoice types
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account', 'generic_invoice_tree')
        view_id = view_id and view_id[1] or False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.invoice',
            'target': 'new',
            'view_mode': 'tree',
            'view_type': 'form',
            'domain': [('id', 'in', inv_ids)],
            'view_id': [view_id],
            'context': {'generic_invoice': True}
        }

    def button_open_invoice(self, cr, uid, ids, context=None):
        """
        Open the attached invoice
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        inv_obj = self.pool.get('account.invoice')

        # special processing for cash_return
        cash_return = False
        for st_line in self.browse(cr, uid, ids, context=context):
            if not st_line.invoice_id:
                raise osv.except_osv(_('Warning'), _('No invoice founded.'))
            if st_line.from_cash_return:
                cash_return = True
                break
        if cash_return:
            invoice = self.browse(cr, uid, ids[0], context=context).invoice_id
            # get the doc name in the singular
            doc_name = dict(inv_obj.fields_get(cr, uid, context=context)['doc_type']['selection']).get(invoice.doc_type)
            action_xmlid = inv_obj._invoice_action_act_window.get(invoice.doc_type)
            if not action_xmlid:
                raise osv.except_osv(_('Warning'), _('Impossible to retrieve the view to display.'))
            act = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, action_xmlid, ['form', 'tree'], context=context)
            act_context = act.get('context', "{}") or "{}"
            eval_context = safe_eval(act_context)
            eval_context.update({
                'active_id': ids[0],
                'active_ids': ids,
                'from_register': True,
            })
            act['context'] = eval_context
            act['name'] = doc_name
            act['res_id'] = invoice.id
            act['view_mode'] = 'form'
            act['help'] = False  # hide the Tip message displayed on top
            act['target'] = 'new'
            return act

        ## Direct Invoice processing using temp objects

        # Prepare some values
        invoice = self.browse(cr, uid, ids[0], context=context).invoice_id

        # copy the analytic_distribution not to modify the original one
        analytic_distribution = self.pool.get('analytic.distribution')
        new_ad_id = None
        if invoice.analytic_distribution_id:
            new_ad_id = analytic_distribution.copy(cr, uid,
                                                   invoice.analytic_distribution_id.id, context=context)

        create_date = time.strftime('%Y-%m-%d %H:%M:%S')

        # Prepare values for wizard
        vals = {
            'account_id': invoice.account_id.id,
            'address_invoice_id': invoice.address_invoice_id.id,
            'address_contact_id': invoice.address_contact_id.id,
            'amount_total': invoice.amount_total,
            'analytic_distribution_id': new_ad_id,
            'comment': invoice.comment,
            'company_id': invoice.company_id.id,
            'create_date': create_date,
            'currency_id': invoice.currency_id.id,
            'date_invoice': invoice.date_invoice,
            'document_date': invoice.document_date,
            'is_direct_invoice': invoice.is_direct_invoice,
            'journal_id': invoice.journal_id.id,
            'name': invoice.name,
            'number': invoice.number,
            'origin': invoice.origin,
            'original_invoice_id': invoice.id,
            'partner_id': invoice.partner_id.id,
            'partner_bank_id':invoice.partner_bank_id.id,
            'payment_term': invoice.payment_term.id or False,
            'reference': invoice.reference,
            'register_posting_date': invoice.register_posting_date,
            'register_line_id': invoice.register_line_ids[0].id,
            'register_id': invoice.register_line_ids[0].statement_id.id,
            'state': invoice.state,
            'type': invoice.type,
            'user_id': invoice.user_id.id,
        }
        # Create the wizard
        wiz_obj = self.pool.get('account.direct.invoice.wizard')
        wiz_id = wiz_obj.create(cr, uid, vals, context=context)

        # recreate invoice line as temp objects
        wiz_invoice_line = self.pool.get('account.direct.invoice.wizard.line')
        for ivl in invoice.invoice_line:
            # copy the analytic_distribution not to modify the original one
            new_line_ad_id = None
            if ivl.analytic_distribution_id:
                new_line_ad_id = analytic_distribution.copy(cr, uid,
                                                            ivl.analytic_distribution_id.id, context=context)
            ivl_values = {
                'account_id':ivl.account_id.id,
                'analytic_distribution_id': new_line_ad_id,
                'create_date': create_date,
                'invoice_wizard_id':wiz_id,
                'name':ivl.name,
                'original_invoice_line_id':ivl.id,
                'price_unit':ivl.price_unit,
                'price_subtotal':ivl.price_subtotal,
                'product_id':ivl.product_id.id,
                'quantity':ivl.quantity,
                'reference':ivl.reference,
                'uos_id':ivl.uos_id.id,
            }
            wiz_invoice_line.create(cr, uid, ivl_values, context=context)

        # Update some context values
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
            'type': invoice.type,
            'doc_type': invoice.doc_type,
            'journal_type': invoice.journal_id.type,
        })
        # Open it!
        return {
            'name': _('Direct Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.direct.invoice.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': [wiz_id],
            'context': context,
        }


    def button_duplicate(self, cr, uid, ids, context=None):
        """
        Copy given lines and delete all links
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Browse lines
        for line in self.browse(cr, uid, ids, context=context):
            if line.statement_id and line.statement_id.state != 'open':
                raise osv.except_osv(_('Warning'), _("Register not open, you can't duplicate lines."))
            default_vals = ({
                'name': '(copy) ' + line.name,
                'cheque_number': None,
            })
            self.copy(cr, uid, line.id, default_vals, context=context)
        return True

    def button_down_payment(self, cr, uid, ids, context=None):
        """
        Open Down Payment wizard
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        vals = {}
        register_line = self.browse(cr, uid, ids[0], context=context)
        vals.update({'register_line_id': register_line.id})
        if register_line and register_line.down_payment_id:
            vals.update({'purchase_id': register_line.down_payment_id.id})
        if register_line and register_line.state and register_line.state != 'hard':
            vals.update({'state': 'draft'})
        if register_line and register_line.currency_id:
            vals.update({'currency_id': register_line.currency_id.id})
        if register_line and register_line.partner_id:
            vals.update({'partner_id': register_line.partner_id.id})
        wiz_id = self.pool.get('wizard.down.payment').create(cr, uid, vals, context=context)
        # Return view with register_line id
        context.update({
            'active_id': wiz_id,
            'active_ids': [wiz_id],
            'register_line_id': ids[0],
        })
        return {
            'name': _("Down Payment"),
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.down.payment',
            'target': 'new',
            'res_id': [wiz_id],
            'view_mode': 'form',
            'view_type': 'form',
            'context': context,
        }

    def onchange_account(self, cr, uid, ids, account_id=None, statement_id=None, context=None):
        """
        Update Third Party type regarding account type_for_register field.
        """
        # Prepare some values
        acc_obj = self.pool.get('account.account')
        third_type = [('res.partner', 'Partner'), ('hr.employee', 'Employee')]
        third_required = False
        third_selection = 'res.partner,0'
        # if an account is given, then attempting to change third_type and information about the third required
        if account_id:
            a = acc_obj.read(cr, uid, account_id, ['type_for_register'])
            if a['type_for_register'] in ['transfer', 'transfer_same']:
                # UF-428: transfer type shows only Journals instead of Registers as before
                third_type = [('account.journal', 'Journal')]
                third_required = True
                third_selection = 'account.journal,0'
            elif a['type_for_register'] == 'advance':
                third_type = [('hr.employee', 'Employee')]
                third_required = True
                third_selection = 'hr.employee,0'
            elif a['type_for_register'] == 'down_payment':
                third_type = [('res.partner', 'Partner')]
                third_required = True
                third_selection = 'res.partner,0'
            elif a['type_for_register'] == 'payroll':
                third_type = [('res.partner', 'Partner'), ('hr.employee', 'Employee')]
                third_required = True
                third_selection = 'res.partner,0'
        return {'value': {'partner_type_mandatory': third_required, 'partner_type': {'options': third_type, 'selection': third_selection}}}

    def onchange_partner_type(self, cr, uid, ids, partner_type=None, amount_in=None, amount_out=None, context=None):
        """
        Update account_id field if partner_type change
        NB:
         - amount_out = debit
         - amount_in = credit
        """
        res = {}
        amount = (amount_in or 0.0) - (amount_out or 0.0)
        if not partner_type and not amount:
            return res
        if partner_type:
            partner_data = partner_type.split(",")
            if partner_data:
                obj = partner_data[0]
                i = int(partner_data[1])
            # Case where the partner_type is res.partner
            if obj == 'res.partner':
                # if amount is inferior to 0, then we give the account_payable
                res_account = None
                if amount < 0:
                    res_account = self.pool.get('res.partner').read(cr, uid, [i],
                                                                    ['property_account_payable'], context=context)[0].get('property_account_payable', False)
                elif amount > 0:
                    res_account = self.pool.get('res.partner').read(cr, uid, [i],
                                                                    ['property_account_receivable'], context=context)[0].get('property_account_receivable', False)
                if res_account:
                    res['value'] = {'account_id': res_account[0]}
#            # Case where the partner_type is account.bank.statement
#            if obj == 'account.bank.statement':
#                # if amount is inferior to 0, then we give the debit account
#                register = self.pool.get('account.bank.statement').browse(cr, uid, [i], context=context)
#                account_id = False
#                if register and amount < 0:
#                    account_id = register[0].journal_id.default_debit_account_id.i
#                elif register and amount > 0:
#                    account_id = register[0].journal_id.default_credit_account_id.i
#                if account_id:
#                    res['value'] = {'account_id': account_id}
        return res

    def delete_button(self, cr, uid, ids, context=None):
        """
        delete button (except for hard posted state)
        """
        if not ids:
            return False
        if isinstance(ids, (int, long)):
            ids = [ids]
        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
        return self.unlink(cr, real_uid, ids, context=context)

    def _check_account_partner_compat(self, cr, uid, absl_ids, context=None):
        # US-672/2
        if not context.get('sync_update_execution', False):
            if isinstance(absl_ids, (int, long)):
                absl_ids = [absl_ids]
            # get the values of the register line fields related to the partner and the account
            fields_to_read = ['partner_type', 'employee_id', 'transfer_journal_id', 'partner_id', 'account_id']
            for absl in self.read(cr, uid, absl_ids, fields_to_read, context=context):
                partner_type = absl['partner_type'] and 'selection' in absl['partner_type'] \
                    and absl['partner_type']['selection'] or False
                if partner_type:  # format is 'model_name,id'
                    pt_model, pt_id = tuple(partner_type.split(','))
                    if not pt_id:
                        partner_type = False
                account_id = absl['account_id'] and absl['account_id'][0] or False
                employee_id = absl['employee_id'] and absl['employee_id'][0] or False
                transfer_journal_id = absl['transfer_journal_id'] and absl['transfer_journal_id'][0] or False
                partner_id = absl['partner_id'] and absl['partner_id'][0] or False
                self.pool.get('account.account').is_allowed_for_thirdparty(
                    cr, uid, account_id, partner_type=partner_type, employee_id=employee_id,
                    transfer_journal_id=transfer_journal_id, partner_id=partner_id, from_vals=True, raise_it=True,
                    context=context)

    def open_counterpart_transfer_line(self, cr, uid, ids, context=None):
        data_obj = self.pool.get('ir.model.data')
        view_id = data_obj.get_object_reference(cr, uid, 'register_accounting', 'view_account_bank_statement_line_tree')
        search_view_id = data_obj.get_object_reference(cr, uid, 'register_accounting', 'account_bank_statement_line_empty_filter')[1]
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.bank.statement.line',
            'view_type': 'form',
            'view_mode': 'tree',
            'view_id': [view_id[1]],
            'search_view_id': search_view_id,
            'domain': [('counterpart_transfer_st_line_id', 'in', ids)],
            'context': context,
            'target': 'new',
        }

account_bank_statement_line()

class ir_values(osv.osv):
    _name = 'ir.values'
    _inherit = 'ir.values'

    def get(self, cr, uid, key, key2, models, meta=False, context=None, res_id_req=False, without_user=True, key2_req=True, view_id=False):
        if context is None:
            context = {}
        values = super(ir_values, self).get(cr, uid, key, key2, models, meta, context, res_id_req, without_user, key2_req, view_id=view_id)
        if key == 'action' and key2 == 'client_action_multi' and 'account.bank.statement.line' in [x[0] for x in models]:
            new_act = []
            for v in values:
                display = True
                if context.get('type_posting', '') == 'hard':
                    # hide Temp Posting options from the Hard Posting page
                    if v[1] in ('act_wizard_temp_posting', 'act_wizard_temp_post_all'):
                        display = False
                elif context.get('type_posting', '') == 'temp':
                    # hide Hard Posting options from the Temp Posting page
                    if v[1] in ('act_wizard_hard_posting', 'act_wizard_hard_post_all'):
                        display = False
                elif not context.get('type_posting') and not context.get('from_regline_view'):
                    # hide the Hard Post ALL / Temp Post ALL options everywhere else,
                    # except in the Register Lines view accessible from the menu on the right of the registers
                    if v[1] in ('act_wizard_hard_post_all', 'act_wizard_temp_post_all'):
                        display = False
                if display:
                    new_act.append(v)
            values = new_act
        return values


ir_values()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
