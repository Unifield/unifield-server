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
        'document_date': lambda *a: datetime.datetime.now(),
        'posting_date': lambda *a: datetime.datetime.now(),
    }

    def get_period_for_reversal(self, cr, uid, posting_date, initial_period_id, context=None):
        """
        Returns the period to use for the reversal entry
        """
        if context is None:
            context = {}
        period_obj = self.pool.get('account.period')
        # note that Periods 0 (with active = False) are by default excluded, so a date in January should return only ONE period
        reversal_period_ids = period_obj.find(cr, uid, posting_date, context=context)
        if len(reversal_period_ids) == 0:
            raise osv.except_osv(_('Warning'), _("The reversal period has not been found in the system!"))
        elif len(reversal_period_ids) > 1:  # December periods
            # search for the first opened period
            if initial_period_id in reversal_period_ids:
                # if the initial entry is also in a December period, use this period or above (typically a One-Time
                # Accrual for which the reversal date chosen is the same as the original date)
                start_number = period_obj.read(cr, uid, initial_period_id, ['number'], context=context)['number'] or 12
            else:
                start_number = 12
            dec_period_ids = period_obj.search(cr, uid,
                                               [('id', 'in', reversal_period_ids),
                                                ('number', 'in', list(range(start_number, 16))),  # Period 16 excluded
                                                ('state', '=', 'draft')],
                                               order='number', limit=1, context=context)
            if not dec_period_ids:
                raise osv.except_osv(_('Warning'), _("No opened period found to post the reversal entry!"))
            reversal_period_id = dec_period_ids[0]
        else:
            reversal_period_id = reversal_period_ids[0]
            reversal_period = period_obj.browse(cr, uid, reversal_period_id, fields_to_fetch=['state', 'name'], context=context)
            if reversal_period.state != 'draft':
                raise osv.except_osv(_('Warning'), _("The period \"%s\" is not Open!") % (reversal_period.name,))
        return reversal_period_id

    def button_accrual_reversal_confirm(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        accrual_line_obj = self.pool.get('msf.accrual.line')

        if 'active_ids' in context:
            for accrual_line in accrual_line_obj.browse(cr, uid, context['active_ids'], context=context):
                # this option is valid only if the status is "running"
                if accrual_line.state != 'running':
                    raise osv.except_osv(_('Warning !'),
                                         _("The Accrual \"%s\" isn't in Running state, the accrual reversal can't be posted!") %
                                         accrual_line.description)

                # check for dates consistency (note that it is possible to select in the wizard the same posting date as the original entry)
                wizard = self.browse(cr, uid, ids, context=context)[0]
                document_date = wizard.document_date
                posting_date = wizard.posting_date
                accrual_move_date = accrual_line.period_id.date_stop
                if datetime.datetime.strptime(posting_date, "%Y-%m-%d").date() < datetime.datetime.strptime(document_date, "%Y-%m-%d").date():
                    raise osv.except_osv(_('Warning !'), _("Posting date should be later than Document Date."))
                if datetime.datetime.strptime(document_date, "%Y-%m-%d").date() < datetime.datetime.strptime(accrual_move_date, "%Y-%m-%d").date():
                    raise osv.except_osv(_('Warning !'), _("Document Date should be later than the accrual date."))

                reversal_period_id = self.get_period_for_reversal(cr, uid, posting_date, accrual_line.period_id.id, context=context)

                # post the accrual reversal
                accrual_line_obj.accrual_reversal_post(cr, uid, [accrual_line.id], document_date, posting_date,
                                                       reversal_period_id, context=context)

        # close the wizard
        return {'type': 'ir.actions.act_window_close'}


wizard_accrual_reversal()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
