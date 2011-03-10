#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution    
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    Author: Tempo Consulting (<http://www.tempo-consulting.fr/>), MSF
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

class cashbox_write_off(osv.osv_memory):
    _name = 'cashbox.write.off'
    _columns = {
        'choice' : fields.selection( (('writeoff', 'Accepting write-off and close CashBox'), ('reopen', 'Re-open CashBox')), \
            string="Decision about CashBox", required=True),
    }

    def action_confirm_choice(self, cr, uid, ids, context={}):
        """
        Do what the user wants, but not coffee ! Just this : 
        - re-open the cashbox
        - do a write-off
        """
        id = context.get('active_id', False)
        if not id:
            raise osv.except_osv('Warning', 'You cannot decide about Cash Discrepancy without selecting any CashBox!')
        else:
            # searching cashbox object
            cashbox = self.pool.get('account.bank.statement').browse(cr, uid, id)
            cstate = cashbox.state
            # What about cashbox state ?
            if cstate not in ['partial_close', 'confirm']:
                raise osv.except_osv('Warning', 'You cannot do anything as long as the CashBox has been closed!')
            # looking at user choice
            choice = self.browse(cr,uid,ids)[0].choice
            if choice == 'reopen':
                # reopening case
                cashbox.write({'state': 'open'})
                return { 'type': 'ir.actions.act_window_close', }
            elif choice == 'writeoff':
                # writing-off case
                if cstate != 'partial_close':
                    raise osv.except_osv('Warning', 'This option is only useful for CashBox with cash discrepancy!')
                    return False
                else:
                    ## FIXME: In which account write off ?
                    ## FIXME: Do a write-off here !
                    cashbox.write({'state': 'confirm'})
                return { 'type': 'ir.actions.act_window_close', }
            else:
                raise osv.except_osv('Warning', 'An error has occured !')
        return { 'type': 'ir.actions.act_window_close', }

cashbox_write_off()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
