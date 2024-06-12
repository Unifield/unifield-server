# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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


class validate_account_move_lines(osv.osv_memory):
    _name = "validate.account.move.lines"
    _description = "Validate Account Move Lines"

    def validate_move_lines(self, cr, uid, ids, context=None):
        obj_move_line = self.pool.get('account.move.line')
        obj_move = self.pool.get('account.move')
        obj_subscription_line = self.pool.get('account.subscription.line')
        obj_recurring_plan = self.pool.get('account.subscription')
        moves = []
        if context is None:
            context = {}
        data_line = obj_move_line.browse(cr, uid, context['active_ids'], context)
        for line in data_line:
            if line.move_id.state == 'draft':
                moves.append(line.move_id)
        moves = list(set(moves))
        if not moves:
            raise osv.except_osv(_('Warning'), _('Selected Entry Lines do not have any account move entries in draft state'))
        # check G/L account validity
        for am in moves:
            for aml in am.line_id:
                vals_to_check = {'date': aml.date, 'period_id': aml.period_id.id,
                                 'account_id': aml.account_id.id, 'journal_id': aml.journal_id.id}
                obj_move_line._check_date(cr, uid, vals_to_check, context=context)
        move_ids = [m.id for m in moves]
        obj_move.button_validate(cr, uid, move_ids, context)
        # update the state of the related Recurring Plans if any
        sub_line_ids = obj_subscription_line.search(cr, uid, [('move_id', 'in', move_ids)], context=context)
        if sub_line_ids:
            recurring_plans = set()
            for sub_line in obj_subscription_line.browse(cr, uid, sub_line_ids, fields_to_fetch=['subscription_id'], context=context):
                recurring_plans.add(sub_line.subscription_id.id)
            for recurring_plan_id in recurring_plans:
                obj_recurring_plan.update_plan_state(cr, uid, recurring_plan_id, context=context)
        return {'type': 'ir.actions.act_window_close'}
validate_account_move_lines()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

