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
    _description = 'FP / CC / destination valid values view'
    _auto = False
  
    
    def init(self, cr):
       # SELECT ((('1'::text || lpad(fp.id::text, 3, '0'::text)) || lpad(cc.id::text, 3, '0'::text)) || lpad(lnk.id::text, 3, '0'::text))::integer AS id, 
       cr.execute("""CREATE OR REPLACE VIEW financing_contract_account_quadruplet AS (
            SELECT abs(('x'||substr(md5(fp.code || cc.code || lnk.name),1,16))::bit(32)::int) as id,
            lnk.id AS account_destination_id, cc.id AS cost_center_id, fp.id AS funding_pool_id, lnk.name AS account_destination_name
            FROM account_analytic_account fp, 
                 account_analytic_account cc, 
                 funding_pool_associated_cost_centers fpacc, 
                 funding_pool_associated_destinations fpad, 
                 account_destination_link lnk
           WHERE fpacc.funding_pool_id = fp.id 
             AND fpacc.cost_center_id = cc.id 
             AND lnk.id = fpad.tuple_id 
             AND fp.id = fpad.funding_pool_id
           ORDER BY lnk.name, cc.code DESC)""")
        
    
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
        # financing_contract_funding_pool_line.contract_id is a FK for financing_contract_format.id
        # TODO this should be renamed format_id 
        cr.execute('''select account_quadruplet_id
                        from financing_contract_actual_account_quadruplets
                        where actual_line_id in (select id from financing_contract_format_line 
                                                where format_id = %s and is_quadruplet is true)''' % (contract.format_id.id))
        rows = cr.fetchall()
        for id in [x[0] for x in rows]:
            exclude[id] = True
        for id in ids:
            res[id] = id in exclude
        return res
        
    
    
    def _can_be_used_in_contract(self, cr, uid, ids, field_name, arg, context=None):
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
        # financing_contract_funding_pool_line.contract_id is a FK for financing_contract_format.id
        # TODO this should be renamed format_id during refactoring    
        exclude = {}
        cr.execute('''select id from financing_contract_account_quadruplet 
                        where funding_pool_id in 
                             (select funding_pool_id 
                             from financing_contract_funding_pool_line
                             where contract_id = %s)
                      and exists (select 'X' 
                                from financing_contract_cost_center cc
                                where cc.contract_id = %s
                                and cc.cost_center_id = 
                                    financing_contract_account_quadruplet.cost_center_id)''' % (contract.format_id.id,contract.format_id.id))
        for id in [x[0] for x in cr.fetchall()]:
            exclude[id] = True   
        for id in ids:
            res[id] = id in exclude
        return res
    

    def _search_can_be(self, cr, uid, ids, field_name, arg, context=None):
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
        cr.execute('''select id from financing_contract_account_quadruplet 
                        where funding_pool_id in 
                             (select funding_pool_id 
                             from financing_contract_funding_pool_line
                             where contract_id = %s)
                      and exists (select 'X' 
                                from financing_contract_cost_center cc
                                where cc.contract_id = %s
                                and cc.cost_center_id = 
                                    financing_contract_account_quadruplet.cost_center_id)''' % (contract.format_id.id,contract.format_id.id))    
        someids = []
        someids += [x[0] for x in cr.fetchall()]
        return [('id','in',someids)]

 
    
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
        funding_pool_ids = self.pool.get('financing.contract.funding.pool.line').search(cr, uid, [('contract_id','=',context['contract_id'])])

        exclude = []
        for line in contract.actual_line_ids:
            if context.get('active_id', False) and line.id != context['active_id']:
                for account_destination in line.account_destination_ids:
                    cr.execute('''select account_quadruplet_id
                                  from financing_contract_actual_account_quadruplets
                                  where actual_line_id in (select l.id from financing_contract_contract c,
                                                          financing_contract_format f,
                                                          financing_contract_format_line l
                                                          where c.id = %s
                                                          and f.id = c.format_id
                                                          and l.format_id = f.id)''' % (contract.format_id.id))           
                    exclude += [x[0] for x in cr.fetchall()]
                for account_quadruplet in line.account_quadruplet_ids:
                    exclude.append(account_quadruplet.id)
        return [('id', 'not in', exclude)]
    
    
    # columns for original table
#     _columns = {
#        'format_id': fields.many2one('financing.contract.format', 'Format'),
# 
#         'cost_center_id': fields.many2one('account.analytic.account', 'Cost Centre'),
#         'funding_pool_id': fields.many2one('account.analytic.account', 'Funding Pool'),
#         'account_destination_name': fields.char('Account', size=64),
#         'used_in_contract': fields.function(_get_used_in_contract, method=True, type='boolean', string='Used', fnct_search=_search_used_in_contract),
#      }
        
    #columns for view
    _columns = {
        'account_destination_id': fields.many2one('account.destination.link', 'Account/Destination', relate=True, readonly=True),
        'cost_center_id': fields.many2one('account.analytic.account', 'Cost Centre', relate=True, readonly=True),
        'funding_pool_id': fields.many2one('account.analytic.account', 'Funding Pool', relate=True, readonly=True),
        'account_destination_name': fields.char('Account', size=64, readonly=True),
        'used_in_contract': fields.function(_get_used_in_contract, method=True, type='boolean', string='Used', fnct_search=_search_used_in_contract),
        'can_be_used': fields.function(_can_be_used_in_contract, method=True, type='boolean', string='Can', fnct_search=_search_can_be),
     }
    
    _order = 'account_destination_name asc, funding_pool_id asc, cost_center_id asc'
    
    
financing_contract_account_quadruplet()

class financing_contract_format_line(osv.osv):
    
    _name = "financing.contract.format.line"
    _inherit = "financing.contract.format.line"
    
    _columns = {
        'account_quadruplet_ids': many2many_sorted('financing.contract.account.quadruplet', 'financing_contract_actual_account_quadruplets', 'actual_line_id', 'account_quadruplet_id', string='Accounts/Destinations/Funding Pools/Cost Centres'),
        'quadruplet_update': fields.char('Internal Use Only', size=128),
    }
        
financing_contract_format_line()
 

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

