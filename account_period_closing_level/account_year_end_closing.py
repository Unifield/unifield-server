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
from tools.translate import _
import calendar


class account_year_end_closing(osv.osv):
    _name = "account.year.end.closing"
    _auto = False

    # valid special period numbers and their month
    _period_month_map = { 0: 1, 16: 12, }

    _journals = {
        'EOY': 'End of Year',
        'IB': 'Initial Balances',
    }

    def check_before_closing_process(self, cr, uid, fy_rec_or_id=False,
        context=None):
        level = self.pool.get('res.users').browse(cr, uid, [uid],
            context=context)[0].company_id.instance_id.level
        if level not in ('section', 'coordo', ):
            raise osv.except_osv(_('Warning'),
                _('You can only close FY at HQ or Coordo'))

        if isinstance(fy_rec_or_id, (int, long, )):
            fy_rec = self._browse_fy(cr, uid, fy_rec_or_id, context=context)
        else:
            fy_rec = fy_rec_or_id
        if fy_rec.state != 'draft':
            raise osv.except_osv(_('Warning'),
                _('You can only close an opened FY'))

        # check FY closable regarding level
        field = False
        if level == 'coordo':
            field = 'is_mission_closable'
        elif level == 'section':
            field = 'is_hq_closable'
        if not field or not getattr(fy_rec, field):
            raise osv.except_osv(_('Warning'),
                _('FY can not be closed due to its periods state'))

        # check next FY exists (we need FY+1 Period 0 for initial balances)
        if not self._get_next_fy_id(cr, uid, fy_rec, context=context):
            raise osv.except_osv(_('Warning'),
                _('FY+1 required to close FY'))

    def create_periods(self, cr, uid, fy_id, periods_to_create=[0, 16, ],
        context=None):
        """
        create closing special periods 0/16 for given FY
        :param fy_id: fy id to create periods in
        """
        period_numbers = [ pn for pn in periods_to_create \
            if pn in self._period_month_map.keys() ]
        fy_rec = fy_rec = self._browse_fy(cr, uid, fy_id, context=context)
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

    def delete_year_end_entries(self, cr, uid, context=None):
        """
        Cancel the FY year end entries FOR THE INSTANCE
        - delete all entries of 'year end' 'system' journals
        """
        instance_ID = self.pool.get('res.users').browse(cr, uid, [uid],
            context=context)[0].company_id.instance_id.ID
        # TODO
        raise NotImplementedError()

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

        # TODO: ccy table prevails if given by wizard (like year end reval)
        local_context = context.copy() if context else {}
        local_context['date'] = '%d-01-01' % (fy_year, )

        # compute balance in SQL
        # TODO: only account B/S report types (2 types)
        # => and pay attention US-227: all B/S accounts not retrieved
        sql = '''select ml.currency_id as currency_id,
            max(c.name) as currency_code,
            ml.account_id as account_id, max(a.code) as account_code,
            sum(ml.debit - ml.credit) as balance
            from account_move_line ml
            inner join account_account a on a.id = ml.account_id
            inner join account_journal j on j.id = ml.journal_id
            inner join res_currency c on c.id = ml.currency_id
            where j.instance_id = %d
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

account_year_end_closing()


class account_period(osv.osv):
    _inherit = "account.period"

    # period 0 not available for picking in journals/selector/reports
    # except for following reports: general ledger, trial balance, balance sheet
    # => always hide Period 0 except if 'show_period_0' found in context
    def search(self, cr, uid, args, offset=0, limit=None, order=None,
        context=None, count=False):
        if not args:
            args = []
        if context is None or 'show_period_0' not in context:
            args.append(('number', '!=', 0))
        res = super(account_period, self).search(cr, uid, args, offset=offset,
            limit=limit, order=order, context=context, count=count)
        return res

account_period()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
