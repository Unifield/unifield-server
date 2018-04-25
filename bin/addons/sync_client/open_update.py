#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2018 TeMPO Consulting, MSF. All Rights Reserved
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


class open_update(osv.osv):
    _name = 'open.update'

    def open_update_received(self, cr, uid, ids, context=None):
        """
        Opens the Updates Received View with the SD ref of the selected entry already filled in
        """
        update_received_obj = self.pool.get('sync.client.update_received')
        return update_received_obj.open_update_list(cr, uid, ids, model=self._name, context=context)

    def open_update_sent(self, cr, uid, ids, context=None):
        """
        Opens the Updates Sent View with the SD ref of the selected entry already filled in
        """
        update_sent_obj = self.pool.get('sync.client.update_to_send')
        return update_sent_obj.open_update_list(cr, uid, ids, model=self._name, context=context)

open_update()


class account_move_line(osv.osv):
    _name = 'account.move.line'
    _inherit = ['account.move.line', 'open.update']

account_move_line()


class account_analytic_line(osv.osv):
    _name = 'account.analytic.line'
    _inherit = ['account.analytic.line', 'open.update']

account_analytic_line()


class account_move(osv.osv):
    _name = 'account.move'
    _inherit = ['account.move', 'open.update']

account_move()


class res_partner(osv.osv):
    _name = 'res.partner'
    _inherit = ['res.partner', 'open.update']

res_partner()


class account_bank_statement(osv.osv):
    _name = 'account.bank.statement'
    _inherit = ['account.bank.statement', 'open.update']

account_bank_statement()


class account_bank_statement_line(osv.osv):
    _name = 'account.bank.statement.line'
    _inherit = ['account.bank.statement.line', 'open.update']

account_bank_statement_line()


class hq_entries(osv.osv):
    _name = 'hq.entries'
    _inherit = ['hq.entries', 'open.update']

hq_entries()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
