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

    def check_before_closing_process(self, cr, uid, fy_id=False, fy_rec=False,
            context=None):
        level = self.pool.get('res.users').browse(cr, uid, [uid],
            context=context)[0].company_id.instance_id.level
        if level not in ('section', 'coordo', ):
            raise osv.except_osv(_('Warning'),
                _('You can only close FY at HQ or Coordo'))

        if not fy_id and not fy_rec:
            return
        if not fy_rec:
            fy_rec = self._browse_fy(cr, uid, fy_id, context=context)
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
        period_year_month = (fy_year, self._period_month_map[pn], )

        for pn in period_numbers:
            code = "Period %d" % (pn, )
            vals = {
                'name': code,
                'code': code,
                'number': pn,
                'special': True,
                'date_start': '%s-%02d-01' % period_year_month,
                'date_stop': '%s-%02d-31' % period_year_month,
                'fiscalyear_id': fy_id,
                'state': 'created',
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
        instance_rec = self.pool.get('res.users').browse(cr, uid, [uid],
            context=context)[0].company_id.instance_id

        cr.execute(
            '''select c.name as currency_code, a.code as account_code,
            sum(ml.debit - ml.credit) as bal from account_move_line ml
            inner join account_account a on a.id = ml.account_id
            inner join account_journal j on j.id = ml.journal_id
            inner join res_currency c on c.id = ml.currency_id
            where j.instance_id = %d
            group by currency_code, account_code''' % (instance_rec.id, )
        )
        if not cr.rowcount:
            return

        for r in cr.fetchall():
            print r

    def _search_record(self, cr, uid, model, domain, context=None):
        ids = self.pool.get(model).search(cr, uid, domain, context=context)
        return ids and ids[0] or False

    def _browse_fy(self, cr, uid, fy_id, context=None):
        return self.pool.get('account.fiscalyear').browse(cr, uid, fy_id,
            context=context)

    def _get_next_fy_id(self, cr, uid, fy_rec, context=None):
        year = int(fy_rec.date_start[0:4])
        domain = [
            ('company_id', '=', fy_rec.company_id.id),
            ('date_start', '=', "%d-01-01" % (year+1, )),
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
