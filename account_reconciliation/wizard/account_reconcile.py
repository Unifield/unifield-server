#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
from tools.translate import _

class account_move_line_reconcile(osv.osv_memory):
    _inherit = 'account.move.line.reconcile'
    _name = 'account.move.line.reconcile'

    _columns = {
        'state': fields.selection([('total', 'Full Reconciliation'), ('partial', 'Partial Reconciliation')], string="State", 
            required=True, readonly=True),
    }

    _defaults = {
        'state': lambda *a: 'total',
    }

    def default_get(self, cr, uid, fields, context={}):
        """
        Add state field in res
        """
        # Some verifications
        if not context:
            context = {}
        # Default value
        res = super(account_move_line_reconcile, self).default_get(cr, uid, fields, context=context)
        # Retrieve some value
        data = self.trans_rec_get(cr, uid, context['active_ids'], context=context)
        # Update res with state value
        if 'state' in fields and 'state' in data:
            res.update({'state': data['state']})
        return res

    def trans_rec_get(self, cr, uid, ids, context={}):
        """
        Add some values to res
        - state: if write-off is 0.0, then 'total' else 'partial'
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = super(account_move_line_reconcile, self).trans_rec_get(cr, uid, ids, context=context)
        state = 'partial'
        # Adapt state value
        if 'writeoff' in res:
            if res.get('writeoff') == 0.0:
                state = 'total'
        res.update({'state': state})
        return res

account_move_line_reconcile()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
