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

class account_journal(osv.osv):
    _name = "account.journal"
    _inherit = "account.journal"

    _columns = {
        'type': fields.selection([('sale', 'Sale'),('sale_refund','Sale Refund'), ('purchase', 'Purchase'), ('purchase_refund','Purchase Refund'), \
            ('cash', 'Cash'), ('bank', 'Bank and Cheques'), ('general', 'General'), ('cheque', 'Cheque'), \
            ('situation', 'Opening/Closing Situation')], 'Type', size=32, required=True,
             help="Select 'Sale' for Sale journal to be used at the time of making invoice."\
             " Select 'Purchase' for Purchase Journal to be used at the time of approving purchase order."\
             " Select 'Cash' to be used at the time of making payment."\
             " Select 'General' for miscellaneous operations."\
             " Select 'Opening/Closing Situation' to be used at the time of new fiscal year creation or end of year entries generation."),
        }

account_journal()

class account_account(osv.osv):
    _name = "account.account"
    _inherit = "account.account"

    _columns = {
        'type_for_register': fields.selection([('none', 'None'), ('transfer', 'Transfer'), ('advance', 'Cash Advance')], string="Type for Third Parties", 
            help="""This permit to give a type to this account that impact registers. In fact this will link an account with a type of element 
            that could be attached. For an example make the account to be a transfer type will display only registers to the user in the Cash Register 
            when he add a new register line.
            """, required=True)
    }

    _defaults = {
        'type_for_register': lambda *a: 'none',
    }

    def name_get(self, cr, uid, ids, context={}):
        """
        Give only code account for each id given by ids
        """
        res = self.pool.get('account.account').read(cr, uid, ids, ['code'], context=context)
        return [(int(x['id']), x['code']) for x in res]

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
            if move.partner_id:
                res[move.id] = 'res.partner,%s' % move.partner_id.id
            else:
                # Catching lines that have a third party
                move_lines_with_third_parties = []
                for move_line in move.line_id:
                    if move_line.third_parties:
                        move_lines_with_third_parties.append(move_line)
                # If number of remembered lines is equivalent to all attaches move lines, so we can display a third parties
                nb_move_line = len(move.line_id)
                nb_line_with_third_parties = len(move_lines_with_third_parties)
                if nb_move_line == nb_line_with_third_parties:
                    # Verify that all third parties are similar
                    total = 0
                    for (i, mlwtp) in enumerate(move_lines_with_third_parties):
                        if i == 0:
                            first_third_party = mlwtp.third_parties
                            total += 1
                        else:
                            if first_third_party == mlwtp.third_parties:
                                total += 1
                    if total == nb_line_with_third_parties:
                        res[move.id] = ','.join([str(first_third_party._table_name), str(first_third_party.id)])
        return res

    _columns = {
        'partner_type': fields.function(_get_third_parties_from_move_line, string="Third Parties", selection=[('account.bank.statement', 'Register'), ('hr.employee', 'Employee'), 
            ('res.partner', 'Partner')], size=128, readonly="1", type="reference", method=True),
    }

account_move()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
