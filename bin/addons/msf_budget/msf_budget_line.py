# encoding: utf-8
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import fields, osv

# Overloading the one2many.get for budget lines to filter regarding context.
class one2many_budget_lines(fields.one2many):

    def get(self, cr, obj, ids, name, uid=None, offset=0, context=None, values=None):
        """
        Use 'granularity' value in context to filter budget lines.
        If granularity is 'view', then display only budget line that have line_type = view
        If 'expense', display budget lines that have line_type = view and normal
        If 'all' display budget lines that are view, normal and destination line_type
        Else, display view, normal and destination line_type ones.

        NB: This context also permit "Budget vs. Actual" report to work and display right lines regarding a given granularity.
        """
        if context is None:
            context = {}
        if values is None:
            values = {}
        res = {}
        display_type = {}

        domain = ['view', 'normal', 'destination']
        tuples = {
            'view': ['view'],
            'expense': ['view', 'normal'],
            'all': domain,
        }
        line_obj = obj.pool.get('msf.budget.line')

        if 'granularity' in context:
            display_type = context.get('granularity', False)
            if display_type and display_type in ['view', 'expense', 'all']:
                domain = tuples[display_type]

        for budget_id in ids:
            res[budget_id] = line_obj.search(cr, uid, [('budget_id', '=', budget_id), ('line_type', 'in', domain)])

        return res

class msf_budget_line(osv.osv):
    _name = "msf.budget.line"
    _order = "account_order, destination_id DESC, id"
    def _get_name(self, cr, uid, ids, field_names=None, arg=None, context=None):
        result = self.browse(cr, uid, ids, context=context)
        res = {}
        for rs in result:
            account = rs.account_id
            name = account.code
            if rs.destination_id:
                name += " "
                name += rs.destination_id.code
            name += " "
            name += account.name
            res[rs.id] = name
        return res

    def _get_month_names(self, number=12):
        """
        Return a list of all month field to be used from the first one to the given number (included).
        """
        res = []
        # Do not permit to give a number superior to 12!
        if number > 12:
            number = 12
        for x in xrange(1, number+1, 1):
            res.append('month' + str(x))
        return res

    def _get_domain(self, line_type, account_id, cost_center_ids, destination_id, date_start, date_stop):
        """
        Create a domain regarding budget line elements (to be used in a search()).
        Return a list.
        """
        if isinstance(cost_center_ids, (int, long)):
            cost_center_ids = [cost_center_ids]
        res = [
            ('cost_center_id', 'in', cost_center_ids),
            ('date', '>=', date_start),
            ('date', '<=', date_stop),
        ]
        if line_type == 'destination':
            res.append(('destination_id', '=', destination_id))
        if line_type in ['destination', 'normal']:
            res.append(('general_account_id', '=', account_id)),
        else:
            res.append(('general_account_id', 'child_of', account_id))
        return res

    def _get_sql_domain(self, cr, uid, request, params, line_type, account_id, destination_id):
        """
        Create a SQL domain regarding budget line elements (to be used in a SQL request).
        Return a 2 params:
          - SQL request
          - SQL params (list)
        """
        if not request:
            request = ""
        if not params:
            params = []
        if line_type == 'destination':
            request += """ AND destination_id = %s """
            params.append(destination_id)
        if line_type in ['destination', 'normal']:
            request += """ AND general_account_id = %s """
            params.append(account_id)
        else:
            request += """ AND general_account_id IN %s """
            account_ids = self.pool.get('account.account').search(cr, uid, [('parent_id', 'child_of', account_id)])
            params.append(tuple(account_ids))
        return request, params

    def _get_account_order(self, cr, uid, ids, field_names=None, arg=None, context=None):
        ret = {}
        account_obj = self.pool.get('account.account')
        if isinstance(ids, (int, long)):
            ids = [ids]
        seen = {}
        for line in self.read(cr, uid, ids, ['account_id'], context=context):
            account_id = line['account_id'] and line['account_id'][0]
            if account_id:
                if account_id not in seen:
                    acc = account_obj.read(cr, uid, account_id, ['parent_left'])
                    seen[account_id] = acc['parent_left']
                ret[line['id']] = seen[account_id]
            else:
                ret[line['id']] = 0
        return ret

    def _get_amounts(self, cr, uid, ids, field_names=None, arg=None, context=None):
        """
        Those field can be asked for:
          - actual_amount
          - comm_amount
          - balance
          - percentage
        With some depends:
          - percentage needs actual_amount, comm_amount, balance and budget_amount
          - balance needs actual_amount, comm_amount and budget_amount

        NB:
          - if 'period_id' in context, we change date_stop for SQL request to the date_stop of the given period to reduce computation
          - if 'currency_table_id' in context, we compute actual amounts (and commitment ones) currency by currency
        """
        # Some checks
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        budget_ok = False
        actual_ok = False
        commitment_ok = False
        percentage_ok = False
        balance_ok = False
        budget_amounts = {}
        actual_amounts = {}
        comm_amounts = {}
        cur_obj = self.pool.get('res.currency')
        # If period_id in context, use another date_stop element.
        date_period_stop = False
        month_number = 12
        if 'period_id' in context:
            period = self.pool.get('account.period').read(cr, uid, context.get('period_id', False), ['date_stop', 'number'], context=context)
            if period and period.get('date_stop', False):
                date_period_stop = period.get('date_stop')
            if period and period.get('number', False):
                month_number = period.get('number')
        # Check if we need to use another currency_table_id
        other_currencies = False
        date_context = {}
        company_currency_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        if context.get('currency_table_id', False):
            other_currencies = True
            date_context.update({'currency_table_id': context.get('currency_table_id')})
        # Check in which case we are regarding field names. Compute actual and commitment when we need balance and/or percentage.
        if 'budget_amount' in field_names:
            budget_ok = True
        if 'actual_amount' in field_names:
            actual_ok = True
        if 'comm_amount' in field_names:
            actual_ok = True
            commitment_ok = True
        if 'percentage' in field_names:
            budget_ok = True
            actual_ok = True
            percentage_ok = True
        if 'balance' in field_names:
            budget_ok = True
            actual_ok = True
            balance_ok = True
        # In some cases (reports) we don't want to display commitment values. But we have to include them into "balance" and percentage computation.
        if 'commitment' in context:
            commitment_ok = context.get('commitment', False)
        # Compute actual and/or commitments
        if actual_ok or commitment_ok or percentage_ok or balance_ok:
            # COMPUTE ACTUAL/COMMITMENT
            ana_obj = self.pool.get('account.analytic.line')
            ana_account_obj = self.pool.get('account.analytic.account')
            cur_obj = self.pool.get('res.currency')
            # Create default values
            for index in ids:
                if actual_ok:
                    actual_amounts.setdefault(index, 0.0)
                if commitment_ok:
                    comm_amounts.setdefault(index, 0.0)
            # Now, only use 'destination' line to do process and complete parent one at the same time
            sql = """
                SELECT l.id, l.line_type, l.account_id, l.destination_id, b.cost_center_id, f.date_start, f.date_stop
                FROM msf_budget_line AS l, msf_budget AS b, account_fiscalyear AS f
                WHERE l.budget_id = b.id
                AND b.fiscalyear_id = f.id
                AND l.id IN %s
                ORDER BY l.line_type, l.id"""
            cr.execute(sql, (tuple(ids),))
            # Prepare SQL2 request that contains sum of amount of given analytic lines (in functional currency)
            sql2 = """
                SELECT SUM(amount)
                FROM account_analytic_line
                WHERE id in %s"""
            # Prepare SQL3 request in case we have other currencies to compute
            sql3 = """
                SELECT l.currency_id, SUM(l.amount_currency)
                FROM account_analytic_line AS l, account_analytic_journal AS j
                WHERE l.journal_id = j.id
                AND l.cost_center_id IN %s
                AND l.date >= %s
                AND l.date <= %s"""
            sql3_end = """ GROUP BY l.currency_id"""
            # Process destination lines
            for line in cr.fetchall():
                # fetch some values
                line_id, line_type, account_id, destination_id, cost_center_id, date_start, date_stop = line
                cost_center_ids = ana_account_obj.search(cr, uid, [('parent_id', 'child_of', cost_center_id)])
                if date_period_stop:
                    date_stop = date_period_stop
                criteria = self._get_domain(line_type, account_id, cost_center_ids, destination_id, date_start, date_stop)
                # TWO METHODS to display actual/commitments
                # (1) Either we use functional amounts (no currency_table)
                # (2) Or we use a currency table to change amounts to functional amounts at fiscalyear date_stop
                if not other_currencies:
                    # (1) Use functional amounts: NO conversion
                    # fill in ACTUAL AMOUNTS
                    if actual_ok:
                        actual_criteria = list(criteria) + [('journal_id.type', '!=', 'engagement')]
                        ana_ids = ana_obj.search(cr, uid, actual_criteria)
                        if ana_ids:
                            cr.execute(sql2, (tuple(ana_ids),))
                            mnt_result = cr.fetchall()
                            if mnt_result:
                                actual_amounts[line_id] += mnt_result[0][0] * -1
                    # fill in COMMITMENT AMOUNTS
                    if commitment_ok:
                        commitment_criteria = list(criteria) + [('journal_id.type', '=', 'engagement')]
                        ana_ids = ana_obj.search(cr, uid, commitment_criteria)
                        if ana_ids:
                            cr.execute(sql2, (tuple(ana_ids),))
                            mnt_result = cr.fetchall()
                            if mnt_result:
                                comm_amounts[line_id] += mnt_result[0][0] * -1
                else:
                    # (2) OTHER CURRENCIES to compute
                    # Note that to not compute each analytic lines we use the sum of each currency and convert it to the functional currency using the given currency_table_id in the context
                    tmp_sql_params = [tuple(cost_center_ids), date_start, date_stop]
                    tmp_sql, sql_params = self._get_sql_domain(cr, uid, sql3, tmp_sql_params, line_type, account_id, destination_id)
                    # Use fiscalyear end date as date on which we do conversion
                    date_context.update({'currency_date': date_stop})

                    def get_amounts_and_compute_total(local_request, local_params, local_end_request):
                        """
                        Use request.
                        Finish it with local_end_request.
                        Execute it.
                        Fetch amounts.
                        Compute them by currency.
                        Return total result
                        """
                        total = 0.0
                        if local_end_request:
                            local_request += local_end_request
                        cr.execute(local_request, tuple(local_params))
                        if cr.rowcount:
                            analytic_amounts = cr.fetchall()
                            # Browse each currency amount and convert it to the functional currency (company one)
                            for currency_id, amount in analytic_amounts:
                                tmp_amount = cur_obj.compute(cr, uid, currency_id, company_currency_id, amount, round=False, context=date_context)
                                total += (tmp_amount * -1) # As analytic amounts are negative, we should use the opposite to make budget with positive values
                        return total

                    if actual_ok:
                        actual_sql = tmp_sql + """ AND j.type != 'engagement' """
                        actual_amounts[line_id] += get_amounts_and_compute_total(actual_sql, sql_params, sql3_end)
                    if commitment_ok:
                        commitment_sql = tmp_sql + """ AND j.type = 'engagement' """
                        comm_amounts[line_id] += get_amounts_and_compute_total(commitment_sql, sql_params, sql3_end)
        # Budget line amounts
        if budget_ok:
            month_names = self._get_month_names(month_number)
            sql = """
            SELECT id, COALESCE(""" + '+'.join(month_names) + """, 0.0)
            FROM msf_budget_line
            WHERE id IN %s;
            """ # not_a_user_entry
            cr.execute(sql, (tuple(ids),))
            tmp_res = cr.fetchall()
            if tmp_res:
                budget_amounts = dict(tmp_res)
        # Prepare result
        for line_id in ids:
            actual_amount = line_id in actual_amounts and actual_amounts[line_id] or 0.0
            comm_amount = line_id in comm_amounts and comm_amounts[line_id] or 0.0
            res[line_id] = {'actual_amount': actual_amount, 'comm_amount': comm_amount, 'balance': 0.0, 'percentage': 0.0, 'budget_amount': 0.0,}
            if budget_ok:
                budget_amount = line_id in budget_amounts and budget_amounts[line_id] or 0.0
                res[line_id].update({'budget_amount': budget_amount,})
            if balance_ok:
                balance = budget_amount - actual_amount
                if commitment_ok:
                    balance -= comm_amount
                res[line_id].update({'balance': balance,})
            if percentage_ok:
                if budget_amount != 0.0:
                    base = actual_amount
                    if commitment_ok:
                        base += comm_amount
                    percentage = round(base / budget_amount * 100.0)
                    res[line_id].update({'percentage': percentage,})
        return res

    def _get_total(self, cr, uid, ids, field_names=None, arg=None, context=None):
        """
        Give the sum of all month for the given budget lines.
        If period_id in context, just display months from the first one to the given period month (included)
        """
        # Some checks
        if isinstance(ids,(int, long)):
            ids = [ids]
        month_number = 12
        if 'period_id' in context:
            period = self.pool.get('account.period').read(cr, uid, context.get('period_id', False), ['number'])
            if period and period.get('number', False):
                month_number = period.get('number')
        month_names = self._get_month_names(month_number)
        # Prepare some values
        res = {}
        sql = """
            SELECT id, COALESCE(""" + '+'.join(month_names) + """, 0.0)
            FROM msf_budget_line
            WHERE id IN %s""" # not_a_user_entry
        cr.execute(sql, (tuple(ids),))
        tmp_res = cr.fetchall()
        if tmp_res:
            res = dict(tmp_res)
        return res

    _columns = {
        'budget_id': fields.many2one('msf.budget', 'Budget', ondelete='cascade', select=1),
        'account_id': fields.many2one('account.account', 'Account', required=True, domain=[('type', '!=', 'view')]),
        'destination_id': fields.many2one('account.analytic.account', 'Destination', domain=[('category', '=', 'DEST')], select=1),
        'name': fields.function(_get_name, method=True, store=False, string="Name", type="char", readonly="True", size=512),
        'month1': fields.float("Month 01"),
        'month2': fields.float("Month 02"),
        'month3': fields.float("Month 03"),
        'month4': fields.float("Month 04"),
        'month5': fields.float("Month 05"),
        'month6': fields.float("Month 06"),
        'month7': fields.float("Month 07"),
        'month8': fields.float("Month 08"),
        'month9': fields.float("Month 09"),
        'month10': fields.float("Month 10"),
        'month11': fields.float("Month 11"),
        'month12': fields.float("Month 12"),
        'total': fields.function(_get_total, method=True, store=False, string="Total", type="float", readonly=True, help="Get all month total amount"),
        'budget_amount': fields.function(_get_amounts, method=True, store=False, string="Budget amount", type="float", readonly=True, multi="budget_amounts"),
        'actual_amount': fields.function(_get_amounts, method=True, store=False, string="Actual amount", type="float", readonly=True, multi="budget_amounts"),
        'comm_amount': fields.function(_get_amounts, method=True, store=False, string="Commitments amount", type="float", readonly=True, multi="budget_amounts"),
        'balance': fields.function(_get_amounts, method=True, store=False, string="Balance", type="float", readonly=True, multi="budget_amounts"),
        'percentage': fields.function(_get_amounts, method=True, store=False, string="Percentage", type="float", readonly=True, multi="budget_amounts"),
        'parent_id': fields.many2one('msf.budget.line', 'Parent Line'),
        'child_ids': fields.one2many('msf.budget.line', 'parent_id', 'Child Lines'),
        'line_type': fields.selection([('view','View'),
                                       ('normal','Normal'),
                                       ('destination', 'Destination')], 'Line type', required=True),
        'account_code': fields.related('account_id', 'code', type='char', string='Account code', size=64, store=True, write_relate=False),
        'account_order': fields.function(_get_account_order, type='integer', string='order', method=True, store=True),
    }


    _defaults = {
        'line_type': lambda *a: 'normal',
        'month1': lambda *a: 0.0,
        'month2': lambda *a: 0.0,
        'month3': lambda *a: 0.0,
        'month4': lambda *a: 0.0,
        'month5': lambda *a: 0.0,
        'month6': lambda *a: 0.0,
        'month7': lambda *a: 0.0,
        'month8': lambda *a: 0.0,
        'month9': lambda *a: 0.0,
        'month10': lambda *a: 0.0,
        'month11': lambda *a: 0.0,
        'month12': lambda *a: 0.0,
    }

msf_budget_line()

class msf_budget(osv.osv):
    _name = "msf.budget"
    _inherit = "msf.budget"

    _columns = {
        'budget_line_ids': one2many_budget_lines('msf.budget.line', 'budget_id', 'Budget Lines'),
    }

msf_budget()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
