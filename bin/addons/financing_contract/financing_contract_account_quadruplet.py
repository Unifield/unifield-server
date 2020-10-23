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

from osv import fields, osv
from tools import sql

class financing_contract_account_quadruplet(osv.osv):
    _name = 'financing.contract.account.quadruplet'
    _rec_name = 'cost_center_id'
    _description = 'FP / CC / destination valid values view'
    _auto = False


    def _auto_init(self, cr, context=None):
        res = super(financing_contract_account_quadruplet, self)._auto_init(cr, context)
        sql.drop_view_if_exists(cr, 'financing_contract_account_quadruplet')
        cr.execute("""CREATE OR REPLACE VIEW financing_contract_account_quadruplet AS (
            SELECT id, account_destination_id, cost_center_id, funding_pool_id, account_destination_name, account_id, disabled, account_destination_link_id FROM
            (
            -- all cc = f, G/L = f
            SELECT abs(('x'||substr(md5(fp.code || cc.code || lnk.name),1,16))::bit(32)::int) as id,
            lnk.destination_id AS account_destination_id, cc.id AS cost_center_id, fp.id AS funding_pool_id, lnk.name AS account_destination_name, lnk.account_id, lnk.disabled, lnk.id as account_destination_link_id
            FROM account_analytic_account fp,
                 account_analytic_account cc,
                 funding_pool_associated_cost_centers fpacc,
                 funding_pool_associated_destinations fpad,
                 account_destination_link lnk
           WHERE fpacc.funding_pool_id = fp.id
             AND fpacc.cost_center_id = cc.id
             AND lnk.id = fpad.tuple_id
             AND fp.id = fpad.funding_pool_id

           UNION

            -- all cc = t, G/L = t
            select abs(('x'||substr(md5(fp.code || cc.code || lnk.name),1,16))::bit(32)::int) as id,
            lnk.destination_id AS account_destination_id, cc.id AS cost_center_id, fp.id AS funding_pool_id, lnk.name AS account_destination_name, lnk.account_id, lnk.disabled, lnk.id as account_destination_link_id
            FROM
                account_analytic_account fp,
                account_analytic_account cc,
                fp_account_rel,
                account_target_costcenter target,
                account_destination_link lnk,
                account_account  gl_account
            where
                fp.allow_all_cc_with_fp = 't' and
                cc.type != 'view' and
                cc.category = 'OC' and
                target.cost_center_id = cc.id and
                target.instance_id = fp.instance_id and
                fp.select_accounts_only = 't' and
                fp_account_rel.fp_id = fp.id and
                fp_account_rel.account_id= gl_account.id and
                lnk.account_id = gl_account.id

            UNION

            -- all cc = f, G/L = t
            select abs(('x'||substr(md5(fp.code || cc.code || lnk.name),1,16))::bit(32)::int) as id,
            lnk.destination_id AS account_destination_id, cc.id AS cost_center_id, fp.id AS funding_pool_id, lnk.name AS account_destination_name, lnk.account_id, lnk.disabled, lnk.id as account_destination_link_id
            FROM
                account_analytic_account fp,
                account_analytic_account cc,
                funding_pool_associated_cost_centers fpacc,
                fp_account_rel,
                account_destination_link lnk,
                account_account  gl_account
            where
                fp.allow_all_cc_with_fp = 'f' and
                fpacc.funding_pool_id = fp.id and
                fpacc.cost_center_id = cc.id and
                fp.select_accounts_only = 't' and
                fp_account_rel.fp_id = fp.id and
                fp_account_rel.account_id= gl_account.id and
                lnk.account_id = gl_account.id

            UNION

            -- all cc = t , G/L = f
            select abs(('x'||substr(md5(fp.code || cc.code || lnk.name),1,16))::bit(32)::int) as id,
            lnk.destination_id AS account_destination_id, cc.id AS cost_center_id, fp.id AS funding_pool_id, lnk.name AS account_destination_name, lnk.account_id, lnk.disabled, lnk.id as account_destination_link_id
            FROM
                account_analytic_account fp,
                account_analytic_account cc,
                funding_pool_associated_destinations fpad,
                account_target_costcenter target,
                account_destination_link lnk
            where
                fp.allow_all_cc_with_fp = 't' and
                cc.type != 'view' and
                cc.category = 'OC' and
                target.cost_center_id = cc.id and
                target.instance_id = fp.instance_id and
                fp.select_accounts_only = 'f' and
                lnk.id = fpad.tuple_id and
                fp.id = fpad.funding_pool_id
            ) AS combinations

           ORDER BY account_destination_name)""")
        return res


    # The result set with {ID:Flag} if Flag=True, the line will be grey, otherwise, it is selectable
    def _get_used_in_contract(self, cr, uid, ids, field_name, arg, context=None):
        ids_to_exclude = {}
        if context is None:
            context = {}
        exclude = {}

        contract_id = context.get('contract_id', False)
        if not contract_id:
            for id in ids:
                ids_to_exclude[id] = False
            return ids_to_exclude

        ctr_obj = self.pool.get('financing.contract.contract')
        contract = ctr_obj.browse(cr, uid, contract_id)
        # financing_contract_funding_pool_line.contract_id is a FK for financing_contract_format.id
        # TODO this should be renamed format_id
        cr.execute('''select account_quadruplet_id
                        from financing_contract_actual_account_quadruplets
                        where account_quadruplet_id in %s and actual_line_id in (select id from financing_contract_format_line
                                                where format_id = %s and is_quadruplet is true)''', (tuple(ids), contract.format_id.id,))
        rows = cr.fetchall()
        for id in [x[0] for x in rows]:
            exclude[id] = True

        active_id = context.get('active_id', False)
        for line in contract.actual_line_ids:
            if not active_id or line.id != active_id:
                for account_destination in line.account_destination_ids:
                    # search the quadruplet to exclude
                    quadruplet_ids_to_exclude = self.search(cr, uid, [('id', 'in', ids), ('account_id', '=', account_destination.account_id.id),('account_destination_id','=',account_destination.destination_id.id)])
                    for item in quadruplet_ids_to_exclude:
                        exclude[item] = True
                for account in line.reporting_account_ids:
                    # exclude the quadruplets when the account has been selected in lines with "accounts only"
                    for quad in self.search(cr, uid, [('account_id', '=', account.id)], order='NO_ORDER', context=context):
                        exclude[quad] = True

        for id in ids:
            ids_to_exclude[id] = id in exclude
        return ids_to_exclude

    def _can_be_used_in_contract(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        if context is None:
            context = {}
        res = {}

        if not context.get('contract_id'):
            for id in ids:
                res[id] = False
            return res

        for _id in ids:
            res[_id] = False

        for _id in self.search(cr, uid, [('can_be_used', '=', True)], context=context):
            res[_id] = True
        return res

    def _search_can_be(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        if context is None:
            context = {}

        if not context.get('contract_id'):
            for id in ids:
                res[id] = False
            return res

        ctr_obj = self.pool.get('financing.contract.contract')
        contract = ctr_obj.browse(cr, uid, context['contract_id'], fields_to_fetch=['funding_pool_ids', 'cost_center_ids'])
        cc_ids = [cc.id for cc in contract.cost_center_ids]
        fp_ids = [fp.funding_pool_id.id for fp in contract.funding_pool_ids]
        return [('cost_center_id', 'in', cc_ids), ('funding_pool_id', 'in', fp_ids)]

    #columns for view
    _columns = {
        'account_destination_id': fields.many2one('account.analytic.account', 'Destination', relate=True, readonly=True),
        'cost_center_id': fields.many2one('account.analytic.account', 'Cost Centre', relate=True, readonly=True),
        'funding_pool_id': fields.many2one('account.analytic.account', 'Funding Pool', relate=True, readonly=True),
        'account_destination_name': fields.char('Account', size=64, readonly=True),
        'used_in_contract': fields.function(_get_used_in_contract, method=True, type='boolean', string='Used'),
        'can_be_used': fields.function(_can_be_used_in_contract, method=True, type='boolean', string='Can', fnct_search=_search_can_be),
        'account_id': fields.many2one('account.account', 'Account ID', relate=True, readonly=True),
        'account_destination_link_id': fields.many2one('account.destination.link', 'Link id', readonly=True),
        'disabled': fields.boolean('Disabled'),
    }

    _order = 'account_destination_name asc, funding_pool_id asc, cost_center_id asc'

financing_contract_account_quadruplet()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

