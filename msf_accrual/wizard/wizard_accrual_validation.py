# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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
import datetime
from dateutil.relativedelta import relativedelta

class wizard_accrual_validation(osv.osv_memory):
    _name = 'wizard.accrual.validation'

    def button_confirm(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        accrual_line_obj = self.pool.get('msf.accrual.line')
        period_obj = self.pool.get('account.period')
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        if 'active_ids' in context:
            for accrual_line in accrual_line_obj.browse(cr, uid, context['active_ids'], context=context):
                # check for periods, distribution, etc.
                if accrual_line.state == 'posted':
                    raise osv.except_osv(_('Warning !'), _("The line '%s' is already posted!") % accrual_line.description)
                elif not accrual_line.period_id:
                    raise osv.except_osv(_('Warning !'), _("The line '%s' has no period set!") % accrual_line.description)
                elif not accrual_line.analytic_distribution_id:
                    raise osv.except_osv(_('Warning !'), _("The line '%s' has no analytic distribution!") % accrual_line.description)
                else:
                    move_date = accrual_line.period_id.date_stop
                    reversal_move_date = (datetime.datetime.strptime(move_date, '%Y-%m-%d') + relativedelta(days=1)).strftime('%Y-%m-%d')
                    # check if periods are open
                    reversal_period_ids = period_obj.find(cr, uid, reversal_move_date, context=context)
                    if len(reversal_period_ids) == 0:
                        raise osv.except_osv(_('Warning !'), _("No period (M+1) was found in the system!"))
                    
                    reversal_period_id = reversal_period_ids[0]
                    reversal_period = period_obj.browse(cr, uid, reversal_period_id, context=context)
                    if accrual_line.period_id.state != 'draft':
                        raise osv.except_osv(_('Warning !'), _("The period '%s' is not open!" % accrual_line.period_id.name))
                    elif reversal_period.state != 'draft':
                        raise osv.except_osv(_('Warning !'), _("The reversal period '%s' is not open!" % reversal_period.name))
                    
                    # Create moves
                    move_vals = {
                        'ref': accrual_line.reference,
                        'period_id': accrual_line.period_id.id,
                        'journal_id': accrual_line.journal_id.id,
                        'date': move_date
                    }
                    reversal_move_vals = {
                        'ref': accrual_line.reference,
                        'period_id': reversal_period_id,
                        'journal_id': accrual_line.journal_id.id,
                        'date': reversal_move_date
                    }
                    move_id = move_obj.create(cr, uid, move_vals, context=context)
                    reversal_move_id = move_obj.create(cr, uid, reversal_move_vals, context=context)
                    
                    reversal_description = "REV - " + accrual_line.description
                    
                    # Create move lines
                    accrual_move_line_vals = {
                        'accrual': True,
                        'move_id': move_id,
                        'date': move_date,
                        'document_date': accrual_line.document_date,
                        'journal_id': accrual_line.journal_id.id,
                        'period_id': accrual_line.period_id.id,
                        'reference': accrual_line.reference,
                        'name': accrual_line.description,
                        'account_id': accrual_line.accrual_account_id.id,
                        'partner_id': ((accrual_line.partner_id) and accrual_line.partner_id.id) or False,
                        'employee_id': ((accrual_line.employee_id) and accrual_line.employee_id.id) or False,
                        'credit_currency': accrual_line.accrual_amount,
                        'currency_id': accrual_line.currency_id.id,
                    }
                    expense_move_line_vals = {
                        'accrual': True,
                        'move_id': move_id,
                        'date': move_date,
                        'document_date': accrual_line.document_date,
                        'journal_id': accrual_line.journal_id.id,
                        'period_id': accrual_line.period_id.id,
                        'reference': accrual_line.reference,
                        'name': accrual_line.description,
                        'account_id': accrual_line.expense_account_id.id,
                        'partner_id': ((accrual_line.partner_id) and accrual_line.partner_id.id) or False,
                        'employee_id': ((accrual_line.employee_id) and accrual_line.employee_id.id) or False,
                        'debit_currency': accrual_line.accrual_amount,
                        'currency_id': accrual_line.currency_id.id,
                        'analytic_distribution_id': accrual_line.analytic_distribution_id.id,
                    }
                    
                    # and their reversal (source_date to keep the old change rate)
                    reversal_accrual_move_line_vals = {
                        'accrual': True,
                        'move_id': reversal_move_id,
                        'date': reversal_move_date,
                        'document_date': reversal_move_date,
                        'source_date': move_date,
                        'journal_id': accrual_line.journal_id.id,
                        'period_id': reversal_period_id,
                        'reference': accrual_line.reference,
                        'name': reversal_description,
                        'account_id': accrual_line.accrual_account_id.id,
                        'partner_id': ((accrual_line.partner_id) and accrual_line.partner_id.id) or False,
                        'employee_id': ((accrual_line.employee_id) and accrual_line.employee_id.id) or False,
                        'debit_currency': accrual_line.accrual_amount,
                        'currency_id': accrual_line.currency_id.id,
                    }
                    reversal_expense_move_line_vals = {
                        'accrual': True,
                        'move_id': reversal_move_id,
                        'date': reversal_move_date,
                        'document_date': reversal_move_date,
                        'source_date': move_date,
                        'journal_id': accrual_line.journal_id.id,
                        'period_id': reversal_period_id,
                        'reference': accrual_line.reference,
                        'name': reversal_description,
                        'account_id': accrual_line.expense_account_id.id,
                        'partner_id': ((accrual_line.partner_id) and accrual_line.partner_id.id) or False,
                        'employee_id': ((accrual_line.employee_id) and accrual_line.employee_id.id) or False,
                        'credit_currency': accrual_line.accrual_amount,
                        'currency_id': accrual_line.currency_id.id,
                        'analytic_distribution_id': accrual_line.analytic_distribution_id.id,
                    }
                    
                    accrual_move_line_id = move_line_obj.create(cr, uid, accrual_move_line_vals, context=context)
                    expense_move_line_id = move_line_obj.create(cr, uid, expense_move_line_vals, context=context)
                    reversal_accrual_move_line_id = move_line_obj.create(cr, uid, reversal_accrual_move_line_vals, context=context)
                    reversal_expense_move_line_id = move_line_obj.create(cr, uid, reversal_expense_move_line_vals, context=context)
                    
                    # Post the moves
                    move_obj.post(cr, uid, [move_id, reversal_move_id], context=context)
                    # Reconcile the accrual move line with its reversal
                    move_line_obj.reconcile_partial(cr, uid, [accrual_move_line_id, reversal_accrual_move_line_id], context=context)
                    # validate the accrual line
                    accrual_line_obj.write(cr, uid, [accrual_line.id], {'state': 'posted'}, context=context)
                
        # we open a wizard
        return {'type' : 'ir.actions.act_window_close'}
    
wizard_accrual_validation()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
