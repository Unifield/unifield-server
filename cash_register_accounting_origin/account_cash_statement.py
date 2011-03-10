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
        'name': 'The name would be generated automatically',
        'state': lambda *a: 'draft',
    }
    
    _sql_constraints = [
        ('name_uniq', 'UNIQUE(name)', _('The CashBox name must be unique!')),
    ]

    def create(self, cr, uid, vals, context={}):
        """
        Create a Cash Register with a preformed name
        """
        # Give a Cash Register Name with the following  composition : 
        #+ Cash Journal Code + A Sequence Number (like /02)
        if 'journal_id' in vals:
            journal_id = vals.get('journal_id')
            journal_code = self.pool.get('account.journal').read(cr, uid, journal_id, [('code')], context=context).get('code')
            seq = self.pool.get('ir.sequence').get(cr, uid, 'cash.register')
            name = journal_code + seq
            vals.update({'name': name})
        else:
            raise osv.except_osv(_('Warning'), _('Name field is not filled in!'))
        return super(account_cash_statement, self).create(cr, uid, vals, context=context)

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

    _columns = {
            'state': fields.selection((('draft', 'Draft'), ('open', 'Open'), ('partial_close', 'Partial Close'), ('confirm', 'Closed')), \
                readonly="True", string='State'),
            'name': fields.char('Name', size=64, required=True, readonly=True, \
                help='if you give the Name other than     /, its created Accounting Entries Move will be with same name as \
                statement name. This allows the statement entries to have the same references than the     statement itself'),
    }

account_cash_statement()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
