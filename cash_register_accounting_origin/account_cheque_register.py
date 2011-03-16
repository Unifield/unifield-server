#!/usr/bin/env python
# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution    
#    Copyright (C) Tempo Consulting (<http://www.tempo-consulting.fr/>), MSF.
#    All Rigts Reserved
#    Developer: Olivier DOSSMANN
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

class account_cheque_register(osv.osv):
    _name = "account.bank.statement"
    _inherit = "account.bank.statement"

    _columns = {
        'display_type': fields.selection([('all', 'All'), ('reconciled', 'Reconciled'), ('unreconciled', 'Not Reconciled')], string="Display type"),
    }

    def button_open_cheque(self, cr, uid, ids, context={}):
        """
        When you click on "Open Cheque Register"
        """
        return self.write(cr, uid, ids, {'state': 'open'}, context=context)

    def button_confirm_cheque(self, cr, uid, ids, context={}):
        """
        When you press "Confirm" on a Cheque Register.
        You have to verify that all lines are in hard posting, then that they are reconciled.
        """
        # @ this moment, the button_confirm_bank verify that all lines are hard posted and reconciled
        return self.button_confirm_bank(cr, uid, ids, context=context)

account_cheque_register()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
