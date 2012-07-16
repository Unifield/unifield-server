# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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

from osv import fields, osv

class account_analytic_journal(osv.osv):
    _name = 'account.analytic.journal'
    _inherit = 'account.analytic.journal'
    
    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
    }
    
    _defaults = {
        'instance_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.instance_id.id,
    }

    def _check_engagement_count(self, cr, uid, ids, context=None):
        """
        Check that no more than one engagement journal exists for one instance
        """
        if not context:
            context={}
        instance_ids = self.pool.get('msf.instance').search(cr, uid, [], context=context)
        for instance_id in instance_ids:
            eng_ids = self.search(cr, uid, [('type', '=', 'engagement'), ('instance_id', '=', instance_id)])
            if len(eng_ids) and len(eng_ids) > 1:
                return False
        return True

    _constraints = [
        (_check_engagement_count, 'You cannot have more than one engagement journal per instance!', ['type', 'instance_id']),
    ]

account_analytic_journal()

class account_journal(osv.osv):
    _name = 'account.journal'
    _inherit = 'account.journal'
    
    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
    }
    
    _defaults = {
        'instance_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.instance_id.id,
    }

account_journal()

class account_analytic_line(osv.osv):
    _name = 'account.analytic.line'
    _inherit = 'account.analytic.line'
    
    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
    }
    
    def create(self, cr, uid, vals, context=None):
        if 'journal_id' in vals:
            journal = self.pool.get('account.analytic.journal').browse(cr, uid, vals['journal_id'], context=context)
            vals['instance_id'] = journal.instance_id.id
        return super(account_analytic_line, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        if 'journal_id' in vals:
            journal = self.pool.get('account.analytic.journal').browse(cr, uid, vals['journal_id'], context=context)
            vals['instance_id'] = journal.instance_id.id
        return super(account_analytic_line, self).write(cr, uid, ids, vals, context=context)

account_analytic_line()

class account_move(osv.osv):
    _name = 'account.move'
    _inherit = 'account.move'
    
    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
    }
    
    def create(self, cr, uid, vals, context=None):
        if 'journal_id' in vals:
            journal = self.pool.get('account.journal').browse(cr, uid, vals['journal_id'], context=context)
            vals['instance_id'] = journal.instance_id.id
        return super(account_move, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        if 'journal_id' in vals:
            journal = self.pool.get('account.journal').browse(cr, uid, vals['journal_id'], context=context)
            vals['instance_id'] = journal.instance_id.id
        return super(account_move, self).write(cr, uid, ids, vals, context=context)

account_move()

class account_move_line(osv.osv):
    _name = 'account.move.line'
    _inherit = 'account.move.line'
    
    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
    }
    
    def create(self, cr, uid, vals, context=None, check=True):
        if 'journal_id' in vals:
            journal = self.pool.get('account.journal').browse(cr, uid, vals['journal_id'], context=context)
            vals['instance_id'] = journal.instance_id.id
        return super(account_move_line, self).create(cr, uid, vals, context=context, check=check)
    
    def write(self, cr, uid, ids, vals, context=None, check=True, update_check=True):
        if 'journal_id' in vals:
            journal = self.pool.get('account.journal').browse(cr, uid, vals['journal_id'], context=context)
            vals['instance_id'] = journal.instance_id.id
        return super(account_move_line, self).write(cr, uid, ids, vals, context=context, check=check, update_check=update_check)

account_move_line()

class account_bank_statement(osv.osv):
    _name = 'account.bank.statement'
    _inherit = 'account.bank.statement'
    
    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
    }
    
    def create(self, cr, uid, vals, context=None):
        if 'journal_id' in vals:
            journal = self.pool.get('account.journal').browse(cr, uid, vals['journal_id'], context=context)
            vals['instance_id'] = journal.instance_id.id
        return super(account_bank_statement, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        if 'journal_id' in vals:
            journal = self.pool.get('account.journal').browse(cr, uid, vals['journal_id'], context=context)
            vals['instance_id'] = journal.instance_id.id
        return super(account_bank_statement, self).write(cr, uid, ids, vals, context=context)

account_bank_statement()

class account_bank_statement_line(osv.osv):
    _name = 'account.bank.statement.line'
    _inherit = 'account.bank.statement.line'
    
    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
    }
    
    def create(self, cr, uid, vals, context=None):
        if 'statement_id' in vals:
            register = self.pool.get('account.bank.statement').browse(cr, uid, vals['statement_id'], context=context)
            vals['instance_id'] = register.instance_id.id
        return super(account_bank_statement_line, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        if 'statement_id' in vals:
            register = self.pool.get('account.bank.statement').browse(cr, uid, vals['statement_id'], context=context)
            vals['instance_id'] = register.instance_id.id
        return super(account_bank_statement_line, self).write(cr, uid, ids, vals, context=context)

account_bank_statement_line()

class account_cashbox_line(osv.osv):
    _name = 'account.cashbox.line'
    _inherit = 'account.cashbox.line'
    
    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
    }
    
    def create(self, cr, uid, vals, context=None):
        if 'starting_id' in vals:
            register = self.pool.get('account.bank.statement').browse(cr, uid, vals['starting_id'], context=context)
            vals['instance_id'] = register.instance_id.id
        elif 'ending_id' in vals:
            register = self.pool.get('account.bank.statement').browse(cr, uid, vals['ending_id'], context=context)
            vals['instance_id'] = register.instance_id.id
        return super(account_cashbox_line, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        if 'starting_id' in vals:
            register = self.pool.get('account.bank.statement').browse(cr, uid, vals['starting_id'], context=context)
            vals['instance_id'] = register.instance_id.id
        elif 'ending_id' in vals:
            register = self.pool.get('account.bank.statement').browse(cr, uid, vals['ending_id'], context=context)
            vals['instance_id'] = register.instance_id.id
        return super(account_cashbox_line, self).write(cr, uid, ids, vals, context=context)

account_cashbox_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
