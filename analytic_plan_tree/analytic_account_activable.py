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

import datetime
from dateutil.relativedelta import relativedelta
from osv import fields, osv
from tools.translate import _

class analytic_account_activable(osv.osv):
    _inherit = "account.analytic.account"
    
    _columns = {
        'date_start': fields.date('Active from', required=True),
        'date': fields.date('Inactive from', select=True),
    }
    
    _defaults ={
        'date_start': lambda *a: (datetime.datetime.today() + relativedelta(months=-3)).strftime('%Y-%m-%d')
    }
    
    def _check_date(self, vals):
        if 'date' in vals and vals['date'] is not False:
            if vals['date'] <= datetime.date.today().strftime('%Y-%m-%d'):
                 # validate the date (must be > today)
                 raise osv.except_osv(_('Warning !'), _('You cannot set an inactivity date lower than tomorrow!'))
            elif 'date_start' in vals and not vals['date_start'] < vals['date']:
                # validate that activation date 
                raise osv.except_osv(_('Warning !'), _('Activation date must be lower than inactivation date!'))
    
    def create(self, cr, uid, vals, context=None):
        self._check_date(vals)
        return super(analytic_account_activable, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        self._check_date(vals)
        return super(analytic_account_activable, self).write(cr, uid, ids, vals, context=context)

    def search(self, cr, uid, args, offset=0, limit=None, order=None,
            context=None, count=False):
        if context and 'filter_inactive_accounts' in context and context['filter_inactive_accounts']:
            args.append(('date_start', '<=', datetime.date.today().strftime('%Y-%m-%d')))
            args.append('|')
            args.append(('date', '>', datetime.date.today().strftime('%Y-%m-%d')))
            args.append(('date', '=', False))
            
        return super(analytic_account_activable, self).search(cr, uid, args, offset, limit,
                order, context=context, count=count)
    
analytic_account_activable()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
