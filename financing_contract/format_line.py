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
import pooler
from analytic_distribution.destination_tools import many2many_sorted
from account_override import ACCOUNT_RESTRICTED_AREA



class financing_contract_format_line(osv.osv):
    
    _name = "financing.contract.format.line"
    
    def _create_domain(self, header, element_list):
        domain = "('" + header + "', 'in', ["
        if len(element_list) > 0:
            for element in element_list:
                domain += str(element.id)
                domain += ', '
            domain = domain[:-2]
        domain += "])"
        return domain
    
    def _create_account_destination_domain(self, account_destination_list, general_domain):
        if len(account_destination_list) == 0:
            return ['&',
                    '&',
                    ('general_account_id', 'in', []),
                    ('destination_id', 'in', []),
                    '&',
                    eval(general_domain['cost_center_domain']),
                    eval(general_domain['funding_pool_domain'])]
        elif len(account_destination_list) == 1:
            return ['&',
                    '&',
                    ('general_account_id', '=', account_destination_list[0].account_id.id),
                    ('destination_id', '=', account_destination_list[0].destination_id.id),
                    '&',
                    eval(general_domain['cost_center_domain']),
                    eval(general_domain['funding_pool_domain'])]
        else:
            return ['|'] \
                 + self._create_account_destination_domain([account_destination_list[0]], general_domain) \
                 + self._create_account_destination_domain(account_destination_list[1:], general_domain)
    
    def _create_account_quadruplet_domain(self, account_quadruplet_list, funding_pool_ids):
        if len(account_quadruplet_list) == 0:
            return ['&',
                    '&',
                    ('general_account_id', '=', False),
                    ('destination_id', '=', False),
                    '&',
                    ('cost_center_id', '=', False),
                    ('account_id', '=', False)]
        elif len(account_quadruplet_list) == 1:
            if account_quadruplet_list[0].funding_pool_id.id in funding_pool_ids:
                return ['&',
                        '&',
                        ('general_account_id', '=', account_quadruplet_list[0].account_destination_id.account_id.id),
                        ('destination_id', '=', account_quadruplet_list[0].account_destination_id.destination_id.id),
                        '&',
                        ('cost_center_id', '=', account_quadruplet_list[0].cost_center_id.id),
                        ('account_id', '=', account_quadruplet_list[0].funding_pool_id.id)]
            else:
                return ['&',
                        '&',
                        ('general_account_id', '=', False),
                        ('destination_id', '=', False),
                        '&',
                        ('cost_center_id', '=', False),
                        ('account_id', '=', False)]
        else:
            return ['|'] \
                 + self._create_account_quadruplet_domain([account_quadruplet_list[0]], funding_pool_ids) \
                 + self._create_account_quadruplet_domain(account_quadruplet_list[1:], funding_pool_ids)

    def _get_number_of_childs(self, cr, uid, ids, field_name=None, arg=None, context=None):
        # Verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
                    #account_quadruplet_domain = ['&',('funding_pool_id', 'in', (36,40))]
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = line.child_ids and len(line.child_ids) or 0
        return res
    
    def _get_parent_ids(self, cr, uid, ids, context=None):
        res = []
        for line in self.browse(cr, uid, ids, context=context):
            if line.parent_id:
                res.append(line.parent_id.id)
        return res
    
    def _get_total_costs(self, cr, uid, browse_overhead_line, field_name=None, context=None):
        # since this is only called from the overhead line, the domain is
        # "all children, except the overhead lines"
        result = 0.0
        total_line_ids = [line.id for line in browse_overhead_line.format_id.actual_line_ids if line.line_type in ['actual', 'consumption']]
        total_costs = {}
        if field_name and field_name in ('allocated_budget', 'project_budget'):
            total_costs = self._get_budget_amount(cr, uid, total_line_ids, field_name, context=context)
        else:
            total_costs = self._get_actual_amount(cr, uid, total_line_ids, field_name, context=context)
        for total_cost in total_costs.values():
            result += total_cost
        return result
    
    def _get_account_destination_quadruplets(self, browse_line):
        account_destination_result = []
        account_quadruplet_result = []
        if browse_line.line_type != 'view':
            if browse_line.is_quadruplet:
                account_quadruplet_result = [account_quadruplet for account_quadruplet in browse_line.account_quadruplet_ids]
            else:
                account_destination_result = [account_destination for account_destination in browse_line.account_destination_ids]
        else:
            for child_line in browse_line.child_ids:
                temp = self._get_account_destination_quadruplets(child_line)
                account_destination_result += temp['account_destination_list']
                account_quadruplet_result += temp['account_quadruplet_list']
        return {'account_destination_list': account_destination_result,
                'account_quadruplet_list': account_quadruplet_result}
    
    def _get_general_domain(self, cr, uid, browse_format, domain_type, context=None):
        # Method to get the domain (allocated or project) of a line
        date_domain = "[('document_date', '>=', '"
        date_domain += browse_format.eligibility_from_date
        date_domain += "'), ('document_date', '<=', '"
        date_domain += browse_format.eligibility_to_date
        date_domain += "')]"
        # Funding pools
        funding_pool_ids = []
        if domain_type == 'allocated': 
            funding_pool_ids = [funding_pool_line.funding_pool_id for funding_pool_line in browse_format.funding_pool_ids if funding_pool_line.funded]
        else:
            funding_pool_ids = [funding_pool_line.funding_pool_id for funding_pool_line in browse_format.funding_pool_ids]
        funding_pool_domain = self._create_domain('account_id', funding_pool_ids)
        # Cost centers
        cost_center_domain = self._create_domain('cost_center_id', browse_format.cost_center_ids)
        return {'date_domain': date_domain,
                'funding_pool_domain': funding_pool_domain,
                'cost_center_domain': cost_center_domain,
                'funding_pool_ids': [x.id for x in funding_pool_ids]}
    
    def _get_analytic_domain(self, cr, uid, browse_line, domain_type, context=None):
        if browse_line.line_type in ('consumption', 'overhead'):
            # No domain for those
            return False
        else:
            # last domain: get only non-corrected lines.
            non_corrected_domain = [('is_reallocated', '=', False),
                                    ('is_reversal', '=', False)]
            format = browse_line.format_id
            if format.eligibility_from_date and format.eligibility_to_date:
                general_domain = self._get_general_domain(cr, uid, format, domain_type, context=context)
                # Account + destination domain
                account_destination_quadruplet_ids = self._get_account_destination_quadruplets(browse_line)
                account_destination_domain = self._create_account_destination_domain(account_destination_quadruplet_ids['account_destination_list'], general_domain)
                account_quadruplet_domain = self._create_account_quadruplet_domain(account_destination_quadruplet_ids['account_quadruplet_list'], general_domain['funding_pool_ids'])
                # create the final domain
                date_domain = eval(general_domain['date_domain'])
                return [date_domain[0], date_domain[1]]  + non_corrected_domain + ['|'] + account_destination_domain + account_quadruplet_domain
            else:
                # Dates are not set (since we are probably in a donor).
                # Return False
                return False
    
    def _is_overhead_present(self, cr, uid, ids, context={}):
        for line in self.browse(cr, uid, ids, context=context):
            if line.line_type == 'overhead':
                return True
            elif line.line_type == 'view':
                if self._is_overhead_present(cr, uid, [x.id for x in line.child_ids], context=context):
                    return True
        return False
    
    def _get_actual_line_ids(self, cr, uid, ids, context={}):
        actual_line_ids = []
        for line in self.browse(cr, uid, ids, context=context):
            if line.line_type == 'view':
                actual_line_ids += self._get_actual_line_ids(cr, uid, [x.id for x in line.child_ids], context=context)
            elif line.line_type in ['actual', 'consumption']:
                actual_line_ids.append(line.id)
        return actual_line_ids
    
    def _get_view_amount(self, browse_line, total_costs, retrieved_lines):
        if browse_line.line_type == 'view':
            sum = 0.0
            for child_line in browse_line.child_ids:
                if child_line.id not in retrieved_lines:
                    self._get_view_amount(child_line, total_costs, retrieved_lines)
                sum += retrieved_lines[child_line.id]
            retrieved_lines[browse_line.id] = sum
        elif browse_line.line_type == 'overhead':
            if browse_line.overhead_type == 'cost_percentage':
                # percentage of all costs (sum of all 2nd-level lines, except overhead)
                retrieved_lines[browse_line.id] = round(total_costs * browse_line.overhead_percentage / 100.0)
            elif browse_line.overhead_type == 'grant_percentage':
                # percentage of all costs (sum of all 2nd-level lines, except overhead)
                retrieved_lines[browse_line.id] = round(total_costs * browse_line.overhead_percentage / (100.0 - browse_line.overhead_percentage))
        

    def _get_budget_amount(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
            Method to compute the allocated budget/amounts, depending on the information in the line
        """
        res = {}
        # 1st step: get the real list of actual lines to compute
        actual_line_ids = []
        overhead = self._is_overhead_present(cr, uid, ids, context=context)
        if overhead and len(ids) > 0:
            line_for_format = self.browse(cr, uid, ids[0], context=context)
            actual_line_ids = [line.id for line in line_for_format.format_id.actual_line_ids if line.line_type in ['actual', 'consumption']]
        else:
            actual_line_ids = self._get_actual_line_ids(cr, uid, ids, context=context)
        
        # 2nd step: retrieve values for all actual lines above
        for line in self.browse(cr, uid, actual_line_ids, context=context):
            # default value
            res[line.id] = 0.0
            if line.line_type:
                if line.line_type in ('actual', 'consumption'):
                    # Value is set by the user, just return it
                    if field_name == 'allocated_budget':
                        res[line.id] = line.allocated_budget_value
                    elif field_name == 'project_budget':
                        res[line.id] = line.project_budget_value
                        
        # 3rd step: compute all remaining lines from the retrieved results
        total_budget_costs = 0.0
        if overhead:
            total_budget_costs = sum(res.values())
        for line in self.browse(cr, uid, [id for id in ids if id not in actual_line_ids], context=context):
            if line.id not in res:
                self._get_view_amount(line, total_budget_costs, res)
        
        return res

    def _get_actual_amount(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
            Method to compute the allocated budget/amounts, depending on the information in the line
        """
        res = {}
        # 1st step: get the real list of actual lines to compute
        actual_line_ids = []
        overhead = self._is_overhead_present(cr, uid, ids, context=context)
        if overhead and len(ids) > 0:
            line_for_format = self.browse(cr, uid, ids[0], context=context)
            actual_line_ids = [line.id for line in line_for_format.format_id.actual_line_ids if line.line_type in ['actual', 'consumption']]
        else:
            actual_line_ids = self._get_actual_line_ids(cr, uid, ids, context=context)
        
        # 2nd step: retrieve values for all actual lines above
        for line in self.browse(cr, uid, actual_line_ids, context=context):
            # default value
            res[line.id] = 0.0
            if line.line_type:
                if line.line_type == 'consumption':
                    # Value is set by the user, just return it
                    if field_name == 'allocated_real':
                        res[line.id] = line.allocated_real_value
                    elif field_name == 'project_real':
                        res[line.id] = line.project_real_value
                elif line.line_type == 'actual':
                    # sum of analytic lines, determined by the domain
                    analytic_domain = []
                    if field_name == 'project_real':
                        analytic_domain = self._get_analytic_domain(cr, uid, line, 'project', context=context)
                    elif field_name == 'allocated_real':
                        analytic_domain = self._get_analytic_domain(cr, uid, line, 'allocated', context=context)
                    # selection of analytic lines
                    if 'reporting_currency' in context:
                        analytic_line_obj = self.pool.get('account.analytic.line')
                        analytic_lines = analytic_line_obj.search(cr, uid, analytic_domain ,context=context)
                        real_sum = 0.0
                        currency_table = None
                        if 'currency_table_id' in context:
                            currency_table = context['currency_table_id']
                        for analytic_line in analytic_line_obj.browse(cr, uid, analytic_lines, context=context):
                            date_context = {'date': analytic_line.document_date,
                                            'currency_table_id': currency_table}
                            real_sum += self.pool.get('res.currency').compute(cr,
                                                                              uid,
                                                                              analytic_line.currency_id.id,
                                                                              context['reporting_currency'], 
                                                                              analytic_line.amount_currency or 0.0,
                                                                              round=False,
                                                                              context=date_context)
                        # Invert the result from the lines (positive for out, negative for in)
                        real_sum = -real_sum
                        res[line.id] = real_sum
                        
        # 3rd step: compute all remaining lines from the retrieved results
        total_actual_costs = 0.0
        if overhead:
            total_actual_costs = sum(res.values())
        for line in self.browse(cr, uid, [id for id in ids if id not in actual_line_ids], context=context):
            if line.id not in res:
                self._get_view_amount(line, total_actual_costs, res)
        
        return res


    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'code': fields.char('Code', size=16, required=True),
        'format_id': fields.many2one('financing.contract.format', 'Format'),
        'is_quadruplet': fields.boolean('Input CC/FP at line level?'),
        'account_destination_ids': many2many_sorted('account.destination.link', 'financing_contract_actual_account_destinations', 'actual_line_id', 'account_destination_id', string='Accounts/Destinations', domain=ACCOUNT_RESTRICTED_AREA['contract_reporting_lines']),
        'parent_id': fields.many2one('financing.contract.format.line', 'Parent line'),
        'child_ids': fields.one2many('financing.contract.format.line', 'parent_id', 'Child lines'),
        'line_type': fields.selection([('view','View'),
                                       ('actual','Actual'),
                                       ('consumption','Consumption'),
                                       ('overhead','Overhead')], 'Line type', required=True),
        'overhead_type': fields.selection([('cost_percentage','Percentage of direct costs'),
                                           ('grant_percentage','Percentage of grant')], 'Overhead calculation mode'),
        'allocated_budget_value': fields.float('Budget allocated amount (value)'),
        'project_budget_value': fields.float('Budget project amount (value)'),
        'allocated_real_value': fields.float('Real allocated amount (value)'),
        'project_real_value': fields.float('Real project amount (value)'),
        'overhead_percentage': fields.float('Overhead percentage'),

        'allocated_budget': fields.function(_get_budget_amount, method=True, store=False, string="Funded - Budget", type="float", readonly=True),
        'project_budget': fields.function(_get_budget_amount, method=True, store=False, string="Total project - Budget", type="float", readonly=True),

        'allocated_real': fields.function(_get_actual_amount, method=True, store=False, string="Funded - Actuals", type="float", readonly=True),
        'project_real': fields.function(_get_actual_amount, method=True, store=False, string="Total project - Actuals", type="float", readonly=True),
        'quadruplet_update': fields.char('Internal Use Only', size=128),
    }
 
    
    
    _defaults = {
        'is_quadruplet': False,
        'line_type': 'actual',
        'overhead_type': 'cost_percentage',
        'parent_id': lambda *a: False
    }

    _order = 'code asc'
 
    def create(self, cr, uid, vals, context=None):
        if not context:
            context = {}
        
        # if the account is set as view, remove budget and account values
        quads_list = []
        if 'line_type' in vals and vals['line_type'] == 'view':
            vals['allocated_amount'] = 0.0
            vals['project_amount'] = 0.0
            vals['account_destination_ids'] = []
            vals['account_quadruplet_ids'] = []
        else: 
            if vals.get('is_quadruplet', False):
                # delete account/destinations
                vals['account_destination_ids'] = []
                if context.get('sync_update_execution'):
                    quads_list = []
                    if vals.get('quadruplet_update', False):
                        quadrup_str = vals['quadruplet_update']
                        quads_list = map(int, quadrup_str.split(','))
                    vals['account_quadruplet_ids'] =[(6, 0, quads_list)]
                else:
                    temp = vals['account_quadruplet_ids']
                    if temp[0]: 
                        vals['quadruplet_update'] = str(temp[0][2]).strip('[]')
            else:
                # delete quadruplets
                vals['account_quadruplet_ids'] = []
                vals['quadruplet_update'] = ''
                
        return super(financing_contract_format_line, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        # if the account is set as view, remove budget and account values
        if 'line_type' in vals and vals['line_type'] == 'view':
            vals['allocated_amount'] = 0.0
            vals['project_amount'] = 0.0
            vals['account_destination_ids'] = [(6, 0, [])]
            vals['account_quadruplet_ids'] = [(6, 0, [])]
        else: 
            if vals.get('is_quadruplet', False):
                # delete account/destinations
                vals['account_destination_ids'] = []
                if context.get('sync_update_execution'):
                    quads_list = []
                    if vals.get('quadruplet_update', False):
                        quadrup_str = vals['quadruplet_update']
                        quads_list = map(int, quadrup_str.split(','))
                    vals['account_quadruplet_ids'] =[(6, 0, quads_list)]
                else:
                    temp = vals['account_quadruplet_ids']
                    if temp[0]: 
                        vals['quadruplet_update'] = str(temp[0][2]).strip('[]')
                # delete previous account/destinations
                vals['account_destination_ids'] = [(6, 0, [])]
            else:
                # delete quadruplets
                vals['account_quadruplet_ids'] = [(6, 0, [])]
                vals['quadruplet_update'] = ''
                
        return super(financing_contract_format_line, self).write(cr, uid, ids, vals, context=context)
    
    def copy_format_line(self, cr, uid, browse_source_line, destination_format_id, parent_id=None, context=None):
        if destination_format_id:
            format_line_vals = {
                'name': browse_source_line.name,
                'code': browse_source_line.code,
                'format_id': destination_format_id,
                'parent_id': parent_id,
                'line_type': browse_source_line.line_type,
                'account_quadruplet_ids': [(6, 0, [])],
            }
            account_destination_ids = [account_destination.id for account_destination in browse_source_line.account_destination_ids]
            format_line_vals['account_destination_ids'] = [(6, 0, account_destination_ids)]
            parent_line_id = self.pool.get('financing.contract.format.line').create(cr, uid, format_line_vals, context=context)
            for child_line in browse_source_line.child_ids:
                self.copy_format_line(cr, uid, child_line, destination_format_id, parent_line_id, context=context)
        return
            
financing_contract_format_line()

class financing_contract_format(osv.osv):
    
    _name = "financing.contract.format"
    _inherit = "financing.contract.format"
    
    _columns = {
        'actual_line_ids': fields.one2many('financing.contract.format.line', 'format_id', 'Actual lines')
    }
    
    def copy_format_lines(self, cr, uid, source_id, destination_id, context=None):
        # remove all old report lines
        destination_obj = self.browse(cr, uid, destination_id, context=context)
        for to_remove_line in destination_obj.actual_line_ids:
            self.pool.get('financing.contract.format.line').unlink(cr, uid, to_remove_line.id, context=context)
        source_obj = self.browse(cr, uid, source_id, context=context)
        # Method to copy a format
        # copy format lines
        for source_line in source_obj.actual_line_ids:
            if not source_line.parent_id:
                self.pool.get('financing.contract.format.line').copy_format_line(cr,
                                                                                 uid,
                                                                                 source_line,
                                                                                 destination_id,
                                                                                 parent_id=None,
                                                                                 context=context)
        return
        
financing_contract_format()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
