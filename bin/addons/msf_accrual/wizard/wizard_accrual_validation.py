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

from osv import osv
from tools.translate import _
import datetime
from dateutil.relativedelta import relativedelta


class wizard_accrual_validation(osv.osv_memory):
    _name = 'wizard.accrual.validation'

    def button_confirm(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        accrual_line_obj = self.pool.get('msf.accrual.line')
        if 'active_ids' in context:
            for accrual_line in accrual_line_obj.browse(cr, uid, context['active_ids'], context=context):
                # check for periods, distribution, etc.
                if accrual_line.state == 'done':
                    raise osv.except_osv(_('Warning'), _('The Accrual "%s" is already in Done state!') % accrual_line.description)
                elif accrual_line.state == 'running':
                    raise osv.except_osv(_('Warning'), _('The Accrual "%s" is already in Running state!') % accrual_line.description)
                elif accrual_line.state == 'cancel':
                    raise osv.except_osv(_('Warning'), _('The Accrual "%s" is cancelled and can\'t be re-posted.') % accrual_line.description)
                elif not accrual_line.expense_line_ids:
                    raise osv.except_osv(_('Warning'),
                                         _('Please add some lines to the Accrual "%s" before posting it!') % accrual_line.description)
                elif accrual_line.period_id.state != 'draft':
                    raise osv.except_osv(_('Warning'), _("The period \"%s\" is not Open!") % accrual_line.period_id.name)
                if not accrual_line.analytic_distribution_id:
                    for expense_line in accrual_line.expense_line_ids:
                        if not expense_line.analytic_distribution_id:
                            raise osv.except_osv(_('Warning'), _('Some of the lines of the Accrual "%s" have no analytic distribution!') %
                                                 expense_line.description)
                same_symbol = all(l.accrual_amount >= 0 for l in accrual_line.expense_line_ids) or \
                    all(l.accrual_amount < 0 for l in accrual_line.expense_line_ids)
                if not same_symbol:
                    raise osv.except_osv(_('Warning'),
                                         _('The Accrual "%s" has both positive and negative lines!') % accrual_line.description)
                # post the accrual
                accrual_line_obj.accrual_post(cr, uid, [accrual_line.id], context=context)
                # post its reversal only if it is a reversing accrual
                if accrual_line.accrual_type == 'reversing_accrual':
                    reversal_date = (datetime.datetime.strptime(accrual_line.date, '%Y-%m-%d') + relativedelta(days=1)).strftime('%Y-%m-%d')
                    # use the same method to get the reversal period as from the reversal wizard
                    reversal_period_id = self.pool.get('wizard.accrual.reversal').get_period_for_reversal(cr, uid,
                                                                                                          reversal_date,
                                                                                                          accrual_line.period_id.id,
                                                                                                          context=context)
                    accrual_line_obj.accrual_reversal_post(cr, uid, [accrual_line.id], reversal_date, reversal_date,
                                                           reversal_period_id, context=context)

        # close the wizard
        return {'type': 'ir.actions.act_window_close'}


wizard_accrual_validation()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
