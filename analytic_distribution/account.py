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
import tools
from lxml import etree

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
    _order = 'name, id'

    def _get_tuple_name(self, cr, uid, ids, name=False, args=False, context=None):
        """
        Get account_id code for tuple name
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not ids:
            return {}
        # Prepare some values
        res = {}
        # Browse given invoices
        for t in self.browse(cr, uid, ids):
            res[t.id] = ''
            # condition needed when a tuple is deleted from account.account
            if self.read(cr, uid, t.id, ['account_id']):
                res[t.id] = "%s %s"%(t.account_id and t.account_id.code or '', t.destination_id and t.destination_id.code or '')
        return res

    def _get_account_ids(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        return self.pool.get('account.destination.link').search(cr, uid, [('account_id', 'in', ids)], limit=0)

    def _get_analytic_account_ids(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        return self.pool.get('account.destination.link').search(cr, uid, [('destination_id', 'in', ids)], limit=0)

    def _get_used(self, cr, uid, ids, name=False, args=False, context=None):
        if context is None:
            context = {}

        used = []
        if context.get('dest_in_use') and isinstance(context['dest_in_use'], list):
            try:
                used = context['dest_in_use'][0][2]
            except ValueError:
                pass
        if isinstance(ids, (int, long)):
            ids = [ids]
        ret = {}
        for id in ids:
            ret[id] = id in used
        return ret

    _columns = {
        'account_id': fields.many2one('account.account', "G/L Account", required=True, domain="[('type', '!=', 'view'), ('user_type_code', '=', 'expense')]", readonly=True),
        'destination_id': fields.many2one('account.analytic.account', "Analytical Destination Account", required=True, domain="[('type', '!=', 'view'), ('category', '=', 'DEST')]", readonly=True),
        'funding_pool_ids': fields.many2many('account.analytic.account', 'funding_pool_associated_destinations', 'tuple_id', 'funding_pool_id', "Funding Pools"),
        'name': fields.function(_get_tuple_name, method=True, type='char', size=254, string="Name", readonly=True, 
            store={
                'account.destination.link': (lambda self, cr, uid, ids, c={}: ids, ['account_id', 'destination_id'], 20),
                'account.analytic.account': (_get_analytic_account_ids, ['code'], 10),
                'account.account': (_get_account_ids, ['code'], 10),
            }),
        'used': fields.function(_get_used, string='Used', method=True, type='boolean'),
    }

account_destination_link()

class account_destination_summary(osv.osv):
    _name = 'account.destination.summary'
    _description = 'Destinations by accounts'
    _auto = False

    _columns = {
        'account_id': fields.many2one('account.account', "G/L Account"),
        'funding_pool_id': fields.many2one('account.analytic.account', 'Funding Pool'),
    }

    def fields_get(self, cr, uid, fields=None, context=None):
        fields = super(account_destination_summary, self).fields_get(cr, uid, fields, context)
        dest_obj = self.pool.get('account.analytic.account')
        destination_ids = dest_obj.search(cr, uid, [('type', '!=', 'view'), ('category', '=', 'DEST'), ('parent_id', '!=', False)])
        for dest in dest_obj.read(cr, uid, destination_ids, ['name']):
            fields['dest_%s'%(dest['id'])] = {'type': 'boolean', 'string': dest['name']}
        return fields

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        view = super(account_destination_summary, self).fields_view_get(cr, uid, view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
        if view_type == 'tree':
            fields_to_add = []
            form = etree.fromstring(view['arch'])
            tree = form.xpath('//tree')
            for field in view.get('fields', {}):
                if field.startswith('dest_'):
                    fields_to_add.append(int(field.split('_')[1]))

            if fields_to_add:
                for dest_order in self.pool.get('account.analytic.account').search(cr, uid, [('id', 'in', fields_to_add)], order='name'):
                    new_field = etree.Element('field', attrib={'name': 'dest_%d'%dest_order})
                    tree[0].append(new_field)
            view['arch'] = etree.tostring(form)
        return view

    def read(self, cr, uid, ids, fields_to_read=None, context=None, load='_classic_read'):
        first = False
        if isinstance(ids, (int, long)):
            ids = [ids]
            first = True
        ret = super(account_destination_summary, self).read(cr, uid, ids, fields_to_read, context, load)
        f_to_read = []
        for field in fields_to_read:
            if field.startswith('dest_'):
                f_to_read.append(field)

        if f_to_read:
            cr.execute('''
                SELECT
                    sum.id,
                    l.destination_id
                FROM
                    account_destination_link l,
                    account_destination_summary sum,
                    funding_pool_associated_destinations d
                WHERE
                    d.tuple_id = l.id and
                    sum.account_id = l.account_id and
                    sum.funding_pool_id = d.funding_pool_id and
                    sum.id in %s
                ''',(tuple(ids),)
                )
            tmp_result = {}
            for x in cr.fetchall():
                tmp_result.setdefault(x[0], []).append(x[1])

            for x in ret:
                for dest in tmp_result.get(x['id'], []):
                    x['dest_%s'%(dest,)] = True
                for false_value in f_to_read:
                    if false_value not in x:
                        x[false_value] = False

        if first:
            return ret[0]
        return ret



    def init(self, cr):
        # test if id exists in funding_pool_associated_destinations or create it
        cr.execute("SELECT attr.attname FROM pg_attribute attr, pg_class class WHERE attr.attrelid = class.oid AND class.relname = 'funding_pool_associated_destinations' AND attr.attname='id'")
        if not cr.fetchall():
            cr.execute("ALTER TABLE funding_pool_associated_destinations ADD COLUMN id SERIAL")

        tools.drop_view_if_exists(cr, 'account_destination_summary')
        cr.execute(""" 
            CREATE OR REPLACE view account_destination_summary AS (
                SELECT
                    min(d.id) AS id,
                    l.account_id AS account_id,
                    d.funding_pool_id AS funding_pool_id
                FROM
                    account_destination_link l,
                    funding_pool_associated_destinations d
                WHERE
                    d.tuple_id = l.id
                GROUP BY
                    l.account_id,d.funding_pool_id
            )
        """)
    _order = 'account_id'
account_destination_summary()

class account_account(osv.osv):
    _name = 'account.account'
    _inherit = 'account.account'

    _columns = {
        'user_type_code': fields.related('user_type', 'code', type="char", string="User Type Code", store=False),
        'user_type_report_type': fields.related('user_type', 'report_type', type="char", string="User Type Report Type", store=False),
        'funding_pool_line_ids': fields.many2many('account.analytic.account', 'funding_pool_associated_accounts', 'account_id', 'funding_pool_id', 
            string='Funding Pools'),
        'default_destination_id': fields.many2one('account.analytic.account', 'Default Destination', domain="[('type', '!=', 'view'), ('category', '=', 'DEST')]"),
        'destination_ids': destination_m2m('account.analytic.account', 'account_destination_link', 'account_id', 'destination_id', 'Destinations', readonly=True),
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
        data = self.pool.get('account.account.type').read(cr, uid, user_type_id, ['code', 'report_type'])
        if data:
            res.setdefault('value', {}).update({'user_type_code': data.get('code', False), 'user_type_report_type': data.get('report_type', False)})
        return res

account_account()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
