# -*- coding: utf-8 -*-
##############################################################################
#
#    Author: Yannick Vaucher, Guewen Baconnier
#    Copyright 2012 Camptocamp SA
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

import datetime

from dateutil.relativedelta import relativedelta

from osv import osv, fields
from tools.translate import _

class WizardCurrencyrevaluation(osv.osv_memory):
    _name = 'wizard.currency.revaluation'

    _columns = {'revaluation_date': fields.date(
                    _('Revaluation Date')),
                'revaluation_method': fields.selection(
                    [('liquidity', _("Liquidity (Month-end)")),
                     ('other_bs', _("Liquidity & Other B/S (Year-end)")),
                     ],
                    string=_("Revaluation method"), required=True),
                'revaluation_year_ok': fields.boolean(
                    _("Year-end revaluation"),
                    help=_("In 'Liquidity' mode, you can choose to do a "
                           "year-end revaluation instead of month-end.")),
                'fiscalyear_id': fields.many2one(
                    'account.fiscalyear', string=_("Fiscal year"),
                    domain=[('state', '=', 'draft')],
                    required=True),
                'period_id': fields.many2one(
                    'account.period', string=_("Period"),
                    domain="[('fiscalyear_id', '=', fiscalyear_id), ('state', '!=', 'created')]"),
                'currency_table_id': fields.many2one(
                    'res.currency.table', string=_("Currency table"),
                    domain=[('state', '=', 'valid')]),
                'journal_id': fields.many2one(
                    'account.journal', string=_("Entry journal"),
                    #domain="[('type','=','general')]",
                    help=_("Journal used for revaluation entries."),
                    readonly=True),
                'result_period_id': fields.many2one(
                    'account.period', string=_(u"Entry period"),
                    domain="[('fiscalyear_id', '=', fiscalyear_id), ('state', '!=', 'created')]",
                    help=_("Period used for revaluation entries.")),
                'posting_date': fields.date(
                    _('Entry date'), readonly=True,
                    help=_("Revaluation entry date (document and posting date)")),
                'label': fields.char(
                    'Entry description',
                     size=100,
                     help="This label will be inserted in entries description."
                         " You can use %(account)s, %(currency)s"
                         " and %(rate)s keywords.",
                     required=True),
    }

    def _get_default_revaluation_date(self, cr, uid, context):
        """Get stop date of the fiscal year."""
        if context is None:
            context = {}
        #period_obj = self.pool.get('account.period')
        #period_id = self._get_default_result_period_id(cr, uid, context=context)
        #if period_id:
        #    period = period_obj.browse(cr, uid, period_id, context=context)
        #    return period.date_stop
        #return False
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        fiscalyear_id = self._get_default_fiscalyear_id(cr, uid, context=context)
        if fiscalyear_id:
            fiscalyear = fiscalyear_obj.browse(cr, uid, fiscalyear_id, context=context)
            return fiscalyear.date_stop
        return False

    def _get_default_fiscalyear_id(self, cr, uid, context=None):
        """Get default fiscal year to process."""
        if context is None:
            context = {}
        user_obj = self.pool.get('res.users')
        cp = user_obj.browse(cr, uid, uid, context=context).company_id
        current_date = datetime.date.today().strftime('%Y-%m-%d')
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        fiscalyear_ids = fiscalyear_obj.search(
            cr, uid,
            [('date_start', '<', current_date),
             ('date_stop', '>', current_date),
             ('company_id', '=', cp.id)],
            limit=1,
            context=context)
        return fiscalyear_ids and fiscalyear_ids[0] or False

    def _get_default_period_id(self, cr, uid, context=None):
        """Get default period to process."""
        if context is None:
            context = {}
        period_obj = self.pool.get('account.period')
        period_date = datetime.date.today()
        if period_date.month > 1:
            period_date = period_date - relativedelta(months=1)
        # NOTE: the method 'get_period_from_date()' supplied by the
        #       'account_tools' module is used here
        period_ids = period_obj.get_period_from_date(
            cr, uid, period_date.strftime('%Y-%m-%d'))
        return period_ids and period_ids[0] or False

    def _get_default_journal_id(self, cr, uid, context):
        """Get default revaluation journal."""
        journal_obj = self.pool.get('account.journal')
        journal_ids = journal_obj.search(
            cr, uid, [('code', '=', 'REVAL')], context=context)
        if not journal_ids:
            raise osv.except_osv(
                _(u"Error"),
                _(u"No revaluation journal found!"))
        return journal_ids and journal_ids[0] or False

    def _get_default_result_period_id(self, cr, uid, context=None):
        """Get period (period 13) of the fiscal year."""
        if context is None:
            context = {}
        period_obj = self.pool.get('account.period')
        fiscalyear_id = self._get_default_fiscalyear_id(cr, uid, context=context)
        if fiscalyear_id:
            period_ids = period_obj.search(
                cr, uid,
                [('number', '=', 13), ('fiscalyear_id', '=', fiscalyear_id),
                 ('state', '!=', 'created')],
                context=context)
            return period_ids and period_ids[0] or False
        return False

    def _get_default_posting_date(self, cr, uid, context):
        """Get default posting date from the period selected."""
        if context is None:
            context = {}
        period_obj = self.pool.get('account.period')
        period_id = self._get_default_result_period_id(cr, uid, context=context)
        if period_id:
            period = period_obj.browse(cr, uid, period_id, context=context)
            return period.date_stop
        return False

    _defaults = {
        'label': "%(currency)s %(account)s %(rate)s currency revaluation",
        'revaluation_method': lambda *args: 'liquidity',
        'revaluation_date': _get_default_revaluation_date,
        'fiscalyear_id': _get_default_fiscalyear_id,
        'period_id': _get_default_period_id,
        'result_period_id': _get_default_result_period_id,
        'posting_date': _get_default_posting_date,
        'journal_id': _get_default_journal_id,
    }

    def on_change_revaluation_method(
            self, cr, uid, ids, method, fiscalyear_id, period_id):
        """'on_change' method for the 'revaluation_method', 'fiscalyear_id' and
        'period_id' fields.
        """
        if not method or not fiscalyear_id:
            return {}
        value = {}
        warning = {}
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        period_obj = self.pool.get('account.period')
        move_obj = self.pool.get('account.move')
        fiscalyear = fiscalyear_obj.browse(cr, uid, fiscalyear_id)
        # Check
        previous_fiscalyear_ids = fiscalyear_obj.search(
            cr, uid,
            [('date_stop', '<', fiscalyear.date_start),
             ('company_id', '=', fiscalyear.company_id.id)],
            limit=1)
        if previous_fiscalyear_ids:
            special_period_ids = [p.id for p in fiscalyear.period_ids
                                  if p.special == True]
            opening_move_ids = []
            if special_period_ids:
                opening_move_ids = move_obj.search(
                    cr, uid, [('period_id', '=', special_period_ids[0])])
            if not opening_move_ids or not special_period_ids:
                warning = {
                    'title': _('Warning!'),
                    'message': _('No opening entries in opening period for this fiscal year')
                }
        # Set values according to the user input
        value['period_id'] = period_id
        value['revaluation_date'] = False
        if method == 'liquidity':
            if not period_id and fiscalyear_id:
                # If the current fiscal year is the actual one, we get the
                # previous month as the right period (except for january)
                if fiscalyear_id == self._get_default_fiscalyear_id(cr, uid):
                    period_date = datetime.date.today()
                    if period_date.month > 1:
                        period_date = period_date - relativedelta(months=1)
                # If the selected fiscal year is not the actual one, we get its
                # last period
                else:
                    period_date = datetime.datetime.strptime(
                        fiscalyear.date_stop, '%Y-%m-%d')
                # NOTE: the method 'get_period_from_date()' supplied by the
                #       'account_tools' module is used here
                period_ids = period_obj.get_period_from_date(
                    cr, uid, period_date.strftime('%Y-%m-%d'))
                period_id = period_ids and period_ids[0] or False
                value['period_id'] = period_id
            if period_id:
                period = period_obj.browse(cr, uid, period_id)
                value['revaluation_date'] = period.date_stop
        else:
            value['revaluation_date'] = fiscalyear.date_stop
        res = {'value': value, 'warning': warning}
        return res

    def on_change_result_period_id(self, cr, uid, ids, result_period_id, context=None):
        """'on_change' method for the 'result_period_id' field."""
        if context is None:
            context = {}
        value = {}
        warning = {}
        if result_period_id:
            period_obj = self.pool.get('account.period')
            period = period_obj.browse(cr, uid, result_period_id, context=context)
            value['posting_date'] = period.date_stop
        return {'value': value, 'warning': warning}

    def _compute_unrealized_currency_gl(self, cr, uid,
                                        currency_id,
                                        balances,
                                        form,
                                        context=None):
        """
        Update data dict with the unrealized currency gain and loss
        plus add 'currency_rate' which is the value used for rate in
        computation

        @param int currency_id: currency to revaluate
        @param dict balances: contains foreign balance and balance

        @return: updated data for foreign balance plus rate value used
        """
        context = context or {}

        currency_obj = self.pool.get('res.currency')

        # Compute unrealized gain loss
        ctx_rate = context.copy()
        ctx_rate['date'] = form.revaluation_date
        user_obj = self.pool.get('res.users')
        cp_currency_id = user_obj.browse(cr, uid, uid, context=context).company_id.currency_id.id

        currency = currency_obj.browse(cr, uid, currency_id, context=ctx_rate)

        foreign_balance = adjusted_balance = balances.get('foreign_balance', 0.0)
        balance = balances.get('balance', 0.0)
        unrealized_gain_loss =  0.0
        if foreign_balance:
            ctx_rate['revaluation'] = True
            adjusted_balance = currency_obj.compute(
                cr, uid, currency_id, cp_currency_id, foreign_balance,
                context=ctx_rate)
            unrealized_gain_loss =  adjusted_balance - balance
            #revaluated_balance =  balance + unrealized_gain_loss
        else:
            if balance:
                if currency_id != cp_currency_id:
                    unrealized_gain_loss =  0.0 - balance
                else:
                    unrealized_gain_loss = 0.0
            else:
                unrealized_gain_loss =  0.0
        return {'unrealized_gain_loss': unrealized_gain_loss,
                'currency_rate': currency.rate,
                'revaluated_balance': adjusted_balance}

    def _format_label(self, cr, uid, text, account_id, currency_id,
                      rate, context=None):
        """
        Return a text with replaced keywords by values

        @param str text: label template, can use
            %(account)s, %(currency)s, %(rate)s
        @param int account_id: id of the account to display in label
        @param int currency_id: id of the currency to display
        @param float rate: rate to display
        """
        account_obj = self.pool.get('account.account')
        currency_obj = self.pool.get('res.currency')
        account = account_obj.browse(cr, uid,
                                     account_id,
                                    context=context)
        currency = currency_obj.browse(cr, uid, currency_id, context=context)
        data = {'account': account.code or False,
                'currency': currency.name or False,
                'rate': rate or False}
        return text % data

    def _write_adjust_balance(self, cr, uid, account_id, currency_id,
                              partner_id, amount, label, form, sums, context=None):
        """
        Generate entries to adjust balance in the revaluation accounts

        @param account_id: ID of account to be reevaluated
        @param amount: Amount to be written to adjust the balance
        @param label: Label to be written on each entry
        @param form: Wizard browse record containing data

        @return: ids of created move_lines
        """
        if context is None:
            context = {}

        def create_move():
            account = self.pool.get('account.account').browse(
                cr, uid, account_id, context=context)
            currency = self.pool.get('res.currency').browse(
                cr, uid, currency_id, context=context)
            base_move = {'name': label,
                         'ref': "%s - %s" % (account.code, currency.name),
                         'journal_id': form.journal_id.id,
                         'period_id': form.result_period_id.id,
                         'document_date': form.posting_date,
                         'date': form.posting_date}
            return move_obj.create(cr, uid, base_move, context=context)

        def create_move_line(move_id, line_data, sums):
            line_name = "Revaluation - %s" % form.fiscalyear_id.name
            if form.revaluation_method == 'liquidity' and not form.revaluation_year_ok:
                line_name = "Revaluation - %s" % form.period_id.name
            base_line = {'name': line_name,
                         'currency_id': currency_id,
                         'amount_currency': 0.0,
                         'document_date': form.posting_date,
                         'date': form.posting_date,
                         'is_revaluated_ok': True,
                         }
            base_line.update(line_data)
            # we can assume that keys should be equals columns name + gl_
            # but it was not decide when the code was designed. So commented code may sucks
            #for k, v in sums.items():
            #    line_data['gl_' + k] = v
            base_line['gl_foreign_balance'] = sums.get('foreign_balance', 0.0)
            base_line['gl_balance'] = sums.get('balance', 0.0)
            base_line['gl_revaluated_balance'] = sums.get('revaluated_balance', 0.0)
            base_line['gl_currency_rate'] = sums.get('currency_rate', 0.0)
            return move_line_obj.create(cr, uid, base_line, context=context)

        account_obj = self.pool.get('account.account')
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        #user_obj = self.pool.get('res.users')
        distrib_obj = self.pool.get('analytic.distribution')
        cc_distrib_obj = self.pool.get('cost.center.distribution.line')
        fp_distrib_obj = self.pool.get('funding.pool.distribution.line')
        account_ana_obj = self.pool.get('account.analytic.account')
        model_data_obj = self.pool.get('ir.model.data')

        #company = user_obj.browse(cr, uid, uid).company_id
        account = account_obj.browse(cr, uid, account_id, context=context)
        revaluation_account_id = model_data_obj.get_object_reference(
            cr, uid, 'msf_chart_of_account', '6940')[1]
        revaluation_account = account_obj.browse(
            cr, uid, revaluation_account_id, context=context)

        # Prepare the analytic distribution for the account revaluation entry
        # if the account has a 'expense' or 'income' type
        distribution_id = False
        if revaluation_account.user_type.code in ['expense', 'income']:
            destination_id = model_data_obj.get_object_reference(
                cr, uid, 'analytic_distribution', 'analytic_account_destination_support')[1]
            #cost_center_id = model_data_obj.get_object_reference(
            #    cr, uid, 'analytic_distribution', 'analytic_account_project_intermission')[1]
            cost_center_id = account_ana_obj.search(
                cr, uid, [('for_fx_gain_loss', '=', True)], context=context)[0]
            funding_pool_id = model_data_obj.get_object_reference(
                cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
            distribution_id = distrib_obj.create(cr, uid, {}, context=context)
            cc_distrib_obj.create(
                cr, uid,
                {'distribution_id': distribution_id,
                 'analytic_id': cost_center_id,
                 'destination_id': destination_id,
                 'currency_id': currency_id,
                 'percentage': 100.0,
                 'source_date': form.posting_date,
                },
                context=context)
            fp_distrib_obj.create(
                cr, uid,
                {'distribution_id': distribution_id,
                 'analytic_id': funding_pool_id,
                 'destination_id': destination_id,
                 'cost_center_id': cost_center_id,
                 'currency_id': currency_id,
                 'percentage': 100.0,
                 'source_date': form.posting_date,
                },
                context=context)

        created_ids = []
        # over revaluation
        if amount >= 0.01:
            if revaluation_account_id:
                move_id = create_move()
                # Create a move line to Debit account to be revaluated
                line_data = {
                    'debit': amount,
                    'debit_currency': False,
                    'move_id': move_id,
                    'account_id': account_id,
                }
                created_ids.append(create_move_line(move_id, line_data, sums))
                # Create a move line to Credit revaluation account
                line_data = {
                    'credit': amount,
                    'credit_currency': False,
                    'move_id': move_id,
                    'account_id': revaluation_account_id,
                    'analytic_distribution_id': distribution_id,
                }
                created_ids.append(create_move_line(move_id, line_data, sums))
        # under revaluation
        elif amount <= -0.01:
            amount = -amount
            if revaluation_account_id:
                move_id = create_move()

                # Create a move line to Debit revaluation loss account
                line_data = {
                    'debit': amount,
                    'move_id': move_id,
                    'account_id': revaluation_account_id,
                    'analytic_distribution_id': distribution_id,
                }

                created_ids.append(create_move_line(move_id, line_data, sums))
                # Create a move line to Credit account to be revaluated
                line_data = {
                    'credit': amount,
                    'move_id': move_id,
                    'account_id': account_id,
                }
                created_ids.append(create_move_line(move_id, line_data, sums))
        # Hard post the move
        move_obj.post(cr, uid, [move_id], context=context)
        return move_id, created_ids

    def revaluate_currency(self, cr, uid, ids, context=None):
        """
        Compute unrealized currency gain and loss and add entries to
        adjust balances

        @return: dict to open an Entries view filtered on generated move lines
        """
        if context is None:
            context = {}
        user_obj = self.pool.get('res.users')
        account_obj = self.pool.get('account.account')
        #move_obj = self.pool.get('account.move')
        currency_obj = self.pool.get('res.currency')

        company = user_obj.browse(cr, uid, uid).company_id

        created_ids = []

        if isinstance(ids, (int, long)):
            ids = [ids]
        form = self.browse(cr, uid, ids[0], context=context)

        # Set the currency table in the context for later computations
        if form.revaluation_method == 'other_bs':
            context['currency_table_id'] = form.currency_table_id.id

        # Get all currency names to map them with main currencies later
        currency_codes_from_table = {}
        if form.revaluation_method == 'other_bs':
            for currency in form.currency_table_id.currency_ids:
                # Check the revaluation date and dates in the currency table
                #if currency.date != form.revaluation_date:
                #    raise osv.except_osv(
                #        _("Error"),
                #        _("The revaluation date seems to differ with the data of "
                #          "the currency table."))
                currency_codes_from_table[currency.name] = currency.id

        # Get posting date (as the field is readonly, its value is not sent
        # to the server by the web client
        form.posting_date = form.result_period_id and form.result_period_id.date_stop
        #if form.revaluation_method == 'liquidity':
        #    form.revaluation_date = form.period_id and form.period_id.date_stop

        # Search for accounts Balance Sheet or Liquidity to be eevaluated
        account_ids = []
        if form.revaluation_method == 'liquidity':
            account_ids = account_obj.search(
                cr, uid,
                [('currency_revaluation', '=', True),
                 ('type', '=', 'liquidity'),
                 ('user_type_code', '=', 'cash')],
                 #('user_type.close_method', '!=', 'none'),
                context=context)
        elif form.revaluation_method == 'other_bs':
            account_ids = account_obj.search(
                cr, uid,
                [('currency_revaluation', '=', True),
                 ('user_type_code', 'in', ['receivables', 'payables', 'asset', 'stock'])],
                 #('type', '!=', 'liquidity')],
                context=context)
        if not account_ids:
            raise osv.except_osv(
                _('Settings Error!'),
                _("No account to be revaluated found. "
                  "Please check 'Included in revaluation' "
                  "for at least one account in account form."))

        special_period_ids = [p.id for p in form.fiscalyear_id.period_ids if p.special == True]
        if not special_period_ids:
            raise osv.except_osv(_('Error!'),
                                 _('No special period found for the fiscalyear %s') %
                                   form.fiscalyear_id.code)

        # FIXME
        #opening_move_ids = []
        #if special_period_ids:
        #    opening_move_ids = move_obj.search(
        #        cr, uid, [('period_id', '=', special_period_ids[0])])
        #    if not opening_move_ids:
        #        # if the first move is on this fiscalyear, this is the first
        #        # financial year
        #        first_move_id = move_obj.search(
        #            cr, uid, [('company_id', '=', company.id)],
        #            order='date', limit=1)
        #        if not first_move_id:
        #            raise osv.except_osv(
        #                _('Error!'),
        #                _('No fiscal entries found'))
        #        first_move = move_obj.browse(
        #                cr, uid, first_move_id[0], context=context)
        #        if fiscalyear.id != first_move.period_id.fiscalyear_id:
        #            raise osv.except_osv(
        #                _('Error!'),
        #                _('No opening entries in opening period for this fiscal year %s' % (
        #                    fiscalyear.code,)))

        period_ids = []
        if form.revaluation_method == 'liquidity' and not form.revaluation_year_ok:
            period_ids = [form.period_id.id]
        else:
            period_ids = [p.id for p in form.fiscalyear_id.period_ids]
        if not period_ids:
            raise osv.except_osv(
                _('Error!'),
                _('No period found for the fiscalyear %s') % (
                    form.fiscalyear_id.code))

        # Get balance sums
        account_sums = account_obj.compute_revaluations(
            cr, uid, account_ids, period_ids, form.fiscalyear_id.id,
            form.revaluation_date, context=context)
        for account_id, account_tree in account_sums.iteritems():
            for currency_id, sums in account_tree.iteritems():
                new_currency_id = currency_id
                # If the method is 'other_bs', check if the account move
                # currency is declared in the currency table and get it
                if form.revaluation_method == 'other_bs':
                    currency = currency_obj.browse(cr, uid, currency_id, context=context)
                    if currency.id != company.currency_id.id and currency.name not in currency_codes_from_table:
                        raise osv.except_osv(
                            _("Error"),
                            _("The currency %s is not declared in the currency table.") % currency.name)
                    new_currency_id = currency_codes_from_table[currency.name]
                if not sums['balance']:
                    continue
                # Update sums with compute amount currency balance
                diff_balances = self._compute_unrealized_currency_gl(
                    cr, uid, new_currency_id, sums, form, context=context)
                account_sums[account_id][currency_id].update(diff_balances)
        # Create entries only after all computation have been done
        for account_id, account_tree in account_sums.iteritems():
            for currency_id, sums in account_tree.iteritems():
                new_currency_id = currency_id
                # If the method is 'other_bs', get the account move currency in
                # the currency table
                if form.revaluation_method == 'other_bs':
                    currency = currency_obj.browse(cr, uid, currency_id, context=context)
                    new_currency_id = currency_codes_from_table[currency.name]
                adj_balance = sums.get('unrealized_gain_loss', 0.0)
                if not adj_balance:
                    continue

                rate = sums.get('currency_rate', 0.0)
                label = self._format_label(
                    cr, uid, form.label, account_id, new_currency_id, rate)

                # Write an entry to adjust balance
                move_id, new_ids = self._write_adjust_balance(
                    cr, uid,
                    account_id, currency_id, False, adj_balance,
                    label, form, sums, context=context)
                created_ids.extend(new_ids)
                # Create a second journal entry that will offset the first one
                # if the revaluation method is 'Other B/S'
                if form.revaluation_method == 'other_bs':
                    move_id, rev_line_ids = self._reverse_other_bs_move_lines(
                        cr, uid, form, move_id, new_ids, context=context)
                    created_ids.extend(rev_line_ids)

        if created_ids:
            # Set all booking amount to 0 for revaluation lines
            cr.execute('UPDATE account_move_line '
                       'SET debit_currency = 0, credit_currency = 0'
                       'WHERE id IN %s', (tuple(created_ids),))
            # Return the view
            return {'domain': "[('id','in', %s)]" % (created_ids,),
                    'name': _("Created revaluation lines"),
                    'view_type': 'form',
                    'view_mode': 'tree,form',
                    'auto_search': True,
                    'res_model': 'account.move.line',
                    'view_id': False,
                    'search_view_id': False,
                    'type': 'ir.actions.act_window'}
        else:
            raise osv.except_osv(_("Warning"),
                                 _("No revaluation accounting entry have been posted."))

    def _get_next_fiscalyear_id(self, cr, uid, fiscalyear_id, context=None):
        """Return the next fiscal year ID."""
        if context is None:
            context = {}
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        fiscalyear = fiscalyear_obj.browse(
            cr, uid, fiscalyear_id, context=context)
        date_stop = datetime.datetime.strptime(
            fiscalyear.date_stop, '%Y-%m-%d')
        next_year_start = date_stop + relativedelta(years=1)
        next_fiscalyear_ids = fiscalyear_obj.search(
            cr, uid,
            [('state', '=', 'draft'),
             ('date_start', '<=', next_year_start.strftime('%Y-%m-%d')),
             ('date_stop', '>=', next_year_start.strftime('%Y-%m-%d'))],
            context=context)
        if not next_fiscalyear_ids:
            raise osv.except_osv(
                _("Error"),
                _("The next fiscal year does not exist."))
        return next_fiscalyear_ids[0]

    def _get_first_fiscalyear_period_id(self, cr, uid, fiscalyear_id, context=None):
        """Return the first period ID of a fiscal year."""
        if context is None:
            context = {}
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        period_obj = self.pool.get('account.period')
        period_ids = period_obj.search(
            cr, uid,
            [('fiscalyear_id', '=', fiscalyear_id), ('number', '=', 1)],
            context=context)
        if not period_ids:
            fiscalyear = fiscalyear_obj.browse(
                cr, uid, fiscalyear_id, context=context)
            raise osv.except_osv(
                _("Error"),
                _("No first period found in the fiscal year %s.") % (
                    fiscalyear.name))
        return period_ids[0]

    def _reverse_other_bs_move_lines(
            self, cr, uid, form, move_id, line_ids, context=None):
        """Reverse 'Other B/S' revaluation entries."""
        if context is None:
            context = {}
        move_obj = self.pool.get('account.move')
        line_obj = self.pool.get('account.move.line')
        aal_obj = self.pool.get('account.analytic.line')
        period_obj = self.pool.get('account.period')
        # Get reserved move
        rev_move = move_obj.browse(cr, uid, move_id, context=context)
        # Compute the posting date:
        # Get the stop date of the next period, or the first period of the next
        # fiscal year if the selected period is 'Period 13' 
        posting_date = form.result_period_id.date_stop
        period_id = form.result_period_id.id
        if form.result_period_id.number == 13:
            # Get the first period of the next fiscal year and its date stop as
            # posting date
            fiscalyear_id = self._get_next_fiscalyear_id(
                cr, uid, form.fiscalyear_id.id, context=context)
            period_id = self._get_first_fiscalyear_period_id(
                cr, uid, fiscalyear_id, context=context)
            period = period_obj.browse(cr, uid, period_id, context=context)
            posting_date = period.date_stop
        # Create a new move
        move_vals = {
            'journal_id': form.journal_id.id,
            'period_id': period_id,
            'date': posting_date,
            'ref': rev_move.ref,
        }
        move_id = move_obj.create(cr, uid, move_vals, context=context)
        # Reverse lines + associate them to the newly created move
        rev_line_ids = []
        for line in line_obj.browse(cr, uid, line_ids, context=context):
            # Prepare default value for new line
            vals = {
                'move_id': move_id,
                'date': posting_date,
                'document_date': posting_date,
                'journal_id': form.journal_id.id,
                'period_id': period_id,
            }
            # Copy the line
            rev_line_id = line_obj.copy(cr, uid, line.id, vals, context=context)
            # Do the reverse
            amt = -1 * line.amount_currency
            vals.update({
                'debit': line.credit,
                'credit': line.debit,
                'amount_currency': amt,
                'journal_id': form.journal_id.id,
                'name': line_obj.join_without_redundancy(line.name, 'REV'),
                'reversal_line_id': line.id,
                'account_id': line.account_id.id,
                'source_date': line.date,
                'reversal': True,
                'reference': line.move_id and line.move_id.name or '',
                'ref': line.move_id and line.move_id.name or '',
            })
            line_obj.write(cr, uid, [rev_line_id], vals, context=context)
            # Inform old line that it have been corrected
            #line_obj.write(
            #    cr, uid, [line.id],
            #    {'corrected': True, 'have_an_historic': True},
            #    context=context)
            # Search analytic lines from first move line
            aal_ids = aal_obj.search(cr, uid, [('move_id', '=', line.id)])
            aal_obj.write(cr, uid, aal_ids, {'is_reallocated': True})
            # Search analytic lines from reversed line and flag them as "is_reversal"
            new_aal_ids = aal_obj.search(cr, uid, [('move_id', '=', rev_line_id)])
            aal_obj.write(cr, uid, new_aal_ids, {'is_reversal': True,})
            rev_line_ids.append(rev_line_id)
        # Hard post the move
        move_obj.post(cr, uid, [move_id], context=context)
        return move_id, rev_line_ids

WizardCurrencyrevaluation()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
