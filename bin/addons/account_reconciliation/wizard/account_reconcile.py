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

class account_move_line_reconcile(osv.osv_memory):
    _inherit = 'account.move.line.reconcile'
    _name = 'account.move.line.reconcile'

    _columns = {
        'state': fields.selection([('total', 'Full Reconciliation'), ('partial', 'Partial Reconciliation'),
                                   ('total_change', 'Full Reconciliation with change'), ('partial_change', 'Partial Reconciliation with change')], string="State",
                                  required=True, readonly=True),
        'different_currencies': fields.boolean('Is this reconciliation in different currencies? (2 at most)'),
    }

    _defaults = {
        'state': lambda *a: 'total',
        'different_currencies': lambda *a: False,
    }

    # moved to bin/addons/account/wizard/account_reconcile.py
    # def default_get(self, cr, uid, fields, context=None, from_web=False):
    # def trans_rec_get(self, cr, uid, ids, context=None):


    def total_reconcile(self, cr, uid, ids, context=None):
        """
        Do a total reconciliation for given active_ids in context.
        Add another line to reconcile if some gain/loss of rate recalculation.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Prepare some value
        to_reconcile = context['active_ids']
        self.pool.get('account.move.line').reconcile(cr, uid, to_reconcile, 'manual', False, False, False, context=context)
        return {'type': 'ir.actions.act_window_close'}

    def partial_reconcile(self, cr, uid, ids, context=None):
        """
        Do a partial reconciliation
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Do partial reconciliation
        self.pool.get('account.move.line').reconcile_partial(cr, uid, context['active_ids'], 'manual', context=context)
        return {'type': 'ir.actions.act_window_close'}

account_move_line_reconcile()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
