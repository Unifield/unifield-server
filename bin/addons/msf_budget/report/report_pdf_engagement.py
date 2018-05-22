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
from report import report_sxw
import locale
import pooler
import datetime
from tools.translate import _
from osv import osv
import time

class report_pdf_engagement(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(report_pdf_engagement, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'get_fiscal_year': self.get_fiscal_year,
            'check_distribution': self.check_distribution,
            'get_report_lines': self.get_report_lines,
            'time': time,
            'locale': locale,
            'isPos': self.isPos,
        })
        return

    def isPos(self, nb):
        if nb < 0:
            return False
        return True

    def get_fiscal_year(self, purchase_order):
        pool = pooler.get_pool(self.cr.dbname)

        po_date = purchase_order.delivery_confirmed_date.val or purchase_order.delivery_requested_date.val
        fiscalyear_id = pool.get('account.fiscalyear').find(self.cr, self.uid, po_date, False, context={})
        if fiscalyear_id:
            fiscalyear = pool.get('account.fiscalyear').browse(self.cr, self.uid, fiscalyear_id, context={})
            return fiscalyear.name
        return False

    def _add_purchase_order_amount(self, cr, uid, browse_po_line, browse_analytic_distribution, functional_currency_id, expense_account_id, value_list, value_list2):

        pool = pooler.get_pool(self.cr.dbname)
        for cc_line in browse_analytic_distribution.cost_center_lines:

            if cc_line.analytic_id and str(cc_line.analytic_id.id)+'_'+str(cc_line.destination_id.id) not in value_list:
                value_list[str(cc_line.analytic_id.id)+'_'+str(cc_line.destination_id.id)] = {}
                value_list2[str(cc_line.analytic_id.id)+'_'+str(cc_line.destination_id.id)] = {}
            # convert amount to today's rate
            date_context = {'date': datetime.datetime.today()}
            functional_amount = pool.get('res.currency').compute(self.cr,
                                                                 self.uid,
                                                                 browse_po_line.currency_id.id,
                                                                 functional_currency_id,
                                                                 cc_line.percentage * browse_po_line.price_subtotal / 100.0,
                                                                 round=True,
                                                                 context=date_context)
            expense_line = [0, 0, 0, functional_amount, -functional_amount]
            if expense_account_id not in value_list[str(cc_line.analytic_id.id)+'_'+str(cc_line.destination_id.id)]:
                value_list[str(cc_line.analytic_id.id)+'_'+str(cc_line.destination_id.id)][expense_account_id] = expense_line
            else:
                value_list[str(cc_line.analytic_id.id)+'_'+str(cc_line.destination_id.id)][expense_account_id] = [sum(pair) for pair in zip(value_list[str(cc_line.analytic_id.id)+'_'+str(cc_line.destination_id.id)][expense_account_id], expense_line)]
            value_list2[str(cc_line.analytic_id.id)+'_'+str(cc_line.destination_id.id)][expense_account_id] = cc_line.destination_id.code

        return

    def check_distribution(self, purchase_order):
        # 3 cases:
        # 1. header distribution or distribution on all lines; return True
        # 2. no header distribution and distribution on not all lines; return False
        # 3. no header distribution and no distribution on lines; raise error
        has_one_distribution = False
        has_all_distribution = True
        if purchase_order.analytic_distribution_id:
            return True
        else:
            for po_line in purchase_order.order_line:

                if po_line.analytic_distribution_id:
                    has_one_distribution = True
                else:
                    has_all_distribution = False

        if has_one_distribution and has_all_distribution:
            return has_one_distribution

        elif not has_one_distribution:
            raise osv.except_osv(_('Error'), _('No distribution found in PO %s.') % (purchase_order.name))

    def _cmp_cc_dest(self, a, b):
        """
        Comparison function to sort by cost center code and then destination code
        """
        analytic_acc_obj = self.pool.get('account.analytic.account')
        a = a.split('_')
        b = b.split('_')
        if len(a) != 2 or len(b) != 2 or not a[0] or not b[0] or not a[1] or not b[1]:
            return 0
        a_cc = analytic_acc_obj.read(self.cr, self.uid, int(a[0]), ['code'])['code'].upper()
        a_dest = analytic_acc_obj.read(self.cr, self.uid, int(a[1]), ['code'])['code'].upper()
        b_cc = analytic_acc_obj.read(self.cr, self.uid, int(b[0]), ['code'])['code'].upper()
        b_dest = analytic_acc_obj.read(self.cr, self.uid, int(b[1]), ['code'])['code'].upper()
        if a_cc > b_cc:
            return 1
        elif a_cc < b_cc:
            return -1
        else:
            if a_dest > b_dest:
                return 1
            elif a_dest < b_dest:
                return -1
        return 0

    def get_report_lines(self, purchase_order):
        # Input: a purchase order
        # temp_data: a dict of dict of list {cost_center_name: {expense_account: [budget_amount, ...],
        #                                                       expense_account: [...],
        #                                                       expense_account: [budget_amount, ...]}}
        # Output: a formatted list of list
        res = []
        temp_data = {}
        temp_data2 = {}
        pool = pooler.get_pool(self.cr.dbname)
        cr = self.cr
        uid = self.uid
        context = {}

        functional_currency_id = pool.get('res.users').browse(cr, uid, uid, context).company_id.currency_id.id

        if purchase_order:
            for po_line in purchase_order.order_line:
                if po_line.state.startswith('cancel'):
                    continue
                expense_account_id = False
                if po_line.product_id and \
                   po_line.product_id.property_account_expense:
                    expense_account_id = po_line.product_id.property_account_expense.id
                elif po_line.product_id and \
                        po_line.product_id.categ_id and \
                        po_line.product_id.categ_id.property_account_expense_categ:
                    expense_account_id = po_line.product_id.categ_id.property_account_expense_categ.id
                else:
                    continue

                if po_line.analytic_distribution_id:
                    # a line has a distribution
                    self._add_purchase_order_amount(cr,
                                                    uid,
                                                    po_line,
                                                    po_line.analytic_distribution_id,
                                                    functional_currency_id,
                                                    expense_account_id,
                                                    temp_data,temp_data2)
                elif purchase_order.analytic_distribution_id:
                    # a line does not have a distribution, but there is a header one
                    self._add_purchase_order_amount(cr,
                                                    uid,
                                                    po_line,
                                                    purchase_order.analytic_distribution_id,
                                                    functional_currency_id,
                                                    expense_account_id,
                                                    temp_data,temp_data2)

            # PO data is filled, now to the temp_data
            # Get the corresponding fiscal year (delivery confirmed date or delivery requested date)
            po_date = purchase_order.delivery_confirmed_date.val or purchase_order.delivery_requested_date.val
            fiscalyear_id = pool.get('account.fiscalyear').find(cr, uid, po_date, False, context=context)
            if fiscalyear_id:
                fiscalyear = pool.get('account.fiscalyear').browse(cr, uid, fiscalyear_id, context=context)
                cost_center_ids = temp_data.keys()

                # add by cost center
                for cost_dest in cost_center_ids:
                    split = cost_dest.split('_')

                    cost_center_id = split[0] and int(split[0])
                    destination_id = split[1] and int(split[1])


                    expense_account_ids = temp_data[str(cost_center_id)+'_'+str(destination_id)].keys()
                    # Create the actual domain
                    actual_domain = [('cost_center_id', '=', cost_center_id)]
                    actual_domain.append(('date', '>=', fiscalyear.date_start))
                    actual_domain.append(('date', '<=', fiscalyear.date_stop))
                    # get only wanted accounts
                    actual_domain.append(('general_account_id', 'in', expense_account_ids))

                    # get actual values
                    actuals = pool.get('msf.budget.tools')._get_actual_amounts(cr,
                                                                               uid,
                                                                               functional_currency_id,
                                                                               actual_domain,
                                                                               context=context)
                    # we only save the main accounts, not the destinations (new key: account id only)
                    actuals = dict([(item[0], actuals[item]) for item in actuals if item[1] is False])

                    for account_id in actuals.keys():
                        if account_id in expense_account_ids:
                            # sum the values, we only need the total
                            total_actual = sum(actuals[account_id])
                            # create the line to add
                            actual_line = [0, total_actual, -total_actual, 0, -total_actual]
                            temp_data[str(cost_center_id)+'_'+str(destination_id)][account_id] = [sum(pair) for pair in zip(temp_data[str(cost_center_id)+'_'+str(destination_id)][account_id], actual_line)]

                    # get budget values                for cost_center_id in cost_center_list:
                    cr.execute("SELECT id FROM msf_budget WHERE fiscalyear_id = %s \
                                                            AND cost_center_id = %s \
                                                            AND state != 'draft' \
                                                            ORDER BY decision_moment_order DESC, version DESC LIMIT 1",
                               (fiscalyear_id,
                                cost_center_id))
                    if cr.rowcount:
                        # get the lines for the account ids
                        domain = [
                            ('budget_id', '=', cr.fetchall()[0][0]),
                            ('account_id', 'in', expense_account_ids),
                            ('destination_id', '=', destination_id),
                            ('line_type', '=', 'destination'),
                        ]
                        budget_line_ids = pool.get('msf.budget.line').search(cr, uid, domain, context=context)
                        budget_data = pool.get('msf.budget.line').read(cr, uid, budget_line_ids, ['account_id', 'total'])
                        budget_amounts = dict([(x.get('account_id', [])[0], x.get('total', 0.0)) for x in budget_data])

                        for account_id in budget_amounts.keys():
                            # sum the values, we only need the total
                            total_budget = budget_amounts[account_id]
                            # create the line to add
                            budget_line = [total_budget, 0, total_budget, 0, total_budget]
                            temp_data[str(cost_center_id)+'_'+str(destination_id)][account_id] = [sum(pair) for pair in zip(temp_data[str(cost_center_id)+'_'+str(destination_id)][account_id], budget_line)]
                    else:
                        # No budget found, fill the corresponding lines with "Budget Missing"
                        for account_id in temp_data[str(cost_center_id)+'_'+str(destination_id)].keys():
                            temp_data[str(cost_center_id)+'_'+str(destination_id)][account_id][0] = str('Budget missing')

            # Now we format the data to form the result
            total_values = [0, 0, 0, 0, 0]
            cost_center_ids = temp_data.keys()
            cost_center_ids.sort(self._cmp_cc_dest)

            for cost_dest in cost_center_ids:

                split = cost_dest.split('_')
                cost_center_id = split[0] and int(split[0])
                destination_id = split[1] and int(split[1])

                cost_center_data = temp_data[str(cost_center_id)+'_'+str(destination_id)]
                expense_account_ids = cost_center_data.keys()

                expense_accounts = pool.get('account.account').browse(cr, uid, expense_account_ids, context=context)
                for expense_account in sorted(expense_accounts, key=lambda a: a.code):
                    values = cost_center_data[expense_account.id]
                    cost_center = pool.get('account.analytic.account').browse(cr, uid, cost_center_id, context=context)
                    formatted_line = ["%s - %s" % (cost_center.code or ' ', cost_center.name)]
                    formatted_line += ["%s - %s" % (expense_account.code, expense_account.name)]
                    if values[0] != 'Budget missing':
                        total_values = [round(sum(pair)) for pair in zip(values, total_values)]
                        formatted_line += [values[0]]
                    else:
                        total_values = [round(sum(pair)) for pair in zip([0] + values[1:], total_values)]
                        formatted_line += [values[0]]
                    formatted_line += values[1:]
                    formatted_line += [ temp_data2[str(cost_center_id)+'_'+str(destination_id)][expense_account.id] ]
                    res.append(formatted_line)

                # empty line between cost centers
                res.append([''] * 7)
            # append formatted total
            res.append(['TOTALS', ''] + map(int, total_values))
        return res

report_sxw.report_sxw('report.msf.pdf.engagement', 'purchase.order', 'addons/msf_budget/report/engagement.rml', parser=report_pdf_engagement, header=False)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
