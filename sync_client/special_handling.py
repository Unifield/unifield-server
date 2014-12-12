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


##############################################################################
#
#    This class is a common place for special treatment of cases that happen only
#    when running with the synchronisation module
#
##############################################################################

from osv import fields, osv
from tools.translate import _

class account_analytic_line(osv.osv):
    _name = 'account.analytic.line'
    _inherit = 'account.analytic.line'
    
    def create(self, cr, uid, vals, context=None):
        if not context:
            context = {}

        # Check if the create request comes from the sync data and from some specific trigger 
        # for example: the create/write of account.move, account.move.line from sync data must not 
        # create this object, because this object is sync-ed on a separate rule 
        # otherwise duplicate entries will be created and these entries will be messed up in the later update
        if 'do_not_create_analytic_line' in context:
            if context.get('sync_update_execution'):
                return False
            del context['do_not_create_analytic_line']
        
        # UF-2479: Block the creation of an AJI if the given period is not open, in sync context
        if context.get('sync_update_execution') and 'date' in vals:
            period_ids = self.pool.get('account.period').get_period_from_date(cr, uid, vals['date'])
            if not period_ids:
                raise osv.except_osv(_('Warning'), _('No period found for the given date: %s') % (vals['date'] or ''))
            period = self.pool.get('account.period').browse(cr, uid, period_ids)[0]
            if period and period.state == 'created':
                raise osv.except_osv(_('Error !'), _('Period \'%s\' of the given date %s is not open! No AJI is created') % (period.name, vals['date'] or ''))

        # continue the create request if it comes from a normal requester
        return super(account_analytic_line, self).create(cr, uid, vals, context=context)
    
account_analytic_line()

class account_move(osv.osv):
    _name = 'account.move'
    _inherit = 'account.move'
    
    def create(self, cr, uid, vals, context=None):
        if not context:
            context = {}
        
        # indicate to the account.analytic.line not to create such an object to avoid duplication
        context['do_not_create_analytic_line'] = True
        return super(account_move, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        if not context:
            context = {}

        # indicate to the account.analytic.line not to create such an object to avoid duplication
        context['do_not_create_analytic_line'] = True

        if context.get('sync_update_execution', False):
            # UTP-1097: Add explicit the value if they are sent by sync with False but removed by the sync engine!
            # THIS IS A BUG OF SYNC CORE!
            if context.get('fields', False):
                fields =  context.get('fields')
                if 'ref' in fields and 'ref' not in vals:
                    vals['ref'] = False

        return super(account_move, self).write(cr, uid, ids, vals, context=context)

account_move()

class account_move_line(osv.osv):
    _name = 'account.move.line'
    _inherit = 'account.move.line'
    
    def create(self, cr, uid, vals, context=None, check=True):
        if not context:
            context = {}
            
        # indicate to the account.analytic.line not to create such an object to avoid duplication
#        context['do_not_create_analytic_line'] = True

        sync_check = check
        if context.get('sync_update_execution', False):
            sync_check = False

        return super(account_move_line, self).create(cr, uid, vals, context=context, check=sync_check)

    def write(self, cr, uid, ids, vals, context=None, check=True, update_check=True):
        # UTP-632: re-add write(), but only for the check variable
        if not context:
            context = {}
            
        sync_check = check
        if context.get('sync_update_execution', False):
            sync_check = False

            # UTP-1100: Add explicit the value of partner/employee if they are sent by sync with False but removed by the sync engine!
            # THIS IS A BUG OF SYNC CORE!
            if context.get('fields', False):
                fields =  context.get('fields')
                if 'partner_txt' in fields and 'partner_txt' not in vals:
                    vals['partner_txt'] = False 
                if 'partner_id/id' in fields and 'partner_id' not in vals:
                    vals['partner_id'] = False                 
                if 'partner_id2/id' in fields and 'partner_id2' not in vals:
                    vals['partner_id2'] = False                 
                if 'employee_id/id' in fields and 'employee_id' not in vals:
                    vals['employee_id'] = False
                if 'reference' in fields and 'reference' not in vals:
                    # UTP-1097: same issue as UTP-1100 (when ref field is cleared)
                    vals['reference'] = False
                if 'ref' in fields and 'ref' not in vals:
                    # UTP-1097: same issue as UTP-1100 (when ref field is cleared)
                    vals['ref'] = False
                
        return super(account_move_line, self).write(cr, uid, ids, vals, context=context, check=sync_check, update_check=update_check)
    
    def _hook_call_update_check(self, cr, uid, ids, vals, context=None):
        if context is None:
            context = {}
        field_to_check = {'account_id': 'm2o', 'journal_id': 'm2o', 'period_id': 'm2o', 'move_id': 'm2o', 'debit': 'float', 'credit': 'float', 'date': 'date'}
        done = {}
        if not context.get('sync_update_execution'):
            return super(account_move_line, self)._hook_call_update_check(cr, uid, ids, vals, context)

        # rewrite update_check, to raise error *only if values to write and values in DB differ*
        for l in self.browse(cr, uid, ids):
            for f,typ in field_to_check.iteritems():
                if f in vals:
                    to_write_val = l[f]
                    if typ == 'm2o' and l[f]:
                        to_write_val = l[f].id
                    diff_val = vals[f] != to_write_val
                    if typ == 'float' and l[f] and vals[f]:
                        diff_val = abs(vals[f] - l[f]) > 10**-4
                    if diff_val and l.move_id.state <> 'draft' and l.state <> 'draft' and (not l.journal_id.entry_posted):
                        # US-14: do not raised but remove the data
                        if f in ('debit', 'credit'):
                            del vals[f]
                        else:
                            raise osv.except_osv(_('Error !'), _('You can not do this modification on a confirmed entry ! Please note that you can just change some non important fields !'))
                    elif diff_val and l.reconcile_id:
                        # US-14
                        if f in ('debit', 'credit'):
                            del vals[f]
                        else:
                            raise osv.except_osv(_('Error !'), _('You can not do this modification on a reconciled entry ! Please note that you can just change some non important fields !'))
                t = (l.journal_id.id, l.period_id.id)
                if t not in done:
                    self._update_journal_check(cr, uid, l.journal_id.id, l.period_id.id, context)
                    done[t] = True

account_move_line()

