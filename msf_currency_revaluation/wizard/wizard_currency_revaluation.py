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

from datetime import date

from osv import osv, fields
from tools.translate import _

class WizardCurrencyrevaluation(osv.osv_memory):
    _name = 'wizard.currency.revaluation'

    _columns = {'revaluation_date': fields.date(
                    'Revaluation Date', readonly=True),
                'revaluation_method': fields.selection(
                    [('liquidity', u"Liquidity"),
                     ('other_bs', u"Other B/S"),
                     ],
                    string=u"Revaluation method", required=True),
                'fiscalyear_id': fields.many2one(
                    'account.fiscalyear', string=u"Fiscal year",
                    domain=[('state', '=', 'draft')],
                    required=True),
                'period_id': fields.many2one(
                    'account.period', string=u"Period",
                    domain="[('fiscalyear_id', '=', fiscalyear_id), ('state', '!=', 'created')]"),
                'currency_table_id': fields.many2one(
                    'res.currency.table', string=u"Currency table",
                    domain=[('state', '=', 'valid')],
                    required=True),
                'journal_id': fields.many2one(
                    'account.journal', string=_("Entry journal"),
                    #domain="[('type','=','general')]",
                    help=_("Journal used for revaluation entries."),
                    readonly=True),
                'result_period_id': fields.many2one(
                    'account.period', string=_(u"Entry period"),
                    domain="[('fiscalyear_id', '=', fiscalyear_id), ('state', '!=', 'created')]",
                    help=_("Period used for revaluation entries.")),
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
        current_date = date.today().strftime('%Y-%m-%d')
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        fiscalyear_ids = fiscalyear_obj.search(
            cr, uid,
            [('date_start', '<', current_date),
             ('date_stop', '>', current_date),
             ('company_id', '=', cp.id)],
            limit=1,
            context=context)
        return fiscalyear_ids and fiscalyear_ids[0] or False

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

    _defaults = {
        'label': "%(currency)s %(account)s %(rate)s currency revaluation",
        'revaluation_method': lambda *args: 'liquidity',
        #'revaluation_date': _get_default_revaluation_date,
        'fiscalyear_id': _get_default_fiscalyear_id,
        'result_period_id': _get_default_result_period_id,
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
            if period_id:
                period = period_obj.browse(cr, uid, period_id)
                value['revaluation_date'] = period.date_stop
        else:
            value['revaluation_date'] = fiscalyear.date_stop
        res = {'value': value, 'warning': warning}
        return res

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
                         'document_date': form.revaluation_date,
                         'date': form.revaluation_date}
            return move_obj.create(cr, uid, base_move, context=context)

        def create_move_line(move_id, line_data, sums):
            base_line = {'name': "Revaluation - %s" % form.fiscalyear_id.name,
                         #'partner_id': partner_id,
                         'currency_id': currency_id,
                         'amount_currency': 0.0,
                         'document_date': form.revaluation_date,
                         'date': form.revaluation_date,
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
        user_obj = self.pool.get('res.users')
        distrib_obj = self.pool.get('analytic.distribution')
        cc_distrib_obj = self.pool.get('cost.center.distribution.line')
        fp_distrib_obj = self.pool.get('funding.pool.distribution.line')
        model_data_obj = self.pool.get('ir.model.data')

        company = user_obj.browse(cr, uid, uid).company_id
        account = account_obj.browse(cr, uid, account_id, context=context)
        revaluation_account_id = model_data_obj.get_object_reference(
            cr, uid, 'msf_chart_of_account', '6940')[1]

        # Prepare the analytic distribution for the account revaluation entry
        # if the account has a 'expense' or 'income' type
        distribution_id = False
        if account.user_type.code in ['expense', 'income']:
            destination_id = model_data_obj.get_object_reference(
                cr, uid, 'analytic_distribution', 'analytic_account_destination_support')[1]
            cost_center_id = model_data_obj.get_object_reference(
                cr, uid, 'analytic_distribution', 'analytic_account_project_intermission')[1]
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
                'source_date': form.revaluation_date,
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
                'source_date': form.revaluation_date,
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
                    'account_id': revaluation_account_id,
                }
                created_ids.append(create_move_line(move_id, line_data, sums))
                # Create a move line to Credit revaluation gain account
                line_data = {
                    'credit': amount,
                    'credit_currency': False,
                    'account_id': account_id,
                    'move_id': move_id,
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
                    'account_id': account_id,
                    'analytic_distribution_id': distribution_id,
                }

                created_ids.append(create_move_line(move_id, line_data, sums))
                # Create a move line to Credit account to be revaluated
                line_data = {
                    'credit': amount,
                    'move_id': move_id,
                    'account_id': revaluation_account_id,
                }
                created_ids.append(create_move_line(move_id, line_data, sums))
        return created_ids

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
        context['currency_table_id'] = form.currency_table_id.id

        # Get all currency names to map them with main currencies later
        currency_codes_from_table = {}
        for currency in form.currency_table_id.currency_ids:
            # Check the revaluation date and dates in the currency table
            #if currency.date != form.revaluation_date:
            #    raise osv.except_osv(
            #        _("Error"),
            #        _("The revaluation date seems to differ with the data of "
            #          "the currency table."))
            currency_codes_from_table[currency.name] = currency.id

        # Search for accounts Balance Sheet or Liquidity to be eevaluated
        account_ids = []
        if form.revaluation_method == 'liquidity':
            account_ids = account_obj.search(
                cr, uid,
                [('currency_revaluation', '=', True), ('type', '=', 'liquidity')],
                 #('user_type.close_method', '!=', 'none'),
                context=context)
        elif form.revaluation_method == 'other_bs':
            account_ids = account_obj.search(
                cr, uid,
                [('currency_revaluation', '=', True), ('type', '!=', 'liquidity')],
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
                                 _('No special period found for the fiscalyear %s' %
                                   form.fiscalyear_id.code))

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

        period_ids = [p.id for p in form.fiscalyear_id.period_ids]
        if form.revaluation_method == 'other_bs':
            if not period_ids:
                raise osv.except_osv(
                    _('Error!'),
                    _('No period found for the fiscalyear %s' % (
                        form.fiscalyear_id.code,)))
        else:
            period_ids = [form.period_id.id]

        # Get balance sums
        account_sums = account_obj.compute_revaluations(
            cr, uid, account_ids, period_ids, form.revaluation_date, context=context)
        for account_id, account_tree in account_sums.iteritems():
            for currency_id, currency_tree in account_tree.iteritems():
                # Check if the account move currency is declared in the
                # currency table
                currency = currency_obj.browse(cr, uid, currency_id, context=context)
                if currency.id != company.currency_id.id and currency.name not in currency_codes_from_table:
                    raise osv.except_osv(
                        _("Error"),
                        _("The currency %s is not declared in the currency table." % currency.name))
                new_currency_id = currency_codes_from_table[currency.name]
                for partner_id, sums in currency_tree.iteritems():
                    if not sums['balance']:
                        continue
                    # Update sums with compute amount currency balance
                    diff_balances = self._compute_unrealized_currency_gl(
                        cr, uid, new_currency_id, sums, form, context=context)
                    account_sums[account_id][currency_id][partner_id].update(
                        diff_balances)
        # Create entries only after all computation have been done
        for account_id, account_tree in account_sums.iteritems():
            for currency_id, currency_tree in account_tree.iteritems():
                new_currency_id = currency_codes_from_table[currency.name]
                for partner_id, sums in currency_tree.iteritems():
                    adj_balance = sums.get('unrealized_gain_loss', 0.0)
                    if not adj_balance:
                        continue

                    rate = sums.get('currency_rate', 0.0)
                    label = self._format_label(
                        cr, uid, form.label, account_id, new_currency_id, rate)

                    # Write an entry to adjust balance
                    new_ids = self._write_adjust_balance(
                        cr, uid,
                        account_id, currency_id, partner_id, adj_balance,
                        label, form, sums, context=context)
                    created_ids.extend(new_ids)

        if created_ids:
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
                                 _("No accounting entry have been posted."))

WizardCurrencyrevaluation()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
