# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) MSF, TeMPO Consulting.
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
from time import strftime
import decimal_precision as dp
from base import currency_date


class analytic_distribution1(osv.osv):
    _name = "analytic.distribution"

    _columns = {
        'analytic_lines': fields.one2many('account.analytic.line', 'distribution_id', 'Analytic Lines'),
        'invoice_ids': fields.one2many('account.invoice', 'analytic_distribution_id', string="Invoices"),
        'invoice_line_ids': fields.one2many('account.invoice.line', 'analytic_distribution_id', string="Invoice Lines"),
        'register_line_ids': fields.one2many('account.bank.statement.line', 'analytic_distribution_id', string="Register Lines"),
        'move_line_ids': fields.one2many('account.move.line', 'analytic_distribution_id', string="Move Lines"),
        'commitment_ids': fields.one2many('account.commitment', 'analytic_distribution_id', string="Commitments voucher"),
        'commitment_line_ids': fields.one2many('account.commitment.line', 'analytic_distribution_id', string="Commitment voucher lines"),
    }

    def copy(self, cr, uid, distrib_id, default=None, context=None):
        """
        Copy an analytic distribution without the one2many links
        """
        if default is None:
            default = {}
        default.update({
            'analytic_lines': False,
            'invoice_ids': False,
            'invoice_line_ids': False,
            'register_line_ids': False,
            'move_line_ids': False,
            'commitment_ids': False,
            'commitment_line_ids': False,
        })
        return super(osv.osv, self).copy(cr, uid, distrib_id, default, context=context)

    def update_distribution_line_amount(self, cr, uid, ids, amount=False, context=None):
        """
        Update amount on distribution lines for given distribution (ids)
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not amount:
            return False
        # Process distributions
        for distrib_id in ids:
            for dl_name in ['cost.center.distribution.line', 'funding.pool.distribution.line', 'free.1.distribution.line', 'free.2.distribution.line']:
                dl_obj = self.pool.get(dl_name)
                dl_ids = dl_obj.search(cr, uid, [('distribution_id', '=', distrib_id)], context=context)
                for dl in dl_obj.read(cr, uid, dl_ids, ['percentage'], context=context):
                    dl_vals = {
                        'amount': round(dl.get('percentage', False) * amount) / 100.0,
                    }
                    dl_obj.write(cr, uid, [dl.get('id')], dl_vals, context=context)
        return True

    def update_distribution_line_account(self, cr, uid, line_ids, account_id, context=None):
        """
        Update account on distribution line
        """
        # Some verifications
        if not context:
            context = {}
        # Return False if no line_ids
        if not account_id or not line_ids: # fix bug on UF-2205 with analytic lines that comes from INTL Engagement journal without any distribution
            return False
        if isinstance(line_ids, (int, long)):
            line_ids = [line_ids]
        # Prepare some values
        account = self.pool.get('account.analytic.account').browse(cr, uid, [account_id], context=context)[0]
        if account.category == 'OC':
            vals = {'cost_center_id': account_id}
        elif account.category == 'DEST':
            vals = {'destination_id': account_id}
        else:
            vals = {'analytic_id': account_id}
        if account.category == 'FREE1':
            obj = self.pool.get('free.1.distribution.line')
        elif account.category == 'FREE2':
            obj = self.pool.get('free.2.distribution.line')
        else:
            obj = self.pool.get('funding.pool.distribution.line')
        return obj.write(cr, uid, line_ids, vals, context=context)

    def create_funding_pool_lines(self, cr, uid, ids, account_id=False, context=None):
        """
        Create funding pool lines regarding cost_center_lines from analytic distribution.
        If funding_pool_lines exists, then nothing appends.
        By default, add funding_pool_lines with MSF Private Fund element (written in an OpenERP demo file).
        For destination axis, get those from account_id default configuration (default_destination_id).
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        # Browse distributions
        for distrib in self.browse(cr, uid, ids, context=context):
            if distrib.funding_pool_lines:
                res[distrib.id] = False
                continue
            # Browse cost center lines
            for line in distrib.cost_center_lines:
                # Search MSF Private Fund
                try:
                    pf_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution',
                                                                                'analytic_account_msf_private_funds')[1]
                except ValueError:
                    pf_id = 0
                if pf_id:
                    vals = {
                        'analytic_id': pf_id,
                        'amount': line.amount or 0.0,
                        'percentage': line.percentage or 0.0,
                        'currency_id': line.currency_id and line.currency_id.id or False,
                        'distribution_id': distrib.id or False,
                        'cost_center_id': line.analytic_id and line.analytic_id.id or False,
                        'destination_id': line.destination_id and line.destination_id.id or False,
                    }
                    if distrib and distrib.partner_type:
                        vals.update({'partner_type': distrib.partner_type})

                    # Search default destination if no one given
                    if account_id and not vals.get('destination_id'):
                        account = self.pool.get('account.account').browse(cr, uid, account_id)
                        if account and account.is_analytic_addicted:
                            vals.update({'destination_id': account.default_destination_id and account.default_destination_id.id or False})
                    self.pool.get('funding.pool.distribution.line').create(cr, uid, vals, context=context)
            res[distrib.id] = True
        return res

    def create_account_analytic_lines(self, cr, uid, ids, name, date, amount, journal_id, currency_id, document_date=False, ref=False,
                                      source_date=False, general_account_id=False, move_id=False, invoice_line_id=False,
                                      commitment_line_id=False, period_id=False, context=None):
        """
        Create analytic lines from given elements:
         - date
         - name
         - amount
         - journal_id (analytic_journal_id)
         - currency_id
         - ref (optional)
         - source_date (optional)
         - general_account_id (optional)
         - move_id (optional)
         - invoice_line_id (optional)
         - commitment_line_id (optional)
        Return all created ids, otherwise return false (or [])
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not name or not date or not amount or not journal_id or not currency_id:
            return False
        if not document_date:
            document_date = date
        # Prepare some values
        res = []
        curr_date = currency_date.get_date(self, cr, document_date, date, source_date=source_date)
        vals = {
            'name': name,
            'date': date,
            'document_date': document_date,
            'ref': ref or False,
            'journal_id': journal_id,
            'general_account_id': general_account_id or False,
            'move_id': move_id or False,
            'invoice_line_id': invoice_line_id or False,
            'user_id': uid,
            'currency_id': currency_id,
            'source_date': source_date or False,
            'commitment_line_id': commitment_line_id or False,
        }
        if period_id:
            vals['real_period_id'] = period_id

        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        # Browse distribution(s)
        for distrib in self.browse(cr, uid, ids, context=context):
            vals.update({'distribution_id': distrib.id,})
            # create lines
            for distrib_lines in [distrib.funding_pool_lines, distrib.free_1_lines, distrib.free_2_lines]:
                for distrib_line in distrib_lines:
                    context.update({'currency_date': curr_date})  # for the computation of the fctal amount
                    anal_amount = (distrib_line.percentage * amount) / 100
                    vals.update({
                        'amount': -1 * self.pool.get('res.currency').compute(cr, uid, currency_id, company_currency,
                                                                             anal_amount, round=False, context=context),
                        'amount_currency': round(-1 * anal_amount, 2),
                        'account_id': distrib_line.analytic_id.id,
                        'cost_center_id': False,
                        'destination_id': False,
                        'distrib_line_id': '%s,%s'%(distrib_line._name, distrib_line.id),
                    })
                    # Update values if we come from a funding pool
                    if distrib_line._name == 'funding.pool.distribution.line':
                        vals.update({'cost_center_id': distrib_line.cost_center_id and distrib_line.cost_center_id.id or False,
                                     'destination_id': distrib_line.destination_id and distrib_line.destination_id.id or False,})
                    # create analytic line
                    al_id = self.pool.get('account.analytic.line').create(cr, uid, vals, context=context)
                    res.append(al_id)
        return res

analytic_distribution1()

class distribution_line(osv.osv):
    _name = "distribution.line"

    _columns = {
        'name': fields.char('Name', size=64),
        "distribution_id": fields.many2one('analytic.distribution', 'Associated Analytic Distribution', ondelete='cascade', select="1"),
        "analytic_id": fields.many2one('account.analytic.account', 'Analytical Account', ondelete='restrict'),
        "amount": fields.float('Amount', digits_compute=dp.get_precision('Account')),
        "percentage": fields.float('Percentage', digits=(16,4)),
        "currency_id": fields.many2one('res.currency', 'Currency', required=True),
        "date": fields.date(string="Date"),
        "source_date": fields.date(string="Source Date", help="This date is for source_date for analytic lines"),
        'partner_type': fields.text(string='Partner Type of FO/PO', required=False, readonly=True),
    }

    _defaults ={
        'name': 'Distribution Line',
        'date': lambda *a: strftime('%Y-%m-%d'),
        'source_date': lambda *a: strftime('%Y-%m-%d'),
    }

    def _check_percentage(self, cr, uid, ids, context=None):
        """
        Do not allow 0.0 percentage value
        """
        for l in self.browse(cr, uid, ids):
            if l.percentage == 0.0:
                return False
        return True

    _constraints = [
        (_check_percentage, '0 is not allowed as percentage value!', ['percentage']),
    ]

    def create_analytic_lines(self, cr, uid, ids, move_line_id, date, document_date, source_date=False, name=False, ref='', context=None):
        '''
        Creates an analytic lines from a distribution line and an account.move.line
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        ret = {}
        move_line = self.pool.get('account.move.line').browse(cr, uid, move_line_id)
        company = self.pool.get('res.users').browse(cr, uid, uid).company_id
        company_currency_id = company.currency_id.id
        instance_id = company.instance_id.id

        for line in self.browse(cr, uid, ids):
            amount_cur = round((move_line.credit_currency - move_line.debit_currency) * line.percentage / 100, 2)
            ctx = {'currency_date': currency_date.get_date(self, cr, document_date, date, source_date=source_date)}
            amount = self.pool.get('res.currency').compute(cr, uid, move_line.currency_id.id, company_currency_id, amount_cur, round=False, context=ctx)

            # US-945: deduce real period id from date
            # TO NOTE that, in correction wizard:
            # in December we are well in December, never in 13, 14, 15, 16
            period_ids = self.pool.get('account.period').get_period_from_date(
                cr, uid, date=date, context=context)

            curr_date = currency_date.get_date(self, cr, move_line.document_date, move_line.date,
                                               source_date=source_date or move_line.source_date)
            vals = {
                'instance_id': instance_id,
                'account_id': line.analytic_id.id,
                'amount_currency': amount_cur,
                'amount': amount,
                'currency_id': move_line.currency_id.id,
                'general_account_id': move_line.account_id.id,
                'date': date,
                # UFTP-361: source_date or source date from line or from line posting date if any
                # for rev line must be the source date of the move line: posting date of reversed line
                'source_date': curr_date,
                'document_date': document_date,
                'journal_id': move_line.journal_id and move_line.journal_id.analytic_journal_id and move_line.journal_id.analytic_journal_id.id or False,
                'move_id': move_line.id,
                'name': name or move_line.name,
                'distrib_id': line.distribution_id.id,
                'distribution_id': line.distribution_id.id,
                'distrib_line_id': '%s,%s'%(self._name, line.id),
                'ref': ref or move_line.move_id.name or False,
                'real_period_id':  period_ids and period_ids[0] or False,  # US-945
            }
            if self._name == 'funding.pool.distribution.line':
                vals.update({
                    'destination_id': line.destination_id and line.destination_id.id or False,
                    'cost_center_id': line.cost_center_id and line.cost_center_id.id or False,
                })
            ret[line.id] = self.pool.get('account.analytic.line').create(cr, uid, vals)

        return ret

distribution_line()

class cost_center_distribution_line(osv.osv):
    _name = "cost.center.distribution.line"
    _inherit = "distribution.line"
    _columns = {
        "destination_id": fields.many2one('account.analytic.account', 'Destination', domain="[('type', '!=', 'view'), ('category', '=', 'DEST')]", required=True, ondelete='restrict'),
    }

cost_center_distribution_line()


class funding_pool_distribution_line(osv.osv):
    _name = "funding.pool.distribution.line"
    _inherit = "distribution.line"
    _columns = {
        "cost_center_id": fields.many2one('account.analytic.account', 'Cost Center Account', required=True, ondelete='restrict'),
        "destination_id": fields.many2one('account.analytic.account', 'Destination', domain="[('type', '!=', 'view'), ('category', '=', 'DEST')]", required=True, ondelete='restrict'),
    }

    def _check_fp(self, cr, uid, ids, context=None):
        """
        Raises an error if no Funding Pool is linked to the FP distrib line(s)
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for distrib_line in self.browse(cr, uid, ids, fields_to_fetch=['analytic_id'], context=context):
            if not distrib_line.analytic_id:
                raise osv.except_osv(_('Error'), _('Funding Pool not found.'))

    def create(self, cr, uid, vals, context=None):
        distrib_line_id = super(funding_pool_distribution_line, self).create(cr, uid, vals, context=context)
        self._check_fp(cr, uid, distrib_line_id, context=context)
        return distrib_line_id

    def write(self, cr, uid, ids, vals, context=None):
        res = super(funding_pool_distribution_line, self).write(cr, uid, ids, vals, context=context)
        self._check_fp(cr, uid, ids, context=context)
        return res

funding_pool_distribution_line()


class free_1_distribution_line(osv.osv):
    _name = "free.1.distribution.line"
    _inherit = "distribution.line"
    _columns = {
        "destination_id": fields.many2one('account.analytic.account', 'Destination', domain="[('type', '!=', 'view'), ('category', '=', 'DEST')]", required=False, ondelete='restrict'),
    }

free_1_distribution_line()

class free_2_distribution_line(osv.osv):
    _name = "free.2.distribution.line"
    _inherit = "distribution.line"
    _columns = {
        "destination_id": fields.many2one('account.analytic.account', 'Destination', domain="[('type', '!=', 'view'), ('category', '=', 'DEST')]", required=False, ondelete='restrict'),
    }

free_2_distribution_line()

class analytic_distribution(osv.osv):
    _name = 'analytic.distribution'
    _inherit = "analytic.distribution"

    def _get_lines_count(self, cr, uid, ids, name=False, args=False, context=None):
        """
        Get count of each analytic distribution lines type.
        Example: with an analytic distribution with 2 cost center, 3 funding pool and 1 Free 1:
        2 CC; 3 FP; 1 F1; 0 F2;
        (Number of chars: 20 chars + 4 x some lines number)
        """
        # Some verifications
        if not context:
            context = {}
        # Prepare some values
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Browse given invoices
        for distrib in self.browse(cr, uid, ids, context=context):
            txt = ''
            txt += str(len(distrib.cost_center_lines) or '0') + ' CC; '
            txt += str(len(distrib.funding_pool_lines) or '0') + ' FP; '
            txt += str(len(distrib.free_1_lines) or '0') + ' F1; '
            txt += str(len(distrib.free_2_lines) or '0') + ' F2'
            if not txt:
                txt = ''
            res[distrib.id] = txt
        return res

    _columns = {
        'cost_center_lines': fields.one2many('cost.center.distribution.line', 'distribution_id', 'Cost Center Distribution'),
        'funding_pool_lines': fields.one2many('funding.pool.distribution.line', 'distribution_id', 'Funding Pool Distribution'),
        'free_1_lines': fields.one2many('free.1.distribution.line', 'distribution_id', 'Free 1 Distribution'),
        'free_2_lines': fields.one2many('free.2.distribution.line', 'distribution_id', 'Free 2 Distribution'),
        'name': fields.function(_get_lines_count, method=True, type='char', size=256, string="Name", readonly=True, store=False),
    }

analytic_distribution()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
