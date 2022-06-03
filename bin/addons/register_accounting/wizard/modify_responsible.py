#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) TeMPO Consulting (<http://www.tempo-consulting.fr/>), MSF.
#    All Rights Reserved
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


class modify_responsible(osv.osv_memory):
    _name = 'modify.responsible'

    def _get_registers(self, cr, uid, context=None):
        if context is None:
            context = {}
        return context.get('active_ids', False)

    def _get_responsible_ids(self, cr, uid, context=None):
        if context is None:
            context = {}
        ids = context.get('active_ids', False)
        if ids and len(ids) == 1:
            return self.pool.get('account.bank.statement').read(cr, uid, ids[0], ['responsible_ids'], context=context)['responsible_ids']
        return []

    _columns = {
        'registers_ids': fields.many2many('account.bank.statement','modify_responsible_bank_statement_rel',
                                          'statement_id', 'wizard_id', string="Impacted Registers"),
        'responsible_ids': fields.many2many('res.users', 'bank_statement_users_rel', 'statement_id', 'user_id',
                                            'Responsibles'),
    }
    _defaults = {
        'registers_ids': _get_registers,
        'responsible_ids': _get_responsible_ids,
    }

    def modify_responsible(self, cr, uid, ids, context=None):
        '''
        US-8003: Write the list of users in the selected registers responsible list
        '''
        if context is None:
            context = {}
        reg_obj = self.pool.get('account.bank.statement')
        active_ids = context.get('active_ids', False)
        if active_ids:
            resp_ids = self.read(cr, uid, ids, ['responsible_ids'])[0]['responsible_ids']
            reg_obj.write(cr, uid, active_ids, {'responsible_ids': [(6, 0, resp_ids)]}, context=context)
        return {'type': 'ir.actions.act_window_close'}


modify_responsible()
