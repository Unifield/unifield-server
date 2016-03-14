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

class cashbox_write_off(osv.osv_memory):
    _name = 'cashbox.write.off'

    _columns = {
        # Deleted from selection since UTP-209:
        #('writeoff', 'Accept write-off and close register'),
        'choice' : fields.selection( [('reopen', 'Re-open Register')], \
            string="Decision about CashBox", required=True),
        'account_id': fields.many2one('account.account', string="Write-off Account", domain="[('type', '!=', 'view'), ('user_type_code', '=', 'expense')]"),
        'amount': fields.float(string="CashBox difference", digits=(16, 2), readonly=True),
    }

    def default_get(self, cr, uid, fields=None, context=None):
        """
        Return the difference between balance_end and balance_end_cash from the cashbox and diplay it in the wizard.
        """
        if context is None:
            context = {}
        res = super(cashbox_write_off, self).default_get(cr, uid, fields, context=context)
        # Have we got any cashbox id ?
        if 'active_id' in context:
            # search values
            cashbox_id = context.get('active_id')
            cashbox = self.pool.get('account.bank.statement').browse(cr, uid, cashbox_id)
            amount = cashbox.balance_end - cashbox.balance_end_cash
            res.update({'amount': amount})
        return res

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Define elements for two case:
         - when raising an error : give a wizard with some information
         - other case : give the normal wizard
        """
        res = super(cashbox_write_off, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        if 'active_id' in context:
            # search values
            cashbox_id = context.get('active_id')
            cashbox = self.pool.get('account.bank.statement').browse(cr, uid, cashbox_id)
            if cashbox.state not in ['partial_close', 'confirm']:
                raise osv.except_osv(_('Warning'), _("Please use 'Close CashBox' button before."))
        return res

    def action_confirm_choice(self, cr, uid, ids, context=None):
        """
        Do what the user wants, but not coffee ! Just this :
        - re-open the cashbox
        - do a write-off
        """
        if context is None:
            context = {}
        w_id = context.get('active_id', False)
        if not w_id:
            raise osv.except_osv(_('Warning'), _('You cannot decide about Cash Discrepancy without selecting any CashBox!'))
        else:
            # search cashbox object
            cashbox = self.pool.get('account.bank.statement').browse(cr, uid, w_id)
            cstate = cashbox.state
            # What about cashbox state ?
            if cstate not in ['partial_close', 'confirm']:
                raise osv.except_osv(_('Warning'), _('You cannot do anything as long as the "Close CashBox" button has not been used.'))
            # look at user choice
            choice = self.browse(cr,uid,ids)[0].choice
            if choice == 'reopen':
                if cstate not in ['partial_close']:
                    raise osv.except_osv(_('Warning'), _('This action is only for partially closed registers.'))
                # re-open case
                cashbox.write({'state': 'open'})
                return { 'type': 'ir.actions.act_window_close', 'res_id': w_id}
            # Write-off choice have been disabled since UTP-209
            else:
                raise osv.except_osv(_('Warning'), _('An error has occured !'))
        return { 'type': 'ir.actions.act_window_close', 'res_id': w_id}

cashbox_write_off()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
