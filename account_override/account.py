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
from osv import fields
from tools.translate import _

class account_account(osv.osv):
    _name = "account.account"
    _inherit = "account.account"

    _columns = {
        'type_for_register': fields.selection([('none', 'None'), ('transfer', 'Internal Transfer'), ('transfer_same','Internal Transfer (same currency)'), 
            ('advance', 'Operational Advance'), ('payroll', 'Third party required - Payroll'), ('down_payment', 'Down payment'), ('donation', 'Donation')], string="Type for specific treatment", required=True,
            help="""This permit to give a type to this account that impact registers. In fact this will link an account with a type of element 
            that could be attached. For an example make the account to be a transfer type will display only registers to the user in the Cash Register 
            when he add a new register line.
            """),
    }

    _defaults = {
        'type_for_register': lambda *a: 'none',
    }

account_account()

class account_journal(osv.osv):
    _inherit = 'account.journal'

    # @@@override account>account.py>account_journal>create_sequence
    def create_sequence(self, cr, uid, vals, context=None):
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')

        name = vals['name']
        code = vals['code'].lower()

        types = {
            'name': name,
            'code': code
        }
        seq_typ_pool.create(cr, uid, types)

        seq = {
            'name': name,
            'code': code,
            'active': True,
            'prefix': '',
            'padding': 6,
            'number_increment': 1
        }
        return seq_pool.create(cr, uid, seq)
    
account_journal()


class account_move(osv.osv):
    _inherit = 'account.move'

    _columns = {
        'name': fields.char('Entry Sequence', size=64, required=True),
        'statement_line_ids': fields.many2many('account.bank.statement.line', 'account_bank_statement_line_move_rel', 'statement_id', 'move_id', 
            string="Statement lines", help="This field give all statement lines linked to this move."),
    }

    def create(self, cr, uid, vals, context=None):
        # Change the name for (instance_id.move_prefix) + (journal_id.code) + sequence number
        instance = self.pool.get('res.users').browse(cr, uid, uid, context).company_id.instance_id
        journal = self.pool.get('account.journal').browse(cr, uid, vals['journal_id'])
        sequence_number = self.pool.get('ir.sequence').get_id(cr, uid, journal.sequence_id.id)
        if instance and journal and sequence_number and ('name' not in vals or vals['name'] == '/'):
            if not instance.move_prefix:
                raise osv.except_osv(_('Warning'), _('No move prefix found for this instance! Please configure it on Company view.'))
            vals['name'] = "%s-%s-%s" % (instance.move_prefix, journal.code, sequence_number)
        return super(account_move, self).create(cr, uid, vals, context=context)
    
    def name_get(self, cursor, user, ids, context=None):
        # Override default name_get (since it displays "*12" names for unposted entries)
        return super(osv.osv, self).name_get(cursor, user, ids, context=context)

account_move()

class account_move_line(osv.osv):
    _inherit = 'account.move.line'
    
    # @@@override account>account_move_line.py>account_move_line>name_get
    def name_get(self, cr, uid, ids, context=None):
        # Override default name_get (since it displays the move line reference)
        if not ids:
            return []
        result = []
        for line in self.browse(cr, uid, ids, context=context):
            result.append((line.id, line.move_id.name))
        return result

account_move_line()

class account_move_reconcile(osv.osv):
    _inherit = 'account.move.reconcile'
    
    def get_name(self, cr, uid, context=None):
        instance = self.pool.get('res.users').browse(cr, uid, uid, context).company_id.instance_id
        sequence_number = self.pool.get('ir.sequence').get(cr, uid, 'account.move.reconcile')
        if instance and sequence_number:
            return instance.reconcile_prefix + "-" + sequence_number
        else:
            return ''

    _columns = {
        'name': fields.char('Entry Sequence', size=64, required=True),
        'statement_line_ids': fields.many2many('account.bank.statement.line', 'account_bank_statement_line_move_rel', 'statement_id', 'move_id', 
            string="Statement lines", help="This field give all statement lines linked to this move."),
    }
    _defaults = {
        'name': lambda self,cr,uid,ctx={}: self.get_name(cr, uid, ctx),
    }

account_move_reconcile()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
