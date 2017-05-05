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

class account_journal_period(osv.osv):
    _name = "account.journal.period"
    _inherit = "account.journal.period"

    # @@@override@account.account_journal_period.create()
    def create(self, cr, uid, vals, context=None):
        period_id=vals.get('period_id',False)
        if period_id:
            period = self.pool.get('account.period').browse(cr, uid, period_id, context=context)
            # If the period is not open, the move line/account journal period are not created.
            if period.state == 'created':
                raise osv.except_osv(_('Error !'), _('Period \'%s\' is not open!') % (period.name,))
            elif period.state != 'done':
                vals['state'] = 'draft'
            else:
                vals['state'] = 'done'
        return super(osv.osv, self).create(cr, uid, vals, context)
    # @@@end

account_journal_period()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
