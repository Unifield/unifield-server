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

class register_reopen(osv.osv_memory):
    _name = 'register.reopen'

    _columns = {
        # Deleted from selection since UTP-209:
        #('writeoff', 'Accept write-off and close register'),
        'choice' : fields.selection( [('reopen', 'Reopen Register')], \
                                     string="Decision to make", required=True),
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        res = super(register_reopen, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        if 'active_id' in context:
            # search values
            cashbox_id = context.get('active_id')
            cashbox = self.pool.get('account.bank.statement').browse(cr, uid, cashbox_id)
            if cashbox.state not in ['confirm']:
                raise osv.except_osv(_('Warning'), _("This action is only applied to closed registers!"))

            period = cashbox.period_id
            if not period or 'closed' in period.state:
                raise osv.except_osv(_('Warning'), _('The period \'%s\' of this register is already \'%s\', the register cannot be reopen!') % (period.name, period.state))

        return res

    def action_confirm_reopen(self, cr, uid, ids, context=None):
        '''
        US-807: Allow user to reopen the closed registers for those in open periods.
        '''
        if context is None:
            context = {}
        w_id = context.get('active_id', False)
        if not w_id:
            raise osv.except_osv(_('Warning'), _('You have to select a closed register!'))
        else:
            # search cashbox object
            cashbox = self.pool.get('account.bank.statement').browse(cr, uid, w_id)
            cstate = cashbox.state
            # What about cashbox state ?
            if cstate not in ['confirm']:
                raise osv.except_osv(_('Warning'), _('This action is only applied to closed registers.'))
            # look at user choice
            choice = self.browse(cr,uid,ids)[0].choice
            if choice == 'reopen':
                #US-807: Check if the given period is still open, if it's closed -> cannot reopen this register!
                period = cashbox.period_id
                if not period or 'closed' in period.state:
                    raise osv.except_osv(_('Warning'), _('The period \'%s\' of this register is already \'%s\', the register cannot be reopen!') % (period.name, period.state))

                # re-open case
                cashbox.write({'state': 'open'})
                return { 'type': 'ir.actions.act_window_close', 'res_id': w_id}
            # Write-off choice have been disabled since UTP-209
            else:
                raise osv.except_osv(_('Warning'), _('An error has occurred !'))
        return { 'type': 'ir.actions.act_window_close', 'res_id': w_id}

register_reopen()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
