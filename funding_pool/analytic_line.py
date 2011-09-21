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
from osv import fields
from tools.translate import _

class analytic_line(osv.osv):
    _name = "account.analytic.line"
    _inherit = "account.analytic.line"

    _columns = {
        "distribution_id": fields.many2one('analytic.distribution', 'Analytic Distribution'),
        "cost_center_id": fields.many2one('account.analytic.account', 'Cost Center'),
    }

    def _check_date(self, cr, uid, vals, context={}):
        """
        Check if given account_id is active for given date
        """
        if not context:
            context={}
        if not 'account_id' in vals:
            raise osv.except_osv(_('Error'), _('No account_id found in given values!'))
        if 'date' in vals and vals['date'] is not False:
            account_obj = self.pool.get('account.analytic.account')
            account = account_obj.browse(cr, uid, vals['account_id'], context=context)
            if vals['date'] < account.date_start \
            or (account.date != False and \
                vals['date'] >= account.date):
                raise osv.except_osv(_('Error !'), _("The analytic account selected '%s' is not active.") % account.name)

    def create(self, cr, uid, vals, context={}):
        """
        Check date for given date and given account_id
        """
        self._check_date(cr, uid, vals, context=context)
        return super(analytic_line, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context={}):
        """
        Verify date for all given ids with account
        """
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for id in ids:
            if not 'account_id' in vals:
                line = self.browse(cr, uid, [id], context=context)
                account_id = line and line[0] and line[0].account_id.id or False
                vals.update({'account_id': account_id})
            self._check_date(cr, uid, vals, context=context)
        return super(analytic_line, self).write(cr, uid, ids, vals, context=context)

analytic_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
