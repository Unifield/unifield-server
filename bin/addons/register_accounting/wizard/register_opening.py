#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2017 TeMPO Consulting, MSF. All Rights Reserved
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


class wizard_register_opening_confirmation(osv.osv_memory):

    _name = 'wizard.register.opening.confirmation'

    _columns = {
        'register_id': fields.many2one('account.bank.statement', 'Register', required=True, readonly=True),
        'confirm_opening_period': fields.boolean(string='Do you want to open the register on the following period?',
                                                 required=False),
        'opening_period': fields.related('register_id', 'period_id', string='Opening Period', type='many2one',
                                         relation='account.period', readonly=True),
    }

    def button_confirm_register_opening(self, cr, uid, ids, context=None):
        """
        Triggers the opening of the register if all the confirmation tick boxes have been ticked
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        reg_obj = self.pool.get('account.bank.statement')
        wiz = self.browse(cr, uid, ids[0], context=context)
        reg_id = wiz.register_id.id
        period_ok = wiz.confirm_opening_period
        if not period_ok:
            raise osv.except_osv(_('Warning'), _('You must tick the box before clicking on Yes.'))
        else:
            reg_obj.open_register(cr, uid, reg_id, context=context)
        return {'type': 'ir.actions.act_window_close'}


wizard_register_opening_confirmation()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
