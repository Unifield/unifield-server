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

from osv import osv
from tools.translate import _

class account_period(osv.osv):
    _name = 'account.period'
    _inherit = 'account.period'

    def action_set_state(self, cr, uid, ids, context=None):
        """
        Check that all hq entries from the given period are validated.
        This check is only done on COORDO level!
        """
        # Some verifications
        if not context:
            context = {}
        # Are we in coordo level?
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        if user and user.company_id and user.company_id.instance_id and user.company_id.instance_id.level and user.company_id.instance_id.level == 'coordo':
          # Check hq entries
          period_ids = self.search(cr, uid, [('id', 'in', ids), ('state', '=', 'draft')])
          if isinstance(period_ids, (int, long)):
              period_ids = [period_ids]
          hq_ids = self.pool.get('hq.entries').search(cr, uid, [('period_id', 'in', period_ids), ('user_validated', '=', False)])
          if hq_ids:
             raise osv.except_osv(_('Warning'), _('Some HQ entries are not validated in this period. Please validate them before field-closing this period.'))
        return super(account_period, self).action_set_state(cr, uid, ids, context)

account_period()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
