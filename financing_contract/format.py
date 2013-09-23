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
    }
    
    _defaults = {
        'format_name': 'Format',
        'reporting_type': 'all',
        'overhead_type': 'cost_percentage',
    }
    
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
    
    def get_data_for_quadruplets(self, cr, format_id):
        # Get all existing account/destination links
        cr.execute('''select id from account_destination_link''')
        account_destination_ids = [x[0] for x in cr.fetchall()]
        # Get funding pools
        cr.execute('''select distinct funding_pool_id 
                      from financing_contract_funding_pool_line
                      where contract_id = %s ''' % (format_id))
        funding_pool_ids = [x[0] for x in cr.fetchall()]
        # Get cost centers
        cr.execute('''select distinct cost_center_id
                      from financing_contract_cost_center
                      where contract_id = %s ''' % (format_id))
        cost_center_ids = [x[0] for x in cr.fetchall()]
        
        return {'account_destination_ids': account_destination_ids,
                'funding_pool_ids': funding_pool_ids,
                'cost_center_ids': cost_center_ids}
        
    def create(self, cr, uid, vals, context=None):
        result = super(financing_contract_format, self).create(cr, uid, vals, context=context)
        if 'cost_center_ids' in vals or 'funding_pool_ids' in vals:
            # Create quadruplets accordingly
            data = self.get_data_for_quadruplets(cr, result)
            quad_obj = self.pool.get('financing.contract.account.quadruplet')
            # for each funding pool, add all quadruplets
            for funding_pool_id in data['funding_pool_ids']:
                for cost_center_id in data['cost_center_ids']:
                    for account_destination_id in data['account_destination_ids']:
                        quad_obj.create(cr, uid,
                                        {'format_id': result,
                                         'account_destination_id': account_destination_id,
                                         'cost_center_id': cost_center_id,
                                         'funding_pool_id': funding_pool_id}, context=context)
        return result
        
    def write(self, cr, uid, ids, vals, context=None):
        # Only for CC; FPs and Accts/Dests are edited in their objects
        if 'cost_center_ids' in vals:
            quad_obj = self.pool.get('financing.contract.account.quadruplet')
            
            # Compare "before" and "after" in order to delete/create quadruplets
            for id in ids:
                data = self.get_data_for_quadruplets(cr, id)
                old_cost_centers = data['cost_center_ids']
                new_cost_centers = vals['cost_center_ids'][0][2]
            
                # create "diffs" for CC and FP
                cc_to_add = [cc_id for cc_id in new_cost_centers if cc_id not in old_cost_centers]
                cc_to_remove = [cc_id for cc_id in old_cost_centers if cc_id not in new_cost_centers]
                # remove quadruplets accordingly
                
                quads_to_delete = quad_obj.search(cr, uid, [('cost_center_id', 'in', cc_to_remove)], context=context)
                quad_obj.unlink(cr, uid, quads_to_delete, context=context)
                # add missing cost center's quadruplets
                for funding_pool_id in data['funding_pool_ids']:
                    for cost_center_id in cc_to_add:
                        for account_destination_id in data['account_destination_ids']:
                            quad_obj.create(cr, uid,
                                            {'format_id': id,
                                             'account_destination_id': account_destination_id,
                                             'cost_center_id': cost_center_id,
                                             'funding_pool_id': funding_pool_id}, context=context)
                            
        return super(financing_contract_format, self).write(cr, uid, ids, vals, context=context)
    
    def unlink(self, cr, uid, ids, context=None):
        # for unlink, simple: remove all lines for that format
        quad_obj = self.pool.get('financing.contract.account.quadruplet')
        quads_to_delete = quad_obj.search(cr, uid, [('format_id', 'in', ids)], context=context)
        quad_obj.unlink(cr, uid, quads_to_delete, context=context)
                            
        return super(financing_contract_format, self).unlink(cr, uid, ids, context=context)

financing_contract_format()

class account_destination_link(osv.osv):
    _name = 'account.destination.link'
    _inherit = 'account.destination.link'

    def _get_used_in_contract(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        if context is None:
            context = {}
        exclude = {}

        if not context.get('contract_id') and not context.get('donor_id'):
            for id in ids:
                res[id] = False
            return res

        if context.get('contract_id'):
            ctr_obj = self.pool.get('financing.contract.contract')
            id_toread = context['contract_id']
        elif context.get('donor_id'):
            ctr_obj = self.pool.get('financing.contract.donor')
            id_toread = context['donor_id']

        exclude = {}
        for line in ctr_obj.browse(cr, uid, id_toread).actual_line_ids:
            if context.get('active_id', False) and line.id != context['active_id']:
                for account_destination in line.account_destination_ids:
                    exclude[account_destination.id] = True
                for account_quadruplet in line.account_quadruplet_ids:
                    exclude[account_quadruplet.account_destination_id.id] = True
        for id in ids:
            res[id] = id in exclude
        return res

    def _search_used_in_contract(self, cr, uid, obj, name, args, context=None):
        if not args:
            return []
        if context is None:
            context = {}
        assert args[0][1] == '=' and args[0][2], 'Filter not implemented'
        if not context.get('contract_id') and not context.get('donor_id'):
            return []

        if context.get('contract_id'):
            ctr_obj = self.pool.get('financing.contract.contract')
            id_toread = context['contract_id']
        elif context.get('donor_id'):
            ctr_obj = self.pool.get('financing.contract.donor')
            id_toread = context['donor_id']

        exclude = {}
        for line in ctr_obj.browse(cr, uid, id_toread).actual_line_ids:
            if context.get('active_id', False) and line.id != context['active_id']:
                for account_destination in line.account_destination_ids:
                    exclude[account_destination.id] = True
                for account_quadruplet in line.account_quadruplet_ids:
                    exclude[account_quadruplet.account_destination_id.id] = True

        return [('id', 'not in', exclude.keys())]

    _columns = {
        'used_in_contract': fields.function(_get_used_in_contract, method=True, type='boolean', string='Used', fnct_search=_search_used_in_contract),
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if context is None:
            context = {}
        if view_type == 'tree' and (context.get('contract_id') or context.get('donor_id')) :
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'financing_contract', 'view_account_destination_link_for_contract_tree')[1]
        return super(account_destination_link, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
    
    def create(self, cr, uid, vals, context=None):
        result = super(account_destination_link, self).create(cr, uid, vals, context=context)
        # Add quadruplets for each format/CC/FP combination
        quad_obj = self.pool.get('financing.contract.account.quadruplet')
        format_obj = self.pool.get('financing.contract.format')
        # get all formats
        cr.execute('''select id from financing_contract_format''')
        format_ids = [x[0] for x in cr.fetchall()]
        for format_id in format_ids:
            data = format_obj.get_data_for_quadruplets(cr, format_id)
            # for each funding pool, add all quadruplets
            for funding_pool_id in data['funding_pool_ids']:
                for cost_center_id in data['cost_center_ids']:
                    quad_obj.create(cr, uid,
                                    {'format_id': format_id,
                                     'account_destination_id': result,
                                     'cost_center_id': cost_center_id,
                                     'funding_pool_id': funding_pool_id}, context=context)
        return result
        
    def write(self, cr, uid, ids, vals, context=None):
        # Nothing to be done, since the id does not change
        return super(account_destination_link, self).write(cr, uid, ids, vals, context=context)
    
    def unlink(self, cr, uid, ids, context=None):
        # for unlink, simple: remove all lines for that account/destination
        quad_obj = self.pool.get('financing.contract.account.quadruplet')
        quads_to_delete = quad_obj.search(cr, uid, [('account_destination_id', 'in', ids)], context=context)
        quad_obj.unlink(cr, uid, quads_to_delete, context=context)
                            
        return super(account_destination_link, self).unlink(cr, uid, ids, context=context)

account_destination_link()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
