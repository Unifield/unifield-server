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
from tools.translate import _


def filter_chars(text):
    # US-583: exclude chars in action name
    # (chars to exclude list obtained using string.printable and testing)
    exclude_list = "\"'`^\@~;$&#"

    res = text
    for c in exclude_list:
        res = res.replace(c, '')
    return res


class msf_budget_summary(osv.osv_memory):
    _name = "msf.budget.summary"

    _budget_summary_line_label_pattern = '{budget_code} - Budget lines'

    def _get_amounts(self, cr, uid, ids, field_names=None, arg=None, context=None):
        """
        Fetch total budget amount from the linked budget
        Fetch actual amount (all analytic lines) for the given budgets and its childs.
        """
        # Prepare some values
        res = {}
        for summary_line in self.browse(cr, uid, ids, context=context):
            actual_amount = 0.0
            budget_amount = 0.0
            if summary_line.budget_id.type == 'view':
                for child_line in summary_line.child_ids:
                    child_amounts = self._get_amounts(cr, uid, [child_line.id], context=context)
                    actual_amount += child_amounts[child_line.id]['actual_amount']
                    budget_amount += child_amounts[child_line.id]['budget_amount']
            else:
                #  Budget Amount (use total budget amount field)
                budget_amount = summary_line.budget_id.total_budget_amount
                # Actual amount is the sum of amount of all analytic lines that correspond to the budget elements (commitments included)
                sql = """
                    SELECT SUM(amount)
                    FROM account_analytic_line
                    WHERE cost_center_id = %s
                    AND date >= %s
                    AND date <= %s
                """
                cc_id = summary_line.budget_id.cost_center_id.id
                date_start = summary_line.budget_id.fiscalyear_id.date_start
                date_stop = summary_line.budget_id.fiscalyear_id.date_stop
                # REF-25 Improvement: Use a SQL request instead of browse
                cr.execute(sql, (cc_id, date_start, date_stop))
                if cr.rowcount:
                    tmp_res = cr.fetchall()
                    tmp_amount = tmp_res and tmp_res[0] and tmp_res[0][0] or 0.0
                    actual_amount += tmp_amount

            actual_amount = abs(actual_amount)
            res[summary_line.id] = {
                'actual_amount': actual_amount,
                'budget_amount': budget_amount,
                'balance_amount': budget_amount - actual_amount,  # utp-857
            }
        return res

    _columns = {
        'budget_id': fields.many2one('msf.budget', 'Budget', required=True),

        'name': fields.related('budget_id', 'name', type="char", string="Budget Name", store=False, write_relate=False),
        'code': fields.related('budget_id', 'code', type="char", string="Budget Code", store=False, write_relate=False),
        'budget_amount': fields.function(_get_amounts, method=True, store=False, string="Budget Amount", type="float", multi="all"),
        'actual_amount': fields.function(_get_amounts, method=True, store=False, string="Actual Amount", type="float", multi="all"),
        'balance_amount': fields.function(_get_amounts, method=True, store=False, string="Balance Amount", type="float", multi="all"),  # utp-857

        'parent_id': fields.many2one('msf.budget.summary', 'Parent'),
        'child_ids': fields.one2many('msf.budget.summary', 'parent_id', 'Children'),
    }

    _defaults = {
        'parent_id': lambda *a: False
    }

    def create(self, cr, uid, vals, context=None):
        """
        Create a summary line for each child of the cost center used by the budget given in vals
        """
        # Some checks
        if context is None:
            context = {}
        # Prepare some values
        sql = """
            SELECT id
            FROM msf_budget
            WHERE fiscalyear_id = %s
            AND cost_center_id = %s
            AND decision_moment_id = %s
            AND state != 'draft'
            ORDER BY version DESC
            LIMIT 1"""
        res = super(msf_budget_summary, self).create(cr, uid, vals, context=context)
        if 'budget_id' in vals:
            budget = self.pool.get('msf.budget').read(cr, uid, vals['budget_id'], ['fiscalyear_id', 'decision_moment_id', 'cost_center_id'], context=context)
            if budget.get('cost_center_id', False):
                itself = budget.get('cost_center_id')[0]
                cost_center = self.pool.get('account.analytic.account').read(cr, uid, itself, ['child_ids'])
                for child_id in cost_center.get('child_ids', []):
                    cr.execute(sql, (budget.get('fiscalyear_id', [False])[0], child_id, budget.get('decision_moment_id', [False])[0]))
                    if cr.rowcount:
                        child_budget_id = cr.fetchall()[0][0]
                        self.create(cr, uid, {'budget_id': child_budget_id, 'parent_id': res}, context=context)
        return res

    def action_open_budget_summary_budget_lines(self, cr, uid, ids, context=None):
        res = {}
        if not ids:
            return res
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}

        mbs_obj = self.pool.get('msf.budget.summary')
        mbsl_obj = self.pool.get('msf.budget.summary.line')

        # get summary line
        summary_line_id = ids[0]
        # search for the line to validate it truly exists as osv.memory
        check_ids = mbs_obj.search(cr, uid, [
            ('id', '=', summary_line_id),
        ], context=context)
        if not check_ids:
            return res

        # get summary line data and do checks
        summary_br = mbs_obj.browse(cr, uid, [summary_line_id],
                                    context=context)[0]
        # abort if no budget found or not a last level summary node (perfs)
        if not summary_br.budget_id:
            raise osv.except_osv(_('Error'), _('Budget not found'))
        if summary_br.child_ids:
            raise osv.except_osv(_('Warning'),
                                 _('Only childest budgets are drillable'))

        # build tree
        root_id = mbsl_obj.build_tree(cr, uid, summary_br, context=context)

        # set action
        name = self._budget_summary_line_label_pattern.format(
            budget_code=summary_br.budget_id.code or '')
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid,
                                                                      'msf_budget', 'view_msf_budget_summary_budget_line_tree')[1]
        res = {
            'name': filter_chars(name),
            'type': 'ir.actions.act_window',
            'res_model': 'msf.budget.summary.line',
            'view_type': 'tree',
            'view_mode': 'tree',
            'view_id': [view_id],
            'domain': [('id', '=', root_id)],
            'context': context,
        }

        return res

msf_budget_summary()


class msf_budget_summary_line(osv.osv_memory):
    _name = "msf.budget.summary.line"

    _aji_label_pattern = "{budget_code} / {budget_line} - Analytic Items"

    def _get_account_code(self, cr, uid, ids, name, args, context=None):
        res = {}
        if not ids:
            return res

        for r in self.read(cr, uid, ids, ['parent_id', 'name'],
                           context=context):
            if r['parent_id']:
                parts = r['name'].split(' ')
                res[r['id']] = parts and parts[0] or ''
            else:
                res[r['id']] = ''
        return res

    _columns = {
        'budget_id': fields.many2one('msf.budget', 'Budget', required=True),
        'budget_line_id': fields.many2one('msf.budget.line', 'Budget Line', required=True),
        'account': fields.char('Account', size=5),

        'name': fields.char('Name', size=128),
        'budget_amount': fields.float("Budget Amount"),
        'actual_amount': fields.float("Actual Amount"),
        'balance': fields.float("Balance Amount"),

        'parent_id': fields.many2one('msf.budget.summary.line', 'Parent'),
        'child_ids': fields.one2many('msf.budget.summary.line', 'parent_id', 'Children'),
    }

    _defaults = {
        'parent_id': lambda *a: False
    }

    def build_tree(self, cr, uid, summary_line_br, context=None):
        aa_obj = self.pool.get('account.account')
        mbl_obj = self.pool.get('msf.budget.line')

        if context is None:
            context = {}
        context['commitment'] = 1

        # get account tree
        account_ids = aa_obj.search(cr, uid, [])
        account_tree = {}
        for a in aa_obj.read(cr, uid, account_ids, ['parent_id', ],
                             context=context):
            account_tree[a['id']] = a['parent_id'] and a['parent_id'][0] \
                or False

        # create root node
        vals = {
            'budget_id': summary_line_br.budget_id.id,
            'budget_line_id': False,

            'name': summary_line_br.code or '',
            'budget_amount': summary_line_br.budget_amount,
            'actual_amount': summary_line_br.actual_amount,
            'balance': summary_line_br.balance_amount,

            'parent_id': False,
        }
        root_id = self.create(cr, uid, vals, context=context)

        # build nodes from budget lines
        id = False
        fields = [ 'name', 'budget_amount', 'actual_amount', 'balance', ]

        budget_lines_ids = mbl_obj.search(cr, uid, [
            ('budget_id', '=', summary_line_br.budget_id.id),
            ('line_type', 'in', ('view', 'normal')),
        ], context=context)

        # mapping between build tree lines and budget lines by account
        mapping = {}

        # get line truely in parent_left order
        # (the native order of budget lines)
        line_read = {}
        for bl_r in mbl_obj.read(cr, uid, budget_lines_ids,
                                 fields + [ 'account_id', 'comm_amount', ], context=context):
            line_read[bl_r['id']] = bl_r

        for bl_id in budget_lines_ids:
            bl_r = line_read[bl_id]

            # get account level
            parts = bl_r['name'].split(' ')
            account = parts and parts[0] or ''

            # parent mapping
            account_id = bl_r['account_id'][0]
            parent_id = root_id
            if account_tree.get(account_id):
                parent_account = account_tree[account_id]
                if parent_account in mapping:
                    parent_id = mapping[parent_account]

            # set vals
            vals = {
                'budget_id': summary_line_br.budget_id.id,
                'budget_line_id': bl_r['id'],
                'account': account,

                'parent_id': parent_id,
            }
            for f in fields:
                vals[f] = bl_r[f]
                if f == 'actual_amount':
                    # include commitments
                    vals[f] += bl_r['comm_amount']

            # create node
            id = self.create(cr, uid, vals, context=context)
            mapping[account_id] = id
            if not id:
                break

        return root_id

    def action_open_analytic_lines(self, cr, uid, ids, context):
        def get_analytic_domain(sl_br):
            cc_ids = self.pool.get('msf.budget.tools')._get_cost_center_ids(cr,
                                                                            uid, sl_br.budget_id.cost_center_id)

            return [
                ('cost_center_id', 'in', cc_ids),
                ('date', '>=', sl_br.budget_id.fiscalyear_id.date_start),
                ('date', '<=', sl_br.budget_id.fiscalyear_id.date_stop),
                ('general_account_id', 'child_of',
                    [sl_br.budget_line_id.account_id.id]),
            ]

        res = {}
        if not ids:
            return res
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}

        sl_br = self.browse(cr, uid, ids[0], context=context)
        if not sl_br.budget_line_id:
            # no AJI drill for the root line: only from 1 level (like 6, 7)
            raise osv.except_osv(_('Warning'),
                                 _('You can not drill analytic journal items of the root line'))
        name = self._aji_label_pattern.format(
            budget_code=sl_br.budget_id.code or '',
            budget_line=sl_br.name or '')

        res = {
            'name': filter_chars(name),
            'type': 'ir.actions.act_window',
            'res_model': 'account.analytic.line',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'domain': get_analytic_domain(sl_br),
            'context': context,
        }

        return res

msf_budget_summary_line()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
