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
        'name': False,
        'state': lambda *a: 'draft',
    }

    def create(self, cr, uid, vals, context={}):
        """
        Create a Cash Register without an error overdue to having open two cash registers on the same journal
        """
        # @@@override@account.account_cash_statement.create()
        if self.pool.get('account.journal').browse(cr, uid, vals['journal_id'], context=context).type == 'cash':
            open_close = self._get_cash_open_close_box_lines(cr, uid, context)
            if vals.get('starting_details_ids', False):
                for start in vals.get('starting_details_ids'):
                    dict_val = start[2]
                    for end in open_close['end']:
                       if end[2]['pieces'] == dict_val['pieces']:
                           end[2]['number'] += dict_val['number']
            vals.update({
                 'ending_details_ids': open_close['start'],
                'starting_details_ids': open_close['end']
            })
        else:
            vals.update({
                'ending_details_ids': False,
                'starting_details_ids': False
            })
        # @@@end
        res_id = super(osv.osv, self).create(cr, uid, vals, context=context)
        return res_id

    def button_open_cash(self, cr, uid, ids, context={}):
        """
        when pressing 'Open CashBox' button
        """
        # Give a Cash Register Name with the following composition : 
        #+ Cash Journal Code + A Sequence Number (like /02)
        st = self.browse(cr, uid, ids)[0]
        if st.journal_id and st.journal_id.code:
            seq = self.pool.get('ir.sequence').get(cr, uid, 'cash.register')
            name = st.journal_id.code + seq
            res_id = self.write(cr, uid, ids, {'state' : 'open', 'name': name})
            return res_id
        else:
            return False

    def button_confirm_cash(self, cr, uid, ids, context={}):
        """
        when you're attempting to close a CashBox via 'Close CashBox'
        """
        # First verify that all lines are in hard state
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
            'name': fields.char('Name', size=64, required=False, readonly=True, \
                help='if you give the Name other than     /, its created Accounting Entries Move will be with same name as \
                statement name. This allows the statement entries to have the same references than the     statement itself'),
            'period_id': fields.many2one('account.period', 'Period', required=True, states={'partial_close':[('readonly', True)], \
                'confirm':[('readonly', True)]}),
            'line_ids': fields.one2many('account.bank.statement.line', 'statement_id', 'Statement lines', \
                states={'partial_close':[('readonly', True)], 'confirm':[('readonly', True)]}),
    }

    def button_wiz_temp_posting(self, cr, uid, ids, context={}):
        """
        When pressing 'Temp Posting' button then opening a wizard to select some account_bank_statement_line and change them into temp posting state.
        """
        domain = [('statement_id', '=', ids[0]), ('state', '=', 'draft')]
        return {
            'name': 'Temp Posting',
            'type': 'ir.actions.act_window',
            'res_model': 'account.bank.statement.line',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'domain': domain,
            'context': context,
            'target': 'crush', # use any word to crush the actual tab
        }

    def button_wiz_hard_posting(self, cr, uid, ids, context={}):
        """
        When pressing 'Hard Posting' button then opening a wizard to select some account_bank_statement_line and change them into hard posting state.
        """
        domain = [('statement_id', '=', ids[0]), ('state', 'in', 'draft,temp')]
        return {
            'name': 'Select elements for Hard Posting',
            'type': 'ir.actions.act_window',
            'res_model': 'account.bank.statement.line',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'domain': domain,
            'context': context,
            'target': 'crush', # use any word to crush the actual tab
        }

account_cash_statement()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
