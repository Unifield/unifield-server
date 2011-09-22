#!/usr/bin/env python
#-*- encoding:utf-8 -*-
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
from time import strftime
from tools.translate import _

class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    def action_reverse_engagement_lines(self, cr, uid, ids, context, *args):
        """
        Reverse an engagement lines with an opposite amount
        """
        if not context:
            context = {}
        eng_obj = self.pool.get('account.analytic.line')
        # Browse invoice
        for inv in self.browse(cr, uid, ids, context=context):
            # Search engagement journal line ids
            invl_ids = [x.id for x in inv.invoice_line]
            eng_ids = eng_obj.search(cr, uid, [('invoice_line_id', 'in', invl_ids)])
            # Browse engagement journal line ids
            for eng in eng_obj.browse(cr, uid, eng_ids, context=context):
                # Create new line and change some fields:
                # - name with REV
                # - amount * -1
                # - date with invoice_date
                # Copy this line for reverse
                new_line_id = eng_obj.copy(cr, uid, eng.id, context=context)
                # Prepare reverse values
                vals = {
                    'name': eng_obj.join_without_redundancy(eng.name, 'REV'),
                    'amount': eng.amount * -1,
                    'date': inv.date_invoice,
                    'reversal_origin': eng.id,
                    'amount_currency': eng.amount_currency * -1,
                    'currency_id': eng.currency_id.id,
                }
                # Write changes
                eng_obj.write(cr, uid, [new_line_id], vals, context=context)
        return True

    def action_open_invoice(self, cr, uid, ids, context={}, *args):
        """
        Give function to use when changing invoice to open state
        """
        if not self.action_date_assign(cr, uid, ids, context, args):
            return False
        if not self.action_move_create(cr, uid, ids, context, args):
            return False
        if not self.action_reverse_engagement_lines(cr, uid, ids, context, args):
            return False
        if not self.action_number(cr, uid, ids, context):
            return False
        return self.write(cr, uid, ids, {'state': 'open'}, context=context)

account_invoice()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
