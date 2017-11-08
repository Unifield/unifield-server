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
        'total_to_transfer': fields.float('Total Cash Request to transfer', digits_compute=dp.get_precision('Account')),
        'total_to_transfer_line_ids': fields.one2many('total.transfer.line', 'cash_request_id',
                                                      'Lines of Total Cash Request to transfer', readonly=True),
    }

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
        for curr in cash_req.transfer_currency_ids:
            if curr.percentage < 0:
                raise osv.except_osv(_('Error'), _('The percentage of one of the currencies of transfers is negative.'))
            percentage += curr.percentage
        if percentage > 10**-3 and abs(percentage - 100) > 10**-3:
            raise osv.except_osv(_('Error'), _('The total percentage of the currencies of transfers is incorrect.'))
        if nb_lines > 1 and abs(percentage) <= 10**-3:
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
        Sums the amounts from all the tabs to get the total Cash Request
        """
        if context is None:
            context = {}
        total = 0.0
        if cash_req_id:
            cash_req = self.browse(cr, uid, cash_req_id, fields_to_fetch=['commitment_ids'], context=context)
            # Commitment lines
            for cl in cash_req.commitment_ids:
                total += cl.total_commitment
        return total

    def compute_total_to_transfer(self, cr, uid, ids, context=None):
        """
        If all the checks are ok, computes the total to transfer (see formula below) and does a split per currency:
        Formula = (Total cash request - Transfer to come + security envelop) + %buffer
        """
        if context is None:
            context = {}
        transfer_line_obj = self.pool.get('total.transfer.line')
        for cash_req in self.browse(cr, uid, ids, fields_to_fetch=['buffer', 'transfer_to_come', 'security_envelope'],
                                    context=context):
            self._check_currencies(cr, uid, cash_req.id, context=context)
            # buffer shouldn't be negative nor > 100
            if cash_req.buffer < 0 or cash_req.buffer - 100 > 10**-3:
                raise osv.except_osv(_('Error'), _('The percentage in the Buffer field is incorrect.'))
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
                total_curr = total * percentage / 100
                transfer_line_vals = {'currency_id': curr.currency_id.id,
                                      'amount': total_curr,
                                      'cash_request_id': cash_req.id}
                transfer_line_obj.create(cr, uid, transfer_line_vals, context=context)
            self.write(cr, uid, cash_req.id, cash_req_vals, context=context)
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
        'instance_id': fields.many2one('msf.instance', 'Prop. Instance', required=True),
        'instance_code': fields.related('instance_id', 'code', string='Instance code', type='char', store=False, readonly=True),
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
    _description = 'Lines of Total to transfer for Cash Request'

    _columns = {
        'currency_id': fields.many2one('res.currency', 'Currency', required=True),
        'amount': fields.float('Amount', digits_compute=dp.get_precision('Account')),
        'cash_request_id': fields.many2one('cash.request', 'Cash Request', required=True, ondelete='cascade'),
    }


total_transfer_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
