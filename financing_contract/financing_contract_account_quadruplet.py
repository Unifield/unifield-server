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
from analytic_distribution.destination_tools import many2many_sorted

class financing_contract_account_quadruplet(osv.osv):
    _name = 'financing.contract.account.quadruplet'

    def _get_used_in_contract(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        if context is None:
            context = {}
        exclude = {}

        if not context.get('contract_id'):
            for id in ids:
                res[id] = False
            return res

        ctr_obj = self.pool.get('financing.contract.contract')
        contract = ctr_obj.browse(cr, uid, context['contract_id'])

        exclude = {}
        for line in contract.actual_line_ids:
            if context.get('active_id', False) and line.id != context['active_id']:
                for account_destination in line.account_destination_ids:
                    cr.execute('''select id
                                  from financing_contract_account_quadruplet
                                  where format_id = %s and account_destination_id = %s''' % (contract.format_id.id, account_destination.id))
                    for id in [x[0] for x in cr.fetchall()]:
                        exclude[id] = True
                for account_quadruplet in line.account_quadruplet_ids:
                    exclude[account_quadruplet.id] = True
        for id in ids:
            res[id] = id in exclude
        return res

    def _search_used_in_contract(self, cr, uid, obj, name, args, context=None):
        if not args:
            return []
        if context is None:
            context = {}
        assert args[0][1] == '=' and args[0][2], 'Filter not implemented'
        if not context.get('contract_id'):
            return []

        ctr_obj = self.pool.get('financing.contract.contract')
        contract = ctr_obj.browse(cr, uid, context['contract_id'])

        exclude = []
        for line in contract.actual_line_ids:
            if context.get('active_id', False) and line.id != context['active_id']:
                for account_destination in line.account_destination_ids:
                    cr.execute('''select id
                                  from financing_contract_account_quadruplet
                                  where format_id = %s and account_destination_id = %s''' % (contract.format_id.id, account_destination.id))
                    exclude += [x[0] for x in cr.fetchall()]
                for account_quadruplet in line.account_quadruplet_ids:
                    exclude.append(account_quadruplet.id)
        for id in ids:
            res[id] = id in exclude

        return [('id', 'not in', exclude)]

    _columns = {
        'format_id': fields.many2one('financing.contract.format', 'Format'),
        'account_destination_id': fields.many2one('account.destination.link', 'Account/Destination'),
        'cost_center_id': fields.many2one('account.analytic.account', 'Cost Centre'),
        'funding_pool_id': fields.many2one('account.analytic.account', 'Funding Pool'),
        'account_destination_name': fields.char('Account', size=64),
        'used_in_contract': fields.function(_get_used_in_contract, method=True, type='boolean', string='Used', fnct_search=_search_used_in_contract),
    }
    
    _order = 'account_destination_name asc, funding_pool_id asc, cost_center_id asc'
    
    def create(self, cr, uid, vals, context=None):
        if 'account_destination_id' in vals:
            account_destination = self.pool.get('account.destination.link').browse(cr, uid, vals['account_destination_id'], context=context)
            if account_destination.account_id and account_destination.destination_id:
                vals['account_destination_name'] = account_destination.account_id.code + " " + account_destination.destination_id.code
        return super(financing_contract_account_quadruplet, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        if 'account_destination_id' in vals:
            account_destination = self.pool.get('account.destination.link').browse(cr, uid, vals['account_destination_id'], context=context)
            if account_destination.account_id and account_destination.destination_id:
                vals['account_destination_name'] = account_destination.account_id.code + " " + account_destination.destination_id.code
        return super(financing_contract_account_quadruplet, self).write(cr, uid, ids, vals, context=context)
    
financing_contract_account_quadruplet()

class financing_contract_format_line(osv.osv):
    
    _name = "financing.contract.format.line"
    _inherit = "financing.contract.format.line"
    
    _columns = {
        'account_quadruplet_ids': many2many_sorted('financing.contract.account.quadruplet', 'financing_contract_actual_account_quadruplets', 'actual_line_id', 'account_quadruplet_id', string='Accounts/Destinations/Funding Pools/Cost Centres'),
    }
        
financing_contract_format_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

