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
        'type_for_register': fields.selection([('none', 'None'), ('transfer', 'Transfer'), ('advance', 'Cash Advance')], string="Type for Third Parties", 
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

    def _reconcile_compute(self, cr, uid, ids, name, args, context, where =''):
        # UF-418: Add a new column to show the reconcile or partial reconcile value in the Journal Entries list
        if not ids: 
            return {}
        # get the ids of the reconcile or partially reconcile lines
        cr.execute( 'SELECT move_id, case when reconcile_partial_id is null then reconcile_id else reconcile_partial_id end '\
                    'FROM account_move_line '\
                    'WHERE move_id IN %s ', (tuple(ids),))
        result = dict(cr.fetchall())
        rec_pool = self.pool.get('account.move.reconcile')

        for id in ids:
            result.setdefault(id, None)
            # from each reconcile or partially reconcile id, get the name and amount in case of partially reconcile
            if result[id]:
                # this logic is taken from account_move_reconcile.name_get        
                r = rec_pool.browse(cr, uid, result[id], context=context)
                total = reduce(lambda y,t: (t.debit or 0.0) - (t.credit or 0.0) + y, r.line_partial_ids, 0.0)
                if total:
                    result[id] = '%s (%.2f)' % (r.name, total)
                else:
                    result[id] = r.name
        return result

    _columns = {
        'partner_type': fields.function(_get_third_parties_from_move_line, string="Third Parties", selection=[('account.bank.statement', 'Register'), ('hr.employee', 'Employee'), 
            ('res.partner', 'Partner')], size=128, readonly="1", type="reference", method=True),
        'reconcile_id': fields.function(_reconcile_compute, method=True, string='Reconcile', type='char'),
    }

account_move()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
