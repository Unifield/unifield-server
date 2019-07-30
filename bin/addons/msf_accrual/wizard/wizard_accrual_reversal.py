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


class wizard_accrual_reversal(osv.osv_memory):
    _name = 'wizard.accrual.reversal'

    _columns = {
        'document_date': fields.date("Document Date", required=True),
        'posting_date': fields.date("Posting Date", required=True),
    }

    _defaults = {
        'document_date': datetime.datetime.now(),
        'posting_date': datetime.datetime.now(),
    }

    def button_accrual_reversal_confirm(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        accrual_line_obj = self.pool.get('msf.accrual.line')
        period_obj = self.pool.get('account.period')

        if 'active_ids' in context:
            for accrual_line in accrual_line_obj.browse(cr, uid, context['active_ids'], context=context):
                # this option is valid only if the status is "partially posted"
                if accrual_line.state != 'partially_posted':
                    raise osv.except_osv(_('Warning !'),
                                         _("The line '%s' isn't partially posted, the accrual reversal can't be posted!") % accrual_line.description)

                # check for dates consistency
                document_date = self.browse(cr, uid, ids, context=context)[0].document_date
                posting_date = self.browse(cr, uid, ids, context=context)[0].posting_date
                accrual_move_date = accrual_line.period_id.date_stop
                if datetime.datetime.strptime(posting_date, "%Y-%m-%d").date() < datetime.datetime.strptime(document_date, "%Y-%m-%d").date():
                    raise osv.except_osv(_('Warning !'), _("Posting date should be later than Document Date."))
                if datetime.datetime.strptime(document_date, "%Y-%m-%d").date() < datetime.datetime.strptime(accrual_move_date, "%Y-%m-%d").date():
                    raise osv.except_osv(_('Warning !'), _("Document Date should be later than the accrual date."))

                # check if periods are open
                reversal_period_ids = period_obj.find(cr, uid, posting_date, context=context)
                if len(reversal_period_ids) == 0:
                    raise osv.except_osv(_('Warning !'), _("The reversal period wasn't found in the system!"))

                reversal_period_id = reversal_period_ids[0]
                reversal_period = period_obj.browse(cr, uid, reversal_period_id, context=context)
                if reversal_period.state not in ('draft', 'field-closed'):
                    raise osv.except_osv(_('Warning !'), _("The reversal period '%s' is not open!" % reversal_period.name))

                # post the accrual reversal
                accrual_line_obj.accrual_reversal_post(cr, uid, [accrual_line.id], document_date,
                                                       posting_date, context=context)

        # close the wizard
        return {'type' : 'ir.actions.act_window_close'}

wizard_accrual_reversal()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
