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

from osv import fields, osv
import decimal_precision as dp
from tools.translate import _

class account_move_line_compute_currency(osv.osv):
    _inherit = "account.move.line"
    
    def update_amounts(self, cr, uid, ids):
        cur_obj = self.pool.get('res.currency')
        analytic_obj = self.pool.get('account.analytic.line')
        for move_line in self.browse(cr, uid, ids):
            # amount currency is not set; it is computed from the 2 other fields
            ctx = {}
            if move_line.date:
                ctx['date'] = move_line.date
            if move_line.period_id.state != 'done':
                if move_line.debit_currency != 0.0 or move_line.credit_currency != 0.0:
                    # amount currency is not set; it is computed from the 2 other fields
                    amount_currency = move_line.debit_currency - move_line.credit_currency
                    debit_computed = cur_obj.compute(cr, uid, move_line.currency_id.id,
                        move_line.functional_currency_id.id, move_line.debit_currency, round=True, context=ctx)
                    credit_computed = cur_obj.compute(cr, uid, move_line.currency_id.id,
                        move_line.functional_currency_id.id, move_line.credit_currency, round=True, context=ctx)
                    cr.execute('update account_move_line set debit=%s, \
                                                             credit=%s, \
                                                             amount_currency=%s where id=%s', 
                              (debit_computed, credit_computed, amount_currency, move_line.id))
                elif move_line.debit_currency == 0.0 and \
                     move_line.credit_currency == 0.0 and \
                     move_line.amount_currency == 0.0 and \
                     (move_line.debit != 0.0 or move_line.debit != 0.0):
                    # only the debit/credit in functional currency are set;
                    # the amounts in booking currency are computed
                    debit_currency_computed = cur_obj.compute(cr, uid, move_line.functional_currency_id.id,
                        move_line.currency_id.id, move_line.debit, round=True, context=ctx)
                    credit_currency_computed = cur_obj.compute(cr, uid, move_line.functional_currency_id.id,
                        move_line.currency_id.id, move_line.credit, round=True, context=ctx)
                    amount_currency = debit_currency_computed - credit_currency_computed
                    cr.execute('update account_move_line set debit_currency=%s, \
                                                             credit_currency=%s, \
                                                             amount_currency=%s where id=%s', 
                              (debit_currency_computed, credit_currency_computed, amount_currency, move_line.id))
                elif move_line.debit_currency == 0.0 and \
                     move_line.credit_currency == 0.0 and \
                     move_line.amount_currency != 0.0:
                    # debit/credit currency are not set; it is computed from the amount currency
                    debit_currency = 0.0
                    credit_currency = 0.0
                    if move_line.amount_currency < 0:
                        credit_currency = -move_line.amount_currency
                    else:
                        debit_currency = move_line.amount_currency
                    cr.execute('update account_move_line set debit_currency=%s, \
                                                             credit_currency=%s where id=%s', 
                              (debit_currency, credit_currency, move_line.id))
                # Refresh the associated analytic lines
                analytic_line_ids = []
                for analytic_line in move_line.analytic_lines:
                    analytic_line_ids.append(analytic_line.id)
                analytic_obj.update_amounts(cr, uid, analytic_line_ids)
    
    def check_date(self, cr, uid, vals):
        # check that date is in period
        if 'period_id' in vals and 'date' in vals:
            period = self.pool.get('account.period').browse(cr, uid, vals['period_id'])
            if vals['date'] < period.date_start or vals['date'] > period.date_stop:
                raise osv.except_osv(_('Warning !'), _('Posting date is outside of defined period!'))
            

    def create(self, cr, uid, vals, context=None, check=True):
        self.check_date(cr, uid, vals)
        res_id = super(account_move_line_compute_currency, self).create(cr, uid, vals, context, check=False)
        self.update_amounts(cr, uid, [res_id])
        #@@@override@account.account_move_line.create()
        # The validation is re-done after the amounts have been modified.
        if 'journal_id' in vals:
            journal = self.pool.get('account.journal').browse(cr, uid, vals['journal_id'], context=context)
            if check and ((not context.get('no_store_function')) or journal.entry_posted):
                tmp = self.pool.get('account.move').validate(cr, uid, [vals['move_id']], context)
                if journal.entry_posted and tmp:
                    self.pool.get('account.move').button_validate(cr,uid, [vals['move_id']], context)
        return res_id
    
    def write(self, cr, uid, ids, vals, context=None, check=True, update_check=True):
        self.check_date(cr, uid, vals)
        #@@@override@account.account_move_line.write()
        # This is done to retrieve the todo_date from the super method.
        todo_date = None
        if vals.get('date', False):
            todo_date = vals['date']
        # @override
        res = super(account_move_line_compute_currency, self).write(cr, uid, ids, vals, context, check=False, update_check=update_check)
        self.update_amounts(cr, uid, ids)
        #@@@override@account.account_move_line.write()
        # The validation is re-done after the amounts have been modified.
        if check:
            done = []
            for line in self.browse(cr, uid, ids):
                if line.move_id.id not in done:
                    done.append(line.move_id.id)
                    self.pool.get('account.move').validate(cr, uid, [line.move_id.id], context)
                    if todo_date:
                        self.pool.get('account.move').write(cr, uid, [line.move_id.id], {'date': todo_date}, context=context)
        # @override
        return res
    
    _columns = {
        'debit_currency': fields.float('Booking Out', digits_compute=dp.get_precision('Account')),
        'credit_currency': fields.float('Booking In', digits_compute=dp.get_precision('Account')),
        'functional_currency_id': fields.related('account_id', 'company_id', 'currency_id', type="many2one", relation="res.currency", string="Functional Currency", store=False),
        # Those fields are for UF-173: Accounting Journals.
        # Since they are used in the move line view, they are added in Multi-Currency.
        'journal_sequence': fields.related('journal_id', 'sequence_id', 'name', type="char", string="Journal Sequence", store=False),
        'instance': fields.related('journal_id', 'instance_id', type="char", string="Proprietary instance", store=False),
    }
    
    _defaults = {
        'debit_currency': 0.0,
        'credit_currency': 0.0,
    }
    
account_move_line_compute_currency()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
