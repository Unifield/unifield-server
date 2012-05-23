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

class destination_m2m(fields.many2many):

    def set(self, cr, obj, id, name, values, user=None, context=None):
        """
        Compare written object and given objects. If new object, create them. If one of them disappears, delete it.
        """
        if not context:
            context = {}
        if not values:
            return
        obj = obj.pool.get(self._obj)
        for act in values:
            if not (isinstance(act, list) or isinstance(act, tuple)) or not act:
                continue
            if act[0] == 6:
                # search current destination
                destination_sql = """
                SELECT destination_id FROM %s
                WHERE account_id = %%s
                """ % self._rel
                cr.execute(destination_sql, (id,))
                destination_ids = cr.fetchall()
                old_list = [x[0] for x in destination_ids if x and x[0]]
                # delete useless destination
                if act[2]:
                    delete_sql = """
                    DELETE FROM %s
                    WHERE account_id = %%s
                    AND destination_id NOT IN %%s
                    """ % self._rel
                    query_sql = (id, tuple(act[2]))
                else:
                    delete_sql = """
                    DELETE FROM %s
                    WHERE account_id = %%s
                    """ % self._rel
                    query_sql = (id,)
                cr.execute(delete_sql, query_sql)
                # insert new destination
                for new_id in list(set(act[2]) - set(old_list)):
                    cr.execute('insert into '+self._rel+' ('+self._id1+','+self._id2+') values (%s, %s)', (id, new_id))
            else:
                return super(destination_m2m, self).set(cr, obj, id, name, values, user, context)

class account_destination_link(osv.osv):
    _name = 'account.destination.link'
    _description = 'Destination link between G/L and Analytic accounts'

    _columns = {
        'account_id': fields.many2one('account.account', "G/L Account", required=True, domain="[('type', '!=', 'view'), ('user_type_code', '=', 'expense')]"),
        'destination_id': fields.many2one('account.analytic.account', "Analytical Destination Account", required=True, domain="[('type', '!=', 'view'), ('category', '=', 'DEST')]"),
        'funding_pool_ids': fields.many2many('account.analytic.account', 'funding_pool_associated_destinations', 'tuple_id', 'funding_pool_id', "Funding Pools"),
    }

account_destination_link()

class account_account(osv.osv):
    _name = 'account.account'
    _inherit = 'account.account'

    _columns = {
        'user_type_code': fields.related('user_type', 'code', type="char", string="User Type Code", store=False),
        'funding_pool_line_ids': fields.many2many('account.analytic.account', 'funding_pool_associated_accounts', 'account_id', 'funding_pool_id', 
            string='Funding Pools'),
        'default_destination_id': fields.many2one('account.analytic.account', 'Default Destination', domain="[('type', '!=', 'view'), ('category', '=', 'DEST')]"),
        'destination_ids': destination_m2m('account.analytic.account', 'account_destination_link', 'account_id', 'destination_id', 'Destinations'),
    }

    def write(self, cr, uid, ids, vals, context=None):
        """
        Add default destination to the list of destination_ids
        """
        # Prepare some values
        if not context:
            context = {}
        # Check default destination presence
        if 'default_destination_id' in vals:
            # Fetch it
            dd_id = vals.get('default_destination_id')
            res = super(account_account, self).write(cr, uid, ids, vals, context=context)
            for a in self.browse(cr, uid, ids):
                if dd_id not in a.destination_ids:
                    all_ids = [x.id for x in a.destination_ids] or []
                    all_ids.append(dd_id)
                    super(account_account, self).write(cr, uid, [a.id], {'destination_ids': [(6, 0, all_ids)]})
            return res
        return super(account_account, self).write(cr, uid, ids, vals, context=context)

    def onchange_user_type(self, cr, uid, ids, user_type_id=False, context=None):
        """
        Update user_type_code with user_type_id code
        """
        res = {}
        if not user_type_id:
            return res
        data = self.pool.get('account.account.type').read(cr, uid, user_type_id, ['code']).get('code', False)
        if data:
            res.setdefault('value', {}).update({'user_type_code': data})
        return res

account_account()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
