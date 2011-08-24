# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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

import datetime
from dateutil.relativedelta import relativedelta
from osv import fields, osv
from tools.translate import _

class account_account_activable(osv.osv):
    _inherit = 'account.account'
    
    '''
        To create a activity period, 2 new fields are created, and are NOT linked to the
        'active' field, since the behaviors are too different.
    '''
    _columns = {
        'activation_date': fields.date('Active from', required=True),
        'inactivation_date': fields.date('Inactive from'),
        'note': fields.char('Note', size=160),
    }
    
    _defaults ={
        'activation_date': lambda *a: (datetime.datetime.today() + relativedelta(months=-3)).strftime('%Y-%m-%d')
    }
    
    def _check_date(self, vals):
        if 'inactivation_date' in vals and vals['inactivation_date'] is not False:
            if vals['inactivation_date'] <= datetime.date.today().strftime('%Y-%m-%d'):
                 # validate the date (must be > today)
                 raise osv.except_osv(_('Warning !'), _('You cannot set an inactivity date lower than tomorrow!'))
            elif 'activation_date' in vals and not vals['activation_date'] < vals['inactivation_date']:
                # validate that activation date 
                raise osv.except_osv(_('Warning !'), _('Activation date must be lower than inactivation date!'))
    
    def create(self, cr, uid, vals, context=None):
        self._check_date(vals)
        return super(account_account_activable, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        self._check_date(vals)
        return super(account_account_activable, self).write(cr, uid, ids, vals, context=context)

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        # UF-419: If the args contains journaltype value of Bank, Cheque, Cash, then add the search condition to show only accounts class 5 
        if not args:
            args = []
        args = args[:]
        
        pos = 0
        while pos < len(args):
            if args[pos][0] == 'journaltype':
                if args[pos][2] in ('cash', 'bank', 'cheque'):
                    args[pos] = ('code', 'like', '5%') # add the search condition to show only accounts class 5
                else:
                    args.remove(args[pos]) # if not, then just remove this element, and add nothing
                pos = len(args) # in both case, exit the loop
            pos += 1
        # End of UF-419
        
        if not context:
            context = {}
        if context.get('filter_inactive_accounts'):
            args.append(('activation_date', '<=', datetime.date.today().strftime('%Y-%m-%d')))
            args.append('|')
            args.append(('inactivation_date', '>', datetime.date.today().strftime('%Y-%m-%d')))
            args.append(('inactivation_date', '=', False))
            
        return super(account_account_activable, self).search(cr, uid, args, offset, limit,
                order, context=context, count=count)
            
            
    
account_account_activable()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
