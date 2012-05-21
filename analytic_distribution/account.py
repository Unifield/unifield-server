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

from osv import fields, osv

class account_account(osv.osv):
    _inherit = 'account.account'

    _columns = {
        'user_type_code': fields.related('user_type', 'code', type="char", string="User Type Code", store=False),
        'funding_pool_line_ids': fields.many2many('account.analytic.account', 'funding_pool_associated_accounts', 'account_id', 'funding_pool_id', 
            string='Funding Pools'),
        'default_destination_analytic_account': fields.many2one('account.analytic.account', 'Default Destination'),
        'destination_ids': fields.many2many('account.analytic.account', 'destination_associated_accounts', 'account_id', 'destination_id', 'Destinations'),
    }

    def write(self, cr, uid, ids, vals, context=None):
        """
        Default destination analytic account is mandatory for expense account !
        """
        expense_type_ids = False
        if vals.get('user_type', False):
            expense_type_ids = self.pool.get('account.account.type').search(cr, uid, [('code', '=', 'expense')])
        for a in self.browse(cr, uid, ids):
            if a.user_type_code == 'expense' or (vals.get('user_type', False) and vals.get('user_type') in expense_type_ids):
                if vals.get('default_destination_analytic_account', False) or a.default_destination_analytic_account:
                    continue
                raise osv.except_osv(_('Warning'), _('Default destination is mandatory for expense accounts!'))
        return super(account_account, self).write(cr, uid, ids, vals, context)

account_account()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
