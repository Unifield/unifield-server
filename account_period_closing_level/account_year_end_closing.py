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
            'Counterpart for B/S debit balance'),
        'ye_pl_cp_for_bs_credit_bal_account': fields.many2one('account.account',
            'Counterpart for B/S credit balance'),

        # US-822 PL/BS matrix of dev2/dev3 accounts"
        'ye_pl_pos_credit_account': fields.many2one('account.account',
            'Credit Account for P&L>0 (Income account)',
            domain=[('type', '=', 'other'), ('user_type.code', '=', 'equity')]),
        'ye_pl_pos_debit_account': fields.many2one('account.account',
            'Debit Account for P&L>0 (B/S account)',
            domain=[('type', '=', 'other'), ('user_type.code', '=', 'equity')]),
        'ye_pl_ne_credit_account': fields.many2one('account.account',
            'Credit Account P&L<0 (B/S account)',
            domain=[('type', '=', 'other'), ('user_type.code', '=', 'equity')]),
        'ye_pl_ne_debit_account': fields.many2one('account.account',
            'Debit Account P&L<0 (Expense account)',
            domain=[('type', '=', 'other'), ('user_type.code', '=', 'equity')]),
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

    def process_closing(self, cr, uid, fy_rec,
        has_move_regular_bs_to_0=False, has_book_pl_results=False,
        context=None):
        """level = self.check_before_closing_process(cr, uid, fy_rec,
            context=context)"""  # TODO uncomment
        level = 'coordo'
        if level == 'coordo':
            # generate closing entries at coordo level
            self.setup_journals(cr, uid, context=context)
            if has_move_regular_bs_to_0:
                self.move_bs_accounts_to_0(cr, uid, fy_rec, context=context)
            if has_book_pl_results:
                self.book_pl_results(cr, uid, fy_rec, context=context)
            # TODO uncomment report_bs_balance_to_next_fy
            # self.report_bs_balance_to_next_fy(cr, uid, fy_rec, context=context)
        # TODO uncomment self.update_fy_state
        #self.update_fy_state(cr, uid, fy_rec.id, context=context)

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
                        ' its periods state'))

            # check next FY exists (we need FY+1 Period 0 for initial balances)
            if not self._get_next_fy_id(cr, uid, fy_rec, context=context):
                raise osv.except_osv(_('Warning'),
                    _('FY+1 required to close FY'))

            # HQ level: check that all coordos have their FY mission closed
            mi_obj = self.pool.get('msf.instance')
            ci_ids = mi_obj.search(cr, uid, [
                    ('parent_id', '=', instance_id.id),
                    ('level', '=', 'coordo'),
                ], context=context)
            if ci_ids:
                afs_obj = self.pool.get("account.fiscalyear.state")
                # check that we have same count of mission-closed fy
                # in fy report than in true coordos
                # => so all have sync up their fy state report
                check_ci_ids = afs_obj.search(cr, uid, [
                        ('fy_id', '=', fy_rec.id),
                        ('instance_id', 'in', ci_ids),
                        ('state', '=', 'mission-closed'),
                    ], context=context)
                if len(check_ci_ids) != len(ci_ids):
                    # enumerate left open coordos for user info warn message
                    check_ci_ids = afs_obj.search(cr, uid, [
                            ('fy_id', '=', fy_rec.id),
                            ('instance_id', 'in', ci_ids),
                            ('state', '=', 'draft'),
                        ], context=context)
                    if check_ci_ids:
                        codes = [ rec.code for rec \
                            in mi_obj.browse(cr, uid, ci_ids, context=context)]
                    else:
                        # fy state report not all sync up: generic warn message
                        codes = [ _('All'), ]
                    raise osv.except_osv(_('Warning'),
                        _('%s Coordo(s): proceed year end closing first') % (
                            ', '.join(codes), ))

            raise osv.except_osv(_('Warning'), 'FAKE')
        return level

    def create_periods(self, cr, uid, fy_id, periods_to_create=[0, 16, ],
        context=None):
        """
        create closing special periods 0/16 for given FY
        :param fy_id: fy id to create periods in
        """
        period_numbers = [ pn for pn in periods_to_create \
            if pn in self._period_month_map.keys() ]
        fy_rec = self._browse_fy(cr, uid, fy_id, context=context)
        fy_year = fy_rec.date_start[:4]

        for pn in period_numbers:
            period_year_month = (fy_year, self._period_month_map[pn], )
            code = "Period %d" % (pn, )
            vals = {
                'name': code,
                'code': code,
                'number': pn,
                'special': True,
                'date_start': '%s-%02d-01' % period_year_month,
                'date_stop': '%s-%02d-31' % period_year_month,
                'fiscalyear_id': fy_id,
                'state': 'draft',  # opened by default
            }
            if pn == number:
                vals['active'] = False

            self.pool.get('account.period').create(cr, uid, vals,
                context=context)

    def setup_journals(self, cr, uid, context=None):
        """
        create GL coordo year end system journals if missing for the instance
        """
        instance_rec = self.pool.get('res.users').browse(cr, uid, [uid],
            context=context)[0].company_id.instance_id
        if instance_rec.level != 'coordo':
            return

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
                    context=context)

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
        cpy_rec = self.pool.get('res.users').browse(cr, uid, [uid],
            context=context)[0].company_id
        if not cpy_rec.ye_pl_cp_for_bs_debit_bal_account \
            or not cpy_rec.ye_pl_cp_for_bs_debit_bal_account:
            raise osv.except_osv(_('Error'),
                _("B/S counterparts accounts credit/debit not set" \
                    " in company settings 'B/S Move to 0 accounts'"))
        instance_rec = cpy_rec.instance_id

        fy_year = self._get_fy_year(cr, uid, fy_rec, context=context)
        posting_date = "%d-12-31" % (fy_year, )

        journal_code = 'EOY'
        journal_id = self._get_journal(cr, uid, 'IB', context=context)
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

    def book_pl_results(self, cr, uid, fy_rec, context=None):
        """
        action 2
        """
        pass

    def report_bs_balance_to_next_fy(self, cr, uid, fy_rec, context=None):
        """
        action 3: report B/S balances to next FY period 0
        """

        def create_journal_entry(ccy_id=False, ccy_code=''):
            """
            create draft CCY/JE to log JI into
            """
            name = "IB-%d-%s-%s" % (fy_year, instance_rec.code, ccy_code, )

            vals = {
                'block_manual_currency_id': True,
                'company_id': cpy_rec.id,
                'currency_id': ccy_id,
                'date': posting_date,
                'document_date': posting_date,
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
            name = "IB-%d-%s-%s-%s" % (fy_year, account_code, instance_rec.code,
                ccy_code, )

            vals = {
                'account_id': account_id,
                'company_id': cpy_rec.id,
                'currency_id': ccy_id,
                'date': posting_date,
                'document_date': posting_date,
                'instance_id': instance_rec.id,
                'journal_id': journal_id,
                'name': name,
                'period_id': period_id,
                'source_date': posting_date,

                'debit_currency': \
                    balance_currency if balance_currency > 0. else 0.,
                'credit_currency': \
                    abs(balance_currency) if balance_currency < 0. else 0.,

                'state':'valid',
                'move_id': je_id,
            }
            id = self.pool.get('account.move.line').create(cr, uid, vals,
                    context=local_context)

            # aggregated functional amount (sum) fx rate agnostic: raw write
            vals = {
                'debit': balance if balance > 0. else 0.,
                'credit': abs(balance) if balance < 0. else 0.,
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
                _("B/S Regular Equity result accounts credit/debit not set" \
                    " in company settings 'P&L result accounts'"))
        instance_rec = cpy_rec.instance_id

        fy_year = self._get_fy_year(cr, uid, fy_rec, context=context)
        next_fy_id = self._get_next_fy_id(cr, uid, fy_rec, context=context)
        posting_date = "%d-01-01" % (fy_year + 1, )

        journal_code = 'IB'
        journal_id = self._get_journal(cr, uid, 'IB', context=context)
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
        re_account_id = False
        sql = '''select sum(ml.debit - ml.credit) as bal
            from account_move_line ml
            inner join account_move m on m.id = ml.move_id
            inner join account_account a on a.id = ml.account_id
            inner join account_account_type t on t.id = a.user_type
            where ml.instance_id = %d
            and t.report_type in ('income', 'expense')
            and ml.date >= '%s' and ml.date <= '%s'
        ''' % (instance_rec.id, fy_rec.date_start, fy_rec.date_stop, )
        cr.execute(sql)
        if cr.rowcount:
            pl_balance = float(cr.fetchone()[0])
            if pl_balance > 0:
                # debit regular/equity result
                re_account_rec = cpy_rec.ye_pl_pos_debit_account
            else:
                # credit regular/equity result
                re_account_rec = cpy_rec.ye_pl_ne_credit_account

        # compute B/S balance in BOOKING breakdown in BOOKING/account
        # date inclusion to have periods 0/1-15/16
        sql = '''select ml.currency_id as currency_id,
            max(c.name) as currency_code,
            ml.account_id as account_id, max(a.code) as account_code,
            sum(ml.debit_currency - ml.credit_currency) as balance_currency,
            sum(ml.debit - ml.credit) as balance
            from account_move_line ml
            inner join account_move m on m.id = ml.move_id
            inner join account_account a on a.id = ml.account_id
            inner join account_account_type t on t.id = a.user_type
            inner join res_currency c on c.id = ml.currency_id
            where ml.instance_id = %d
            and t.report_type in ('asset', 'liability')
            and ml.date >= '%s' and ml.date <= '%s'
            group by ml.currency_id, ml.account_id
        ''' % (instance_rec.id, fy_rec.date_start, fy_rec.date_stop, )
        cr.execute(sql)
        if not cr.rowcount:
            return

        re_account_found_in_bs = False
        je_by_ccy = {}  # JE/CCY, key: ccy id, value: JE id
        for ccy_id, ccy_code, account_id, account_code, \
            balance_currency, balance in cr.fetchall():
            balance_currency = float(balance_currency)
            balance = float(balance)

            if ccy_id == cpy_rec.currency_id.id:
                # entry in functional ccy
                if account_id == re_account_rec.id:
                    # For Regular/Equity account add balance of all P/L balances
                    # note: booking == functional for entry and P/S in functional
                    balance_currency += pl_balance
                    balance += pl_balance
                    re_account_found_in_bs = True

            # CCY JE
            je_id = je_by_ccy.get(ccy_id, False)
            if not je_id:
                # 1st processing of a ccy: create its JE
                je_id = create_journal_entry(ccy_id=ccy_id, ccy_code=ccy_code)
                je_by_ccy[ccy_id] = je_id

            # per ccy/account initial balance item, tied to its CCY JE
            create_journal_item(ccy_id=ccy_id, ccy_code=ccy_code,
                account_id=account_id, account_code=account_code,
                balance_currency=balance_currency, balance=balance, je_id=je_id)

        if not re_account_found_in_bs:
            # No B/S result for result account, add entry with P/L balance
            je_id = je_by_ccy.get(cpy_rec.currency_id.id, False)
            if not je_id:
                je_id = create_journal_entry(ccy_id=ccy_id, ccy_code=ccy_code)
            create_journal_item(ccy_id=cpy_rec.currency_id.id,
                ccy_code=cpy_rec.currency_id.name,
                account_id=re_account_rec.id, account_code=re_account_rec.code,
                balance_currency=balance_currency, balance=balance, je_id=je_id)

    def update_fy_state(self, cr, uid, fy_id, reopen=False, context=None):
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
            vals = { 'state': state, }
            # period 0 (FY+1)/16 state
            period_ids = self._get_periods_ids(cr, uid,
                self._browse_fy(cr, uid, fy_id, context=context),
                context=context)
            if period_ids:
                self.pool.get('account.period').write(cr, uid, period_ids, vals,
                    context=context)

            # fy state
            fy_obj.write(cr, uid, [fy_id], vals, context=context)

    def _search_record(self, cr, uid, model, domain, context=None):
        ids = self.pool.get(model).search(cr, uid, domain, context=context)
        return ids and ids[0] or False

    def _browse_fy(self, cr, uid, fy_id, context=None):
        return self.pool.get('account.fiscalyear').browse(cr, uid, fy_id,
            context=context)

    def _get_fy_year(self, cr, uid, fy_rec, context=None):
        return int(fy_rec.date_start[0:4])

    def _get_next_fy_id(self, cr, uid, fy_rec, context=None):
        date = "%d-01-01" % (
            self._get_fy_year(cr, uid, fy_rec, context=context) + 1, )
        domain = [
            ('company_id', '=', fy_rec.company_id.id),
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
            ('code', 'in', self._journals.keys()),
        ]
        return self.pool.get('account.journal').search(cr, uid, domain,
            context=context)

account_year_end_closing()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
