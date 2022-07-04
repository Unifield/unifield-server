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

class financing_contract_format(osv.osv):

    _name = "financing.contract.format"
    _rec_name = 'format_name'

    _columns = {
        'format_name': fields.char('Name', size=64, required=True),
        'reporting_type': fields.selection([('project','Total project only'),
                                            ('allocated','Earmarked only'),
                                            ('all', 'Earmarked and total project')], 'Reporting type', required=True),
        # For contract only, but needed for line domain;
        # we need to keep them available
        'overhead_percentage': fields.float('Overhead percentage'),
        'overhead_type': fields.selection([('cost_percentage','Percentage of direct costs'),
                                           ('grant_percentage','Percentage of grant')], 'Overhead calculation mode'),
        'eligibility_from_date': fields.date('Eligibility date from'),
        'eligibility_to_date': fields.date('Eligibility date to'),
        'funding_pool_ids': fields.one2many('financing.contract.funding.pool.line', 'contract_id', 'Funding Pools'),
        'cost_center_ids': fields.many2many('account.analytic.account', 'financing_contract_cost_center', 'contract_id', 'cost_center_id', string='Cost Centers'),

        'hidden_instance_id': fields.many2one('msf.instance','Proprietary Instance'),
    }

    _defaults = {
        'format_name': 'Format',
        'reporting_type': 'all',
        'overhead_type': 'cost_percentage',
    }

    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}

        # get previous list of cc
        previous_cc = {}
        cr.execute('''
                select cc.contract_id, array_agg(cc.cost_center_id)
                from
                    financing_contract_cost_center cc
                where 
                    cc.contract_id = %s
                group by cc.contract_id
            ''', (tuple(ids),))
        for x in cr.fetchall():
            previous_cc[x[0]] = set(x[1])


        previous_fp = {}
        # get previous list of fp
        cr.execute('''
                select fp.contract_id, array_agg(fp.funding_pool_id)
                from
                    financing_contract_funding_pool_line fp
                where 
                    fp.contract_id = %s
                group by fp.contract_id
            ''', (tuple(ids),))
        for x in cr.fetchall():
            previous_fp[x[0]] = set(x[1])

        res =  super(financing_contract_format, self).write(cr, uid, ids, vals, context=context)

        # get current list of cc
        current_cc = {}
        cr.execute('''
                select cc.contract_id, array_agg(cc.cost_center_id)
                from
                    financing_contract_cost_center cc
                where 
                    cc.contract_id = %s
                group by cc.contract_id
            ''', (tuple(ids),))
        for x in cr.fetchall():
            current_cc[x[0]] = set(x[1])

        current_fp = {}
        # get previous list of fp
        cr.execute('''
                select fp.contract_id, array_agg(fp.funding_pool_id)
                from
                    financing_contract_funding_pool_line fp
                where 
                    fp.contract_id = %s
                group by fp.contract_id
            ''', (tuple(ids),))
        for x in cr.fetchall():
            current_fp[x[0]] = set(x[1])

        for _id in ids:
            # if cc added or fp added, we don't care of fp or cc deletion bc quad used will be deleted
            if not current_cc.get(_id, set()).issubset(previous_cc.get(_id, set())) or not current_fp.get(_id, set()).issubset(previous_fp.get(_id, set())):
                # reset flag to refresh quad combination if needed
                cr.execute('''update financing_contract_contract set quad_gen_date=NULL where format_id = %s''', (_id,))

            if not context.get('sync_update_execution'):
                # no auto delete from sync , in case of NR on FP lines
                cc_removed = previous_cc.get(_id, set()) - current_cc.get(_id, set())
                cc_removed.add(0)
                current_fp.setdefault(_id, set()).add(0)
                cr.execute("""
                    delete from
                        financing_contract_actual_account_quadruplets quadl using financing_contract_format_line fl, financing_contract_format fm, financing_contract_contract fc, financing_contract_account_quadruplet quad
                    where
                        fl.id = quadl.actual_line_id and
                        fm.id = fl.format_id and
                        fc.format_id = fm.id and
                        fm.id = %s and
                        quad.id = quadl.account_quadruplet_id and
                        (quad.funding_pool_id not in %s  or quad.cost_center_id in %s)
                    returning fl.id
                """, (_id, tuple(current_fp[_id]), tuple(cc_removed)))
                if cr.rowcount:
                    # trigger sync
                    fl = set([x[0] for x in cr.fetchall()])
                    self.pool.get('financing.contract.format.line').sql_synchronize(cr, fl, 'quadruplet_sync_list')

        return res

    def name_get(self, cr, uid, ids, context=None):
        result = self.browse(cr, uid, ids, context=context)
        res = []
        for rs in result:
            format_name = rs.format_name
            res += [(rs.id, format_name)]
        return res

    _sql_constraints = [
        ('date_overlap', 'check(eligibility_from_date < eligibility_to_date)', 'The "Eligibility Date From" should be sooner than the "Eligibility Date To".'),
    ]


financing_contract_format()

class account_destination_link(osv.osv):
    _name = 'account.destination.link'
    _inherit = 'account.destination.link'

    def _get_used_in_contract(self, cr, uid, ids, field_name, arg, context=None):
        ids_to_exclude = {}
        if context is None:
            context = {}
        exclude = {}

        if not context.get('contract_id') and not context.get('donor_id'):
            for id in ids:
                ids_to_exclude[id] = False
            return ids_to_exclude

        if context.get('contract_id'):
            ctr_obj = self.pool.get('financing.contract.contract')
            id_toread = context['contract_id']
        elif context.get('donor_id'):
            ctr_obj = self.pool.get('financing.contract.donor')
            id_toread = context['donor_id']

        active_id = context.get('active_id', False)
        for line in ctr_obj.browse(cr, uid, id_toread).actual_line_ids:
            if not active_id or line.id != active_id:
                for account_destination in line.account_destination_ids: # exclude from other duplet format lines
                    exclude[account_destination.id] = True
                for account_quadruplet in line.account_quadruplet_ids: # exclude from other quadruplet format lines
                    # UFTP-16: The list of all duplet acc/destination needs to be grey if one line of combination in the quad has been selected
                    duplet_ids_to_exclude = self.search(cr, uid, [('account_id', '=', account_quadruplet.account_id.id),('destination_id','=',account_quadruplet.account_destination_id.id)])
                    for item in duplet_ids_to_exclude:
                        exclude[item] = True
                for account in line.reporting_account_ids:
                    # exclude the acc/dest combinations when the account has been selected in lines with "accounts only"
                    for acc_dest in self.search(cr, uid, [('account_id', '=', account.id)], order='NO_ORDER', context=context):
                        exclude[acc_dest] = True

        for id in ids:
            ids_to_exclude[id] = id in exclude
        return ids_to_exclude

    _columns = {
        'used_in_contract': fields.function(_get_used_in_contract, method=True, type='boolean', string='Used'),
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if context is None:
            context = {}
        if view_type == 'tree' and (context.get('contract_id') or context.get('donor_id')) :
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'financing_contract', 'view_account_destination_link_for_contract_tree')[1]
        return super(account_destination_link, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)



account_destination_link()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
