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

from osv import osv
from osv import fields
from tools.translate import _


class res_company(osv.osv):
    """
    account CoA config override
    """
    _inherit = 'res.company'

    _columns = {
        # US-822 counterpart for BS account
        'ye_pl_cp_for_bs_debit_bal_account': fields.many2one('account.account',
                                                             'Counterpart for B/S debit balance',
                                                             domain=['|', ('user_type.code', 'in', ('income', 'expense', 'equity')), '&', ('type', '=', 'other'), ('user_type.code', '=', 'equity')]),
        'ye_pl_cp_for_bs_credit_bal_account': fields.many2one('account.account',
                                                              'Counterpart for B/S credit balance',
                                                              domain=['|', ('user_type.code', 'in', ('income', 'expense')), '&', ('type', '=', 'other'), ('user_type.code', '=', 'equity')]),

        # US-822 PL/BS matrix of dev2/dev3 accounts"
        'ye_pl_pos_credit_account': fields.many2one('account.account',
                                                    'Credit Account for P&L>0 (Income account)',
                                                    domain=[('user_type.code', '=', 'income')]),
        'ye_pl_pos_debit_account': fields.many2one('account.account',
                                                   'Debit Account for P&L>0 (B/S account)',
                                                   domain=[('type', '=', 'other'), ('user_type.code', '=', 'equity')]),
        'ye_pl_ne_credit_account': fields.many2one('account.account',
                                                   'Credit Account P&L<0 (B/S account)',
                                                   domain=[('type', '=', 'other'), ('user_type.code', '=', 'equity')]),
        'ye_pl_ne_debit_account': fields.many2one('account.account',
                                                  'Debit Account P&L<0 (Expense account)',
                                                  domain=[('user_type.code', '=', 'expense')]),
    }

res_company()


class account_account(osv.osv):
    """
    account CoA config override
    """
    _inherit = 'account.account'

    _columns = {
        'include_in_yearly_move': fields.boolean("Include in Yearly move to 0"),
    }

    _defaults = {
        'include_in_yearly_move': False,
    }

account_account()


class account_period(osv.osv):
    _inherit = "account.period"

    _columns = {
        'active': fields.boolean('Active'),
    }

    _defaults = {
        'active': lambda *a: True,
    }

    # period 0 not available for picking in journals/selector/reports
    # except for following reports: general ledger, trial balance, balance sheet
    # => always hide Period 0 except if 'show_period_0' found in context
    def search(self, cr, uid, args, offset=0, limit=None, order=None,
               context=None, count=False):
        if context is None:
            context = {}

        if context.get('show_period_0', False):
            if not args:
                args = []
            active_filter = False
            for a in args:
                if len(a) == 3:
                    if a[0] == 'active':
                        # existing global system filter exists: let it
                        active_filter = True
                        break
            if not active_filter:
                args.append(('active', 'in', ['t', 'f']))

        res = super(account_period, self).search(cr, uid, args, offset=offset,
                                                 limit=limit, order=order, context=context, count=count)
        return res

account_period()


class account_year_end_closing(osv.osv):
    _name = "account.year.end.closing"
    _auto = False

    # valid special period numbers and their month
    _period_month_map = { 0: 1, 16: 12, }

    _journals = {
        'EOY': 'End of Year',
        'IB': 'Initial Balances',
    }

    # IMPORTANT NOTE: be aware that this pattern is used by OCP VI
    # to search PL RESULT entries to export with December
    _book_pl_results_seqnum_pattern = "EOY-%d-%s-%s-PL-RESULT"

    def process_closing(self, cr, uid, fy_rec,
                        has_move_regular_bs_to_0=False, has_book_pl_results=False,
                        context=None):
        level = self.check_before_closing_process(cr, uid, fy_rec,
                                                  context=context)
        if level == 'coordo':
            # generate closing entries at coordo level
            if fy_rec.date_start != '2014-01-01':  # no entries for FY14
                self.setup_journals(cr, uid, context=context)
                if has_move_regular_bs_to_0:
                    self.move_bs_accounts_to_0(cr, uid, fy_rec, context=context)
                if has_book_pl_results:
                    self.book_pl_results(cr, uid, fy_rec, context=context)
                self.report_bs_balance_to_next_fy(cr, uid, fy_rec, context=context)
        self.update_fy_state(cr, uid, fy_rec.id, context=context)

    def _get_mission_ids_from_coordo(self, cr, uid, coo_id, context=None):
        res = self.pool.get('msf.instance').search(cr, uid,
                                                   [('parent_id', '=', coo_id), ], context=context) or []
        res.insert(0, coo_id)
        return res

    def check_before_closing_process(self, cr, uid, fy_rec, context=None):
        """
        :return: instance level
        :rtype: str
        """
        instance_id = self.pool.get('res.users').browse(cr, uid, [uid],
                                                        context=context)[0].company_id.instance_id
        level = instance_id.level
        if level not in ('section', 'coordo', ):
            raise osv.except_osv(_('Warning'),
                                 _('You can only close FY at HQ or Coordo'))

        # check FY closable regarding level
        if fy_rec:
            field = False
            if level == 'coordo':
                field = 'is_mission_closable'
            elif level == 'section':
                field = 'is_hq_closable'
            if not field or not getattr(fy_rec, field):
                raise osv.except_osv(_('Warning'),
                                     _('FY can not be closed due to its state or' \
                                       ' its periods state; or previous FY not closed'))

            if level == 'coordo':
                nb_local_period_ids = self.pool.get('account.period').search(cr, uid,
                                                                             [('fiscalyear_id', '=', fy_rec.id), ('number', 'not in', [0, 16])], context=context)
                cr.execute('''
                    select
                        m.code
                    from
                        msf_instance m
                        left join account_period_state s on
                            s.instance_id = m.id and
                            s.period_id in %s and
                            s.state in ('mission-closed', 'done')
                    where
                        m.state != 'inactve' and
                        m.parent_id = %s
                    group by
                        m.code, m.id
                    having
                        count(s.id) != %s
                ''', (tuple(nb_local_period_ids), instance_id.id, len(nb_local_period_ids)))
                not_closed = [x[0] for x in cr.fetchall()]
                if not_closed:
                    if len(not_closed) > 10:
                        not_closed = not_closed[0:10] + ['+%d' % (len(not_closed)-10)]
                    msg = _('Periods are not at least mission-closed on the following projects:\n%s') % (
                        ', '.join(not_closed), )
                    raise osv.except_osv(_('Warning'), msg)

            # HQ level: check that all coordos have their FY mission closed
            elif level == 'section':
                mi_obj = self.pool.get('msf.instance')
                ci_ids = mi_obj.search(cr, uid, [
                    ('parent_id', '=', instance_id.id),
                    ('level', '=', 'coordo'),
                    ('state', '!=', 'inactive'),
                ], context=context)
                if ci_ids:
                    afs_obj = self.pool.get("account.fiscalyear.state")
                    # check that we have same count of mission-closed fy
                    # in fy report than in true coordos
                    # => so all have sync up their fy state report
                    closed_afs_ids = afs_obj.search(cr, uid, [
                        ('fy_id', '=', fy_rec.id),
                        ('instance_id', 'in', ci_ids),
                        ('state', 'in', ('mission-closed', 'done', )),
                    ], context=context)
                    closed_ci_ids = []
                    if closed_afs_ids:
                        closed_ci_ids = [ afs.instance_id.id \
                                          for afs in afs_obj.browse(cr, uid, closed_afs_ids,
                                                                    context=context) ]
                    if len(closed_ci_ids) != len(ci_ids):
                        # enumerate left open coordos for user info warn message
                        wrong_ci_ids = [ id for id in ci_ids if id not in closed_ci_ids ]
                        if wrong_ci_ids:
                            codes = [ rec.code for rec \
                                      in mi_obj.browse(cr, uid, wrong_ci_ids,
                                                       context=context) ]
                        else:
                            # fy state report not all sync up: generic warn message
                            codes = [ _('All'), ]
                        msg = _('%s Coordo(s): proceed year end closing' \
                                ' first') % (
                            ', '.join(codes), )
                        raise osv.except_osv(_('Warning'), msg)


            # check next FY exists (we need FY+1 Period 0 for initial balances)
            if not self._get_next_fy_id(cr, uid, fy_rec, context=context):
                raise osv.except_osv(_('Warning'),
                                     _('FY+1 required to close FY'))

        return level

    def create_periods(self, cr, uid, fy_id, periods_to_create=[0, 16],
                       context=None):
        """
        create closing special periods 0/16 for given FY
        :param fy_id: fy id to create periods in
        """
        period_obj = self.pool.get('account.period')
        period_numbers = [ pn for pn in periods_to_create \
                           if pn in list(self._period_month_map.keys()) ]
        fy_rec = self._browse_fy(cr, uid, fy_id, context=context)
        fy_year = fy_rec.date_start[:4]

        for pn in period_numbers:
            period_year_month = (fy_year, self._period_month_map[pn], )
            code = "Period %d %s" % (pn, fy_year)
            if not period_obj.search(cr, uid, [('fiscalyear_id', '=', fy_id), ('number', '=', pn), ('active', 'in', ['t', 'f'])],
                                     order='NO_ORDER', context=context):
                vals = {
                    'name': code,
                    'code': code,
                    'number': pn,
                    'special': True,
                    'date_start': '%s-%02d-01' % period_year_month,
                    'date_stop': '%s-%02d-31' % period_year_month,
                    'fiscalyear_id': fy_id,
                    'state': 'draft',  # opened by default
                    'active': pn != 0, # 0 period hidden by default
                }

                period_obj.create(cr, uid, vals,
                                  context=context)

    def setup_journals(self, cr, uid, context=None):
        """
        create GL coordo year end system journals if missing for the instance
        """
        instance_rec = self.pool.get('res.users').browse(cr, uid, [uid],
                                                         context=context)[0].company_id.instance_id
        if instance_rec.level != 'coordo':
            return
        if context is None:
            context = {}
        local_context = context.copy()
        local_context['allow_journal_system_create'] = True

        for code in self._journals:
            id = self._get_journal(cr, uid, code, context=context)
            if not id:
                # create missing journal
                vals = {
                    'instance_id': instance_rec.id,
                    'code': code,
                    'name': self._journals[code],
                    'type': 'system',  # excluded from selection picker
                    'analytic_journal_id': False,  # no AJI year end entries
                }
                self.pool.get('account.journal').create(cr, uid, vals,
                                                        context=local_context)

    def delete_year_end_entries(self, cr, uid, fy_id, context=None):
        """
        Cancel the FY year end entries FOR THE INSTANCE
        - delete all entries of 'year end' 'initial balance' journals
            for the coordo in FY Period 16 and FY+1 Period O
        - do that in sql to bypass the forbid delete of posted entries
        """
        fy_rec = self._browse_fy(cr, uid, fy_id, context=context)
        journal_ids = self._get_journals(cr, uid, context=context)
        period_ids = self._get_periods_ids(cr, uid, fy_rec, context=context)

        # get/delete JIs/JEs entries...
        domain = [
            ('journal_id', 'in', journal_ids),
            ('period_id', 'in', period_ids),
        ]
        to_del_objs = [ self.pool.get(m) \
                        for m in ('account.move.line', 'account.move', ) ]  # in del order
        for o in to_del_objs:
            ids = o.search(cr, uid, domain, context=context)
            if ids:
                o.unlink(cr, uid, ids, context=context)

    def move_bs_accounts_to_0(self, cr, uid, fy_rec, context=None):
        """
        action 1
        """
        def create_journal_entry(ccy_id=False, ccy_code='', account_id=False,
                                 account_code=''):
            """
            create draft CCY/JE to log JI into
            """
            name = "EOY-%d-%s-%s-%s" % (fy_year, account_code,
                                        instance_rec.code, ccy_code, )

            vals = {
                'block_manual_currency_id': True,
                'company_id': cpy_rec.id,
                'currency_id': ccy_id,
                'date': last_day_fy,
                'document_date': last_day_fy,
                'instance_id': instance_rec.id,
                'journal_id': journal_id,
                'name': name,
                'period_id': period_id,
            }
            return self.pool.get('account.move').create(cr, uid, vals,
                                                        context=local_context)

        def create_journal_item(ccy_id=False, ccy_code='', account_id=False,
                                account_code='', balance_currency=0., balance=0., je_id=False):
            """
            create state valid JI in its CCY/JE
            """
            name = 'Balance move to 0'

            vals = {
                'account_id': account_id,
                'company_id': cpy_rec.id,
                'currency_id': ccy_id,
                'date': last_day_fy,
                'document_date': last_day_fy,
                'instance_id': instance_rec.id,
                'journal_id': journal_id,
                'name': name,
                'period_id': period_id,
                'source_date': last_day_fy,

                'debit_currency': \
                balance_currency if balance_currency > 0. else 0.,
                'credit_currency': \
                abs(balance_currency) if balance_currency < 0. else 0.,

                'move_id': je_id,
            }
            id = self.pool.get('account.move.line').create(cr, uid, vals,
                                                           context=local_context)

            # aggregated functional amount (sum) fx rate agnostic: raw write
            vals = {
                'debit': balance if balance > 0. else 0.,
                'credit': abs(balance) if balance < 0. else 0.,
                'state':'valid',
            }
            osv.osv.write(self.pool.get('account.move.line'), cr, uid, [id],
                          vals, context=context)

        cpy_rec = self.pool.get('res.users').browse(cr, uid, [uid],
                                                    context=context)[0].company_id
        if not cpy_rec.ye_pl_cp_for_bs_debit_bal_account \
                or not cpy_rec.ye_pl_cp_for_bs_credit_bal_account:
            raise osv.except_osv(_('Error'),
                                 _("B/S counterparts accounts credit/debit not set" \
                                   " in company settings 'B/S Move to 0 accounts'"))
        instance_rec = cpy_rec.instance_id
        instance_ids = self._get_mission_ids_from_coordo(cr, uid,
                                                         instance_rec.id, context=context)

        fy_year = self._get_fy_year(cr, uid, fy_rec, context=context)
        last_day_fy = "%d-12-31" % (fy_year, )

        journal_code = 'EOY'
        journal_id = self._get_journal(cr, uid, journal_code, context=context)
        if not journal_id:
            raise osv.except_osv(_('Error'),
                                 _('%s journal not found') % (journal_code, ))

        period_number = 16
        period_id = self._get_period_id(cr, uid, fy_rec.id, period_number,
                                        context=context)
        if not period_id:
            raise osv.except_osv(_('Error'),
                                 _("FY 'Period %d' not found") % (period_number, ))

        # local context for transac
        # (write sum of booking and functional fx rate agnostic)
        local_context = context.copy() if context else {}

        # compute balance for ticked accounts, exclude period 16 itself
        sql = '''select ml.account_id as account_id, max(a.code) as account_code,
            ml.currency_id as currency_id, max(c.name) as currency_code,
            (sum(ml.debit_currency) - sum(ml.credit_currency)) as balance_currency,
            (sum(ml.debit) - sum(ml.credit)) as balance,
            ml.reconcile_id, ml.reconcile_partial_id
            from account_move_line ml
            inner join account_move m on m.id = ml.move_id
            inner join account_account a on a.id = ml.account_id
            inner join res_currency c on c.id = ml.currency_id
            inner join account_period p on ml.period_id = p.id
            where ml.instance_id in %s and a.include_in_yearly_move = 't'
            and ml.date >= %s and ml.date <= %s and m.period_id != %s
            and p.number != 0
            group by ml.account_id, ml.currency_id, ml.reconcile_id, ml.reconcile_partial_id
        '''
        cr.execute(sql, (tuple(instance_ids), fy_rec.date_start,
                         fy_rec.date_stop, period_id, ))
        if not cr.rowcount:
            return

        je_by_acc_ccy = {}  # JE/ ACC/CCY, key: (acc_id, ccy_id), value: JE id
        for account_id, account_code, ccy_id, ccy_code, \
                balance_currency, balance, reconcile_id, reconcile_partial_id in cr.fetchall():
            if reconcile_id or reconcile_partial_id:
                raise osv.except_osv(_('Warning'),
                                     _("The yearly closure can't be processed due to one or several reconciled entries "
                                       "that are included in the move to 0."))
            balance_currency = float(balance_currency)
            balance = float(balance)

            # get counterpart account
            if balance_currency > 0:  # debit balance
                cp_account = cpy_rec.ye_pl_cp_for_bs_debit_bal_account
            else:
                cp_account = cpy_rec.ye_pl_cp_for_bs_credit_bal_account

             # CCY JE
            je_id = je_by_acc_ccy.get((account_id, ccy_id, ), False)
            if not je_id:
                # 1st processing of a ccy: create its JE
                je_id = create_journal_entry(ccy_id=ccy_id, ccy_code=ccy_code,
                                             account_id=account_id, account_code=account_code)
                je_by_acc_ccy[(account_id, ccy_id, )] = je_id

            # 2 entries tied to their CCY JE
            # per ccy/account item move to 0: inversed balance
            create_journal_item(ccy_id=ccy_id, ccy_code=ccy_code,
                                account_id=account_id, account_code=account_code,
                                balance_currency=balance_currency*-1, balance=balance*-1,
                                je_id=je_id)
            # and counterpart (balance)
            create_journal_item(ccy_id=ccy_id, ccy_code=ccy_code,
                                account_id=cp_account.id, account_code=cp_account.code,
                                balance_currency=balance_currency, balance=balance,
                                je_id=je_id)

    def book_pl_results(self, cr, uid, fy_rec, context=None):
        """
        action 2
        """
        def create_journal_entry():
            """
            create draft CCY/JE to log JI into
            """
            name = self._book_pl_results_seqnum_pattern % (fy_year,
                                                           instance_rec.code, cpy_rec.currency_id.name, )

            vals = {
                'block_manual_currency_id': True,
                'company_id': cpy_rec.id,
                'currency_id': cpy_rec.currency_id.id,
                'date': posting_date,
                'document_date': posting_date,
                'instance_id': instance_rec.id,
                'journal_id': journal_id,
                'name': name,
                'period_id': period_id,
            }
            return self.pool.get('account.move').create(cr, uid, vals,
                                                        context=local_context)

        def create_journal_item(account_rec, balance, je_id=False):
            """
            create state valid JI in its CCY/JE
            """
            name = 'P&L Result'

            vals = {
                'account_id': account_rec.id,
                'company_id': cpy_rec.id,
                'currency_id': cpy_rec.currency_id.id,
                'date': posting_date,
                'document_date': posting_date,
                'instance_id': instance_rec.id,
                'journal_id': journal_id,
                'name': name,
                'period_id': period_id,

                'move_id': je_id,
            }
            id = self.pool.get('account.move.line').create(cr, uid, vals,
                                                           context=local_context)

            # aggregated functional amount (sum) fx rate agnostic: raw write
            vals = {
                'debit_currency': balance if balance > 0. else 0.,
                'credit_currency': abs(balance) if balance < 0. else 0.,
                'debit': balance if balance > 0. else 0.,
                'credit': abs(balance) if balance < 0. else 0.,
                'state':'valid',
            }
            osv.osv.write(self.pool.get('account.move.line'), cr, uid, [id],
                          vals, context=context)

        cpy_rec = self.pool.get('res.users').browse(cr, uid, [uid],
                                                    context=context)[0].company_id
        if not cpy_rec.ye_pl_pos_credit_account \
            or not cpy_rec.ye_pl_pos_debit_account \
            or not cpy_rec.ye_pl_ne_credit_account \
                or not cpy_rec.ye_pl_ne_debit_account:
            raise osv.except_osv(_('Error'),
                                 _("Accounts not set in company settings \"Fiscal Year Closure\""))
        instance_rec = cpy_rec.instance_id
        instance_ids = self._get_mission_ids_from_coordo(cr, uid,
                                                         instance_rec.id, context=context)

        fy_year = self._get_fy_year(cr, uid, fy_rec, context=context)
        posting_date = "%d-12-31" % (fy_year, )

        journal_code = 'EOY'
        journal_id = self._get_journal(cr, uid, journal_code, context=context)
        if not journal_id:
            raise osv.except_osv(_('Error'),
                                 _('%s journal not found') % (journal_code, ))

        period_number = 16
        period_id = self._get_period_id(cr, uid, fy_rec.id, period_number,
                                        context=context)
        if not period_id:
            raise osv.except_osv(_('Error'),
                                 _("FY 'Period %d' not found") % (period_number, ))

        # local context for transac
        # (write sum of booking and functional fx rate agnostic)
        local_context = context.copy() if context else {}

        # P/L accounts BAL TOTAL in functional ccy
        # date inclusion to have period 0/1-15/16
        sql = '''select (sum(ml.debit) - sum(ml.credit)) as bal
            from account_move_line ml
            inner join account_account a on a.id = ml.account_id
            inner join account_account_type t on t.id = a.user_type
            where ml.instance_id in %s
            and t.report_type in ('income', 'expense')
            and ml.date >= %s and ml.date <= %s
        '''
        cr.execute(sql, (tuple(instance_ids), fy_rec.date_start,
                         fy_rec.date_stop, ))
        if not cr.rowcount:
            return
        # US-1068: if no result, empty 1 row result is returned bc use of an
        # aggregate function (sum() here)
        row = cr.fetchone()
        if row[0] is None:
            return

        balance = float(row[0])
        if balance > 0:  # debit balance
            account = cpy_rec.ye_pl_pos_credit_account  # Credit Account for P&L>0 (Income account)
            cp_account = cpy_rec.ye_pl_pos_debit_account  # Debit Account for P&L>0 (B/S account)
        else:
            account = cpy_rec.ye_pl_ne_debit_account  # Debit Account P&L<0 (Expense account)
            cp_account = cpy_rec.ye_pl_ne_credit_account  # Credit Account P&L<0 (B/S account)
        # invert balance amount to debit or credit amount after account dispatch
        balance *= -1

        je_id = create_journal_entry()
        create_journal_item(account, balance, je_id=je_id)
        create_journal_item(cp_account, balance*-1, je_id=je_id)  # counterpart

    def report_bs_balance_to_next_fy(self, cr, uid, fy_rec, context=None):
        """
        action 3: report B/S balances to next FY period 0
        """

        def create_journal_entry(ccy_id=False, ccy_code='', account_id=False,
                                 account_code=''):
            """
            create draft CCY/JE to log JI into
            """
            name = "IB-%d-%s-%s-%s" % (fy_year + 1, account_code,
                                       instance_rec.code, ccy_code, )

            vals = {
                'block_manual_currency_id': True,
                'company_id': cpy_rec.id,
                'currency_id': ccy_id,
                'date': first_day_next_fy,
                'document_date': first_day_next_fy,
                'instance_id': instance_rec.id,
                'journal_id': journal_id,
                'name': name,
                'period_id': period_id,
            }
            return self.pool.get('account.move').create(cr, uid, vals,
                                                        context=local_context)

        def create_journal_item(ccy_id=False, ccy_code='', account_id=False,
                                account_code='', balance_currency=0., balance=0., je_id=False,
                                name=False):
            """
            create state valid JI in its CCY/JE
            """
            default_name = 'Balance report / Previous Fiscal Year'

            vals = {
                'account_id': account_id,
                'company_id': cpy_rec.id,
                'currency_id': ccy_id,
                'date': first_day_next_fy,
                'document_date': first_day_next_fy,
                'instance_id': instance_rec.id,
                'journal_id': journal_id,
                'name': name or default_name,
                'period_id': period_id,
                'source_date': first_day_next_fy,

                'debit_currency': \
                balance_currency if balance_currency > 0. else 0.,
                'credit_currency': \
                abs(balance_currency) if balance_currency < 0. else 0.,

                'move_id': je_id,
            }
            id = self.pool.get('account.move.line').create(cr, uid, vals,
                                                           context=local_context)

            # aggregated functional amount (sum) fx rate agnostic: raw write
            vals = {
                'debit': balance if balance > 0. else 0.,
                'credit': abs(balance) if balance < 0. else 0.,
                'state':'valid',
            }
            osv.osv.write(self.pool.get('account.move.line'), cr, uid, [id],
                          vals, context=context)

        # init
        # - company and instance
        # - check company config regular equity account (pl matrix: bs accounts)
        # - current FY year
        # - next FY id
        # - posting date
        # - IB journal
        # - next FY period 0
        # - local context
        cpy_rec = self.pool.get('res.users').browse(cr, uid, [uid],
                                                    context=context)[0].company_id
        if not cpy_rec.ye_pl_pos_debit_account \
                or not cpy_rec.ye_pl_ne_credit_account:
            raise osv.except_osv(_('Error'),
                                 _("Accounts not set in company settings \"Fiscal Year Closure\" (B/S accounts)"))
        instance_rec = cpy_rec.instance_id
        instance_ids = self._get_mission_ids_from_coordo(cr, uid,
                                                         instance_rec.id, context=context)

        fy_year = self._get_fy_year(cr, uid, fy_rec, context=context)
        next_fy_id = self._get_next_fy_id(cr, uid, fy_rec, context=context)
        first_day_next_fy = "%d-01-01" % (fy_year + 1, )

        journal_code = 'IB'
        journal_id = self._get_journal(cr, uid, journal_code, context=context)
        if not journal_id:
            raise osv.except_osv(_('Error'),
                                 _('%s journal not found') % (journal_code, ))

        period_number = 0
        period_id = self._get_period_id(cr, uid, next_fy_id, period_number,
                                        context=context)
        if not period_id:
            raise osv.except_osv(_('Error'),
                                 _("FY+1 'Period %d' not found") % (period_number, ))

        # local context for transac
        # (write sum of booking and functional fx rate agnostic)
        local_context = context.copy() if context else {}

        # P/L accounts BAL TOTAL in functional ccy
        # date inclusion to have period 0/1-15/16
        re_account_rec = False  # default no P&L result
        pl_balance = 0.
        sql = '''select (sum(ml.debit) - sum(ml.credit)) as bal
            from account_move_line ml
            inner join account_account a on a.id = ml.account_id
            inner join account_account_type t on t.id = a.user_type
            where ml.instance_id in %s
            and t.report_type in ('income', 'expense')
            and ml.date >= %s and ml.date <= %s
        '''
        cr.execute(sql, (tuple(instance_ids), fy_rec.date_start,
                         fy_rec.date_stop, ))
        if cr.rowcount:
            # US-1068: if no result, empty 1 row result is returned bc use of an
            # aggregate function (sum() here)
            row = cr.fetchone()
            if row[0] is not None:
                pl_balance = float(row[0])
                if pl_balance > 0:
                    # debit regular/equity result
                    re_account_rec = cpy_rec.ye_pl_pos_debit_account
                else:
                    # credit regular/equity result
                    re_account_rec = cpy_rec.ye_pl_ne_credit_account

        # compute B/S balance in BOOKING breakdown in BOOKING/account
        # date inclusion to have periods 0/1-15/16
        sql = '''select
            ml.account_id as account_id, max(a.code) as account_code,
            ml.currency_id as currency_id, max(c.name) as currency_code,
            (sum(ml.debit_currency) - sum(ml.credit_currency)) as balance_currency,
            (sum(ml.debit) - sum(ml.credit)) as balance
            from account_move_line ml
            inner join account_account a on a.id = ml.account_id
            inner join account_account_type t on t.id = a.user_type
            inner join res_currency c on c.id = ml.currency_id
            where ml.instance_id in %s
            and t.report_type in ('asset', 'liability')
            and ml.date >= %s and ml.date <= %s
            group by ml.account_id, ml.currency_id
        '''
        cr.execute(sql, (tuple(instance_ids), fy_rec.date_start,
                         fy_rec.date_stop, ))
        if not cr.rowcount:
            return

        je_by_acc_ccy = {}  # JE/ ACC/CCY, key: (acc_id, ccy_id), value: JE id
        for account_id, account_code, ccy_id, ccy_code, \
                balance_currency, balance in cr.fetchall():
            balance_currency = float(balance_currency)
            if balance is None and balance_currency == 0.:
                # US-1471 FUNC balance is empty AND booking balance is ZERO
                # => consider FUNC balance as ZERO
                # But in other cases leave the actual behaviour,
                # wiser to raise issue if FUNC BAL empty and BOOKING NOT ZERO
                balance = '0.0'  # US-1471
            balance = float(balance)

            # CCY JE
            je_id = je_by_acc_ccy.get((account_id, ccy_id, ), False)
            if not je_id:
                # 1st processing of a ccy: create its JE
                je_id = create_journal_entry(ccy_id=ccy_id, ccy_code=ccy_code,
                                             account_id=account_id, account_code=account_code)
                je_by_acc_ccy[(account_id, ccy_id, )] = je_id

            # per ccy/account initial balance item, tied to its CCY JE
            create_journal_item(ccy_id=ccy_id, ccy_code=ccy_code,
                                account_id=account_id, account_code=account_code,
                                balance_currency=balance_currency, balance=balance, je_id=je_id)

        if re_account_rec:
            # Regular/Equity account result entry for P&L
            # => invert balance amount to debit or credit amount after account dispatch
            je_id = je_by_acc_ccy.get(
                (re_account_rec.id, cpy_rec.currency_id.id, ), False)
            if not je_id:
                je_id = create_journal_entry(ccy_id=ccy_id,
                                             ccy_code=cpy_rec.currency_id.name,
                                             account_id=re_account_rec.id,
                                             account_code=re_account_rec.code)
            create_journal_item(ccy_id=cpy_rec.currency_id.id,
                                ccy_code=cpy_rec.currency_id.name,
                                account_id=re_account_rec.id, account_code=re_account_rec.code,
                                balance_currency=pl_balance, balance=pl_balance, je_id=je_id,
                                name="P&L Result report / Previous Fiscal Year")

    def update_fy_state(self, cr, uid, fy_id, reopen=False, context=None):
        def hq_close_post_entries(period_ids):
            am_obj = self.pool.get('account.move')
            am_ids = am_obj.search(cr, uid, [
                ('period_id', 'in', period_ids),
                ('state', '!=', 'posted')
            ], context=context)
            if am_ids:
                am_obj.write(cr, uid, am_ids, {'state': 'posted', },
                             context=context)

        instance_rec = self.pool.get('res.users').browse(cr, uid, [uid],
                                                         context=context)[0].company_id.instance_id
        state = False
        fy_obj = self.pool.get('account.fiscalyear')

        if reopen:
            # only reopen at coordo level
            if instance_rec.level == 'coordo':
                state = 'draft'
        else:
            if instance_rec.level == 'coordo':
                current_state = fy_obj.read(cr, uid, [fy_id], ['state', ],
                                            context=context)[0]['state']
                if current_state != 'done':
                    state = 'mission-closed'
            elif instance_rec.level == 'section':
                state = 'done'

        if state:
            # period 0 (FY+1)/16 state

            # US-879: for periods update, set 'state_sync_flag' field first,
            # for adhoc sync state flow, like in account_period.action_set_state
            vals = { 'state_sync_flag': state, }
            period_ids = self._get_periods_ids(cr, uid,
                                               self._browse_fy(cr, uid, fy_id, context=context),
                                               context=context)

            # HQ JE posting all year end closing entries
            if period_ids and not reopen and instance_rec.level == 'section':
                hq_close_post_entries(period_ids)

            # periods state
            if period_ids:
                self.pool.get('account.period').write(cr, uid, period_ids, vals,
                                                      context=context)

                # then after 'state_sync_flag' set, set account_journal_period state
                # and period true state
                # (DO NOT CHANGE 'state' in same write than 'state_sync_flag'
                if state == 'done':
                    journal_state = 'done'
                else:
                    journal_state = 'draft'
                cr.execute('UPDATE account_journal_period' \
                           ' SET state=%s WHERE period_id IN %s', (
                               journal_state, tuple(period_ids), ))
                vals = {'state': state, 'field_process': False}
                self.pool.get('account.period').write(cr, uid, period_ids, vals,
                                                      context=context)

            # then set FY state
            vals = { 'state': state, }
            fy_obj.write(cr, uid, [fy_id], vals, context=context)

    def _search_record(self, cr, uid, model, domain, context=None):
        ids = self.pool.get(model).search(cr, uid, domain, context=context)
        return ids and ids[0] or False

    def _browse_fy(self, cr, uid, fy_id, context=None):
        return self.pool.get('account.fiscalyear').browse(cr, uid, fy_id,
                                                          context=context)

    def _get_fy_year(self, cr, uid, fy_rec, context=None):
        return int(fy_rec.date_start[0:4])

    def _get_next_fy_id(self, cr, uid, fy_rec, get_previous=False,
                        context=None):
        offset = -1 if get_previous else 1
        date = "%d-01-01" % (
            self._get_fy_year(cr, uid, fy_rec, context=context) + offset, )
        domain = [
            #('company_id', '=', fy_rec.company_id.id),
            ('date_start', '=', date),
        ]
        return self._search_record(cr, uid, 'account.fiscalyear', domain,
                                   context=context)

    def _get_period_id(self, cr, uid, fy_id, number, context=None):
        new_context = context and context.copy() or {}
        new_context['show_period_0'] = True
        domain = [
            ('fiscalyear_id', '=', fy_id),
            ('number', '=', number),
        ]
        return self._search_record(cr, uid, 'account.period', domain,
                                   context=new_context)

    def _get_periods_map(self, cr, uid, fy_rec, context=None):
        """
        get FY period 16, FY+1 period 0 ids map
        :return : { 16: id, 0: id)
        """
        next_fy_id = self._get_next_fy_id(cr, uid, fy_rec, context=context)
        return {
            16: self._get_period_id(cr, uid, fy_rec.id, 16, context=context),
            0: next_fy_id and self._get_period_id(cr, uid, next_fy_id, 0,
                                                  context=context) or False,
        }

    def _get_periods_ids(self, cr, uid, fy_rec, context=None):
        period_map = self._get_periods_map(cr, uid, fy_rec, context=context)
        return [ period_map[pn] for pn in period_map if period_map[pn] ]

    def _get_journal(self, cr, uid, code, context=None):
        """
        get coordo end year system journal
        :param get_initial_balance: True to get 'initial balance' journal
        :return: journal id
        """
        instance_rec = self.pool.get('res.users').browse(cr, uid, [uid],
                                                         context=context)[0].company_id.instance_id
        if instance_rec.level != 'coordo':
            return False

        domain = [
            ('instance_id', '=', instance_rec.id),
            ('code', '=', code),
        ]
        return self._search_record(cr, uid, 'account.journal', domain,
                                   context=context)

    def _get_journals(self, cr, uid, context=None):
        """
        get coordo end year system journal
        :param get_initial_balance: True to get 'initial balance' journal
        :return: journal id
        """
        instance_rec = self.pool.get('res.users').browse(cr, uid, [uid],
                                                         context=context)[0].company_id.instance_id
        if instance_rec.level != 'coordo':
            return False

        domain = [
            ('instance_id', '=', instance_rec.id),
            ('code', 'in', list(self._journals.keys())),
        ]
        return self.pool.get('account.journal').search(cr, uid, domain,
                                                       context=context)

account_year_end_closing()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
