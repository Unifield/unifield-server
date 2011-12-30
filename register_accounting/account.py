#!/usr/bin/env python
# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
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

class account_account(osv.osv):
    _name = "account.account"
    _inherit = "account.account"

    _columns = {
        'type_for_register': fields.selection([('none', 'None'), ('transfer', 'Transfer'), ('transfer_same','Transfer (same currency)'), 
            ('advance', 'Cash Advance'), ('down_payment', 'Down payment')], string="Type for Third Parties", 
            help="""This permit to give a type to this account that impact registers. In fact this will link an account with a type of element 
            that could be attached. For an example make the account to be a transfer type will display only registers to the user in the Cash Register 
            when he add a new register line.
            """, required=True)
    }

    _defaults = {
        'type_for_register': lambda *a: 'none',
    }

account_account()

class account_move(osv.osv):
    _name = "account.move"
    _inherit = "account.move"

    def _get_third_parties_from_move_line(self, cr, uid, ids, field_name=None, arg=None, context={}):
        """
        Give the third parties of the given account.move.
        If all move lines content the same third parties, then return this third parties.
        If a partner_id field is filled in, then comparing both.
        """
        res = {}
        for move in self.browse(cr, uid, ids, context=context):
            line_ids = []
            res[move.id] = False
            move_line_obj = self.pool.get('account.move.line')
            prev = None
            for move_line in move.line_id:
                if prev is None:
                    prev = move_line.third_parties
                elif prev != move_line.third_parties:
                    prev = False
                    break
            if prev:
                res[move.id] = "%s,%s"%(prev._table_name, prev.id)
        return res

    _columns = {
        'partner_type': fields.function(_get_third_parties_from_move_line, string="Third Parties", selection=[('account.bank.statement', 'Register'), ('hr.employee', 'Employee'), 
            ('res.partner', 'Partner'), ('account.journal', 'Journal')], size=128, readonly="1", type="reference", method=True),
    }

account_move()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
