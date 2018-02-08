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
        if 'active_ids' in context:
            for accrual_line in accrual_line_obj.browse(cr, uid, context['active_ids'], context=context):
                # check for periods, distribution, etc.
                if accrual_line.state == 'posted':
                    raise osv.except_osv(_('Warning !'), _("The line '%s' is already posted!") % accrual_line.description)
                elif accrual_line.state == 'partially_posted':
                    raise osv.except_osv(_('Warning !'), _("The line '%s' is already partially posted!") % accrual_line.description)
                elif accrual_line.state == 'cancel':
                    raise osv.except_osv(_('Warning !'), _("The line '%s' is cancelled and can't be re-posted.") % accrual_line.description)
                elif not accrual_line.period_id:
                    raise osv.except_osv(_('Warning !'), _("The line '%s' has no period set!") % accrual_line.description)
                elif not accrual_line.analytic_distribution_id:
                    raise osv.except_osv(_('Warning !'), _("The line '%s' has no analytic distribution!") % accrual_line.description)
                # US-770/1
                elif accrual_line.period_id.state not in ('draft', 'field-closed'):
                    raise osv.except_osv(_('Warning !'), _("The period '%s' is not open!") % accrual_line.period_id.name)
                elif accrual_line.accrual_type == 'reversing_accrual':
                    # in case of a reversing accrual the reversal period must be open
                    move_date = accrual_line.period_id.date_stop
                    reversal_move_date = (datetime.datetime.strptime(move_date, '%Y-%m-%d') + relativedelta(days=1)).strftime('%Y-%m-%d')
                    reversal_period_ids = period_obj.find(cr, uid, reversal_move_date, context=context)
                    if len(reversal_period_ids) == 0:
                        raise osv.except_osv(_('Warning !'), _("No period (M+1) was found in the system!"))

                    reversal_period_id = reversal_period_ids[0]
                    reversal_period = period_obj.browse(cr, uid, reversal_period_id, context=context)
                    if reversal_period.state not in ('draft', 'field-closed'):
                        raise osv.except_osv(_('Warning !'), _("The reversal period '%s' is not open!" % reversal_period.name))

                # post the accrual
                accrual_line_obj.accrual_post(cr, uid, [accrual_line.id], context=context)
                # post its reversal only if it is a reversing accrual
                if accrual_line.accrual_type == 'reversing_accrual':
                    reversal_date = (datetime.datetime.strptime(accrual_line.date, '%Y-%m-%d') + relativedelta(days=1)).strftime('%Y-%m-%d')
                    accrual_line_obj.accrual_reversal_post(cr, uid, [accrual_line.id], reversal_date,
                                                           reversal_date, context=context)
                
        # close the wizard
        return {'type' : 'ir.actions.act_window_close'}
    
wizard_accrual_validation()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
