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
            if 'sync_data' in context:
                return True
            del context['do_not_create_analytic_line']
        
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
        return super(account_move, self).write(cr, uid, ids, vals, context=context)

account_move()

class account_move_line(osv.osv):
    _name = 'account.move.line'
    _inherit = 'account.move.line'
    
    def create(self, cr, uid, vals, context=None, check=True):
        if not context:
            context = {}
            
        # indicate to the account.analytic.line not to create such an object to avoid duplication
        context['do_not_create_analytic_line'] = True
        return super(account_move_line, self).create(cr, uid, vals, context=context, check=check)
    
    def write(self, cr, uid, ids, vals, context=None, check=True, update_check=True):
        if not context:
            context = {}
            
        # indicate to the account.analytic.line not to create such an object to avoid duplication
        context['do_not_create_analytic_line'] = True
        
        # the coming block is a special treatment when, in sync, the update of an account.analytic.line triggers also an update 
        # on the account move line, in which its move state!=draft, and journal=posted. This update request raises an exception in 
        # opener-addons/account/account_move_line.py, method _update_check, line 1204
        # if this special catch up is not done here, the execution of the synch data is considered as not running due to the exception raised
        if 'sync_data' in context:
            for line in self.browse(cr, uid, ids, context=context):
                if line.move_id.state <> 'draft' and (not line.journal_id.entry_posted):
                    return True
                if line.reconcile_id:
                    return True
                
        return super(account_move_line, self).write(cr, uid, ids, vals, context=context, check=check, update_check=update_check)

account_move_line()