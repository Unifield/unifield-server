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
from osv import fields, osv
from tools.translate import _

class validate_account_move(osv.osv_memory):
    _name = "validate.account.move"
    _description = "Validate Account Move"
    _columns = {
        'journal_id': fields.many2one('account.journal', 'Journal', required=True),
        'period_id': fields.many2one('account.period', 'Period', required=True, domain=[('state','<>','done')]),
    }

    def validate_move(self, cr, uid, ids, context=None):
        obj_move = self.pool.get('account.move')
        if context is None:
            context = {}
        data = self.read(cr, uid, ids, context=context)[0]
        ids_move = obj_move.search(cr, uid, [('state','=','draft'),('journal_id','=',data['journal_id']),('period_id','=',data['period_id'])])
        if not ids_move:
            raise osv.except_osv(_('Warning'), _('Specified Journal does not have any account move entries in draft state for this period'))
        obj_move.button_validate(cr, uid, ids_move, context=context)
        return {'type': 'ir.actions.act_window_close'}

validate_account_move()

class validate_account_move_lines(osv.osv_memory):
    _name = "validate.account.move.lines"
    _description = "Validate Account Move Lines"

    def validate_move_lines(self, cr, uid, ids, context=None):
        obj_move_line = self.pool.get('account.move.line')
        obj_move = self.pool.get('account.move')
        obj_subscription_line = self.pool.get('account.subscription.line')
        obj_recurring_plan = self.pool.get('account.subscription')
        move_ids = []
        if context is None:
            context = {}
        data_line = obj_move_line.browse(cr, uid, context['active_ids'], context)
        for line in data_line:
            am = line.move_id
            if am.state == 'draft':
                for aml in am.line_id:
                    # check G/L account validity
                    vals_to_check = {'date': aml.date, 'period_id': aml.period_id.id,
                                     'account_id': aml.account_id.id, 'journal_id': aml.journal_id.id}
                    obj_move_line._check_date(cr, uid, vals_to_check, context=context)
                move_ids.append(am.id)
        move_ids = list(set(move_ids))
        if not move_ids:
            raise osv.except_osv(_('Warning'), _('Selected Entry Lines does not have any account move enties in draft state'))
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

