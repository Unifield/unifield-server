# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2022 MSF, TeMPO Consulting.
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

from osv import fields, osv
from tools.translate import _
from base import currency_date


class msf_accrual_line_expense(osv.osv):
    # this object corresponds to the "lines" of the "msf.accrual.line"
    _name = 'msf.accrual.line.expense'
    _rec_name = 'description'

    def _have_analytic_distribution_from_header(self, cr, uid, ids, name, arg, context=None):
        """
        Returns False if the expense line has its own AD, else returns True (i.e. the AD to consider is at header level)
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for expense_line in self.browse(cr, uid, ids, fields_to_fetch=['analytic_distribution_id'], context=context):
            if expense_line.analytic_distribution_id:
                res[expense_line.id] = False
            else:
                res[expense_line.id] = True
        return res

    def _get_distribution_state(self, cr, uid, ids, name, args, context=None):
        """
        Gets Analytic Distribution state:
         - if the AD is compatible with the line, then "valid"
         - if there is no distribution at line level, use the AD at header level: if it is compatible with the line, then "valid"
         - if there is no AD at header level either, then "none"
         - in the specific UC where several distrib. lines are applied to a booking amount <= 1, then "invalid_small_amount"
         - all other cases are "invalid"
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for expense_line in self.browse(cr, uid, ids,
                                        fields_to_fetch=['analytic_distribution_id', 'accrual_line_id', 'expense_account_id', 'accrual_amount'],
                                        context=context):
            res[expense_line.id] = self.pool.get('analytic.distribution').\
                _get_distribution_state(cr, uid, expense_line.analytic_distribution_id.id,
                                        expense_line.accrual_line_id.analytic_distribution_id.id,
                                        expense_line.expense_account_id.id, context=context,
                                        amount=expense_line.accrual_amount or 0.0)
        return res

    def _get_distribution_state_recap(self, cr, uid, ids, name, arg, context=None):
        """
        Displays the AD state and "(from header)" if applicable
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for expense_line in self.browse(cr, uid, ids,
                                        fields_to_fetch=['have_analytic_distribution_from_header', 'analytic_distribution_state'],
                                        context=context):
            # note: all accounts used in the expense lines are accounts "with AD"
            if expense_line.have_analytic_distribution_from_header:
                from_header = _(' (from header)')
            else:
                from_header = ''
            ad_state = self.pool.get('ir.model.fields').get_browse_selection(cr, uid, expense_line, 'analytic_distribution_state', context)
            res[expense_line.id] = '%s%s' % (ad_state, from_header)
        return res

    def _get_expense_lines(self, cr, uid, ids, context=None):
        """
        Returns the list of ids of the expense lines related to the Accruals in param
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = []
        for accrual_line in self.browse(cr, uid, ids, fields_to_fetch=['expense_line_ids'], context=context):
            res.extend([l.id for l in accrual_line.expense_line_ids])
        return res

    def _get_functional_amount(self, cr, uid, ids, field_name, arg, context=None):
        """
        Returns the functional amount of the expense lines
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for expense_line in self.browse(cr, uid, ids, fields_to_fetch=['accrual_line_id', 'accrual_amount'], context=context):
            curr_date = currency_date.get_date(self, cr, expense_line.accrual_line_id.document_date, expense_line.accrual_line_id.date)
            date_context = {'currency_date': curr_date}
            res[expense_line.id] = self.pool.get('res.currency').compute(cr, uid,
                                                                         expense_line.accrual_line_id.currency_id.id,
                                                                         expense_line.accrual_line_id.functional_currency_id.id,
                                                                         expense_line.accrual_amount or 0.0,
                                                                         round=True, context=date_context)
        return res

    _columns = {
        'line_number': fields.integer(string='Line Number', readonly=True),
        'description': fields.char('Description', size=64, required=True),
        'expense_account_id': fields.many2one('account.account', 'Expense Account', required=True,
                                              domain=[('restricted_area', '=', 'accruals')]),
        'accrual_amount': fields.float('Accrual Amount', required=True),
        'functional_amount': fields.function(_get_functional_amount, type='float', method=True, readonly=True,
                                             string="Functional Amount",
                                             store={
                                                 'msf.accrual.line.expense': (lambda self, cr, uid, ids, c=None: ids, ['accrual_amount'], 10),
                                                 'msf.accrual.line': (_get_expense_lines, ['currency_id'], 20),
                                             }),
        'accrual_line_id': fields.many2one('msf.accrual.line', 'Accrual Line', required=True, ondelete='cascade'),
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
        'have_analytic_distribution_from_header': fields.function(_have_analytic_distribution_from_header, method=True,
                                                                  store=False, type='boolean', string='Header Distribution'),
        'analytic_distribution_state': fields.function(_get_distribution_state, method=True, store=False, type='selection',
                                                       selection=[('none', 'None'),
                                                                  ('valid', 'Valid'),
                                                                  ('invalid', 'Invalid'),
                                                                  ('invalid_small_amount', 'Invalid')],
                                                       string="Distribution state"),
        'analytic_distribution_state_recap': fields.function(_get_distribution_state_recap, method=True, store=False,
                                                             type='char', size=30, string="Distribution",
                                                             help="Gives the AD state and specify \"from header\" if applicable"),
    }

    _order = 'line_number'

    def create(self, cr, uid, vals, context=None):
        """
        Creates the line and sets the line number.
        """
        if context is None:
            context = {}
        if vals.get('accrual_line_id') and self._name == 'msf.accrual.line.expense':
            accrual = self.pool.get('msf.accrual.line').browse(cr, uid, vals['accrual_line_id'], fields_to_fetch=['sequence_id'])
            if accrual and accrual.sequence_id:
                line_number = accrual.sequence_id.get_id(code_or_id='id', context=context)
                vals.update({'line_number': line_number})
        return super(msf_accrual_line_expense, self).create(cr, uid, vals, context=context)

    def button_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Opens the analytic distribution wizard on the accrual expense line
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        expense_line = self.browse(cr, uid, ids[0],
                                   fields_to_fetch=['analytic_distribution_id', 'accrual_amount', 'accrual_line_id', 'expense_account_id'],
                                   context=context)
        # get the current AD of the line if any
        distrib_id = expense_line.analytic_distribution_id and expense_line.analytic_distribution_id.id or False
        vals = {
            'total_amount': expense_line.accrual_amount or 0.0,
            'accrual_expense_line_id': expense_line.id,
            'currency_id': expense_line.accrual_line_id.currency_id.id,
            'state': 'dispatch',
            'account_id': expense_line.expense_account_id.id,
            'posting_date': expense_line.accrual_line_id.date,
            'document_date': expense_line.accrual_line_id.document_date,
        }
        if distrib_id:
            vals.update({'distribution_id': distrib_id,})
        # create and open the wizard
        wiz_id = self.pool.get('analytic.distribution.wizard').create(cr, uid, vals, context=context)
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        return {
            'name': _('Analytic distribution'),
            'type': 'ir.actions.act_window',
            'res_model': 'analytic.distribution.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': [wiz_id],
            'context': context,
        }

    def copy_data(self, cr, uid, acc_line_exp_id, default=None, context=None):
        """
        Duplicates the expense line, resets its line number, and links it to a COPY of the AD from the initial line.
        """
        if context is None:
            context = {}
        if default is None:
            default = {}
        default.update({
            'line_number': False,
        })
        acc_line_exp_copied = self.browse(cr, uid, [acc_line_exp_id], fields_to_fetch=['analytic_distribution_id'], context=context)[0]
        if acc_line_exp_copied.analytic_distribution_id:
            new_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, acc_line_exp_copied.analytic_distribution_id.id, {},
                                                                         context=context)
            if new_distrib_id:
                default.update({'analytic_distribution_id': new_distrib_id})
        return super(msf_accrual_line_expense, self).copy_data(cr, uid, acc_line_exp_id, default=default, context=context)


msf_accrual_line_expense()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
