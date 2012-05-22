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

class account_destination_link(osv.osv):
    _name = 'account.destination.link'
    _description = 'Destination link between G/L and Analytic accounts'

    _columns = {
        'account_id': fields.many2one('account.account', "G/L Account", required=True),
        'destination_id': fields.many2one('account.analytic.account', 'Analytical Destination Account', required=True, domain="[('type', '!=', 'view'), ('category', '=', 'DEST')]"),
        'default': fields.boolean('Default?', help="If True, the destination account is those by default for this account."),
    }

    _defaults = {
        'default': lambda *a: False,
    }

    def _check_couple(self, cr, uid, ids, context=None):
        """
        Check that no more than one account_id/destination_id couple exists
        """
        for link in self.browse(cr, uid, ids):
            couple_ids = self.search(cr, uid, [('account_id', '=', link.account_id.id), ('destination_id', '=', link.destination_id.id)])
            if len(couple_ids) > 1:
                return False
        return True

    def _check_default(self, cr, uid, ids, context=None):
        """
        Check that no more than one account_id is selected for a given destination_id.
        Tip: In fact we search account_id/default which shouldn't be more than one element.
        """
        for link in self.browse(cr, uid, ids):
            if link.default:
                default_ids = self.search(cr, uid, [('account_id', '=', link.account_id.id), ('default', '=', True)])
                if len(default_ids) > 1:
                    return False
        return True

    _constraints = [
        (_check_couple, 'You cannot have the same couple account/destination twice!', ['account_id', 'destination_id']),
        (_check_default, 'You cannot have more than one destination for this account!', ['account_id', 'default']),
    ]

account_destination_link()

class account_account(osv.osv):
    _name = 'account.account'
    _inherit = 'account.account'

#    def _get_destinations(self, cr, uid, ids, field_name, args, context=None):
#        """
#        Retrieve destination linked to the given accounts (ids).
#        """
#        res = {}
#        for el in self.browse(cr, uid, ids):
#            res[el.id] = False
#            search_ids = self.pool.get('account.destination.link').search(cr, uid, [('account_id', '=', el.id)])
#            if search_ids:
#                res[el.id] = map(lambda x: x, search_ids)
#        return res

#    def _set_destinations(self, cr, uid, id, field, value, arg, context=None):
#        """
#        Write change to account.destination.link Object.
#        """
#        for el in value:
#            if len(el) != 3:
#                continue
#            vals = el[2]
#            if el[0] == 0:
#                vals.update({'account_id': id})
#                self.pool.get('account.destination.link').create(cr, uid, vals)
#            elif el[0] == 1:
#                self.pool.get('account.destination.link').write(cr, uid, el[1], vals)
#        return True

#    def _search_destinations(self, cr, uid, *a, **b):
#        return []

    _columns = {
        'user_type_code': fields.related('user_type', 'code', type="char", string="User Type Code", store=False),
        'funding_pool_line_ids': fields.many2many('account.analytic.account', 'funding_pool_associated_accounts', 'account_id', 'funding_pool_id', 
            string='Funding Pools'),
        'dest_ids': fields.one2many('account.destination.link', 'account_id', "Destination"), #fields.function(_get_destinations, fnct_inv=_set_destinations, fnct_search=_search_destinations, type="many2many", method=True, required=False, relation="account.destination.link"),
    }

account_account()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
