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

from osv import fields, osv
from tools.translate import _
import decimal_precision as dp


class account_bank_statement(osv.osv):

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if context is None:
            context = {}

        if not context.get('sync_update_execution'):
            if 'balance_end_real' in vals:
                new_vals = {'balance_start': vals['balance_end_real']}
                # US-948/2: carry over end of month balance to next registers if
                # the source register is not 'end of month balance' frozen
                # note: the last carry over is processed via
                # 'button_confirm_closing_bank_balance' button
                to_write_id_list = []
                for r in self.read(cr, uid, ids,
                                   [ 'closing_balance_frozen', 'journal_id', ],
                                   context=context):
                    if not r['closing_balance_frozen']:
                        if r['journal_id']:
                            jtype = self.pool.get('account.journal').read(cr,
                                                                          uid, [r['journal_id'][0]], ['type'],
                                                                          context=context)[0]['type']
                            if jtype != 'cash':
                                args = [('prev_reg_id', '=', r['id'])]
                                search_ids = self.search(cr, uid, args,
                                                         context=context)
                                if search_ids:
                                    to_write_id_list.extend(search_ids)
                self.write(cr, uid, to_write_id_list, new_vals, context=context)

        if not vals:
            return True

        return super(account_bank_statement, self).write(cr, uid, ids, vals, context=context)

    def _default_journal_id(self, cr, uid, context=None):
        if context is None:
            context = {}
        journal_pool = self.pool.get('account.journal')
        journal_type = context.get('journal_type', False)
        journal_id = False
        if journal_type:
            ids = journal_pool.search(cr, uid, [('type', '=', journal_type)])
            if ids:
                journal_id = ids[0]
        return journal_id

    def _end_balance(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Calculate register's balance
        """
        if context is None:
            context = {}
        res = {}

        # Add this context in order to escape cheque register filter
        ctx = context.copy()
        ctx.update({'from_end_balance': True})
        for statement in self.browse(cr, uid, ids, context=ctx):
            res[statement.id] = statement.balance_start
            for st_line in statement.line_ids:
                res[statement.id] += st_line.amount or 0.0
            # UF-425: Add the Open Advances Amount when calculating the "Calculated Balance" value
            res[statement.id] -= statement.open_advance_amount or 0.0
            # UF-810: Add a "Unrecorded Expenses" when calculating "Calculated Balance"
            res[statement.id] -= statement.unrecorded_expenses_amount or 0.0
        return res

    def _get_period(self, cr, uid, context=None):
        periods = self.pool.get('account.period').find(cr, uid)
        if periods:
            return periods[0]
        return False

    def _currency(self, cursor, user, ids, name, args, context=None):
        res = {}
        res_currency_obj = self.pool.get('res.currency')
        res_users_obj = self.pool.get('res.users')
        default_currency = res_users_obj.browse(cursor, user,
                                                user, context=context).company_id.currency_id
        for statement in self.browse(cursor, user, ids, context=context):
            currency = statement.journal_id.currency
            if not currency:
                currency = default_currency
            res[statement.id] = currency.id
        currency_names = {}
        for currency_id, currency_name in res_currency_obj.name_get(cursor,
                                                                    user, [x for x in res.values()], context=context):
            currency_names[currency_id] = currency_name
        for statement_id in res.keys():
            currency_id = res[statement_id]
            res[statement_id] = (currency_id, currency_names[currency_id])
        return res

    _name = "account.bank.statement"
    _description = "Bank Statement"
    _columns = {
        'name': fields.char('Register Name', size=64, required=False, readonly=True, states={'draft': [('readonly', False)]}),
        'date': fields.date('Date', required=True, states={'confirm': [('readonly', True)]}),
        'journal_id': fields.many2one('account.journal', 'Journal', required=True, readonly=True),
        'period_id': fields.many2one('account.period', 'Period', required=True),
        'balance_start': fields.float('Starting Balance', digits_compute=dp.get_precision('Account'),
                                      states={'confirm':[('readonly',True)]}),
        'balance_end_real': fields.float('Closing Balance', digits_compute=dp.get_precision('Account'), states={'confirm':[('readonly', True)]},
                                         help="Please enter manually the end-of-month balance, as per the printed bank statement received. Before confirming closing balance & closing the register, you must make sure that the calculated balance of the bank statement is equal to that amount."),
        'balance_end': fields.function(_end_balance, method=True, store=False, string='Calculated Balance'),
        'company_id': fields.related('journal_id', 'company_id', type='many2one', relation='res.company', string='Company', store=True, readonly=True),
        'line_ids': fields.one2many('account.bank.statement.line',
                                    'statement_id', 'Statement lines',
                                    states={'confirm':[('readonly', True)]}),
        'deleted_line_ids': fields.one2many('account.bank.statement.line.deleted', 'statement_id', 'Statement lines'),
        'move_line_ids': fields.one2many('account.move.line', 'statement_id',
                                         'Entry lines', states={'confirm':[('readonly',True)]}),
        'state': fields.selection((('draft', 'Draft'), ('open', 'Open'), ('confirm', 'Closed')),
                                  readonly="True", string='State'),
        'currency': fields.function(_currency, method=True, string='Currency',
                                    type='many2one', relation='res.currency'),
        'account_id': fields.related('journal_id', 'default_debit_account_id', type='many2one', relation='account.account', string='Account used in this journal', readonly=True, help='used in statement reconciliation domain, but shouldn\'t be used elswhere.'),
    }

    _defaults = {
        'name': False,
        'date': lambda *a: time.strftime('%Y-%m-%d'),
        'state': 'draft',
        'balance_start': lambda *a: 0.0,
        'journal_id': _default_journal_id,
        'period_id': _get_period,
    }

    def onchange_date(self, cr, user, ids, date, context=None):
        """
        Returns a dict that contains new values and context
        @param cr: A database cursor
        @param user: ID of the user currently logged in
        @param date: latest value from user input for field date
        @param args: other arguments
        @param context: context arguments, like lang, time zone
        @return: Returns a dict which contains new values, and context
        """
        res = {}
        period_pool = self.pool.get('account.period')

        if context is None:
            context = {}

        pids = period_pool.search(cr, user, [('date_start','<=',date), ('date_stop','>=',date), ('special', '!=', True)])
        if pids:
            res.update({
                'period_id':pids[0]
            })
            context.update({
                'period_id':pids[0]
            })

        return {
            'value':res,
            'context':context,
        }

    def button_dummy(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {}, context=context)

    def statement_close(self, cr, uid, ids, journal_type='bank', context=None):
        return self.write(cr, uid, ids, {'state':'confirm'}, context=context)

    def button_cancel(self, cr, uid, ids, context=None):
        done = []
        account_move_obj = self.pool.get('account.move')
        for st in self.browse(cr, uid, ids, context=context):
            if st.state=='draft':
                continue
            ids = []
            for line in st.line_ids:
                ids += [x.id for x in line.move_ids]
            account_move_obj.unlink(cr, uid, ids, context)
            done.append(st.id)
        return self.write(cr, uid, done, {'state':'draft'}, context=context)

    def onchange_journal_id(self, cr, uid, statement_id, journal_id, context=None):
        cr.execute('SELECT balance_end_real \
                FROM account_bank_statement \
                WHERE journal_id = %s AND NOT state = %s \
                ORDER BY date DESC,id DESC LIMIT 1', (journal_id, 'draft'))
        res = cr.fetchone()
        balance_start = res and res[0] or 0.0
        account_id = self.pool.get('account.journal').read(cr, uid, journal_id, ['default_debit_account_id'], context=context)['default_debit_account_id']
        return {'value': {'balance_start': balance_start, 'account_id': account_id}}

    def unlink(self, cr, uid, ids, context=None):
        stat = self.read(cr, uid, ids, ['state'], context=context)
        unlink_ids = []
        for t in stat:
            if t['state'] in ('draft'):
                unlink_ids.append(t['id'])
            else:
                raise osv.except_osv(_('Invalid action !'), _('Cannot delete bank statement(s) which are already confirmed !'))
        osv.osv.unlink(self, cr, uid, unlink_ids, context=context)
        return True

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        if context is None:
            context = {}
        default = default.copy()
        default['move_line_ids'] = []
        return super(account_bank_statement, self).copy(cr, uid, id, default, context=context)

account_bank_statement()

class account_bank_statement_line(osv.osv):

    def onchange_partner_id(self, cr, uid, ids, partner_id, context=None):
        obj_partner = self.pool.get('res.partner')
        if context is None:
            context = {}
        if not partner_id:
            return {}
        part = obj_partner.browse(cr, uid, partner_id, context=context)
        if not part.supplier and not part.customer:
            type = 'general'
        elif part.supplier and part.customer:
            type = 'general'
        else:
            if part.supplier == True:
                type = 'supplier'
            if part.customer == True:
                type = 'customer'
        res_type = self.onchange_type(cr, uid, ids, partner_id=partner_id, type=type, context=context)
        if res_type['value'] and res_type['value'].get('account_id', False):
            return {'value': {'type': type, 'account_id': res_type['value']['account_id']}}
        return {'value': {'type': type}}

    def onchange_type(self, cr, uid, line_id, partner_id, type, context=None):
        res = {'value': {}}
        obj_partner = self.pool.get('res.partner')
        if context is None:
            context = {}
        if not partner_id:
            return res
        account_id = False
        line = self.browse(cr, uid, line_id, context=context)
        if not line or (line and not line[0].account_id):
            part = obj_partner.browse(cr, uid, partner_id, context=context)
            if type == 'supplier':
                account_id = part.property_account_payable.id
            else:
                account_id = part.property_account_receivable.id
            res['value']['account_id'] = account_id
        return res

    _order = "statement_id desc, sequence"
    _name = "account.bank.statement.line"
    _description = "Bank Statement Line"
    _columns = {
        'name': fields.char('Communication', size=64, required=True),
        'date': fields.date('Date', required=True),
        'amount': fields.float('Amount', digits_compute=dp.get_precision('Account')),
        'type': fields.selection([
            ('supplier','Supplier'),
            ('customer','Customer'),
            ('general','General')
        ], 'Type', required=True),
        'partner_id': fields.many2one('res.partner', 'Partner'),
        'account_id': fields.many2one('account.account','Account',
                                      required=True, hide_default_menu=True),
        'statement_id': fields.many2one('account.bank.statement', 'Statement',
                                        select=True, required=True, ondelete='cascade'),
        'analytic_account_id': fields.many2one('account.analytic.account', 'Analytic Account'),
        'move_ids': fields.many2many('account.move',
                                     'account_bank_statement_line_move_rel', 'move_id','statement_id',
                                     'Moves'),
        'ref': fields.char('Reference', size=32),
        'note': fields.text('Notes'),
        'sequence': fields.integer('Sequence', help="Gives the sequence order when displaying a list of bank statement lines."),
        'company_id': fields.related('statement_id', 'company_id', type='many2one', relation='res.company', string='Company', store=True, readonly=True),
    }
    _defaults = {
        'name': lambda self,cr,uid,context={}: self.pool.get('ir.sequence').get(cr, uid, 'account.bank.statement.line'),
        'date': lambda *a: time.strftime('%Y-%m-%d'),
        'type': 'general',
    }

account_bank_statement_line()


class account_bank_statement_line_deleted(osv.osv):
    '''
    Used to keep track of the sequence number for the deleted register lines
    '''

    _order = "statement_id desc, sequence"
    _name = "account.bank.statement.line.deleted"
    _description = "Deleted Bank Statement Line"
    _columns = {
        'statement_id': fields.many2one('account.bank.statement', 'Statement', required=True, select=1),
        'sequence': fields.char('Sequence', size=64, required=True, help='Gives the old sequence of the deleted line.'),
    }

account_bank_statement_line_deleted()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
