#-*- coding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2024 TeMPO Consulting, MSF. All Rights Reserved
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
from osv import fields
from tools.translate import _

class wizard_confirm_closing_balance(osv.osv_memory):
    _name = 'wizard.confirm.closing.balance'

    _columns = {
        'is_prev_reg_open': fields.boolean('Is previous month register open'),
        'display_normal': fields.boolean('Are you sure you want to freeze closing balance?'),
        'display_override': fields.boolean('Are you sure you want to freeze closing balance while the previous period is still open?')
    }

    _defaults = {
        'is_prev_reg_open': True,
        'display_normal': False,
        'display_override': False,
    }

    def button_confirm_closing_balance(self, cr, uid, ids, context=None):
        res = False
        reg_id = context.get('active_id', False) or context.get('active_ids')[0] or False
        if not reg_id:
            raise osv.except_osv(_("Error"), _("Source register lost. Please contact an administrator to solve this problem."))
        res = self.pool.get('account.bank.statement').button_confirm_closing_balance(cr, uid, reg_id, context=context)
        if res:
            return {'type': 'ir.actions.act_window_close'}
        raise osv.except_osv(_('Error'), _('An unknown error has occurred on closing balance freezing confirmation wizard. Please contact an administrator to solve this problem.'))


wizard_confirm_closing_balance()
