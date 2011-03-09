#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution    
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    Author: Tempo Consulting (<http://www.tempo-consulting.fr/>), MSF.
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

class account_cash_statement(osv.osv):
    _name = "account.bank.statement"
    _inherit = "account.bank.statement"

    _defaults = {
        'state': lambda *a: 'draft',
    }
    
    _sql_constraints = [
        ('name_uniq', 'UNIQUE(name)', _('The CashBox name must be unique!')),
    ]

    def button_open(self, cr, uid, ids, context={}):
        """
        when pressing 'Open CashBox' button
        """
        self.write(cr, uid, ids, {'state' : 'open'})
        return True

    def button_confirm_cash(self, cr, uid, ids, context={}):
        """
        when you're attempting to close a CashBox via 'Close CashBox'
        """
        # First verifying that all lines are in hard state
        for st in self.browse(cr, uid, ids, context=context):
            for line in st.line_ids:
                if line.state != 'hard':
                    raise osv.except_osv(_('Warning'), _('All entries must be hard posted before closing CashBox!'))
        # Then we open a wizard to permit the user to confirm that he want to close CashBox
        return {
            'name' : "Closing CashBox",
            'type' : 'ir.actions.act_window',
            'res_model' :"wizard.closing.cashbox",
            'target': 'new',
            'view_mode': 'form',
            'view_type': 'form',
            'context': 
            {
                'active_id': ids[0],
                'active_ids': ids
            }
        }

    def button_reopen(self, cr, uid, ids, context={}):
        """
        When an administrator push the 'Re-open CashBox' button
        """
        self.write(cr, uid, ids, {'state' : 'open'})
        return True

    def button_write_off(self, cr, uid, ids, context={}):
        """
        When an administrator push the 'Write-off' button
        """
        self.write(cr, uid, ids, {'state' : 'confirm'})
        return True

    _columns = {
            'state': fields.selection((('draft', 'Draft'), ('open', 'Open'), ('partial_close', 'Partial Close'), ('confirm', 'Closed')), \
            readonly="True", string='State'),
    }

account_cash_statement()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
