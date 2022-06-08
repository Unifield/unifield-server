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
import time
import logging

class financing_contract_account_quadruplet(osv.osv):
    _name = 'financing.contract.account.quadruplet'
    _rec_name = 'cost_center_id'
    _description = 'FP / CC / destination valid values view'
    _log_access = False
    _auto = True
    _logger = logging.getLogger('contract.quad')

    def migrate_old_quad(self, cr, uid, ids, context=None):
        '''
            ids: list of record in the old view
            return list of new record
        '''

        new_ids = []
        for old_id in ids:
            # DO UPDATE: to return an id
            cr.execute('''
                INSERT INTO financing_contract_account_quadruplet
                    (account_destination_name, account_id, cost_center_id, disabled, account_destination_link_id, funding_pool_id, account_destination_id)
                ( select
                    account_destination_name, account_id, cost_center_id, disabled, account_destination_link_id, funding_pool_id, account_destination_id
                from
                    financing_contract_account_quadruplet_old
                where
                    id=%s
                ) ON CONFLICT ON CONSTRAINT financing_contract_account_quadruplet_check_unique DO UPDATE SET disabled=EXCLUDED.disabled
                RETURNING id ''', (old_id,))
            ret = cr.fetchone()
            if ret:
                new_ids.append(ret[0])
        return new_ids

    def _auto_init(self, cr, context=None):
        sql.drop_view_if_exists(cr, 'financing_contract_account_quadruplet')
        sql.drop_view_if_exists(cr, 'financing_contract_account_quadruplet_view')
        res = super(financing_contract_account_quadruplet, self)._auto_init(cr, context)
        sql.drop_view_if_exists(cr, 'financing_contract_account_quadruplet_old')

        # old sql view kept to manage migration and old sync updates
        cr.execute('''CREATE OR REPLACE VIEW financing_contract_account_quadruplet_old AS (
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
           ORDER BY lnk.name, cc.code DESC)
        ''')

        cr.execute("""CREATE OR REPLACE VIEW financing_contract_account_quadruplet_view AS (
            SELECT account_destination_id, cost_center_id, funding_pool_id, account_destination_name, account_id, disabled, account_destination_link_id FROM
            (
            -- all cc = f, G/L = f
            SELECT
            lnk.destination_id AS account_destination_id, cc.id AS cost_center_id, fp.id AS funding_pool_id, lnk.name AS account_destination_name, lnk.account_id, lnk.disabled, lnk.id as account_destination_link_id
            FROM account_analytic_account fp,
                 account_analytic_account cc,
                 funding_pool_associated_cost_centers fpacc,
                 funding_pool_associated_destinations fpad,
                 account_destination_link lnk,
                 account_analytic_account dest
            LEFT JOIN dest_cc_link ON dest_cc_link.dest_id = dest.id
            
           WHERE
                fpacc.funding_pool_id = fp.id AND
                fpacc.cost_center_id = cc.id AND
                lnk.id = fpad.tuple_id AND
                fp.id = fpad.funding_pool_id AND
                lnk.destination_id = dest.id AND
                (dest.allow_all_cc = 't' or dest_cc_link.cc_id = cc.id)

           UNION

            -- all cc = t, G/L = t
            select
            lnk.destination_id AS account_destination_id, cc.id AS cost_center_id, fp.id AS funding_pool_id, lnk.name AS account_destination_name, lnk.account_id, lnk.disabled, lnk.id as account_destination_link_id
            FROM
                account_analytic_account fp,
                account_analytic_account cc,
                fp_account_rel,
                account_target_costcenter target,
                account_destination_link lnk,
                account_account  gl_account,
                account_analytic_account dest
            LEFT JOIN dest_cc_link ON dest_cc_link.dest_id = dest.id
            where
                fp.allow_all_cc_with_fp = 't' and
                cc.type != 'view' and
                cc.category = 'OC' and
                target.cost_center_id = cc.id and
                target.instance_id = fp.instance_id and
                fp.select_accounts_only = 't' and
                fp_account_rel.fp_id = fp.id and
                fp_account_rel.account_id= gl_account.id and
                lnk.account_id = gl_account.id and
                lnk.destination_id = dest.id and
                (dest.allow_all_cc = 't' or dest_cc_link.cc_id = cc.id)

            UNION

            -- all cc = f, G/L = t
            select
            lnk.destination_id AS account_destination_id, cc.id AS cost_center_id, fp.id AS funding_pool_id, lnk.name AS account_destination_name, lnk.account_id, lnk.disabled, lnk.id as account_destination_link_id
            FROM
                account_analytic_account fp,
                account_analytic_account cc,
                funding_pool_associated_cost_centers fpacc,
                fp_account_rel,
                account_destination_link lnk,
                account_account  gl_account,
                account_analytic_account dest
            LEFT JOIN dest_cc_link ON dest_cc_link.dest_id = dest.id
            where
                fp.allow_all_cc_with_fp = 'f' and
                fpacc.funding_pool_id = fp.id and
                fpacc.cost_center_id = cc.id and
                fp.select_accounts_only = 't' and
                fp_account_rel.fp_id = fp.id and
                fp_account_rel.account_id= gl_account.id and
                lnk.account_id = gl_account.id and
                lnk.destination_id = dest.id and
                (dest.allow_all_cc = 't' or dest_cc_link.cc_id = cc.id)

            UNION

            -- all cc = t , G/L = f
            select
            lnk.destination_id AS account_destination_id, cc.id AS cost_center_id, fp.id AS funding_pool_id, lnk.name AS account_destination_name, lnk.account_id, lnk.disabled, lnk.id as account_destination_link_id
            FROM
                account_analytic_account fp,
                account_analytic_account cc,
                funding_pool_associated_destinations fpad,
                account_target_costcenter target,
                account_destination_link lnk,
                account_analytic_account dest
            LEFT JOIN dest_cc_link ON dest_cc_link.dest_id = dest.id
            where
                fp.allow_all_cc_with_fp = 't' and
                cc.type != 'view' and
                cc.category = 'OC' and
                target.cost_center_id = cc.id and
                target.instance_id = fp.instance_id and
                fp.select_accounts_only = 'f' and
                lnk.id = fpad.tuple_id and
                fp.id = fpad.funding_pool_id and
                lnk.destination_id = dest.id and
                (dest.allow_all_cc = 't' or dest_cc_link.cc_id = cc.id)
            ) AS combinations
           )""")
        return res

    def gen_quadruplet(self, cr, uid, context=None):
        '''
            triggered by unifield-web to generate the list of quadruplets for this contract
            record the last generation date to refresh only if the contract, a dest link or a ana. acccount is modified
        '''
        if context is None:
            context = {}
        contract_id = context.get('contract_id', False)
        if contract_id:
            ctr_obj = self.pool.get('financing.contract.contract')
            contract = ctr_obj.browse(cr, uid, context['contract_id'], fields_to_fetch=['funding_pool_ids', 'cost_center_ids', 'quad_gen_date'], context=context)
            # last_modification: is modified when the record is Save&Edit on the instance
            # date_update: is modified by a sync update
            cr.execute('''
                select max(greatest(last_modification, date_update))
                from
                    ir_model_data
                where
                    module='sd' and
                    model in ('account.analytic.account', 'account.destination.link', 'dest.cc.link')
            ''')
            last_obj_modified = cr.fetchone()[0]
            if not contract.quad_gen_date or last_obj_modified > contract.quad_gen_date or contract.quad_gen_date > time.strftime('%Y-%m-%d %H:%M:%S'):
                # ignore quad_gen_date in the future
                self._logger.info('contract_id: %s, last mod: %s, quad date: %s' % (contract_id, last_obj_modified, contract.quad_gen_date))
                timer = time.time()
                cc_ids = [cc.id for cc in contract.cost_center_ids]
                fp_ids = [fp.funding_pool_id.id for fp in contract.funding_pool_ids]
                if not cc_ids:
                    # do not traceback if cc / fp not set on contract
                    cc_ids = [0]
                if not fp_ids:
                    fp_ids = [0]
                cr.execute('''
                    update financing_contract_account_quadruplet set disabled='t'
                    where
                        funding_pool_id in %s and
                        cost_center_id in %s
                ''', (tuple(fp_ids), tuple(cc_ids)))
                cr.execute('''
                    INSERT INTO financing_contract_account_quadruplet
                        (account_destination_name, account_id, cost_center_id, disabled, account_destination_link_id, funding_pool_id, account_destination_id)
                    (select
                        account_destination_name, account_id, cost_center_id, disabled, account_destination_link_id, funding_pool_id, account_destination_id
                        from
                            financing_contract_account_quadruplet_view
                        where
                            funding_pool_id in %s and
                            cost_center_id in %s
                    )
                    ON CONFLICT ON CONSTRAINT financing_contract_account_quadruplet_check_unique DO UPDATE SET disabled=EXCLUDED.disabled''', (tuple(fp_ids), tuple(cc_ids)))
                cr.execute('update financing_contract_contract set quad_gen_date=%s where id=%s', (last_obj_modified, contract_id))
                self._logger.info('Gen time: %s' % (time.time() - timer))
        return True

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

    _columns = {
        'account_destination_id': fields.many2one('account.analytic.account', 'Destination', relate=True, readonly=True, select=1),
        'cost_center_id': fields.many2one('account.analytic.account', 'Cost Centre', relate=True, readonly=True, select=1),
        'funding_pool_id': fields.many2one('account.analytic.account', 'Funding Pool', relate=True, readonly=True, select=1),
        'account_destination_name': fields.char('Account', size=64, readonly=True, select=1),
        'used_in_contract': fields.function(_get_used_in_contract, method=True, type='boolean', string='Used'),
        'can_be_used': fields.function(_can_be_used_in_contract, method=True, type='boolean', string='Can', fnct_search=_search_can_be),
        'account_id': fields.many2one('account.account', 'Account ID', relate=True, readonly=True, select=1),
        'account_destination_link_id': fields.many2one('account.destination.link', 'Link id', readonly=True, select=1),
        'disabled': fields.boolean('Disabled'),
    }

    _sql_constraints = {
        ('check_unique',
         'unique (account_destination_id, cost_center_id, funding_pool_id, account_id, account_destination_link_id)',
         'not unique!')
    }
    _order = 'account_destination_name asc, funding_pool_id asc, cost_center_id asc, id'


financing_contract_account_quadruplet()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
