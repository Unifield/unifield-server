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


class account_move_line(osv.osv):
    _name = 'account.move.line'
    _inherit = 'account.move.line'

    def open_update_received(self, cr, uid, ids, context=None):
        """
        Opens the Updates Received View with the SD ref of the selected JI already filled in
        """
        update_received_obj = self.pool.get('sync.client.update_received')
        return update_received_obj.open_update_list(cr, uid, ids, model='account.move.line', context=context)

    def open_update_sent(self, cr, uid, ids, context=None):
        """
        Opens the Updates Sent View with the SD ref of the selected JI already filled in
        """
        update_sent_obj = self.pool.get('sync.client.update_to_send')
        return update_sent_obj.open_update_list(cr, uid, ids, model='account.move.line', context=context)

account_move_line()


class account_analytic_line(osv.osv):
    _name = 'account.analytic.line'
    _inherit = 'account.analytic.line'

    def open_update_received(self, cr, uid, ids, context=None):
        """
        Opens the Updates Received View with the SD ref of the selected AJI already filled in
        """
        update_received_obj = self.pool.get('sync.client.update_received')
        return update_received_obj.open_update_list(cr, uid, ids, model='account.analytic.line', context=context)

    def open_update_sent(self, cr, uid, ids, context=None):
        """
        Opens the Updates Sent View with the SD ref of the selected AJI already filled in
        """
        update_sent_obj = self.pool.get('sync.client.update_to_send')
        return update_sent_obj.open_update_list(cr, uid, ids, model='account.analytic.line', context=context)

account_analytic_line()


class account_move(osv.osv):
    _name = 'account.move'
    _inherit = 'account.move'

    def open_update_received(self, cr, uid, ids, context=None):
        """
        Opens the Updates Received View with the SD ref of the selected JE already filled in
        """
        update_received_obj = self.pool.get('sync.client.update_received')
        return update_received_obj.open_update_list(cr, uid, ids, model='account.move', context=context)

    def open_update_sent(self, cr, uid, ids, context=None):
        """
        Opens the Updates Sent View with the SD ref of the selected JE already filled in
        """
        update_sent_obj = self.pool.get('sync.client.update_to_send')
        return update_sent_obj.open_update_list(cr, uid, ids, model='account.move', context=context)

account_move()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
