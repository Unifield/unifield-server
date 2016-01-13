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

    # period 0 not available for picking in journals/selector/reports
    # except for following reports: general ledger, trial balance, balance sheet
    # => always hide Period 0 except if 'show_period_0' found in context
    def search(self, cr, uid, args, offset=0, limit=None, order=None,
        context=None, count=False):
        if not args:
            args = []
        add_0_filter = True
        for a in args:
            if len(a) == 3:
                if a[0] in ('is_system', ):
                    # existing global system filter exists: let it
                    add_0_filter = False
                    break

        if add_0_filter:
            if context is None or 'show_period_0' not in context:
                args.append(('number', '!=', 0))
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

    def process_closing(self, cr, uid, fy_rec, currency_table_id=False,
        from_sync=False, context=None):
        """
        :param from_sync: True if we are at coordo and pulling an HQ year end
            closing trigger
        """
        level = self.check_before_closing_process(cr, uid, fy_rec,
            context=context)
        if level == 'coordo':
            # generate closing entries at coordo level
            self.setup_journals(cr, uid, context=context)
            self.report_bs_balance_to_next_fy(cr, uid, fy_rec,
                currency_table_id=currency_table_id, context=context)
        self.update_fy_state(cr, uid, fy_rec.id, context=context)

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
                sql = "delete from %s where id in (%s)" % (
                    o._name.replace('.', '_'),
                    ','.join([str(id) for id in ids])
                )
                cr.execute(sql)

    def report_bs_balance_to_next_fy(self, cr, uid, fy_rec,
            currency_table_id=False, context=None):
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
            account_code='', balance=0., je_id=False):
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

                'debit_currency': balance if balance > 0. else 0.,
                'credit_currency': abs(balance) if balance < 0. else 0.,

                'state':'valid',
                'move_id': je_id,
            }
            return self.pool.get('account.move.line').create(cr, uid, vals,
                    context=local_context)

        # init
        # - company and instance
        # - current FY year
        # - next FY id
        # - posting date
        # - IB journal
        # - next FY period 0
        # - local context
        cpy_rec = self.pool.get('res.users').browse(cr, uid, [uid],
            context=context)[0].company_id
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

        local_context = context.copy() if context else {}
        local_context['date'] = '%d-01-01' % (fy_year, )  # date for rates
        if currency_table_id:
            # use ccy table
            local_context['currency_table_id'] = currency_table_id

        # compute balance in SQL for B/S report types
        # except Regular/Equity (type 'other'/user_type code 'equity'
        # => and pay attention US-227: all B/S accounts not retrieved
        sql = '''select ml.currency_id as currency_id,
            max(c.name) as currency_code,
            ml.account_id as account_id, max(a.code) as account_code,
            sum(ml.debit - ml.credit) as balance
            from account_move_line ml
            inner join account_account a on a.id = ml.account_id
            inner join account_account_type t on t.id = a.user_type
            inner join account_journal j on j.id = ml.journal_id
            inner join res_currency c on c.id = ml.currency_id
            where j.instance_id = %d and t.report_type in ('asset', 'liability')
            and ml.date >= '%s' and ml.date <= '%s'
            group by ml.currency_id, ml.account_id''' % (
                instance_rec.id, fy_rec.date_start, fy_rec.date_stop, )
        cr.execute(sql)
        if not cr.rowcount:
            return

        je_by_ccy = {}  # JE/CCY, key: ccy id, value: JE id
        for ccy_id, ccy_code, account_id, account_code, bal in cr.fetchall():
            print ccy_id, ccy_code, account_id, account_code, bal

            # CCY JE
            je_id = je_by_ccy.get(ccy_id, False)
            if not je_id:
                # 1st processing of a ccy: create its JE
                je_id = create_journal_entry(ccy_id=ccy_id, ccy_code=ccy_code)
                je_by_ccy[ccy_id] = je_id

            # per ccy/account initial balance item, tied to its CCY JE
            create_journal_item(ccy_id=ccy_id, ccy_code=ccy_code,
                account_id=account_id, account_code=account_code,
                balance=bal, je_id=je_id)

        # post processing: 'raw write' JEs post (after JIs created)
        # as they are unbalanced by nature and not accepted by system
        return self.pool.get('account.move').write(cr, uid, je_by_ccy.values(),
            { 'state':'posted', }, context=local_context)

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
        domain = [
            ('fiscalyear_id', '=', fy_id),
            ('number', '=', number),
        ]
        return self._search_record(cr, uid, 'account.period', domain,
            context=context)

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
