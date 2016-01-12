# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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
import logging
from account_period_closing_level import ACCOUNT_PERIOD_STATE_SELECTION


class account_period(osv.osv):
    _name = "account.period"
    _inherit = "account.period"

    # To avoid issues with existing OpenERP code (account move line for example)
    # the state are:
    #  - 'created' for Draft
    #  - 'draft' for Open
    #  - 'done' for HQ-Closed
    # 1 = state created as 'Draft' ('created') at HQ (update to state handled
    #   in create)
    # 2 = state moves from 'Open' ('draft') -> any close at HQ (sync down)
    # 3 =
    # 3 = state reopened at HQ -> reopen at all levels

    def check_unposted_entries(self, cr, uid, period_id, context=None):
        """
        Check that no oustanding unposted entries remain
        """
        sql = """SELECT COUNT(id) FROM account_move WHERE period_id = %s AND state != 'posted'""" % period_id
        cr.execute(sql)
        sql_res = cr.fetchall()
        count_moves = sql_res and sql_res[0] and sql_res[0][0] or 0
        if count_moves > 0:
            raise osv.except_osv(_('Warning'), _('Period closing is denied: some Journal Entries remain unposted in this period.'))
        return True

    def action_set_state(self, cr, uid, ids, context):
        """
        Change period state
        """

        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # Prepare some elements
        reg_obj = self.pool.get('account.bank.statement')
        sub_obj = self.pool.get('account.subscription.line')
        curr_obj = self.pool.get('res.currency')
        curr_rate_obj = self.pool.get('res.currency.rate')

        # previous state of the period
        ap_dict = self.read(cr, uid, ids)[0]
        previous_state = ap_dict['state']


        # Ticket utp913 set state_sync_flag for conditional sync of state
        # 'none' : no update to the state field via a sync (data is still sent but not updated in target instance)
        # other values; state will be set to this value and then to 'none'
        # note that 'draft' = 'Open' and 'created' = 'Draft' ... see ACCOUNT_PERIOD_STATE_SELECTION in init

        if context.get('sync_update_execution') is None:
            user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
            level = user.company_id.instance_id.level

            if level == 'section': # section = HQ
                if previous_state == 'created' and context['state'] == 'draft':
                    self.write(cr, uid, ids, {'state_sync_flag': 'none'})
                if previous_state == 'draft' and context['state'] == 'field-closed':
                    self.write(cr, uid, ids, {'state_sync_flag': context['state']})
                if previous_state == 'field-closed' and context['state'] == 'mission-closed':
                    self.write(cr, uid, ids, {'state_sync_flag': context['state']})
                if previous_state == 'mission-closed' and context['state'] == 'done':
                    self.write(cr, uid, ids, {'state_sync_flag': context['state']})
                if previous_state == 'mission-closed' and context['state'] == 'field-closed':
                    self.write(cr, uid, ids, {'state_sync_flag': context['state']})
                if previous_state == 'field-closed' and context['state'] == 'draft':
                    self.write(cr, uid, ids, {'state_sync_flag': context['state']})

            if level == 'coordo':
                if previous_state == 'created' and context['state'] == 'draft':
                    self.write(cr, uid, ids, {'state_sync_flag': 'none'})
                if previous_state == 'draft' and context['state'] == 'field-closed':
                    self.write(cr, uid, ids, {'state_sync_flag': context['state']})
                if previous_state == 'field-closed' and context['state'] == 'mission-closed':
                    self.write(cr, uid, ids, {'state_sync_flag': context['state']})
                if previous_state == 'mission-closed' and context['state'] == 'done':
                    self.write(cr, uid, ids, {'state_sync_flag': 'none'})
                if previous_state == 'mission-closed' and context['state'] == 'field-closed':
                    self.write(cr, uid, ids, {'state_sync_flag': 'none'})
                if previous_state == 'field-closed' and context['state'] == 'draft':
                    self.write(cr, uid, ids, {'state_sync_flag': context['state']})

            if level == 'project':
                    self.write(cr, uid, ids, {'state_sync_flag': 'none'})

        # Do verifications for draft periods
        for period in self.browse(cr, uid, ids, context=context):
            # Check state consistency about previous and next periods
            # UF-550: A period now can only be opened if all previous periods (of the same fiscal year) have been already opened
            # UTP-755: More global than the UF-550:
            #       - A period now can only be set to the next state if all
            #         previous periods (of the same fiscal year) are set at a
            #         higher state,
            #       - A period now can only be set to a previous state if all
            #         next periods (of the same fiscal year) are set at a lower
            #         state.
            check_errors = {
                'created': _(
                    "Cannot open this period. "
                    "All previous periods must be opened before opening this one."),
                'draft': _(
                    "Cannot close this period at the field level. "
                    "All previous periods must be closed before closing this one."),
                'field-closed': _(
                    "Cannot close this period at the mission level. "
                    "All previous periods must be closed before closing this one."),
                'mission-closed': _(
                    "Cannot close this period at the HQ level. "
                    "All previous periods must be closed before closing this one."),
            }
            check_states = ['created', 'draft', 'field-closed', 'mission-closed', 'done']
            if not context.get('state'):
                raise osv.except_osv(
                    _("Error"),
                    _("Next state unknown"))
            backward_asked = check_states.index(context['state']) < check_states.index(period.state)
            # Forward operation, no check for 'created' state
            if period.state in check_states[1:] and not backward_asked:
                pp_ids = self.search(
                    cr, uid,
                    [('date_start', '<', period.date_start),
                    ('fiscalyear_id', '=', period.fiscalyear_id.id)],
                    context=context)
                for pp in self.browse(cr, uid, pp_ids, context=context):
                    if check_states.index(pp.state) <= check_states.index(period.state):
                        raise osv.except_osv(_('Warning'), check_errors[period.state])
            # For backward operation, all next periods have to be at the
            # same state or higher than the current period
            elif backward_asked:
                np_ids = self.search(
                    cr, uid,
                    [('date_start', '>', period.date_start),
                    ('fiscalyear_id', '=', period.fiscalyear_id.id)],
                    context=context)
                for np in self.browse(cr, uid, np_ids, context=context):
                    if check_states.index(np.state) >= check_states.index(period.state):
                        raise osv.except_osv(
                            _('Warning'),
                            _("Cannot backward the state of this period. "
                              "All next periods must be at a lower state."))
            # / Check state consistency

            if period.state == 'draft':
                # check if there are draft payroll entries in the period. Ticket uftp-89
                if context['state'] == 'field-closed':
                    hr_payroll_msf_obj = self.pool.get('hr.payroll.msf')
                    payroll_rows = hr_payroll_msf_obj.search(cr, uid, [('period_id','=', period.id),('state','=','draft')])
                    if payroll_rows:
                        raise osv.except_osv(_('Error !'), _('There are outstanding payroll entries in this period; you must validate them to field-close this period.'))
                    # UFTP-351: Check that no Journal Entries are Unposted for this period
                    self.check_unposted_entries(cr, uid, period.id, context=context)

                # first verify that all existent registers for this period are closed
                reg_ids = reg_obj.search(cr, uid, [('period_id', '=', period.id)], context=context)
                for register in reg_obj.browse(cr, uid, reg_ids, context=context):
                    if register.state not in ['confirm']:
                        raise osv.except_osv(_('Warning'), _("The register '%s' is not closed. Please close it before closing period") % (register.name,))
                # check if subscriptions lines were not created for this period
                sub_ids = sub_obj.search(cr, uid, [('date', '<', period.date_stop), ('move_id', '=', False)], context=context)
                if len(sub_ids) > 0:
                    raise osv.except_osv(_('Warning'), _("Recurring entries were not created for period '%s'. Please create them before closing period") % (period.name,))
                # then verify that all currencies have a fx rate in this period
                # retrieve currencies for this period (in account_move_lines)
                sql = """SELECT DISTINCT currency_id
                FROM account_move_line
                WHERE period_id = %s""" % period.id
                cr.execute(sql)
                res = [x[0] for x in cr.fetchall()]
                comp_curr_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id
                # for each currency do a verification about fx rate
                for period_id in res:
                    # search for company currency_id if ID is None
                    if period_id == None or period_id == comp_curr_id:
                        continue
                    rate_ids = curr_rate_obj.search(cr, uid, [('currency_id', '=', period_id), ('name', '>=', period.date_start),
                        ('name', '<=', period.date_stop)], context=context)
                    # if no rate found
                    if not rate_ids:
                        curr_name = curr_obj.read(cr, uid, period_id, ['name']).get('name', False)
                        raise osv.except_osv(_('Warning'), _("No FX rate found for currency '%s'") % curr_name)
## This block could be reused later
#                # finally check supplier invoice for this period and display those of them that have due date to contened in this period
#                inv_ids = inv_obj.search(cr, uid, [('state', 'in', ['draft', 'open']), ('period_id', '=', period.id),
#                    ('type', 'in', ['in_invoice', 'in_refund'])], context=context)
#                inv_to_display = []
#                for inv in inv_obj.browse(cr, uid, inv_ids, context=context):
#                    if not inv.date_due or inv.date_due <= period.date_stop:
#                        inv_to_display.append(inv.id)
#                if inv_to_display:
#                    raise osv.except_osv(_('Warning'), _('Some invoices are not paid and have an overdue date. Please verify this with \
#"Open overdue invoice" button and fix the problem.'))
###################################################

                # Write changes
                if isinstance(ids, (int, long)):
                    ids = [ids]
                for p_id in ids:
                    self.write(cr, uid, p_id, {'state':'field-closed', 'field_process': False}, context=context)
                return True

            # UFTP-351: Check that no Journal Entries are Unposted for this period
            if period.state == 'field-closed' and context['state'] == 'mission-closed':
                self.check_unposted_entries(cr, uid, period.id, context=context)

        # check if unposted move lines are linked to this period
        move_line_obj = self.pool.get('account.move.line')
        move_lines = move_line_obj.search(cr, uid, [('period_id', 'in', ids)])
        for move_line in move_line_obj.browse(cr, uid, move_lines):
            if move_line.state != 'valid':
                raise osv.except_osv(_('Error !'), _('You cannot close a period containing unbalanced move lines!'))

        # otherwise, change the period's and journal period's states
        if context['state']:
            state = context['state']
            if state == 'done':
                journal_state = 'done'
            else:
                journal_state = 'draft'
            for per_id in ids:
                cr.execute('update account_journal_period set state=%s where period_id=%s', (journal_state, per_id))
                # Change cr.execute for period state by a self.write() because of Document Track Changes on Periods ' states
                self.write(cr, uid, per_id, {'state': state, 'field_process': False}) #cr.execute('update account_period set state=%s where id=%s', (state, id))
        return True

    def _get_payroll_ok(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Fetch elements from unifield setup configuration and return payroll_ok field value
        """
        res = {}
        payroll = False
        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        if setup and setup.payroll_ok:
            payroll = True
        for period_id in ids:
            res[period_id] = payroll
        return res

    def _get_is_system(self, cr, uid, ids, field_name=None, arg=None, context=None):
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long, )):
            ids = [ids]

        for rec in self.browse(cr, uid, ids, context=context):
            res[rec.id] = isinstance(rec.number, int) \
                and rec.number in (0, 16, ) or False
        return res

    def _get_search_is_system(self, cr, uid, obj, name, args, context=None):
        res = []
        if not len(args):
            return res
        if len(args) != 1:
            msg = _("Domain %s not suported") % (str(args), )
            raise osv.except_osv(_('Error'), msg)
        if args[0][1] != '=':
            msg = _("Operator '%s' not suported") % (args[0][1], )
            raise osv.except_osv(_('Error'), msg)
        operator = 'in' if args[0][2] else 'not in'

        return [('number', operator, (0, 16, ))]

    _columns = {
        'name': fields.char('Period Name', size=64, required=True, translate=True),
        'special': fields.boolean('Opening/Closing Period', size=12,
            help="These periods can overlap.", readonly=True),
        'state': fields.selection(ACCOUNT_PERIOD_STATE_SELECTION, 'State', readonly=True,
            help='HQ opens a monthly period. After validation, it will be closed by the different levels.'),
        'number': fields.integer(string="Number for register creation", help="This number informs period's order. Should be between 1 and 15. If 16: have not been defined yet."),
        'field_process': fields.boolean('Is this period in Field close processing?', readonly=True),
        'state_sync_flag': fields.char('Sync Flag', required=True, size=64, help='Flag for controlling sync actions on the period state.'),
        'payroll_ok': fields.function(_get_payroll_ok, method=True, type='boolean', store=False, string="Permit to know if payrolls are active", readonly=True),
        'is_system': fields.function(_get_is_system, fnct_search=_get_search_is_system, method=True, type='boolean', string="System period ?", readonly=True),
    }

    _order = 'date_start, number'

    def create(self, cr, uid, vals, context=None):
        if not context:
            context = {}

        if context.get('sync_update_execution') and 'state' not in vals:
            logging.getLogger('init').info('Loading default draft - created - state for account.period')
            vals['state'] = 'created'

        res = super(account_period, self).create(cr, uid, vals, context=context)
        self.pool.get('account.period.state').update_state(cr, uid, res,
                                                           context=context)
        return res

    def write(self, cr, uid, ids, vals, context=None):
        if not context:
            context = {}
        # control conditional push-down of state from HQ. Ticket UTP-913
        if context.get('sync_update_execution'):
            if vals['state_sync_flag'] != 'none':
                vals['state'] = vals['state_sync_flag']
                vals['state_sync_flag'] = 'none'
            else:
                vals['state_sync_flag'] = 'none'

        res = super(account_period, self).write(cr, uid, ids, vals, context=context)
        self.pool.get('account.period.state').update_state(cr, uid, ids,
                                                           context=context)
        return res

    def unlink(self, cr, uid, ids, context=None):
        if not ids:
            return False
        if isinstance(ids, (int, long, )):
            ids = [ids]

        is_system = [ rec.is_system \
            for rec in self.browse(cr, uid, ids, context=context) ]
        if any(is_system):
            raise osv.except_osv(_('Warning'), _('System period not deletable'))
        return super(account_period, self).unlink(cr, uid, ids, context=context)

    _defaults = {
        'state': lambda *a: 'created',
        'number': lambda *a: 16, # Because of 15 period in MSF, no period would use 16 number.
        'special': lambda *a: False,
        'field_process': lambda *a: False,
        'state_sync_flag': lambda *a: 'none',
    }

    def action_reopen_field(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        context['state'] = 'draft'
        return self.action_set_state(cr, uid, ids, context)

    def action_reopen_mission(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        context['state'] = 'field-closed'
        return self.action_set_state(cr, uid, ids, context)

    def action_open_period(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        context['state'] = 'draft'
        return self.action_set_state(cr, uid, ids, context)

    def action_close_field_reopen(self, cr, uid, ids, context=None):
        return self.action_close_field(cr, uid, ids, context=context)

    def action_close_field(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        context['state'] = 'field-closed'
        return self.action_set_state(cr, uid, ids, context)

    def action_close_mission(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        context['state'] = 'mission-closed'
        return self.action_set_state(cr, uid, ids, context)

    def action_close_hq(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        context['state'] = 'done'
        return self.action_set_state(cr, uid, ids, context)

    def register_view(self, cr, uid, ids, register_type='bank', context=None):
        """
        Open list of 'register_type' register from given period.
        register_type is the type of register:
          - bank
          - cheque
          - cash
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = self.pool.get('account.bank.statement').get_statement(cr, uid, [], register_type, context=None)
        # Only display registers from given period
        if res and res.get('domain', False):
            domain = res.get('domain')
            domain.append(('period_id', 'in', ids))
            res.update({'domain': domain})
        # Do not set default "draft" or "open" or "closed" button
        if res and res.get('context', False):
            ctx = res.get('context')
            ctx.update({'search_default_draft': 0, 'search_default_open': 0, 'search_default_confirm': 0})
            res.update({'context': ctx})
        return res

    def button_bank_registers(self, cr, uid, ids, context=None):
        """
        Open Bank registers
        """
        if context is None:
            context = {}
        return self.register_view(cr, uid, ids, 'bank', context=context)

    def button_cheque_registers(self, cr, uid, ids, context=None):
        """
        Open Cheque registers
        """
        if context is None:
            context = {}
        return self.register_view(cr, uid, ids, 'cheque', context=context)

    def button_cash_registers(self, cr, uid, ids, context=None):
        """
        Open Cash registers
        """
        if context is None:
            context = {}
        return self.register_view(cr, uid, ids, 'cash', context=context)

    def invoice_view(self, cr, uid, ids, name=_('Invoices'), domain=[], module='account', view_name='invoice_tree', context=None):
        """
        Open an invoice tree view with the given domain for the period in ids
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # Search invoices
        for period in self.browse(cr, uid, ids, context=context):
            # prepare view
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, module, view_name)
            view_id = view_id and view_id[1] or False
            domain += [('date_invoice', '>=', period.date_start), ('date_invoice', '<=', period.date_stop), ('state', 'in', ['draft', 'open'])]
            context.update({'search_default_draft': 0})
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.invoice',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': [view_id],
                'target': 'current',
                'domain': domain,
                'context': context,
                'name': name,
            }

    # Stock transfer voucher
    def button_stock_transfer_vouchers(self, cr, uid, ids, context=None):
        """
        Create a new tab with Open stock transfer vouchers from given period.
        """
        return self.invoice_view(cr, uid, ids, _('Stock Transfer Vouchers'), [('type','=','out_invoice'), ('is_debit_note', '=', False), ('is_inkind_donation', '=', False), ('is_intermission', '=', False)], context={'type':'out_invoice', 'journal_type': 'sale'})

    def button_customer_refunds(self, cr, uid, ids, context=None):
        """
        Create a new tab with Customer refunds from given period.
        """
        return self.invoice_view(cr, uid, ids, _('Customer Refunds'), [('type', '=', 'out_refund'), ('is_debit_note', '=', False)], context=context)

    # Debit note
    def button_debit_note(self, cr, uid, ids, context=None):
        return self.invoice_view(cr, uid, ids, _('Debit Note'), [('type','=','out_invoice'), ('is_debit_note', '!=', False), ('is_inkind_donation', '=', False)], context={'type':'out_invoice', 'journal_type': 'sale', 'is_debit_note': True})

    # Intermission voucher OUT
    def button_intermission_out(self, cr, uid, ids, context=None):
        return self.invoice_view(cr, uid, ids, _('Intermission Voucher OUT'), [('type','=','out_invoice'), ('is_debit_note', '=', False), ('is_inkind_donation', '=', False), ('is_intermission', '=', True)], context={'type':'out_invoice', 'journal_type': 'intermission'})

    def button_supplier_refunds(self, cr, uid, ids, context=None):
        """
        Open a view that display Supplier invoices for given period
        """
        return self.invoice_view(cr, uid, ids, _('Supplier Refunds'), [('type', '=', 'in_refund')], context={'type':'in_refund', 'journal_type': 'purchase_refund'})

    # Supplier direct invoices
    def button_supplier_direct_invoices(self, cr, uid, ids, context=None):
        """
        Open a view that display Direct invoices for this period
        """
        return self.invoice_view(cr, uid, ids, _('Supplier Direct Invoices'), [('type','=','in_invoice'), ('register_line_ids', '!=', False)], context={'type':'in_invoice', 'journal_type': 'purchase'})

    # In-kind donation
    def button_donation(self, cr, uid, ids, context=None):
        """
        Open a view that display Inkind donation for this period
        """
        return self.invoice_view(cr, uid, ids, _('Donation'), [('type','=','in_invoice'), ('is_debit_note', '=', False), ('is_inkind_donation', '=', True)], context={'type':'in_invoice', 'journal_type': 'inkind'})

    # Intermission voucher IN
    def button_intermission_in(self, cr, uid, ids, context=None):
        """
        Open a view that display intermission voucher in for this period
        """
        return self.invoice_view(cr, uid, ids, _('Intermission Voucher IN'), [('type','=','in_invoice'), ('is_debit_note', '=', False), ('is_inkind_donation', '=', False), ('is_intermission', '=', True)], context={'type':'in_invoice', 'journal_type': 'intermission'})

    # Supplier invoice
    def button_supplier_invoices(self, cr, uid, ids, context=None):
        """
        Open a view that display supplier invoices for this period
        """
        return self.invoice_view(cr, uid, ids, _('Supplier Invoices'), [('type','=','in_invoice'), ('register_line_ids', '=', False), ('is_inkind_donation', '=', False), ('is_debit_note', "=", False), ('is_intermission', '=', False)], context={'type':'in_invoice', 'journal_type': 'purchase'})

    def button_close_field_period(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        return self.write(cr, uid, ids, {'field_process': True}, context)

    def button_fx_rate(self, cr, uid, ids, context=None):
        """
        Open Currencies in a new tab
        """
        # Some checks
        if not context:
            context = {}
        # Default buttons
        context.update({'search_default_active': 1})
        return {
            'name': _('Curencies'),
            'type': 'ir.actions.act_window',
            'res_model': 'res.currency',
            'target': 'current',
            'view_mode': 'tree,form',
            'view_type': 'form',
            'context': context,
            'domain': [('active', 'in', ['t', 'f'])],
        }

    def button_hq(self, cr, uid, ids, context=None):
        """
        Open all HQ entries from given period
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Update context to set "To validate" button by default
        context.update({'search_default_non_validated': 1})
        return {
            'name': _('HQ entries'),
            'type': 'ir.actions.act_window',
            'res_model': 'hq.entries',
            'target': 'current',
            'view_mode': 'tree,form',
            'view_type': 'form',
            'context': context,
            # BKLG-15 do not use ('user_validated', '=', 'False') in domain
            # as already used by 'search_default_non_validated' in context
            'domain': [('period_id', 'in', ids)],
        }

    def button_recurring(self, cr, uid, ids, context=None):
        """
        Open all recurring models
        """
        if not context:
            context = {}
        return {
            'name': _('Reccuring lines'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.model',
            'target': 'current',
            'view_mode': 'tree,form',
            'view_type': 'form',
            'context': context,
        }

    def button_payrolls(self, cr, uid, ids, context=None):
        """
        Open payroll entries list
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        return {
            'name': _('Payroll entries'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payroll.msf',
            'target': 'current',
            'view_mode': 'tree,form',
            'view_type': 'form',
            'context': context,
            'domain': [('state', '=', 'draft'), ('period_id', 'in', ids), ('account_id.is_analytic_addicted', '=', True)]
        }

    def button_open_entries(self, cr, uid, ids, context=None):
        """
        Open G/L selector with some
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Search reconciliable accounts
        account_ids = self.pool.get('account.account').search(cr, uid, [('reconcile', '=', True)],context=context)
        # Create a filter for G/L selector
        vals = {
            'reconciled': 'unreconciled',
            'display_account': True,
            'account_ids': [(6, 0, account_ids)],
            'description': _('Journal items that are on reconciliable accounts but that are not reconciled.'),
            'display_period': True,
            'period_ids': [(6, 0, ids)]
        }
        res_id = self.pool.get('account.mcdb').create(cr, uid, vals, context=context)
        return {
            'name': _('G/L Selector'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.mcdb',
            'res_id': res_id,
            'target': 'current',
            'view_mode': 'form,tree',
            'view_type': 'form',
            'context': context,
        }

    def button_commitments(self, cr, uid, ids, context=None):
        """
        Open commitment list
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Update context to set "Except Done" button by default
        context.update({'search_default_exceptdone': 1, 'search_default_draft': 0, 'search_default_open': 0, 'search_default_done': 0})
        return {
            'name': _('Commitments'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.commitment',
            'target': 'current',
            'view_mode': 'tree,form',
            'view_type': 'form',
            'context': context,
            'domain': [('state', 'in', ['draft', 'open']), ('period_id', 'in', ids)]
        }

account_period()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
