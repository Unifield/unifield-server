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
from time import strftime

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
        'ref': fields.char('Reference', size=64, readonly=True, states={'draft':[('readonly',False)]}),
        'status': fields.selection([('sys', 'system'), ('manu', 'manual')], string="Status", required=True),
        'period_id': fields.many2one('account.period', 'Period', required=True, states={'posted':[('readonly',True)]}, domain="[('state', '=', 'draft')]"),
        'journal_id': fields.many2one('account.journal', 'Journal', required=True, states={'posted':[('readonly',True)]}, domain="[('type', 'not in', ['accrual', 'hq', 'inkind', 'cur_adj'])]"),
        'document_date': fields.date('Document Date', size=255, required=True, help="Used for manual journal entries"),
    }

    _defaults = {
        'status': lambda self, cr, uid, c: c.get('from_web_menu', False) and 'manu' or 'sys',
        'document_date': lambda self, cr, uid, c: c.get('document_date', False) or strftime('%Y-%m-%d'),
        'period_id': lambda *a: '',
    }

    def _check_document_date(self, cr, uid, ids, context=None):
        """
        Check that document's date is done BEFORE posting date
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context.get('from_web_menu', False):
            for m in self.browse(cr, uid, ids):
                if m.document_date and m.date and m.date < m.document_date:
                    raise osv.except_osv(_('Error'), _('Posting date should be later than Document Date.'))
        return True

    def _check_date_in_period(self, cr, uid, ids, context=None):
        """
        Check that date is inside defined period
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context.get('from_web_menu', False):
            for m in self.browse(cr, uid, ids):
                if m.date and m.period_id and m.period_id.date_start and m.date >= m.period_id.date_start and m.period_id.date_stop and m.date <= m.period_id.date_stop:
                    continue
                raise osv.except_osv(_('Error'), _('Posting date should be include in defined Period%s.') % (m.period_id and ': ' + m.period_id.name or '',))
        return True

    def create(self, cr, uid, vals, context=None):
        """
        Change move line's sequence (name) by using instance move prefix.
        """
        if not context:
            context = {}
        # Change the name for (instance_id.move_prefix) + (journal_id.code) + sequence number
        instance = self.pool.get('res.users').browse(cr, uid, uid, context).company_id.instance_id
        journal = self.pool.get('account.journal').browse(cr, uid, vals['journal_id'])
        sequence_number = self.pool.get('ir.sequence').get_id(cr, uid, journal.sequence_id.id)
        if instance and journal and sequence_number and ('name' not in vals or vals['name'] == '/'):
            if not instance.move_prefix:
                raise osv.except_osv(_('Warning'), _('No move prefix found for this instance! Please configure it on Company view.'))
            vals['name'] = "%s-%s-%s" % (instance.move_prefix, journal.code, sequence_number)
        if 'from_web_menu' in context:
            vals.update({'status': 'manu'})
            # Update context in order journal item could retrieve this @creation
            if 'document_date' in vals:
                context['document_date'] = vals.get('document_date')
            if 'date' in vals:
                context['date'] = vals.get('date')
        res = super(account_move, self).create(cr, uid, vals, context=context)
        self._check_document_date(cr, uid, res, context)
        self._check_date_in_period(cr, uid, res, context)
        return res

    def name_get(self, cursor, user, ids, context=None):
        # Override default name_get (since it displays "*12" names for unposted entries)
        return super(osv.osv, self).name_get(cursor, user, ids, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        Check that we can write on this if we come from web menu
        """
        if not context:
            context = {}
        if context.get('from_web_menu', False):
            for m in self.browse(cr, uid, ids):
                if m.status == 'sys':
                    raise osv.except_osv(_('Warning'), _('You cannot edit a Journal Entry created by the system.'))
                # Update context in order journal item could retrieve this @creation
                # Also update some other fields
                for el in ['document_date', 'date', 'journal_id', 'period_id']:
                    if el in vals:
                        context[el] = vals.get(el)
                        for ml in m.line_id:
                            self.pool.get('account.move.line').write(cr, uid, ml.id, {el: vals.get(el)}, context, False, False)
        res = super(account_move, self).write(cr, uid, ids, vals, context=context)
        self._check_document_date(cr, uid, ids, context)
        self._check_date_in_period(cr, uid, ids, context)
        return res

    def button_validate(self, cr, uid, ids, context=None):
        """
        Check that user can approve the move by searching 'from_web_menu' in context. If present and set to True and move is manually created, so User have right to do this.
        """
        if not context:
            context = {}
        for id in ids:
            ml_ids = self.pool.get('account.move.line').search(cr, uid, [('move_id', '=', id)])
            if not ml_ids:
                raise osv.except_osv(_('Warning'), _('No line found. Please add some lines before Journal Entry validation!'))
        if context.get('from_web_menu', False):
            for m in self.browse(cr, uid, ids):
                if m.status == 'sys':
                    raise osv.except_osv(_('Warning'), _('You are not able to approve a Journal Entry that comes from the system!'))
                prev_currency_id = False
                for ml in m.line_id:
                    if not prev_currency_id:
                        prev_currency_id = ml.currency_id.id
                        continue
                    if ml.currency_id.id != prev_currency_id:
                        raise osv.except_osv(_('Warning'), _('You cannot have two different currencies for the same Journal Entry!'))
        return super(account_move, self).button_validate(cr, uid, ids, context=context)

    def onchange_journal_id(self, cr, uid, ids, journal_id=False, context=None):
        """
        Change some fields when journal is changed.
        """
        res = {}
        if not context:
            context = {}
        return res

    def onchange_period_id(self, cr, uid, ids, period_id=False, date=False, context=None):
        """
        Check that given period is open.
        If date outside given period, change it
        """
        res = {}
        if not context:
            context = {}
        if period_id:
            data = self.pool.get('account.period').read(cr, uid, period_id, ['state', 'date_start', 'date_stop'])
            if data.get('state', False) != 'draft':
                raise osv.except_osv(_('Error'), _('Period is not open!'))
            if date and data.get('date_start') and data.get('date_stop'):
                if date > data.get('date_stop') or date < data.get('date_start'):
                    res['value'] = {'date': data.get('date_start')}
        return res

    def button_delete(self, cr, uid, ids, context=None):
        """
        Delete manual and unposted journal entries if we come from web menu
        """
        if not context:
            context = {}
        to_delete = []
        if context.get('from_web_menu', False):
            for m in self.browse(cr, uid, ids):
                if m.status == 'manu' and m.state == 'draft':
                    to_delete.append(m.id)
        self.unlink(cr, uid, to_delete, context)
        return True

account_move()

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
