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
from osv import osv
from tools.translate import _

class analytic_line(osv.osv):
    _inherit = "account.analytic.line"
    
    def _check_date(self, cr, uid, vals):
        if 'date' in vals and vals['date'] is not False:
            account_obj = self.pool.get('account.analytic.account')
            account = account_obj.browse(cr, uid, vals['account_id'])
            if vals['date'] < account.date_start \
            or (account.date != False and \
                vals['date'] >= account.date):
                raise osv.except_osv(_('Error !'), _('The analytic account selected is not active.'))

    def create(self, cr, uid, vals, context=None):
        self._check_date(cr, uid, vals)
        return super(analytic_line, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        self._check_date(cr, uid, vals)
        return super(analytic_line, self).write(cr, uid, ids, vals, context=context)


analytic_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: