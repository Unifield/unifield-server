# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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
from tools.translate import _

class account_unreconcile(osv.osv_memory):
    _name = "account.unreconcile"
    _description = "Account Unreconcile"

    def trans_unrec(self, cr, uid, ids, context=None):
        obj_move_line = self.pool.get('account.move.line')
        if context is None:
            context = {}
        if context.get('active_ids', False):
            if self._check_fx_adjustments(cr, uid, context['active_ids'], context):
                obj_move_line._remove_move_reconcile(cr, uid, context['active_ids'], context=context)
        return {'type': 'ir.actions.act_window_close'}

    def _check_fx_adjustments(self, cr, uid, move_line_ids, context):
        '''
        In case the reconciliation of one of the move lines had triggered an FX adjustment entry,
        the unreconciliation must be prevented.
        '''
        acc_ml_obj = self.pool.get('account.move.line')
        if move_line_ids:
            move_lines = acc_ml_obj.browse(cr, uid, move_line_ids, context)
            reconcile_ids = [(x.reconcile_id and x.reconcile_id.id) or (x.reconcile_partial_id and x.reconcile_partial_id.id) or None for x in move_lines]
            if reconcile_ids:
                # get all the related account move lines
                operator = 'in'
                if len(reconcile_ids) == 1:
                    operator = '='
                ml_ids = acc_ml_obj.search(cr, uid, [('reconcile_id', operator, reconcile_ids)], context=context)
                # search for addendum lines
                for line in acc_ml_obj.browse(cr, uid, ml_ids, context):
                    if line.is_addendum_line:
                       raise osv.except_osv(_('Error'), _('You cannot unreconcile entries with FX adjustment.'))
        return True

account_unreconcile()

class account_unreconcile_reconcile(osv.osv_memory):
    _name = "account.unreconcile.reconcile"
    _description = "Account Unreconcile Reconcile"

    def trans_unrec_reconcile(self, cr, uid, ids, context=None):
        obj_move_reconcile = self.pool.get('account.move.reconcile')
        if context is None:
            context = {}
        rec_ids = context['active_ids']
        if rec_ids:
            obj_move_reconcile.unlink(cr, uid, rec_ids, context=context)
        return {'type': 'ir.actions.act_window_close'}

account_unreconcile_reconcile()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: