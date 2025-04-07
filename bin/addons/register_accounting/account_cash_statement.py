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
from .register_tools import create_cashbox_lines, previous_register_id

class account_cash_statement(osv.osv):
    _name = "account.bank.statement"
    _inherit = "account.bank.statement"

    _order = 'state, period_id, instance_id, journal_id'

    def create(self, cr, uid, vals, context=None):
        """
        Create a Cash Register without an error overdue to having open two cash registers on the same journal
        """
        j_obj = self.pool.get('account.journal')
        journal = j_obj.browse(cr, uid, vals['journal_id'], context=context)

        # UFTP-116: Fixed a serious problem detected very late: the cashbox lines created by default even for the Cash Reg from sync!
        # This leads to the problem that each time, a Cash Reg is new from a sync, it added new 16 lines for the Cash Reg
        sync_update = context.get('sync_update_execution', False)
        if journal.type == 'cash' and not sync_update:
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

        # UF-2479: Block the creation of the register if the given period is not open, in sync context
        if 'period_id' in vals and sync_update:
            period = self.pool.get('account.period').browse(cr, uid, vals.get('period_id'), context)
            if period and period.state == 'created':
                raise osv.except_osv(_('Error !'), _('Period \'%s\' is not open! No Register is created') % (period.name,))

        # Observe register state
        prev_reg = False
        prev_reg_id = vals.get('prev_reg_id', False)
        if prev_reg_id:
            prev_reg = self.browse(cr, uid, [prev_reg_id], context=context)[0]
            # if previous register closing balance is freezed, then retrieving previous closing balance
            # US_410: retrieving previous closing balance even closing balance is not freezed
            # if prev_reg.closing_balance_frozen:
            # US-948: carry over for bank, and always carry over bank
            # accountant manual field
            if journal.type == 'bank':
                vals.update({'balance_start': prev_reg.balance_end_real})

        if not prev_reg and sync_update and vals.get('period_id') and vals.get('journal_id'):
            prev_reg_id = previous_register_id(self, cr, uid, vals['period_id'], vals['journal_id'], context=context, raise_error=False)
            if prev_reg_id:
                prev_reg = self.browse(cr, uid, [prev_reg_id], fields_to_fetch=['responsible_ids', 'signature_id'], context=context)[0]

        if 'responsible_ids' not in vals and prev_reg and prev_reg.responsible_ids:
            vals['responsible_ids'] = [(6, 0, [x.id for x in prev_reg.responsible_ids])]

        res_id = super(account_cash_statement, self).create(cr, uid, vals, context=context)

        if prev_reg and prev_reg.signature_id:
            cr.execute("""
                update signature_line l
                    set user_id=o.user_id, backup=o.backup, user_name=u.name
                from
                    signature sign, signature_line o, signature o_sign, res_users u
                where
                    o.signature_id = o_sign.id
                    and o_sign.signature_res_model = 'account.bank.statement'
                    and o_sign.signature_res_id = %s
                    and o.name_key = l.name_key
                    and sign.signature_res_id = %s
                    and sign.signature_res_model = 'account.bank.statement'
                    and l.signature_id = sign.id
                    and u.id = o.user_id

            """, (prev_reg.id, res_id))
        # take on previous lines if exists (or discard if they come from sync)
        if prev_reg_id and not sync_update:
            create_cashbox_lines(self, cr, uid, [prev_reg_id], ending=True, context=context)
        return res_id


    def do_button_open_cash(self, cr, uid, ids, context=None):
        """
        when pressing 'Open CashBox' button : Open Cash Register and calculate the starting balance
        """
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids] # Calculate the starting balance

        # Prepare some values
        st = self.browse(cr, uid, ids, context=context)[0]

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
            # note: check on closing line duplicates will be skipped as the reg. is still in Draft state at this step
            cashbox_line_obj.create(cr, uid, vals, context=context)
        # Give a Cash Register Name with the following composition :
        #+ Cash Journal Name
        if st.journal_id and st.journal_id.name:
            cash_reg_vals = {'state': 'open', 'name': st.journal_id.name}
            return self.write(cr, uid, ids, cash_reg_vals, context=context)
        else:
            return False

    def button_confirm_cash(self, cr, uid, ids, context=None):
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
                raise osv.except_osv(_('Error'), _('A problem occurred: More than one register have this one as previous register!'))
            # Verify that the closing balance have been freezed
            if not st.closing_balance_frozen:
                raise osv.except_osv(_('Error'), _("Please confirm closing balance before closing register named '%s'") % st.name or '')
            # Do not permit closing Cash Register if previous register is not closed! (confirm state)
            if st.prev_reg_id and st.prev_reg_id.state != 'confirm':
                raise osv.except_osv(_('Error'), _('Please close previous register before closing this one!'))
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

    def _gap_compute(self, cursor, user, ids, name, attr, context=None):
        res = {}
        statements = self.browse(cursor, user, ids, context=context)
        for statement in statements:
            diff_amount = statement.balance_end - statement.balance_end_cash
            res[statement.id] = diff_amount
        return res

    def _get_cash_starting_balance(self, cr, uid, ids, context=None):
        if not ids:
            return {}
        if isinstance(ids, int):
            ids = [ids]

        cr.execute('''
            select
                st.id, coalesce(amount.amount, 0)+coalesce(amount.mig, 0)+coalesce(st.initial_migration_amount,0)
            from
                account_bank_statement st
                inner join account_period p on st.period_id = p.id
                inner join account_journal j on st.journal_id = j.id
                left join lateral (
                    select
                        max(coalesce(p_st.initial_migration_amount,0)) as mig, sum(amount) as amount
                    from
                        account_bank_statement p_st
                        inner join account_bank_statement_line p_st_li on p_st_li.statement_id = p_st.id
                        inner join account_period p_p on p_st.period_id = p_p.id
                    where
                        p_st.journal_id = st.journal_id and
                        p_p.date_start < p.date_start
                    group by st.id
                ) amount on true
            where
                j.type='cash' and
                st.state != 'confirm' and
                st.id in %s
        ''', (tuple(ids), ))

        return dict(cr.fetchall())


    def _msf_calculated_balance_compute(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Sum of starting balance (balance_start) and sum of cash transaction (total_entry_encoding)
        """
        if context is None:
            context = {}
        # Prepare some values
        res = {}
        for st in self.browse(cr, uid, ids):
            amount = (st.balance_start or 0.0) + (st.total_entry_encoding or 0.0)
            res[st.id] = amount
        return res


    _columns = {
        'line_ids': fields.one2many('account.bank.statement.line', 'statement_id', 'Statement lines',
                                    states={'confirm': [('readonly', True)], 'draft': [('readonly', True)]}),
        'open_advance_amount': fields.float('Unrecorded Advances'),
        'unrecorded_expenses_amount': fields.float('Unrecorded expenses'),
        'closing_gap': fields.function(_gap_compute, method=True, string='Gap'),
        'comments': fields.char('Comments', size=64, required=False, readonly=False),
        'msf_calculated_balance': fields.function(_msf_calculated_balance_compute, method=True, readonly=True, string='Calculated Balance',
                                                  help="Starting Balance + Cash Transactions"),

        'initial_migration_amount': fields.float('Initial Migration Amount', readonly=1, help='Used to store the migration initial amount (pre US-7221)'),
    }

    def read(self, cr, uid, ids, vals=None, context=None, load='_classic_read'):
        data = super(account_cash_statement, self).read(cr, uid, ids, vals, context=context, load=load)

        if not vals or 'balance_start' in vals:
            cash_balance_start = self._get_cash_starting_balance(cr, uid, ids, context)
            if cash_balance_start:
                if isinstance(ids, int):
                    data['balance_start'] = cash_balance_start[ids[0]]
                else:
                    for d in data:
                        if d['id'] in cash_balance_start:
                            d['balance_start'] = cash_balance_start[d['id']]
        return data

    def button_wiz_temp_posting(self, cr, uid, ids, context=None):
        """
        When pressing 'Temp Posting' button then opening a wizard to select some account_bank_statement_line and change them into temp posting state.
        """
        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
        self.check_access_rule(cr, real_uid, ids, 'write')
        domain = [('statement_id', '=', ids[0]), ('state', '=', 'draft')]
        if context is None:
            context = {}
        context.update({
            'type_posting': 'temp',
            'register_id': ids[0],
        })
        if not self.pool.get('account.bank.statement.line').search_exists(cr, uid, domain, context=context):
            raise osv.except_osv(_('Warning'), _('There is no line to Temp post'))
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

    def button_wiz_hard_posting(self, cr, uid, ids, context=None):
        """
        When pressing 'Hard Posting' button then opening a wizard to select some account_bank_statement_line and change them into hard posting state.
        """
        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
        self.check_access_rule(cr, real_uid, ids, 'write')
        domain = [('statement_id', '=', ids[0]), ('state', 'in', ['draft','temp'])]
        if context is None:
            context = {}
        context.update({
            'type_posting': 'hard',
            'register_id': ids[0],
        })
        if not self.pool.get('account.bank.statement.line').search_exists(cr, uid, domain, context=context):
            raise osv.except_osv(_('Warning'), _('There is no line to Hard post'))
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


class account_cashbox_line(osv.osv):
    _inherit = "account.cashbox.line"
    _order = "pieces"

account_cashbox_line()


class account_bank_statement_line(osv.osv):
    _inherit = 'account.bank.statement.line'

    _columns = {
        # UTP-482 linked confirmed PO for an operational advance in cache register
        'cash_register_op_advance_po_id': fields.many2one('purchase.order',
                                                          'OPE ADV - LINK TO PO', required=False,
                                                          hide_default_menu=True,
                                                          help='Operational advance purchase order'),
    }

    def check_is_cash_register_op_advance_po_available(self, cr, uid, ids, context=None):
        """
            cash_register_op_advance_po_id m2o allowed
            for an Operational advance type for specific treatment account
        """
        if isinstance(ids, int):
            ids = [ids]
        for o in self.browse(cr, uid, ids, context=context):
            if o.cash_register_op_advance_po_id:
                if o.account_id and o.account_id.type_for_register != 'advance':
                    return False
        return True

    _constraints = [
        (check_is_cash_register_op_advance_po_available, 'You can only link to a purchase order for an Operation advance', ['account_id', 'cash_register_op_advance_po_id']),
    ]

    def create(self, cr, uid, values, context=None):
        if 'cash_register_op_advance_po_id' in values:
            if values['cash_register_op_advance_po_id']:
                domain = [
                    ('cash_register_op_advance_po_id', '=', values['cash_register_op_advance_po_id'])
                ]
                linked_po_ids = self.search(cr, uid, domain, context=context)
                if linked_po_ids:
                    raise osv.except_osv(_("Warning"),_("Selected 'OPE ADV - LINK TO PO' purchase order is already linked to another register line."))
        return super(account_bank_statement_line, self).create(cr, uid, values, context=context)

    def write(self, cr, uid, ids, values, context=None):
        if not ids:
            return True
        if 'cash_register_op_advance_po_id' in values:
            if values['cash_register_op_advance_po_id']:
                domain = [
                    ('id', 'not in', ids),
                    ('cash_register_op_advance_po_id', '=', values['cash_register_op_advance_po_id'])
                ]
                linked_po_ids = self.search(cr, uid, domain, context=context)
                if linked_po_ids:
                    raise osv.except_osv(_("Warning"),_("Selected 'OPE ADV - LINK TO PO' purchase order is already linked to another register line."))
        return super(account_bank_statement_line, self).write(cr, uid, ids, values, context=context)

account_bank_statement_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
