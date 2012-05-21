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

class account_move_line_activable(osv.osv):
    _inherit = "account.move.line"
    
    def _check_date(self, cr, uid, vals, context=None, check=True):
        if 'date' in vals and vals['date'] is not False:
            account_obj = self.pool.get('account.account')
            account = account_obj.browse(cr, uid, vals['account_id'])
            if vals['date'] < account.activation_date \
            or (account.inactivation_date != False and \
                vals['date'] >= account.inactivation_date):
                raise osv.except_osv(_('Error !'), _('The selected account is not active: %s.') % (account.code or '',))
        return super(account_move_line_activable, self)._check_date(cr, uid, vals, context, check)

account_move_line_activable()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
