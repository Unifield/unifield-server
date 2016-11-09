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
from datetime import datetime
from tools.translate import _

class wizard_confirm_bank(osv.osv_memory):
    _name = 'wizard.confirm.bank'
    _description = 'Bank confirmation wizard'

    def button_confirm(self, cr, uid, ids, context=None):
        """
        Confirm that we close the bank statement
        """
        if context is None:
            context = {}
        # Some verification
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not 'statement_id' in context:
            raise osv.except_osv(_('Error'), _('No register selected. Please do a bank confirmation from a bank statement!'))
        # Prepare some variables
        st_id = context.get('statement_id')
        st_obj = self.pool.get('account.bank.statement')
        # All is ok ? Let's go closing the bank statement!
        res = st_obj.write(cr, uid, [st_id], {'state':'confirm', 'closing_date': datetime.today()}, context=context)
        # Then close wizard
        if res:
            return { 'type': 'ir.actions.act_window_close', }
        raise osv.except_osv(_('Error'), _('An unknown error has occured on Bank confirmation wizard. Please contact an administrator to solve this problem.'))

wizard_confirm_bank()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
