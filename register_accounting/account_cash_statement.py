#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution    
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
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
from register_tools import create_cashbox_lines

class account_cash_statement(osv.osv):
    _name = "account.bank.statement"
    _inherit = "account.bank.statement"

    _defaults = {
        'name': False,
        'state': lambda *a: 'draft',
    }

    def create(self, cr, uid, vals, context={}):
        """
        Create a Cash Register without an error overdue to having open two cash registers on the same journal
        """
        j_obj = self.pool.get('account.journal')
        journal = j_obj.browse(cr, uid, vals['journal_id'], context=context)
        # @@@override@account.account_cash_statement.create()
        if journal.type == 'cash':
            open_close = self._get_cash_open_close_box_lines(cr, uid, context)
            if vals.get('starting_details_ids', False):
                for start in vals.get('starting_details_ids'):
                    dict_val = start[2]
                    for end in open_close['end']:
                       if end[2]['pieces'] == dict_val['pieces']:
                           end[2]['number'] += dict_val['number']
            vals.update({
#                'ending_details_ids': open_close['start'],
                'starting_details_ids': open_close['end'],
            })
        else:
            vals.update({
                'ending_details_ids': False,
                'starting_details_ids': False
            })
        # @@@end
        # Observe register state
        prev_reg_id = vals.get('prev_reg_id', False)
        if prev_reg_id:
            prev_reg = self.browse(cr, uid, [prev_reg_id], context=context)[0]
            # if previous register closing balance is freezed, then retrieving previous closing balance
            if prev_reg.closing_balance_frozen:
                if journal.type == 'bank':
                    vals.update({'balance_start': prev_reg.balance_end_real})
        res_id = super(osv.osv, self).create(cr, uid, vals, context=context)
        # take on previous lines if exists
        if prev_reg_id:
            create_cashbox_lines(self, cr, uid, [prev_reg_id], ending=True, context=context)
        # update balance_end
        self._get_starting_balance(cr, uid, [res_id], context=context)
        return res_id

    def button_open_cash(self, cr, uid, ids, context={}):
        """
        when pressing 'Open CashBox' button : Open Cash Register and calculate the starting balance
        """
        # Some verifications
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        st = self.browse(cr, uid, ids)[0]
        # Calculate the starting balance
        res = self._get_starting_balance(cr, uid, ids)
        for rs in res:
            self.write(cr, uid, [rs], res.get(rs))
            # Verify that the starting balance is superior to 0 only if this register has prev_reg_id to False
            register = self.browse(cr, uid, [rs], context=context)[0]
            if register and not register.prev_reg_id:
                if not register.balance_start > 0:
                    raise osv.except_osv(_('Error'), _("Please complete Opening Balance before opening register '%s'!") % register.name)
        # Complete closing balance with all elements of starting balance
        cashbox_line_obj = self.pool.get('account.cashbox.line')
        # Search lines from current register starting balance
        cashbox_line_ids = cashbox_line_obj.search(cr, uid, [('starting_id', '=', st.id)], context=context)
        # Search lines from current register ending balance and delete them
        cashbox_line_end_ids = cashbox_line_obj.search(cr, uid, [('ending_id', '=', st.id)], context=context)
        cashbox_line_obj.unlink(cr, uid, cashbox_line_end_ids, context=context)
        # Recreate all lines from starting to ending
        for line in cashbox_line_obj.browse(cr, uid, cashbox_line_ids, context=context):
            vals = {
                'ending_id': st.id,
                'pieces': line.pieces,
                'number': 0.0,
            }
            cashbox_line_obj.create(cr, uid, vals, context=context)
        # Give a Cash Register Name with the following composition : 
        #+ Cash Journal Code + A Sequence Number (like /02)
        if st.journal_id and st.journal_id.code:
            seq = self.pool.get('ir.sequence').get(cr, uid, 'cash.register')
            name = st.journal_id.code + seq
            res_id = self.write(cr, uid, ids, {'state' : 'open', 'name': name})
            return res_id
        else:
            return False

    def button_confirm_cash(self, cr, uid, ids, context={}):
        """
        when you're attempting to close a CashBox via 'Close CashBox'
        """
        # First verify that all lines are in hard state
        for st in self.browse(cr, uid, ids, context=context):
            for line in st.line_ids:
                if line.state != 'hard':
                    raise osv.except_osv(_('Warning'), _('All entries must be hard posted before closing CashBox!'))
        # Then verify that another Cash Register exists
        for st in self.browse(cr, uid, ids, context=context):
            st_prev_ids = self.search(cr, uid, [('prev_reg_id', '=', st.id)], context=context)
            if len(st_prev_ids) > 1:
                raise osv.except_osv(_('Error'), _('A problem occured: More than one register have this one as previous register!'))
            # Verify that the closing balance have been freezed
            if not st.closing_balance_frozen:
                raise osv.except_osv(_('Error'), _("Please confirm closing balance before closing register named '%s'") % st.name or '')
        # Then we open a wizard to permit the user to confirm that he want to close CashBox
        return {
            'name' : "Closing CashBox",
            'type' : 'ir.actions.act_window',
            'res_model' :"wizard.closing.cashbox",
            'target': 'new',
            'view_mode': 'form',
            'view_type': 'form',
            'context': {
                    'active_id': ids[0],
                    'active_ids': ids
                }
        }

    def _end_balance(self, cr, uid, ids, field_name=None, arg=None, context={}):
        """
        Calculate register's balance: call super, then add the Open Advance Amount to the end balance
        """
        res = super(account_cash_statement, self)._end_balance(cr, uid, ids, field_name, arg, context)
        for statement in self.browse(cr, uid, ids, context):
            # UF-425: Add the Open Advances Amount when calculating the "Calculated Balance" value
            res[statement.id] += statement.open_advance_amount or 0.0
                
        return res

    def _gap_compute(self, cursor, user, ids, name, attr, context=None):
        res = {}
        statements = self.browse(cursor, user, ids, context=context)
        for statement in statements:
            diff_amount = statement.balance_end - statement.balance_end_cash 
            res[statement.id] = diff_amount 
        
        return res

    _columns = {
            'balance_end': fields.function(_end_balance, method=True, store=False, string='Balance', help="Closing balance"),
            'state': fields.selection((('draft', 'Draft'), ('open', 'Open'), ('partial_close', 'Partial Close'), ('confirm', 'Closed')), 
                readonly="True", string='State'),
            'name': fields.char('Register Name', size=64, required=False, readonly=True),
            'period_id': fields.many2one('account.period', 'Period', required=True, states={'draft':[('readonly', False)]}, readonly=True),
            'line_ids': fields.one2many('account.bank.statement.line', 'statement_id', 'Statement lines', 
                states={'partial_close':[('readonly', True)], 'confirm':[('readonly', True)], 'draft':[('readonly', True)]}),
            'open_advance_amount': fields.float('Open Advances Amount'),
            'closing_gap': fields.function(_gap_compute, method=True, string='Gap'),
            'comments': fields.char('Comments', size=64, required=False, readonly=False),
    }

    def button_wiz_temp_posting(self, cr, uid, ids, context={}):
        """
        When pressing 'Temp Posting' button then opening a wizard to select some account_bank_statement_line and change them into temp posting state.
        """
        domain = [('statement_id', '=', ids[0]), ('state', '=', 'draft')]
        if context is None:
            context = {}
        context['type_posting'] = 'temp'
        # Prepare view
        view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'register_accounting', 'view_account_bank_statement_line_tree')
        view_id = view and view[1] or False
        # Prepare search view
        search_view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'register_accounting', 'view_account_bank_statement_line_filter')
        search_view_id = search_view and search_view[1] or False
        return {
            'name': 'Temp Posting from %s' % self.browse(cr, uid, ids[0]).name,
            'type': 'ir.actions.act_window',
            'res_model': 'account.bank.statement.line',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'view_id': [view_id],
            'search_view_id': search_view_id,
            'domain': domain,
            'context': context,
            'target': 'crush', # use any word to crush the actual tab
        }

    def button_wiz_hard_posting(self, cr, uid, ids, context={}):
        """
        When pressing 'Hard Posting' button then opening a wizard to select some account_bank_statement_line and change them into hard posting state.
        """
        domain = [('statement_id', '=', ids[0]), ('state', 'in', ['draft','temp'])]
        if context is None:
            context = {}
        context['type_posting'] = 'hard'
        # Prepare view
        view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'register_accounting', 'view_account_bank_statement_line_tree')
        view_id = view and view[1] or False
        # Prepare search view
        search_view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'register_accounting', 'view_account_bank_statement_line_filter')
        search_view_id = search_view and search_view[1] or False
        return {
            'name': 'Hard Posting from %s' % self.browse(cr, uid, ids[0]).name,
            'type': 'ir.actions.act_window',
            'res_model': 'account.bank.statement.line',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'view_id': [view_id],
            'search_view_id': search_view_id,
            'domain': domain,
            'context': context,
            'target': 'crush', # use any word to crush the actual tab
        }

account_cash_statement()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
