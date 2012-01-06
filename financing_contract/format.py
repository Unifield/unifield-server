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
    
    _columns = {
        'format_name': fields.char('Name', size=64, required=True),
        'reporting_type': fields.selection([('project','Total project costs'),
                                            ('allocated','Funded costs'),
                                            ('all', 'Total project and funded costs')], 'Reporting type', required=True),
        # For contract only, but needed for line domain;
        # we need to keep them available
        'eligibility_from_date': fields.date('Eligibility date from'),
        'eligibility_to_date': fields.date('Eligibility date to'),
        'funding_pool_ids': fields.one2many('financing.contract.funding.pool.line', 'contract_id', 'Funding Pools'),
        'cost_center_ids': fields.many2many('account.analytic.account', 'financing_contract_cost_center', 'contract_id', 'cost_center_id', string='Cost Centers'),
    }
    
    _defaults = {
        'format_name': 'Format',
        'reporting_type': 'all',
    }
    
    def name_get(self, cr, uid, ids, context=None):
        result = self.browse(cr, uid, ids, context=context)
        res = []
        for rs in result:
            format_name = rs.format_name
            res += [(rs.id, format_name)]
        return res
        
financing_contract_format()

class account_account(osv.osv):
    _name = 'account.account'
    _inherit = 'account.account'

    def _get_used(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        if context is None:
            context = {}
        exclude = {}
        
        ctr_obj = self.pool.get('financing.contract.contract')
        exclude = {}
        for line in ctr_obj.browse(cr, uid, context['contract_id']).actual_line_ids:
            for acc in line.account_ids:
                exclude[acc.id] = True
        for id in ids:
            res[id] = id in exclude
        return res

    def _search_used(self, cr, uid, obj, name, args, context={}):
        if not args:
            return []
        if context is None:
            context = {}
        assert args[0][1] == '=' and args[0][2], 'Filter not implemented'
        if not context.get('contract_id'):
            return []
        ctr_obj = self.pool.get('financing.contract.contract')
        exclude = {}
        for line in ctr_obj.browse(cr, uid, context['contract_id']).actual_line_ids:
            for acc in line.account_ids:
                exclude[acc.id] = True

        return [('id', 'not in', exclude.keys())]
    _columns = {
        'used': fields.function(_get_used, method=True, type='boolean', string='Used', fnct_search=_search_used),
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if context is None:
            context = {}
        if view_type == 'tree' and context.get('contract_id'):
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'financing_contract', 'view_account_for_contract_tree')[1]
        return super(account_account, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)

account_account()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
