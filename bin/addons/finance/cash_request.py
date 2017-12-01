#-*- coding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2017 TeMPO Consulting, MSF. All Rights Reserved
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
from datetime import datetime
import time
import decimal_precision as dp
from tools.translate import _
import register_accounting


class cash_request(osv.osv):
    _name = 'cash.request'
    _description = 'Cash Request'

    def _get_current_instance_level(self, cr, uid, ids, name, args, context=None):
        """
        Returns a String with the level of the current instance (section, coordo, project)
        """
        if context is None:
            context = {}
        levels = {}
        company = self._get_company(cr, uid, context=context)
        level = company.instance_id and company.instance_id.level or ''
        for cash_req_id in ids:
            levels[cash_req_id] = level
        return levels

    _columns = {
        'name': fields.char(size=128, string='Name', readonly=True, required=True),
        'prop_instance_id': fields.many2one('msf.instance', 'Proprietary instance', readonly=True, required=True,
                                            domain=[('level', '=', 'coordo')]),
        'mission': fields.related('prop_instance_id', 'mission', string='Mission', type='char', store=False,
                                  readonly=True, required=True),
        'month_period_id': fields.many2one('account.period', 'Month', required=True,
                                           domain=[('date_stop', '>=', time.strftime('%Y-%m-%d')), ('special', '=', False)]),
        'fiscalyear_id': fields.related('month_period_id', 'fiscalyear_id', string='Fiscal Year', type='many2one',
                                        relation='account.fiscalyear', readonly=True),
        'request_date': fields.date('Request Date', required=True),
        'consolidation_currency_id': fields.many2one('res.currency', 'Consolidation Currency',
                                                     required=True, readonly=True),
        'consolidation_currency_name': fields.related('consolidation_currency_id', 'name', type='char',
                                                      string='Consolidation Currency Name', store=False, readonly=True),
        'transfer_account_id': fields.many2one('account.account', 'Transfer Account Code',
                                               domain=[('type', '=', 'other'), ('user_type_code', '=', 'cash')]),
        'transfer_currency_ids': fields.one2many('transfer.currency', 'cash_request_id', 'Currency of Transfers',
                                                 required=True,
                                                 states={'done': [('readonly', True)]}),
        'bank_journal_id': fields.many2one('account.journal', 'Bank', required=True, domain=[('type', '=', 'bank')]),
        'state': fields.selection(
            [('draft', 'Draft'), ('open', 'Open'), ('done', 'Done')], 'State',
            required=True, readonly=True),
        'instance_ids': fields.many2many('msf.instance', 'cash_request_instance_rel', 'cash_request_id', 'instance_id',
                                         string='Mission Settings', readonly=True),
        'transfer_to_come': fields.float('Total Transfer to come', digits_compute=dp.get_precision('Account'),
                                         help='In case a transfer is on its way and not yet received. In functional currency.'),
        'security_envelope': fields.float('Security Envelopes', digits_compute=dp.get_precision('Account'),
                                          help='Amount to encode in functional currency'),
        'buffer': fields.float(digits=(16, 2), string='Buffer (%)'),
        'journal_name': fields.related('bank_journal_id', 'name', string='Journal Name', type='char',
                                       store=False, readonly=True),
        'journal_code': fields.related('bank_journal_id', 'code', string='Journal Code', type='char',
                                       store=False, readonly=True),
        'account_name': fields.related('bank_journal_id', 'bank_account_name', string='Account Name', type='char',
                                       store=False, readonly=True),
        'account_number': fields.related('bank_journal_id', 'bank_account_number', string='Account Number', type='char',
                                         store=False, readonly=True),
        'swift_code': fields.related('bank_journal_id', 'bank_swift_code', string='Swift Code', type='char',
                                     store=False, readonly=True),
        'bank_address': fields.related('bank_journal_id', 'bank_address', string='Address', type='char',
                                       store=False, readonly=True),
        'commitment_ids': fields.one2many('cash.request.commitment', 'cash_request_id', 'Commitments', readonly=True),
        'total_to_transfer': fields.float('Total Cash Request to transfer', digits_compute=dp.get_precision('Account'),
                                          readonly=True),
        'total_to_transfer_line_ids': fields.one2many('total.transfer.line', 'cash_request_id',
                                                      'Lines of Total Cash Request to transfer', readonly=True),
        'recap_mission_ids': fields.one2many('recap.mission', 'cash_request_id', 'Lines of Recap Mission', readonly=True),
        'planned_expense_ids': fields.one2many('cash.request.expense', 'cash_request_id', 'Planned expenses entries',
                                               required=True, states={'done': [('readonly', True)]}),
        'recap_expense_ids': fields.one2many('cash.request.recap.expense', 'cash_request_id', 'Recap Planned expenses',
                                             required=True, readonly=True),
        'past_transfer_ids': fields.many2many('account.move.line', 'cash_request_account_move_line_rel',
                                              'cash_request_id', 'account_move_line_id',
                                              string='Past Transfers', readonly=True),
        'current_instance_level': fields.function(_get_current_instance_level, method=True, type='char',
                                                  string='Current Instance Level', store=False, readonly=True),
        'payable_ids': fields.one2many('cash.request.payable', 'cash_request_id', 'Payables', required=True,
                                       readonly=True),
        'liquidity_bank_ids': fields.one2many('cash.request.liquidity.bank', 'cash_request_id',
                                              'Liquidity Position Bank', required=True, readonly=True),
        'liquidity_cash_ids': fields.one2many('cash.request.liquidity.cash', 'cash_request_id',
                                              'Liquidity Position Cash', required=True, readonly=True),
        'liquidity_cheque_ids': fields.one2many('cash.request.liquidity.cheque', 'cash_request_id',
                                                'Liquidity Position Cheque', required=True, readonly=True),
        'liquidity_total_ids': fields.one2many('cash.request.liquidity.total', 'cash_request_id',
                                               'Liquidity Position Total', required=True, readonly=True),
    }

    def _check_buffer(self, cr, uid, ids):
        """
        Checks that the buffer value isn't negative nor > 100
        """
        for cash_req in self.browse(cr, uid, ids, fields_to_fetch=['buffer']):
            if cash_req.buffer < 0 or cash_req.buffer - 100 > 10**-3:
                return False
        return True

    _constraints = [
        (_check_buffer, _("The percentage in the Buffer field is incorrect."), ['buffer']),
    ]

    def _get_company(self, cr, uid, context=None):
        """
        Returns the company as a browse record
        """
        if context is None:
            context = {}
        user_obj = self.pool.get('res.users')
        company = user_obj.browse(cr, uid, uid, fields_to_fetch=['company_id'], context=context).company_id
        return company

    def _get_prop_instance(self, cr, uid, context=None):
        """
        Returns the current instance as a browse_record if in coordo
        (= level where the Cash Request should always be created), else False
        """
        if context is None:
            context = {}
        company = self._get_company(cr, uid, context=context)
        if company.instance_id and company.instance_id.level == 'coordo':
            return company.instance_id
        return False

    def _get_prop_instance_id(self, cr, uid, context=None):
        """
        Returns the current instance_id if in coordo
        """
        if context is None:
            context = {}
        instance = self._get_prop_instance(cr, uid, context=context)
        return instance and instance.id or False

    def _get_mission(self, cr, uid, context=None):
        """
        Returns the value of Coordo Prop. instance Mission field
        """
        if context is None:
            context = {}
        instance = self._get_prop_instance(cr, uid, context=context)
        return instance and instance.mission or ''

    def _get_consolidation_currency_id(self, cr, uid, context=None):
        """
        Returns the id of the functional currency
        """
        if context is None:
            context = {}
        company = self._get_company(cr, uid, context=context)
        return company.currency_id.id

    def _get_instance_ids(self, cr, uid, context=None):
        """
        Returns the list of ids of the instances within the mission
        """
        if context is None:
            context = {}
        instance_obj = self.pool.get('msf.instance')
        mission = self._get_mission(cr, uid, context=context)
        instance_ids = instance_obj.search(cr, uid, [('mission', '=', mission), ('level', '!=', 'section')],
                                           order='level asc, code asc', context=context)  # coordo first
        return instance_ids

    _defaults = {
        'request_date': lambda *a: datetime.today(),
        'prop_instance_id': _get_prop_instance_id,
        'mission': _get_mission,
        'consolidation_currency_id': _get_consolidation_currency_id,
        'state': 'draft',
    }

    _order = 'name desc'

    def create(self, cr, uid, vals, context=None):
        """
        Creates the Cash Request and automatically fills in the values for the following fields:
        name, instance_ids
        """
        if context is None:
            context = {}
        # Cash Request name = sequence (looks like: Mission code_Cash_request-XXXX)
        sequence = self.pool.get('ir.sequence').get(cr, uid, 'cash.request')
        vals.update({'name': sequence})
        # fill in the list of Prop. Instances
        vals.update({'instance_ids': [(6, 0, self._get_instance_ids(cr, uid, context=context))]})
        return super(cash_request, self).create(cr, uid, vals, context=context)

    def copy(self, cr, uid, cash_req_id, default=None, context=None):
        """
        Duplicates a cash request:
        resets the computed items and changes the date to the one of the day
        """
        if context is None:
            context = {}
        if default is None:
            default = {}
        default.update({
            'request_date': datetime.today(),
            'instance_ids': [],
            'past_transfer_ids': [],
            'total_to_transfer': 0.0,
            'state': 'draft',
            'commitment_ids': [],
            'recap_expense_ids': [],
            'planned_expense_ids': [],
            'total_to_transfer_line_ids': [],
            'recap_mission_ids': [],
            'payable_ids': [],
            'liquidity_bank_ids': [],
            'liquidity_cash_ids': [],
            'liquidity_cheque_ids': [],
            'liquidity_total_ids': [],
        })
        return super(cash_request, self).copy(cr, uid, cash_req_id, default, context=context)

    def _check_currencies(self, cr, uid, cash_req_id, context=None):
        """
        Raises an error if:
        - no currency has been selected
        - one of the percentages is negative
        - the total percentage of the currencies is different from 0 and from 100
        - there are more than one currency and the percentage is 0
        """
        if context is None:
            context = {}
        cash_req = self.browse(cr, uid, cash_req_id, fields_to_fetch=['transfer_currency_ids'], context=context)
        percentage = 0.0
        nb_lines = len(cash_req.transfer_currency_ids)
        if nb_lines == 0:
            raise osv.except_osv(_('Error'), _('You must select at least one currency of transfers.'))
        nb_lines_zero = 0  # count how many lines are equal (or inferior) to zero
        for curr in cash_req.transfer_currency_ids:
            if curr.percentage <= 10**-3:
                nb_lines_zero += 1
            percentage += curr.percentage
        if percentage > 10**-3 and abs(percentage - 100) > 10**-3:
            raise osv.except_osv(_('Error'), _('The total percentage of the currencies of transfers is incorrect.'))
        if nb_lines > 1 and nb_lines_zero:
            raise osv.except_osv(_('Error'), _('Please indicate the percentage for each currency of transfers selected.'))

    def _generate_commitments(self, cr, uid, cash_req_id, context=None):
        """
        Generates data for the Commitment Tab of the Cash Request
        """
        if context is None:
            context = {}
        commitment_obj = self.pool.get('cash.request.commitment')
        cash_req = self.browse(cr, uid, cash_req_id, fields_to_fetch=['instance_ids', 'month_period_id'], context=context)
        # delete previous commitments for this cash request
        old_commitment_ids = commitment_obj.search(cr, uid, [('cash_request_id', '=', cash_req.id)],
                                                   order='NO_ORDER', context=context)
        commitment_obj.unlink(cr, uid, old_commitment_ids, context=context)
        # create new cash req. commitments
        instances = cash_req.instance_ids
        period = cash_req.month_period_id
        if instances and period:
            for inst in instances:
                vals = {'instance_id': inst.id,
                        'period_id': period.id,
                        'cash_request_id': cash_req.id}
                commitment_obj.create(cr, uid, vals, context=context)
        return True

    def _generate_payables(self, cr, uid, cash_req_id, context=None):
        """
        Generates data for the Payables Tab of the Cash Request
        """
        if context is None:
            context = {}
        payable_obj = self.pool.get('cash.request.payable')
        cash_req = self.browse(cr, uid, cash_req_id, fields_to_fetch=['instance_ids'], context=context)
        # delete previous payables for this cash request
        old_payable_ids = payable_obj.search(cr, uid, [('cash_request_id', '=', cash_req.id)],
                                             order='NO_ORDER', context=context)
        payable_obj.unlink(cr, uid, old_payable_ids, context=context)
        # create new cash req. payables
        instances = cash_req.instance_ids
        for inst in instances:
            vals = {'instance_id': inst.id,
                    'cash_request_id': cash_req.id}
            payable_obj.create(cr, uid, vals, context=context)
        return True

    def _generate_liquidity(self, cr, uid, cash_req_id, context=None):
        """
        Generates data for the Liquidity Position Tab of the Cash Request
        """
        if context is None:
            context = {}
        liq_cash_obj = self.pool.get('cash.request.liquidity.cash')
        liq_bank_obj = self.pool.get('cash.request.liquidity.bank')
        liq_cheque_obj = self.pool.get('cash.request.liquidity.cheque')
        liq_total_obj = self.pool.get('cash.request.liquidity.total')
        period_obj = self.pool.get('account.period')
        reg_obj = self.pool.get('account.bank.statement')
        cash_req = self.browse(cr, uid, cash_req_id, fields_to_fetch=['request_date', 'instance_ids'], context=context)
        # delete previous liquidity data for this cash request
        old_liq_cash_ids = liq_cash_obj.search(cr, uid, [('cash_request_id', '=', cash_req.id)], order='NO_ORDER', context=context)
        liq_cash_obj.unlink(cr, uid, old_liq_cash_ids, context=context)
        old_liq_bank_ids = liq_bank_obj.search(cr, uid, [('cash_request_id', '=', cash_req.id)], order='NO_ORDER', context=context)
        liq_bank_obj.unlink(cr, uid, old_liq_bank_ids, context=context)
        old_liq_cheque_ids = liq_cheque_obj.search(cr, uid, [('cash_request_id', '=', cash_req.id)], order='NO_ORDER', context=context)
        liq_cheque_obj.unlink(cr, uid, old_liq_cheque_ids, context=context)
        old_liq_total_ids = liq_total_obj.search(cr, uid, [('cash_request_id', '=', cash_req.id)], order='NO_ORDER', context=context)
        liq_total_obj.unlink(cr, uid, old_liq_total_ids, context=context)
        # create new cash req. liquidity data
        period_ids = period_obj.get_period_from_date(cr, uid, cash_req.request_date, context=context)
        period_id = period_ids and period_ids[0] or False
        instances = cash_req.instance_ids
        for inst in instances:
            # bank and cash registers
            for regtype in ['bank', 'cash']:
                reg_domain = [('instance_id', '=', inst.id),
                              ('period_id', '=', period_id),
                              ('journal_id.type', '=', regtype)]
                reg_ids = reg_obj.search(cr, uid, reg_domain, order='NO_ORDER', context=context)
                for reg_id in reg_ids:
                    vals = {'instance_id': inst.id,
                            'register_id': reg_id,
                            'cash_request_id': cash_req.id}
                    liq_obj = (regtype == 'bank' and liq_bank_obj) or (regtype == 'cash' and liq_cash_obj) or False
                    if liq_obj:
                        liq_id = liq_obj.create(cr, uid, vals, context=context)
                        # do a write on the Calculated bal. in book. curr. to trigger the computation of the balance in func. curr.
                        liq_obj.write(cr, uid, liq_id, {'calculated_balance_booking': 0.0}, context=context)
            # pending cheques
            liq_cheque_obj.create_liquidity_cheque(cr, uid, cash_req_id, period_id, inst.id, context=context)
        # Grand Total for all instances together
        liq_total_obj.create_liquidity_grand_total(cr, uid, cash_req_id, context=context)
        return True

    def _generate_past_transfers(self, cr, uid, cash_req_id, context=None):
        """
        Generates data for the Transfers Follow-up Tab of the Cash Request:
        JI with the accounting code selected in the main tab and within the same Fiscal Year as the Cash Request date
        """
        if context is None:
            context = {}
        aml_obj = self.pool.get('account.move.line')
        period_obj = self.pool.get('account.period')
        cash_req = self.browse(cr, uid, cash_req_id, fields_to_fetch=['transfer_account_id', 'request_date'], context=context)
        period_ids = period_obj.get_period_from_date(cr, uid, cash_req.request_date, context=context)
        period = period_ids and period_obj.browse(cr, uid, period_ids[0], fields_to_fetch=['fiscalyear_id'], context=context)
        fy = period and period.fiscalyear_id
        if cash_req.transfer_account_id and fy:
            aml_ids = aml_obj.search(cr, uid, [('account_id', '=', cash_req.transfer_account_id.id),
                                               ('date', '>=', fy.date_start), ('date', '<=', fy.date_stop)],
                                     order='date desc', context=context)
            vals = {'past_transfer_ids': [(6, 0, aml_ids)]}
            self.write(cr, uid, cash_req_id, vals, context=context)
        return True

    def _update_recap_mission(self, cr, uid, cash_req_id, context=None):
        """
        Updates the Recap Mission in the Main Tab of the Cash Request
        """
        if context is None:
            context = {}
        recap_mission_obj = self.pool.get('recap.mission')
        fields_list = ['instance_ids', 'commitment_ids', 'recap_expense_ids', 'payable_ids', 'liquidity_cash_ids',
                       'liquidity_bank_ids', 'liquidity_cheque_ids']
        cash_req = self.browse(cr, uid, cash_req_id, fields_to_fetch=fields_list, context=context)
        # delete previous recap mission lines for this cash request
        old_lines = recap_mission_obj.search(cr, uid, [('cash_request_id', '=', cash_req.id)], order='NO_ORDER', context=context)
        recap_mission_obj.unlink(cr, uid, old_lines, context=context)
        # create new lines
        instances = cash_req.instance_ids
        for inst in instances:
            commitment_amount = expense_amount = payable_amount = liquidity_amount = 0.0
            # Commitment lines
            for cl in cash_req.commitment_ids:
                commitment_amount += cl.instance_id.id == inst.id and cl.total_commitment or 0.0
            # Foreseen expenses
            for rexp in cash_req.recap_expense_ids:
                expense_amount += rexp.instance_id.id == inst.id and rexp.expense_total or 0.0
            # Payables
            for payable in cash_req.payable_ids:
                payable_amount += payable.instance_id.id == inst.id and payable.balance or 0.0
            # Liquidity amounts
            # Cash
            for cash in cash_req.liquidity_cash_ids:
                liquidity_amount += cash.instance_id.id == inst.id and cash.calculated_balance_functional or 0.0
            # Bank
            for bank in cash_req.liquidity_bank_ids:
                liquidity_amount += bank.instance_id.id == inst.id and bank.calculated_balance_functional or 0.0
            # Pending Cheques
            for cheque in cash_req.liquidity_cheque_ids:
                liquidity_amount += cheque.instance_id.id == inst.id and cheque.pending_cheque_amount_functional or 0.0
            recap_mission_vals = {'instance_id': inst.id,
                                  'commitment_amount': commitment_amount,
                                  'expense_amount': expense_amount,
                                  'payable_amount': payable_amount,
                                  'liquidity_amount': liquidity_amount,
                                  'cash_request_id': cash_req.id}
            recap_mission_obj.create(cr, uid, recap_mission_vals, context=context)

    def _update_recap_expense(self, cr, uid, cash_req_id, context=None):
        """
        Updates the Recap Planned expenses in the Planned expenses Tab of the Cash Request
        """
        if context is None:
            context = {}
        recap_expense_obj = self.pool.get('cash.request.recap.expense')
        cash_req = self.browse(cr, uid, cash_req_id, fields_to_fetch=['instance_ids'], context=context)
        # delete previous recap expense lines for this cash request
        old_lines = recap_expense_obj.search(cr, uid, [('cash_request_id', '=', cash_req.id)], order='NO_ORDER', context=context)
        recap_expense_obj.unlink(cr, uid, old_lines, context=context)
        # create new lines
        instances = cash_req.instance_ids
        for inst in instances:
            recap_expense_vals = {'instance_id': inst.id,
                                  'cash_request_id': cash_req.id}
            recap_expense_obj.create(cr, uid, recap_expense_vals, context=context)

    def generate_cash_request(self, cr, uid, ids, context=None):
        """
        - Computes all automatic fields of the Cash Request
          if the date of the Cash Request is today's date (else raises an error)
        - Changes the state of the cash req. to Open
        """
        if context is None:
            context = {}
        for cash_request_id in ids:
            cash_req = self.read(cr, uid, cash_request_id, ['request_date', 'state'], context=context)
            if cash_req['request_date'] != datetime.today().strftime('%Y-%m-%d'):
                raise osv.except_osv(_('Error'), _('The date of the Cash Request must be the date of the day.'))
            self._generate_payables(cr, uid, cash_request_id, context=context)
            self._generate_commitments(cr, uid, cash_request_id, context=context)
            self._generate_liquidity(cr, uid, cash_request_id, context=context)
            self._generate_past_transfers(cr, uid, cash_request_id, context=context)
            if cash_req['state'] != 'done':
                self.write(cr, uid, cash_request_id, {'state': 'open'}, context=context)
        return True

    def set_to_done(self, cr, uid, ids, context=None):
        """
        Changes the state of the cash req. to Done (which makes it readonly)
        """
        if context is None:
            context = {}
        for cash_request_id in ids:
            self.write(cr, uid, cash_request_id, {'state': 'done'}, context=context)
        return True

    def _get_total_cash_request(self, cr, uid, cash_req_id, context=None):
        """
        Sums all the amounts of the Cash Request
        """
        if context is None:
            context = {}
        total = 0.0
        cash_req = self.browse(cr, uid, cash_req_id, fields_to_fetch=['recap_mission_ids'], context=context)
        for rec in cash_req.recap_mission_ids:
            total += rec.total
        return total

    def _compute_total_to_transfer(self, cr, uid, cash_req_id, context=None):
        """
        If all the checks are ok, computes the total to transfer (see formula below) and does a split per currency:
        Formula = (Total cash request - Transfer to come + security envelop) + %buffer
        """
        if context is None:
            context = {}
        transfer_line_obj = self.pool.get('total.transfer.line')
        cur_obj = self.pool.get('res.currency')
        fields_list = ['buffer', 'transfer_to_come', 'security_envelope', 'request_date', 'consolidation_currency_id',
                       'transfer_currency_ids']
        cash_req = self.browse(cr, uid, cash_req_id, fields_to_fetch=fields_list, context=context)
        self._check_currencies(cr, uid, cash_req.id, context=context)
        # compute the total
        total = self._get_total_cash_request(cr, uid, cash_req.id, context=context) - cash_req.transfer_to_come + cash_req.security_envelope
        total += (cash_req.buffer * total / 100)
        cash_req_vals = {'total_to_transfer': total}
        # split per currency
        # delete previous split lines for this cash request
        old_line_ids = transfer_line_obj.search(cr, uid, [('cash_request_id', '=', cash_req.id)], order='NO_ORDER', context=context)
        transfer_line_obj.unlink(cr, uid, old_line_ids, context=context)
        # create new lines
        currencies = cash_req.transfer_currency_ids
        for curr in currencies:
            percentage = curr.percentage or 100  # if no percentage is given consider 100%
            total_curr = total * percentage / 100  # total in fctal currency
            # convert the amount in booking curr.
            context.update({'date': cash_req.request_date})
            total_curr_booking = cur_obj.compute(cr, uid, cash_req.consolidation_currency_id.id, curr.currency_id.id,
                                                 total_curr or 0.0, round=True, context=context)
            transfer_line_vals = {'currency_id': curr.currency_id.id,
                                  'amount': total_curr_booking,
                                  'cash_request_id': cash_req.id}
            transfer_line_obj.create(cr, uid, transfer_line_vals, context=context)
        self.write(cr, uid, cash_req.id, cash_req_vals, context=context)

    def compute_recap_and_total(self, cr, uid, ids, context=None):
        """
        Triggers the computation of:
        Recap Mission Lines + Recap Planned expenses + Total to transfer (with a split per currencies)
        """
        for cash_req_id in ids:
            self._update_recap_expense(cr, uid, cash_req_id, context=None)
            self._update_recap_mission(cr, uid, cash_req_id, context=None)
            self._compute_total_to_transfer(cr, uid, cash_req_id, context=context)
        return True

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Handles the creation/duplication/edition rights according to the instance level:
        - in coordo: all allowed
        - in HQ: all blocked
        - in project: only edition allowed
        Note: the deletion depends on the state and is not handled here.
        """
        if context is None:
            context = {}
        res = super(cash_request, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context,
                                                        toolbar=toolbar, submenu=submenu)
        company = self._get_company(cr, uid, context=context)
        level = company.instance_id and company.instance_id.level or ''
        if view_type in ['form', 'tree']:
            if level == 'coordo':
                res['arch'] = res['arch']\
                    .replace('hide_new_button="PROP_INSTANCE_HIDE_BUTTON"', '')\
                    .replace('hide_duplicate_button="PROP_INSTANCE_HIDE_BUTTON"', '')\
                    .replace('hide_edit_button="PROP_INSTANCE_HIDE_BUTTON"', '')
            elif level == 'project':
                res['arch'] = res['arch'] \
                    .replace('hide_new_button="PROP_INSTANCE_HIDE_BUTTON"', 'hide_new_button="1"') \
                    .replace('hide_duplicate_button="PROP_INSTANCE_HIDE_BUTTON"', 'hide_duplicate_button="1"') \
                    .replace('hide_edit_button="PROP_INSTANCE_HIDE_BUTTON"', '')
            else:
                res['arch'] = res['arch'] \
                    .replace('hide_new_button="PROP_INSTANCE_HIDE_BUTTON"', 'hide_new_button="1"') \
                    .replace('hide_duplicate_button="PROP_INSTANCE_HIDE_BUTTON"', 'hide_duplicate_button="1"') \
                    .replace('hide_edit_button="PROP_INSTANCE_HIDE_BUTTON"', 'hide_edit_button="1"')
        return res

    def unlink(self, cr, uid, ids, context=None):
        """
        Deletes Cash Request if it is in Draft state
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for cash_req in self.browse(cr, uid, ids, fields_to_fetch=['state']):
            if cash_req.state != 'draft':
                raise osv.except_osv(_('Error'), _('Cash Requests can only be deleted in Draft state.'))
        return super(cash_request, self).unlink(cr, uid, ids, context=context)

    def display_details(self, cr, uid, ids, regtype='cash', context=None):
        """
        Opens a wizard with the details of Liquidity Positions to enable filtering
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if regtype in ['cash', 'bank', 'cheque']:
            if regtype == 'cash':
                liq_obj = self.pool.get('cash.request.liquidity.cash')
                search_view = 'view_cash_request_liquidity_cash_search'
                tree_view = 'view_cash_request_liquidity_cash_tree'
                res_model = 'cash.request.liquidity.cash'
                view_name = _('Liquidity Position - Cash')
            elif regtype == 'bank':
                liq_obj = self.pool.get('cash.request.liquidity.bank')
                search_view = 'view_cash_request_liquidity_bank_search'
                tree_view = 'view_cash_request_liquidity_bank_tree'
                res_model = 'cash.request.liquidity.bank'
                view_name = _('Liquidity Position - Bank')
            else:
                liq_obj = self.pool.get('cash.request.liquidity.cheque')
                search_view = 'view_cash_request_liquidity_cheque_search'
                tree_view = 'view_cash_request_liquidity_cheque_tree'
                res_model = 'cash.request.liquidity.cheque'
                view_name = _('Liquidity Position - Pending Cheques')
            model_data_obj = self.pool.get('ir.model.data')
            fields_list = ['liquidity_cash_ids', 'liquidity_bank_ids', 'liquidity_cheque_ids']
            cash_req = self.browse(cr, uid, ids[0], fields_to_fetch=fields_list, context=context)
            if regtype == 'cash':
                liq_ids = [l.id for l in cash_req.liquidity_cash_ids]
            elif regtype == 'bank':
                liq_ids = [l.id for l in cash_req.liquidity_bank_ids]
            else:
                liq_ids = [l.id for l in cash_req.liquidity_cheque_ids]
            domain = [('id', 'in', liq_ids)]
            module_name = 'finance'
            tree_view_id = model_data_obj.get_object_reference(cr, uid, module_name, tree_view)
            tree_view_id = tree_view_id and tree_view_id[1] or False
            search_view_id = model_data_obj.get_object_reference(cr, uid, module_name, search_view)
            search_view_id = search_view_id and search_view_id[1] or False
            return {
                'name': view_name,
                'type': 'ir.actions.act_window',
                'res_model': res_model,
                'target': 'new',
                'view_type': 'form',
                'view_mode': 'tree',
                'view_id': [tree_view_id],
                'search_view_id': [search_view_id],
                'context': context,
                'domain': domain,
            }
        return True

    def display_details_cash(self, cr, uid, ids, context=None):
        return self.display_details(cr, uid, ids, regtype='cash', context=context)

    def display_details_bank(self, cr, uid, ids, context=None):
        return self.display_details(cr, uid, ids, regtype='bank', context=context)

    def display_details_cheque(self, cr, uid, ids, context=None):
        return self.display_details(cr, uid, ids, regtype='cheque', context=context)


cash_request()


class transfer_currency(osv.osv):
    _name = 'transfer.currency'
    _rec_name = 'cash_request_id'
    _description = 'Currency of Transfers for Cash Request'

    _columns = {
        'currency_id': fields.many2one('res.currency', 'Currency', required=True),
        'percentage': fields.float(digits=(16, 2), string='%'),
        'cash_request_id': fields.many2one('cash.request', 'Cash Request', invisible=True, ondelete='cascade'),
    }

    _order = 'currency_id'

    def _check_percentage(self, cr, uid, ids):
        """
        Checks that the percentage value isn't negative nor > 100
        """
        for cash_req in self.browse(cr, uid, ids, fields_to_fetch=['percentage']):
            if cash_req.percentage < 0 or cash_req.percentage - 100 > 10**-3:
                return False
        return True

    _constraints = [
        (_check_percentage, _("The percentage of the currency is incorrect."), ['percentage']),
    ]

    _sql_constraints = [
        ('cash_request_currency_uniq', 'UNIQUE(cash_request_id, currency_id)',
         _("You have already selected this currency.")),
    ]


transfer_currency()


class cash_request_commitment(osv.osv):
    _name = 'cash.request.commitment'
    _rec_name = 'cash_request_id'
    _description = 'Commitment Line for Cash Request'

    def _total_commitment_compute(self, cr, uid, ids, name, args, context=None):
        """
        Computes the commitment amount regarding the Prop. Instance and the period of the cash_request_commitment:
        = total of the Local Engagement entries (exclude International Eng.), per instance,
        with posting date in the month selected or before.
        """
        if context is None:
            context = {}
        result = {}
        aal_obj = self.pool.get('account.analytic.line')
        for commitment in self.browse(cr, uid, ids, fields_to_fetch=['instance_id', 'period_id'], context=context):
            instance = commitment.instance_id or False
            period = commitment.period_id or False
            if instance and period:
                domain = [('journal_id.type', '=', 'engagement'),
                          ('journal_id.code', '!=', 'ENGI'),
                          ('instance_id', '=', instance.id),
                          ('date', '<=', period.date_stop)]
                commitment_lines = aal_obj.search(cr, uid, domain, context=context, order='NO_ORDER')
                commitment_sum = 0.0
                for l in aal_obj.read(cr, uid, commitment_lines, ['amount'], context=context):
                    commitment_sum += l['amount']
                result[commitment.id] = abs(commitment_sum)
        return result

    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Instance Code', required=True),
        'instance_level': fields.related('instance_id', 'level', string='Instance level', readonly=True, store=True,
                                         type='selection',
                                         selection=[('section', 'Section'), ('coordo', 'Coordo'), ('project', 'Project')]),
        'period_id': fields.many2one('account.period', 'Period', required=True),
        'cash_request_id': fields.many2one('cash.request', 'Cash Request', required=True, ondelete='cascade'),
        'total_commitment': fields.function(_total_commitment_compute, method=True, string='Total', type='float',
                                            digits_compute=dp.get_precision('Account'), store=True),
    }

    _order = 'instance_level, instance_id'


cash_request_commitment()


class total_transfer_line(osv.osv):
    _name = 'total.transfer.line'
    _rec_name = 'cash_request_id'
    _description = 'Line of Total to transfer for Cash Request'

    _columns = {
        'currency_id': fields.many2one('res.currency', 'Currency', required=True),
        'amount': fields.float('Amount', digits_compute=dp.get_precision('Account')),
        'cash_request_id': fields.many2one('cash.request', 'Cash Request', required=True, ondelete='cascade'),
    }

    _order = 'currency_id'


total_transfer_line()


class recap_mission(osv.osv):
    _name = 'recap.mission'
    _rec_name = 'cash_request_id'
    _description = 'Recap Mission Line for Cash Request'

    def _total_compute(self, cr, uid, ids, name, args, context=None):
        """
        Computes the Total Cash requested
        Formula = Cash available - Payable Invoices - Commitments - Foreseen expenses
        """
        if context is None:
            context = {}
        result = {}
        fields_list = ['liquidity_amount', 'payable_amount', 'commitment_amount', 'expense_amount']
        for recap in self.browse(cr, uid, ids, fields_to_fetch=fields_list, context=context):
            total = recap.liquidity_amount - recap.payable_amount - recap.commitment_amount - recap.expense_amount
            result[recap.id] = -1 * total  # ex: 1000 in Bank - 1500 commitments = -500  ==> display 500 to transfer
        return result

    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Instance code / Place of payment', required=True),
        'instance_level': fields.related('instance_id', 'level', string='Instance level', readonly=True, store=True,
                                         type='selection',
                                         selection=[('section', 'Section'), ('coordo', 'Coordo'), ('project', 'Project')]),
        'cash_request_id': fields.many2one('cash.request', 'Cash Request', required=True, ondelete='cascade'),
        'commitment_amount': fields.float('Commitment', digits_compute=dp.get_precision('Account')),
        'liquidity_amount': fields.float('Cash available in mission', digits_compute=dp.get_precision('Account')),
        'payable_amount': fields.float('Payable Invoices', digits_compute=dp.get_precision('Account')),
        'expense_amount': fields.float('Foreseen expenses', digits_compute=dp.get_precision('Account')),
        'total': fields.function(_total_compute, method=True, string='Total Cash requested', type='float',
                                 digits_compute=dp.get_precision('Account'), store=True),
    }

    _order = 'instance_level, instance_id'


recap_mission()


class cash_request_expense(osv.osv):
    _name = 'cash.request.expense'
    _rec_name = 'cash_request_id'
    _description = 'Planned Expenses for Cash Request'

    def _total_booking_compute(self, cr, uid, ids, name, args, context=None):
        """
        Computes the booking amount (qty x unit price)
        """
        if context is None:
            context = {}
        result = {}
        for expense in self.browse(cr, uid, ids, fields_to_fetch=['quantity', 'unit_price'], context=context):
            result[expense.id] = expense.quantity * expense.unit_price
        return result

    def _total_functional_compute(self, cr, uid, ids, name, args, context=None):
        """
        Computes the functional amount (booking / rate at the date of the Cash Request)
        """
        if context is None:
            context = {}
        result = {}
        cur_obj = self.pool.get('res.currency')
        fields_list = ['cash_request_id', 'currency_id', 'total_booking']
        for expense in self.browse(cr, uid, ids, fields_to_fetch=fields_list, context=context):
            cash_req = expense.cash_request_id
            if cash_req:
                context.update({'date': cash_req.request_date})
                total_fctal = cur_obj.compute(cr, uid, expense.currency_id.id, cash_req.consolidation_currency_id.id,
                                              expense.total_booking or 0.0, round=True, context=context)
                result[expense.id] = total_fctal
        return result

    _columns = {
        'cash_request_id': fields.many2one('cash.request', 'Cash Request', invisible=True, ondelete='cascade'),
        'prop_instance_id': fields.many2one('msf.instance', 'Prop. Instance', required=True, readonly=True,
                                            domain=[('level', 'in', ['coordo', 'project'])]),
        'prop_instance_level': fields.related('instance_id', 'level', string='Instance level', readonly=True,
                                              store=True, type='selection',
                                              selection=[('section', 'Section'),
                                                         ('coordo', 'Coordo'),
                                                         ('project', 'Project')]),
        'consumer_instance_id': fields.many2one('msf.instance', 'Instance Consumer', required=True,
                                                domain=[('level', 'in', ['coordo', 'project'])]),
        'is_local_expense': fields.boolean(string='Local Expense'),
        'account_id': fields.many2one('account.account', 'Account', required=True,
                                      domain=[('user_type_code', 'in', ['expense', 'income']),
                                               '|',  # exclude extra-accounting expense accounts
                                               ('user_type_code', '!=', 'expense'),
                                               ('user_type.report_type', '!=', 'none')]),
        'description': fields.char(size=128, string='Description', required=True),
        'is_budgeted': fields.boolean(string='Budgeted'),
        'quantity': fields.float('Quantity', required=True),
        'unit_price': fields.float('Unit Price', required=True, digits_compute=dp.get_precision('Account Computation')),
        'currency_id': fields.many2one('res.currency', 'Currency', required=True),
        'total_booking': fields.function(_total_booking_compute, method=True, string='Total Booking Cur.', type='float',
                                         digits_compute=dp.get_precision('Account'), readonly=True),
        'total_functional': fields.function(_total_functional_compute, method=True, string='Total Functional Cur.',
                                            type='float', digits_compute=dp.get_precision('Account'), readonly=True),
    }

    _defaults = {
        'prop_instance_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.instance_id.id,
    }

    _order = 'prop_instance_level, prop_instance_id'


cash_request_expense()


class cash_request_recap_expense(osv.osv):
    _name = 'cash.request.recap.expense'
    _rec_name = 'cash_request_id'
    _description = 'Recap Planned Expenses for Cash Request'

    def _expense_total_compute(self, cr, uid, ids, name, args, context=None):
        """
        Sums the "Planned expenses entries" of the Cash Request grouped by instance consumer
        """
        if context is None:
            context = {}
        result = {}
        for expense in self.browse(cr, uid, ids, fields_to_fetch=['cash_request_id', 'instance_id'], context=context):
            total = 0.0
            cash_req = expense.cash_request_id
            planned_expenses = cash_req and cash_req.planned_expense_ids
            for planned_exp in planned_expenses:
                total += expense.instance_id.id == planned_exp.consumer_instance_id.id and planned_exp.total_functional or 0.0
            result[expense.id] = total
        return result

    def _budgeted_expense_compute(self, cr, uid, ids, month_index, context=None):
        """
        Sums all the budgets amounts for all the CCs targeted instance by instance:
        - use only normal CC to avoid amount duplication
        - if there are several budget versions, consider only the last one
        - the month used is the one of the Cash Request + month_index
        """
        if context is None:
            context = {}
        result = {}
        budget_obj = self.pool.get('msf.budget')
        target_cc_obj = self.pool.get('account.target.costcenter')
        period_obj = self.pool.get('account.period')
        for expense in self.browse(cr, uid, ids, fields_to_fetch=['cash_request_id', 'instance_id'], context=context):
            total = 0.0
            # get all the normal target CCs for the instance
            target_cc_ids = target_cc_obj.search(cr, uid,
                                                 [('instance_id', '=', expense.instance_id.id),
                                                  ('is_target', '=', True),
                                                  ('cost_center_id.type', '=', 'normal')],
                                                 order='NO_ORDER', context=context)
            target_ccs = target_cc_obj.browse(cr, uid, target_cc_ids, fields_to_fetch=['cost_center_id'], context=context)
            cc_ids = [cc.cost_center_id.id for cc in target_ccs]
            # get the month FY
            cash_req_month_id = expense.cash_request_id.month_period_id.id
            month_id = period_obj.get_next_period_id_at_index(cr, uid, cash_req_month_id, month_index, context=context)
            if month_id:
                month = period_obj.browse(cr, uid, month_id, fields_to_fetch=['fiscalyear_id', 'number'], context=context)
                fy = month.fiscalyear_id
                # get all the budgets for the FY and the CCs found
                budget_ids = budget_obj.search(cr, uid,
                                               [('fiscalyear_id', '=', fy.id), ('cost_center_id', 'in', cc_ids)],
                                               order='NO_ORDER', context=context)
                budget_set = set()
                # keep only the budgets with the highest version
                for budget in budget_obj.read(cr, uid, budget_ids, ['code', 'name', 'decision_moment_id'], context=context):
                    if budget['id'] not in budget_set:
                        sql = '''
                        SELECT id FROM msf_budget 
                        WHERE code = %s AND name = %s AND decision_moment_id = %s
                        AND id IN %s
                        ORDER BY version DESC LIMIT 1;
                        '''
                        cr.execute(sql, (budget['code'], budget['name'], budget['decision_moment_id'][0], tuple(budget_ids),))
                        budg_id = cr.fetchone()[0]
                        budget_set.add(budg_id)
                # add the amounts of each budget line linked to the budgets found AND for the month selected
                for b in budget_obj.browse(cr, uid, list(budget_set), fields_to_fetch=['budget_line_ids'], context=context):
                    for b_l in b.budget_line_ids:
                        month_field = 'month%s' % month.number  # ex: month11
                        total += b_l.line_type == 'normal' and hasattr(b_l, month_field) and getattr(b_l, month_field) or 0.0
                result[expense.id] = total
        return result

    def _budgeted_expense_m_compute(self, cr, uid, ids, name, args, context=None):
        month_index = 0
        return self._budgeted_expense_compute(cr, uid, ids, month_index, context=context)

    def _budgeted_expense_m1_compute(self, cr, uid, ids, name, args, context=None):
        month_index = 1
        return self._budgeted_expense_compute(cr, uid, ids, month_index, context=context)

    def _budgeted_expense_m2_compute(self, cr, uid, ids, name, args, context=None):
        month_index = 2
        return self._budgeted_expense_compute(cr, uid, ids, month_index, context=context)

    def _budgeted_expense_m3_compute(self, cr, uid, ids, name, args, context=None):
        month_index = 3
        return self._budgeted_expense_compute(cr, uid, ids, month_index, context=context)

    _columns = {
        'cash_request_id': fields.many2one('cash.request', 'Cash Request', invisible=True, ondelete='cascade'),
        'instance_id': fields.many2one('msf.instance', 'Prop. Instance', required=True, readonly=True,
                                       domain=[('level', 'in', ['coordo', 'project'])]),
        'instance_level': fields.related('instance_id', 'level', string='Instance level', readonly=True, store=True,
                                         type='selection',
                                         selection=[('section', 'Section'), ('coordo', 'Coordo'), ('project', 'Project')]),
        'expense_total': fields.function(_expense_total_compute, method=True, string='Planned Expenses for the period M',
                                         type='float', digits_compute=dp.get_precision('Account'), readonly=True, store=True),
        'budget_expense_m': fields.function(_budgeted_expense_m_compute, method=True,
                                            string='Budgeted expenses for the period M', type='float',
                                            digits_compute=dp.get_precision('Account'), readonly=True, store=True),
        'budget_expense_m1': fields.function(_budgeted_expense_m1_compute, method=True,
                                             string='Budgeted expenses for the period M+1', type='float',
                                             digits_compute=dp.get_precision('Account'), readonly=True, store=True),
        'budget_expense_m2': fields.function(_budgeted_expense_m2_compute, method=True,
                                             string='Budgeted expenses for the period M+2', type='float',
                                             digits_compute=dp.get_precision('Account'), readonly=True, store=True),
        'budget_expense_m3': fields.function(_budgeted_expense_m3_compute, method=True,
                                             string='Budgeted expenses for the period M+3', type='float',
                                             digits_compute=dp.get_precision('Account'), readonly=True, store=True),
    }

    _order = 'instance_level, instance_id'


cash_request_recap_expense()


class cash_request_payable(osv.osv):
    _name = 'cash.request.payable'
    _rec_name = 'cash_request_id'
    _description = 'Payables for Cash Request'

    def _aml_compute(self, cr, uid, ids, name, args, context=None):
        """
        Gets the ids of the JIs matching all the following criteria:
        - booked on accounts with Internal Type Payables (exclude Donations)
        - posted
        - not fully reconciled
        - booked in the period of the cash request or before
        - for a given Prop. Instance (=> instance_id of the cash_request_payable)
        """
        if context is None:
            context = {}
        result = {}
        aml_obj = self.pool.get('account.move.line')
        acc_obj = self.pool.get('account.account')
        cash_req_obj = self.pool.get('cash.request')
        for cr_payable in self.browse(cr, uid, ids, fields_to_fetch=['cash_request_id', 'instance_id'], context=context):
            acc_domain = [('type', '=', 'payable'), ('type_for_register', '!=', 'donation')]
            account_ids = acc_obj.search(cr, uid, acc_domain, order='NO_ORDER', context=context)
            cash_req_id = cr_payable.cash_request_id.id
            cash_req = cash_req_obj.browse(cr, uid, cash_req_id, fields_to_fetch=['month_period_id'], context=context)
            period = cash_req.month_period_id
            aml_domain = [('account_id', 'in', account_ids),
                          ('move_id.state', '=', 'posted'),
                          ('reconcile_id', '=', False),
                          ('date', '<=', period.date_stop),
                          ('instance_id', '=', cr_payable.instance_id.id)]
            result[cr_payable.id] = aml_obj.search(cr, uid, aml_domain, order='NO_ORDER', context=context)
        return result

    def _debit_compute(self, cr, uid, ids, name, args, context=None):
        """
        Computes the total functional debit amount based on the entries from _aml_compute
        """
        if context is None:
            context = {}
        result = {}
        aml_obj = self.pool.get('account.move.line')
        for cr_payable in self.browse(cr, uid, ids, fields_to_fetch=['account_move_line_ids'], context=context):
            aml_ids = [aml.id for aml in cr_payable.account_move_line_ids]
            amls = aml_obj.browse(cr, uid, aml_ids, fields_to_fetch=['debit'], context=context)
            result[cr_payable.id] = sum([aml.debit or 0.0 for aml in amls])
        return result

    def _credit_compute(self, cr, uid, ids, name, args, context=None):
        """
        Computes the total functional credit amount based on the entries from _aml_compute
        """
        if context is None:
            context = {}
        result = {}
        aml_obj = self.pool.get('account.move.line')
        for cr_payable in self.browse(cr, uid, ids, fields_to_fetch=['account_move_line_ids'], context=context):
            aml_ids = [aml.id for aml in cr_payable.account_move_line_ids]
            amls = aml_obj.browse(cr, uid, aml_ids, fields_to_fetch=['credit'], context=context)
            result[cr_payable.id] = sum([aml.credit or 0.0 for aml in amls])
        return result

    def _balance_compute(self, cr, uid, ids, name, args, context=None):
        """
        Computes the total functional balance: credit - debit. Note that this will make the balance positive
        for the most current use cases (on the contrary to the Trial Balance for instance)
        """
        if context is None:
            context = {}
        result = {}
        for cr_payable_id in ids:
            cr_payable = self.browse(cr, uid, cr_payable_id, fields_to_fetch=['debit', 'credit'], context=context)
            debit = cr_payable.debit or 0.0
            credit = cr_payable.credit or 0.0
            result[cr_payable_id] = credit - debit
        return result

    _columns = {
        'cash_request_id': fields.many2one('cash.request', 'Cash Request', invisible=True, ondelete='cascade'),
        'instance_id': fields.many2one('msf.instance', 'Instance', required=True,
                                       domain=[('level', 'in', ['coordo', 'project'])]),
        'instance_level': fields.related('instance_id', 'level', string='Instance level', readonly=True, store=True,
                                         type='selection',
                                         selection=[('section', 'Section'), ('coordo', 'Coordo'), ('project', 'Project')]),
        'account_move_line_ids': fields.function(_aml_compute, method=True, relation='account.move.line',
                                                 type='many2many', string='Account Move Lines'),
        'debit': fields.function(_debit_compute, method=True, string='Debit', type='float',
                                 digits_compute=dp.get_precision('Account'), readonly=True, store=True),
        'credit': fields.function(_credit_compute, method=True, string='Credit', type='float',
                                  digits_compute=dp.get_precision('Account'), readonly=True, store=True),
        'balance': fields.function(_balance_compute, method=True, string='Balance in functional currency', type='float',
                                   digits_compute=dp.get_precision('Account'), readonly=True),
    }

    _order = 'instance_level, instance_id'


cash_request_payable()


class cash_request_liquidity(osv.osv):
    _name = 'cash.request.liquidity'
    _rec_name = 'cash_request_id'
    _description = 'Liquidity Position for Cash Request'

    def _period_id_compute(self, cr, uid, ids, name, args, context=None):
        """
        Gets the period corresponding to the date of the Cash Request linked to the cash_request_liquidity
        """
        if context is None:
            context = {}
        result = {}
        period_obj = self.pool.get('account.period')
        for liq_id in ids:
            cash_req = self.browse(cr, uid, liq_id, fields_to_fetch=['cash_request_id'], context=context).cash_request_id
            period_ids = period_obj.get_period_from_date(cr, uid, cash_req.request_date, context=context)
            result[liq_id] = period_ids and period_ids[0] or False
        return result

    def _get_journal_type(self, cr, uid, context=None):
        """
        Returns a list of tuples containing the different Journal Types
        """
        return self.pool.get('account.journal').get_journal_type(cr, uid, context=context)

    def _balance_functional_compute(self, cr, uid, ids, name, args, context=None):
        """
        Gets the functional balance by using the conversion method from the Liquidity Position report
        """
        if context is None:
            context = {}
        result = {}
        fields_list = ['register_id', 'calculated_balance_booking', 'period_id']
        for liq in self.browse(cr, uid, ids, fields_to_fetch=fields_list, context=context):
            liquidity_pos_report = register_accounting.report.report_liquidity_position \
                .report_liquidity_position3(cr, uid, 'fakereport', context=context)
            balance_amount = 0.0
            if liquidity_pos_report and liq.register_id and liq.calculated_balance_booking and liq.period_id:
                # note: report_period param must be a period browse period
                balance_amount = liquidity_pos_report.getConvert(liq.register_id.currency.id,
                                                                 liq.calculated_balance_booking,
                                                                 report_period=liq.period_id) or 0.0
            result[liq.id] = balance_amount
        return result

    _columns = {
        'cash_request_id': fields.many2one('cash.request', 'Cash Request', invisible=True, ondelete='cascade'),
        'instance_id': fields.many2one('msf.instance', 'Proprietary instance', required=True,
                                       domain=[('level', 'in', ['coordo', 'project'])]),
        'instance_level': fields.related('instance_id', 'level', string='Instance level', readonly=True, store=True,
                                         type='selection',
                                         selection=[('section', 'Section'), ('coordo', 'Coordo'), ('project', 'Project')]),
        'register_id': fields.many2one('account.bank.statement', 'Register', required=True),
        'type': fields.related('register_id', 'journal_id', 'type', string='Register Type', type='selection',
                               selection=_get_journal_type, readonly=True, store=True),
        'journal_code': fields.related('register_id', 'journal_id', 'code', string='Journal Code', type='char',
                                       readonly=True),
        'journal_name': fields.related('register_id', 'journal_id', 'name', string='Journal Name', type='char',
                                       readonly=True),
        'status': fields.related('register_id', 'state', string='Status', readonly=True, type='selection',
                                 selection=[('draft', 'Draft'), ('open', 'Open'),
                                            ('partial_close', 'Partial Close'), ('confirm', 'Closed')]),
        'period_id': fields.function(_period_id_compute, method=True, relation='account.period',
                                     type='many2one', string='Period', readonly=True),
        'opening_balance': fields.related('register_id', 'balance_start', string='Opening Balance in register currency',
                                          type='float', readonly=True, store=True),
        'calculated_balance_booking': fields.related('register_id', 'msf_calculated_balance',
                                                     string='Calculated Balance in register currency', type='float',
                                                     readonly=True, store=True),
        'booking_currency_id': fields.related('register_id', 'currency', string='Register Currency', type='many2one',
                                              relation='res.currency', readonly=True, store=True),
        'functional_currency_id': fields.related('cash_request_id', 'consolidation_currency_id',
                                                 string='Functional Currency', type='many2one', relation='res.currency',
                                                 store=False, readonly=True),
    }

    _order = 'type, instance_level, instance_id'


cash_request_liquidity()


class cash_request_liquidity_cash(osv.osv):
    """
    Class used in particular for display purpose in the Cash Request (not possible to display the same fields
    three times for cash / bank / cheque in the same form)...
    """
    _name = 'cash.request.liquidity.cash'
    _inherit = 'cash.request.liquidity'

    def _cashbox_balance_functional_compute(self, cr, uid, ids, name, args, context=None):
        """
        Gets the cash balance in func. currency by using the conversion method from the Liquidity Position report
        """
        if context is None:
            context = {}
        result = {}
        fields_list = ['register_id', 'cashbox_balance_booking', 'period_id']
        for liq in self.browse(cr, uid, ids, fields_to_fetch=fields_list, context=context):
            liquidity_pos_report = register_accounting.report.report_liquidity_position \
                .report_liquidity_position3(cr, uid, 'fakereport', context=context)
            balance_amount = 0.0
            if liquidity_pos_report and liq.register_id and liq.cashbox_balance_booking and liq.period_id:
                # note: report_period param must be a period browse period
                balance_amount = liquidity_pos_report.getConvert(liq.register_id.currency.id,
                                                                 liq.cashbox_balance_booking,
                                                                 report_period=liq.period_id) or 0.0
            result[liq.id] = balance_amount
        return result

    def _balance_functional_compute_from_cash(self, cr, uid, ids, name, args, context=None):
        """
        Calls the method from cash.request.liquidity
        (if called directly the fields used would be seen as not existing on the browse records handled)
        """
        return self._balance_functional_compute(cr, uid, ids, name, args, context=None)

    _columns = {
        'cashbox_balance_booking': fields.related('register_id', 'balance_end_cash',
                                                  string='Cash Box Balance in register currency', type='float',
                                                  readonly=True, store=True),
        'cashbox_balance_functional': fields.function(_cashbox_balance_functional_compute, method=True,
                                                      string='Cash Box Balance in functional currency',
                                                      type='float', digits_compute=dp.get_precision('Account'),
                                                      readonly=True, store=True),
        'calculated_balance_functional': fields.function(_balance_functional_compute_from_cash, method=True,
                                                         string='Calculated Balance in functional currency',
                                                         type='float', digits_compute=dp.get_precision('Account'),
                                                         readonly=True,
                                                         store={
                                                             'cash.request.liquidity.cash': (lambda self, cr, uid, ids, c=None: ids, ['calculated_balance_booking'], 10),
                                                         }),
    }


cash_request_liquidity_cash()


class cash_request_liquidity_bank(osv.osv):
    """
    Class used in particular for display purpose in the Cash Request (not possible to display the same fields
    three times for cash / bank / cheque in the same form)...
    """
    _name = 'cash.request.liquidity.bank'
    _inherit = 'cash.request.liquidity'

    def _bank_statement_balance_functional_compute(self, cr, uid, ids, name, args, context=None):
        """
        Gets the bank statement balance in func. currency by using the conversion method from the Liquidity Position report
        """
        if context is None:
            context = {}
        result = {}
        fields_list = ['register_id', 'bank_statement_balance_booking', 'period_id']
        for liq in self.browse(cr, uid, ids, fields_to_fetch=fields_list, context=context):
            liquidity_pos_report = register_accounting.report.report_liquidity_position \
                .report_liquidity_position3(cr, uid, 'fakereport', context=context)
            balance_amount = 0.0
            if liquidity_pos_report and liq.register_id and liq.bank_statement_balance_booking and liq.period_id:
                balance_amount = liquidity_pos_report.getConvert(liq.register_id.currency.id,
                                                                 liq.bank_statement_balance_booking,
                                                                 report_period=liq.period_id) or 0.0
            result[liq.id] = balance_amount
        return result

    def _balance_functional_compute_from_bank(self, cr, uid, ids, name, args, context=None):
        """
        Calls the method from cash.request.liquidity
        (if called directly the fields used would be seen as not existing on the browse records handled)
        """
        return self._balance_functional_compute(cr, uid, ids, name, args, context=None)

    _columns = {
        'bank_statement_balance_booking': fields.related('register_id', 'balance_end_real',
                                                         string='Bank Statement Balance in register currency', type='float',
                                                         readonly=True, store=True),
        'bank_statement_balance_functional': fields.function(_bank_statement_balance_functional_compute, method=True,
                                                             string='Bank Statement Balance in functional currency',
                                                             type='float', digits_compute=dp.get_precision('Account'),
                                                             readonly=True, store=True),
        'calculated_balance_functional': fields.function(_balance_functional_compute_from_bank, method=True,
                                                         string='Calculated Balance in functional currency',
                                                         type='float', digits_compute=dp.get_precision('Account'),
                                                         readonly=True,
                                                         store={
                                                             'cash.request.liquidity.bank': (lambda self, cr, uid, ids, c=None: ids, ['calculated_balance_booking'], 10),
                                                         }),
    }


cash_request_liquidity_bank()


class cash_request_liquidity_cheque(osv.osv):
    """
    Class used in particular for display purpose in the Cash Request (not possible to display the same fields
    three times for cash / bank / cheque in the same form)...
    """
    _name = 'cash.request.liquidity.cheque'
    _inherit = 'cash.request.liquidity'

    def create_liquidity_cheque(self, cr, uid, cash_request_id, period_id, instance_id, context=None):
        """"
        This method creates the cash_request_liquidity_cheques corresponding to the criteria in parameter.
        It is based on the method get_pending_cheques_ids() from the registers to get the data to take into account.
        """
        if context is None:
            context = {}
        period_obj = self.pool.get('account.period')
        journal_obj = self.pool.get('account.journal')
        reg_obj = self.pool.get('account.bank.statement')
        aml_obj = self.pool.get('account.move.line')
        period = period_obj.browse(cr, uid, period_id, fields_to_fetch=['date_start', 'date_stop'], context=context)
        period_ids = period_obj.search(cr, uid, [('date_start', '<=', period.date_start)], order='NO_ORDER', context=context)
        cheque_j_domain = [('type', '=', 'cheque'), ('instance_id', '=', instance_id)]
        cheque_j_ids = journal_obj.search(cr, uid, cheque_j_domain, order='NO_ORDER', context=context)
        journal_fields_list = ['default_debit_account_id', 'default_credit_account_id']
        for cheque_j in journal_obj.browse(cr, uid, cheque_j_ids, fields_to_fetch=journal_fields_list, context=context):
            reg_domain = [('journal_id', '=', cheque_j.id), ('period_id', 'in', period_ids)]
            reg_ids = reg_obj.search(cr, uid, reg_domain, order='NO_ORDER', context=context)
            if reg_ids:
                account_ids = [cheque_j.default_debit_account_id.id, cheque_j.default_credit_account_id.id]
                aml_ids = reg_obj.get_pending_cheque_ids(cr, uid, reg_ids, account_ids, period.date_stop)
                aml_fields_list = ['debit_currency', 'credit_currency', 'debit', 'credit']
                amls = aml_obj.browse(cr, uid, aml_ids, fields_to_fetch=aml_fields_list, context=context)
                amount_book_currency = amount_func_currency = 0.0
                for aml in amls:
                    amount_book_currency += aml.debit_currency - aml.credit_currency or 0.0
                    amount_func_currency += aml.debit - aml.credit or 0.0
                # get the most recent register for this journal (used in particular to determine the reg. status)
                most_recent_date = most_recent_reg = False
                for reg in reg_obj.browse(cr, uid, reg_ids, fields_to_fetch=['period_id'], context=context):
                    if not most_recent_reg:
                        most_recent_date = reg.period_id.date_stop
                        most_recent_reg = reg
                        continue
                    if reg.period_id.date_stop > most_recent_date:
                        most_recent_date = reg.period_id.date_stop
                        most_recent_reg = reg
                if most_recent_reg:
                    vals = {
                        'cash_request_id': cash_request_id,
                        'instance_id': instance_id,
                        'register_id': most_recent_reg.id,
                        'pending_cheque_amount_booking': amount_book_currency,
                        'pending_cheque_amount_functional': amount_func_currency,
                    }
                    self.create(cr, uid, vals, context=context)

    def _get_cheque_reg_status(self, cr, uid, ids, name, args, context=None):
        """
        Returns a String with the status of the cheque register, based on the Liquidity Pos. Report method:
        - classical register state Value if the reg. is the one of the Cash Req. period
        - "Not Created" if the register of the month doesn't exist yet
        """
        if context is None:
            context = {}
        result = {}
        period_obj = self.pool.get('account.period')
        liquidity_pos_report = register_accounting.report.report_liquidity_position \
            .report_liquidity_position3(cr, uid, 'fakereport', context=context)
        for liq in self.browse(cr, uid, ids, fields_to_fetch=['cash_request_id', 'register_id'], context=context):
            period_ids = period_obj.get_period_from_date(cr, uid, liq.cash_request_id.request_date, context=context)
            state = ''
            if liquidity_pos_report and period_ids:
                state = liquidity_pos_report.getRegisterState(liq.register_id, report_period_id=period_ids[0])
            result[liq.id] = state
        return result

    _columns = {
        'status': fields.function(_get_cheque_reg_status,  # can be "Not Created" if the cheque reg. of the month is not created yet
                                  method=True, type='char', size=64, string='Status', store=True, readonly=True),
        'bank_journal_code': fields.related('register_id', 'journal_id', 'bank_journal_id', 'code',
                                            string='Bank Journal Code', type='char', readonly=True),
        'bank_journal_name': fields.related('register_id', 'journal_id', 'bank_journal_id', 'name',
                                            string='Bank Journal Name', type='char', readonly=True),
        'pending_cheque_amount_booking': fields.float('Pending cheque amount in register currency',
                                                      digits_compute=dp.get_precision('Account')),
        'pending_cheque_amount_functional': fields.float('Pending cheque amount in functional currency',
                                                         digits_compute=dp.get_precision('Account')),
    }


cash_request_liquidity_cheque()


class cash_request_liquidity_total(osv.osv):
    _name = 'cash.request.liquidity.total'
    _rec_name = 'cash_request_id'
    _description = 'Liquidity Position Grand Total per Currency for Cash Request'

    def create_liquidity_grand_total(self, cr, uid, cash_request_id, context=None):
        """"
        This method creates the cash_request_liquidity_totals for the Cash Request in parameter.
        It sums the liquidity values per currencies.
        """
        if context is None:
            context = {}
        result = {}
        cash_req_obj = self.pool.get('cash.request')
        fields_list = ['liquidity_cash_ids', 'liquidity_bank_ids', 'liquidity_cheque_ids']
        cash_req = cash_req_obj.browse(cr, uid, cash_request_id, fields_to_fetch=fields_list, context=context)
        # Cash amounts
        for cash in cash_req.liquidity_cash_ids:
            if cash.booking_currency_id.id not in result:
                result[cash.booking_currency_id.id] = {}
                result[cash.booking_currency_id.id]['amount_booking'] = 0.0
                result[cash.booking_currency_id.id]['amount_functional'] = 0.0
            result[cash.booking_currency_id.id]['amount_booking'] += cash.calculated_balance_booking or 0.0
            result[cash.booking_currency_id.id]['amount_functional'] += cash.calculated_balance_functional or 0.0
        # Bank amounts
        for bank in cash_req.liquidity_bank_ids:
            if bank.booking_currency_id.id not in result:
                result[bank.booking_currency_id.id] = {}
                result[bank.booking_currency_id.id]['amount_booking'] = 0.0
                result[bank.booking_currency_id.id]['amount_functional'] = 0.0
            result[bank.booking_currency_id.id]['amount_booking'] += bank.calculated_balance_booking or 0.0
            result[bank.booking_currency_id.id]['amount_functional'] += bank.calculated_balance_functional or 0.0
        # Cheque amounts
        for cheque in cash_req.liquidity_cheque_ids:
            if cheque.booking_currency_id.id not in result:
                result[cheque.booking_currency_id.id] = {}
                result[cheque.booking_currency_id.id]['amount_booking'] = 0.0
                result[cheque.booking_currency_id.id]['amount_functional'] = 0.0
            result[cheque.booking_currency_id.id]['amount_booking'] += cheque.pending_cheque_amount_booking or 0.0
            result[cheque.booking_currency_id.id]['amount_functional'] += cheque.pending_cheque_amount_functional or 0.0
        # Creation of one entry per currency
        for curr in result:
            vals = {
                'cash_request_id': cash_request_id,
                'booking_currency_id': curr,
                'amount_booking': result[curr]['amount_booking'],
                'amount_functional': result[curr]['amount_functional'],
            }
            self.create(cr, uid, vals, context=context)

    _columns = {
        'cash_request_id': fields.many2one('cash.request', 'Cash Request', invisible=True, ondelete='cascade'),
        'booking_currency_id': fields.many2one('res.currency', 'Booking Currency', required=True, readonly=True),
        'functional_currency_id': fields.related('cash_request_id', 'consolidation_currency_id',
                                                 string='Functional Currency', type='many2one', relation='res.currency',
                                                 store=False, readonly=True),
        'amount_booking': fields.float('Grand Total Register Currency',
                                       digits_compute=dp.get_precision('Account')),
        'amount_functional': fields.float('Grand Total Functional Currency',
                                          digits_compute=dp.get_precision('Account')),
    }

    _order = 'booking_currency_id'


cash_request_liquidity_total()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
