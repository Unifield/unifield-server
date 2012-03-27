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
from datetime import datetime
from ..register_tools import create_cashbox_lines

class wizard_closing_cashbox(osv.osv_memory):
    
    _name = 'wizard.closing.cashbox'
    _columns = {
        'be_sure': fields.boolean( string="Are you sure ?", required=False ),
    }

    def button_close_cashbox(self, cr, uid, ids, context=None):
        # retrieve context active id (verification)
        if context is None:
            context = {}
        id = context.get('active_id', False)
        if not id:
            raise osv.except_osv(_('Warning'), _("You don't select any item!"))
        else:
            # retrieve user's choice
            res = self.browse(cr,uid,ids)[0].be_sure
            if res:
                st_obj = self.pool.get('account.bank.statement')
                # retrieve Calculated balance
                balcal = st_obj.read(cr, uid, id, ['balance_end']).get('balance_end')
                # retrieve CashBox Balance
                bal = st_obj.read(cr, uid, id, ['balance_end_cash']).get('balance_end_cash')
                
                # compare the selected balances
                equivalent = balcal == bal
                if not equivalent:
                    # verify that no other lines should be created
                    res_id = st_obj.write(cr, uid, [id], {'state' : 'partial_close'})
                    return { 'type' : 'ir.actions.act_window_close', 'active_id' : res_id }
                else:
                    # @@@override@account.account_bank_statement.button_confirm_bank()
                    obj_seq = self.pool.get('ir.sequence')

                    for st in st_obj.browse(cr, uid, [id], context=context):
                        j_type = st.journal_id.type
                        company_currency_id = st.journal_id.company_id.currency_id.id
                        if not st_obj.check_status_condition(cr, uid, st.state, journal_type=j_type):
                            continue

                        st_obj.balance_check(cr, uid, st.id, journal_type=j_type, context=context)
                        if (not st.journal_id.default_credit_account_id) \
                                or (not st.journal_id.default_debit_account_id):
                            raise osv.except_osv(_('Configuration Error !'),
                                    _('Please verify that an account is defined in the journal.'))

                        if not st.name == '/':
                            st_number = st.name
                        else:
                            if st.journal_id.sequence_id:
                                c = {'fiscalyear_id': st.period_id.fiscalyear_id.id}
                                st_number = obj_seq.get_id(cr, uid, st.journal_id.sequence_id.id, context=c)
                            else:
                                st_number = obj_seq.get(cr, uid, 'account.bank.statement')

                        for line in st.move_line_ids:
                            if line.state <> 'valid':
                                raise osv.except_osv(_('Error !'),
                                        _('The account entries lines are not in valid state.'))
                        for st_line in st.line_ids:
                            if st_line.analytic_account_id:
                                if not st.journal_id.analytic_journal_id:
                                    raise osv.except_osv(_('No Analytic Journal !'),_("You have to define an analytic journal on the '%s' journal!") \
                                        % (st.journal_id.name,))
                    # @@@end
                            if not st_line.amount:
                                 continue
                        # Create next register starting cashbox_lines if necessary
                        create_cashbox_lines(self, cr, uid, st.id, context=context)
                        # Change cashbox state
                        res_id = st_obj.write(cr, uid, [st.id], {'name': st_number, 'state':'confirm', 'closing_date': datetime.today()}, context=context)
                return { 'type' : 'ir.actions.act_window_close', 'active_id' : res_id }
            else:
                raise osv.except_osv(_('Warning'), _("You don't have really confirm by ticking!"))
        return { 'type' : 'ir.actions.act_window_close', 'active_id' : id }

wizard_closing_cashbox()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
