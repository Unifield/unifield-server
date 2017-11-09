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


class cash_request(osv.osv):
    _name = 'cash.request'
    _description = 'Cash Request'

    _columns = {
        'name': fields.char(size=128, string='Name', readonly=True, required=True),
        'prop_instance_id': fields.many2one('msf.instance', 'Proprietary instance', readonly=True, required=True,
                                            domain=[('level', '=', 'coordo')]),
        'mission': fields.related('prop_instance_id', 'mission', string='Mission', type='char', store=False,
                                  readonly=True, required=True),
        'month_period_id': fields.many2one('account.period', 'Month', required=True,
                                           domain=[('date_stop', '>=', time.strftime('%Y-%m-%d')), ('special', '=', False)]),
        'fiscalyear_id': fields.related('month_period_id', 'fiscalyear_id', string='Fiscal Year', type='many2one',
                                        relation='account.fiscalyear'),
        'request_date': fields.date('Request Date', required=True),
        'consolidation_currency_id': fields.many2one('res.currency', 'Consolidation Currency',
                                                     required=True, readonly=True),
        'consolidation_currency_name': fields.related('consolidation_currency_id', 'name', type='char',
                                                      string='Consolidation Currency Name', store=False, readonly=True),
        'transfer_account_id': fields.many2one('account.account', 'Transfer Account Code',
                                               domain=[('type', '=', 'other'), ('user_type_code', '=', 'cash')]),
        'transfer_currency_ids': fields.one2many('transfer.currency', 'cash_request_id', 'Currency of Transfers',
                                                 required=True),
        'bank_journal_id': fields.many2one('account.journal', 'Bank', required=True, domain=[('type', '=', 'bank')]),
        'state': fields.selection(
            [('draft', 'Draft'), ('validated', 'Validated'), ('done', 'Done')], 'State',
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
                                               required=True),
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
        instance_ids = []
        instance_obj = self.pool.get('msf.instance')
        mission = self._get_mission(cr, uid, context=context)
        instance_ids.extend(instance_obj.search(cr, uid, [('mission', '=', mission), ('level', '!=', 'section')],
                                                order='level, code', context=context))  # coordo first
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
        resets the computed items, changes the date to the one of the day and gets the updated list of instances
        """
        if context is None:
            context = {}
        if default is None:
            default = {}
        default.update({
            'request_date': datetime.today(),
            'instance_ids': self._get_instance_ids(cr, uid, context=context),
            'total_to_transfer': 0.0,
            'state': 'draft',
            'commitment_ids': [],
            'planned_expense_ids': [],
            'total_to_transfer_line_ids': [],
            'recap_mission_ids': [],
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
        if cash_req_id:
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

    def _update_recap_mission(self, cr, uid, cash_req_id, context=None):
        """
        Updates the Recap Mission in the Main Tab of the Cash Request
        """
        if context is None:
            context = {}
        if cash_req_id:
            recap_mission_obj = self.pool.get('recap.mission')
            cash_req = self.browse(cr, uid, cash_req_id, fields_to_fetch=['instance_ids', 'commitment_ids'], context=context)
            # delete previous recap mission lines for this cash request
            old_lines = recap_mission_obj.search(cr, uid, [('cash_request_id', '=', cash_req.id)], order='NO_ORDER', context=context)
            recap_mission_obj.unlink(cr, uid, old_lines, context=context)
            # create new lines
            instances = cash_req.instance_ids
            for inst in instances:
                # Commitment lines
                commitment_amount = 0.0
                for cl in cash_req.commitment_ids:
                    commitment_amount += cl.instance_id.id == inst.id and cl.total_commitment or 0.0
                recap_mission_vals = {'instance_id': inst.id,
                                      'commitment_amount': commitment_amount,
                                      'cash_request_id': cash_req.id}
                recap_mission_obj.create(cr, uid, recap_mission_vals, context=context)

    def generate_cash_request(self, cr, uid, ids, context=None):
        """
        Computes all automatic fields of the Cash Request
        if the date of the Cash Request is today's date (else raises an error)
        """
        if context is None:
            context = {}
        for cash_request_id in ids:
            cash_req = self.read(cr, uid, cash_request_id, ['request_date'], context=context)
            if cash_req['request_date'] != datetime.today().strftime('%Y-%m-%d'):
                raise osv.except_osv(_('Error'), _('The date of the Cash Request must be the date of the day.'))
            self._generate_commitments(cr, uid, cash_request_id, context=context)
        return True

    def _get_total_cash_request(self, cr, uid, cash_req_id, context=None):
        """
        Sums all the amounts of the Cash Request
        """
        if context is None:
            context = {}
        total = 0.0
        if cash_req_id:
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
        Triggers the computation of Recap Mission Lines + Total to transfer (with a split per currencies)
        """
        for cash_req_id in ids:
            self._update_recap_mission(cr, uid, cash_req_id, context=None)
            self._compute_total_to_transfer(cr, uid, cash_req_id, context=context)
        return True


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
        if ids:
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
        'period_id': fields.many2one('account.period', 'Period', required=True),
        'cash_request_id': fields.many2one('cash.request', 'Cash Request', required=True, ondelete='cascade'),
        'total_commitment': fields.function(_total_commitment_compute, method=True, string='Total', type='float',
                                            digits_compute=dp.get_precision('Account'), store=True),
    }

    _order = 'instance_id'


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
        if ids:
            fields_list = ['liquidity_amount', 'payable_amount', 'commitment_amount', 'expense_amount']
            for recap in self.browse(cr, uid, ids, fields_to_fetch=fields_list, context=context):
                total = recap.liquidity_amount - recap.payable_amount - recap.commitment_amount - recap.expense_amount
                result[recap.id] = -1 * total  # ex: 1000 in Bank - 1500 commitments = -500  ==> display 500 to transfer
        return result

    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Instance code / Place of payment', required=True),
        'cash_request_id': fields.many2one('cash.request', 'Cash Request', required=True, ondelete='cascade'),
        'commitment_amount': fields.float('Commitment', digits_compute=dp.get_precision('Account')),
        'liquidity_amount': fields.float('Cash available in mission', digits_compute=dp.get_precision('Account')),
        'payable_amount': fields.float('Payable Invoices', digits_compute=dp.get_precision('Account')),
        'expense_amount': fields.float('Foreseen expenses', digits_compute=dp.get_precision('Account')),
        'total': fields.function(_total_compute, method=True, string='Total Cash requested', type='float',
                                 digits_compute=dp.get_precision('Account'), store=True),
    }

    _order = 'instance_id'


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
        if ids:
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
        if ids:
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

    _order = 'prop_instance_id'


cash_request_expense()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
