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

class financing_contract_contract(osv.osv):
    
    _name = "financing.contract.contract"
    _inherits = {"financing.contract.format": "format_id"}
    
    def _create_parent_line(self, cr, uid, contract_id, context=None):
        # create parent reporting line (representing the contract in the tree view)
        report_line_obj = self.pool.get('financing.contract.donor.reporting.line')
        contract = self.browse(cr, uid, contract_id, context=context)
        if contract.report_line:
            # delete existing parent reporting line (representing the contract in the tree view)
            report_line_obj.unlink(cr, uid, contract.report_line.id, context=context)
        parent_line_id = False
        vals = {}
        general_information = self._get_general_information(cr, uid, contract, context=context)
        if contract.name and contract.code and contract.reporting_type:
            parent_line_vals = {
                'name': contract.name,
                'code': contract.code,
                'date_domain': general_information['date_domain'],
                'funding_pool_domain': general_information['funding_pool_domain'],
                'cost_center_domain': general_information['cost_center_domain'],
                'computation_type': 'children_sum',
            }
            vals['report_line'] = report_line_obj.create(cr, uid, parent_line_vals, context=context)
        super(financing_contract_contract, self).write(cr, uid, contract_id, vals, context=context)
        return
    
    def _get_general_information(self, cr, uid, browse_contract, context=None):
        # common part of the analytic domain
        date_domain = "[('date', '>=', '"
        date_domain += browse_contract.eligibility_from_date
        date_domain += "'), ('date', '<=', '"
        date_domain += browse_contract.eligibility_to_date
        date_domain += "')]"
        funding_pool_domain = "('account_id', 'in', ["
        # list of expense accounts in the funding pools.
        # Unicity is not important, it's just for a future comparison
        funding_pool_account_ids = []
        # list of cost centers in the funding pools.
        # Unicity is important
        cost_center_ids = []
        if len(browse_contract.funding_pool_ids) > 0:
            for funding_pool in browse_contract.funding_pool_ids:
                funding_pool_domain += str(funding_pool.id)
                funding_pool_domain += ", "
                for account in funding_pool.account_ids:
                    funding_pool_account_ids.append(account.id)
                if len(funding_pool.cost_center_ids) > 0:
                    for cost_center in funding_pool.cost_center_ids:
                        cost_center_ids.append(cost_center.id)
            funding_pool_domain = funding_pool_domain[:-2]
        funding_pool_domain += "])"
        cost_center_domain = "('cost_center_id', 'in', ["
        if len(cost_center_ids) > 0:
            cost_center_set = set(cost_center_ids)
            for cost_center_id in cost_center_set:
                cost_center_domain += str(cost_center_id)
                cost_center_domain += ', '
            cost_center_domain = cost_center_domain[:-2]
        cost_center_domain += "])"
        return {'date_domain': date_domain,
                'funding_pool_domain': funding_pool_domain,
                'cost_center_domain': cost_center_domain,
                'account_ids': funding_pool_account_ids}
    
    def _create_actual_reporting_line(self, cr, uid, browse_actual_line, general_information, parent_line_id=False, context=None):
        report_line_obj = self.pool.get('financing.contract.donor.reporting.line')
        if general_information \
           and 'date_domain' in general_information \
           and 'funding_pool_domain' in general_information \
           and 'cost_center_domain' in general_information \
           and 'account_ids' in general_information:
            line_vals = {
                'name': browse_actual_line.name,
                'code': browse_actual_line.code,
                'parent_id': parent_line_id,
                'date_domain': general_information['date_domain'],
                'funding_pool_domain': general_information['funding_pool_domain'],
                'cost_center_domain': general_information['cost_center_domain'],
            }
            if browse_actual_line.line_type == 'view':
                # view lines have no information, they take it from their children
                line_vals['computation_type'] = 'children_sum'
            elif browse_actual_line.line_type == 'normal':
                # normal actual lines retrieve their amounts from the analytic lines
                line_vals['computation_type'] = 'analytic_sum'
                line_vals['allocated_budget_value'] = browse_actual_line.allocated_amount
                line_vals['project_budget_value'] = browse_actual_line.project_amount
                # compute domain from accounts
                account_ids = [account.id for account in browse_actual_line.account_ids if account.id in general_information['account_ids']]
                account_domain = "('general_account_id', 'in', ["
                if len(account_ids) > 0:
                    for account_id in account_ids:
                        account_domain += str(account_id)
                        account_domain += ", "
                    account_domain = account_domain[:-2]
                account_domain += "])"
                line_vals['account_domain'] = account_domain
            new_line_id = report_line_obj.create(cr, uid, line_vals, context=context)
            # create children, and retrieve their list of accounts
            for child_line in browse_actual_line.child_ids:
                self._create_actual_reporting_line(cr, uid, child_line, general_information, new_line_id, context=context)
        return
    
    def _create_actual_lines(self, cr, uid, contract_id, context=None):
        contract = self.browse(cr, uid, contract_id, context=context)
        if contract.report_line:
            # retrieve parent reporting line
            parent_line_id = contract.report_line.id
            # common part of the analytic domain
            general_information = self._get_general_information(cr, uid, contract, context=context)
            for line in contract.actual_line_ids:
                if not line.parent_id:
                    # "top" actual lines; the other are created recursively
                    self._create_actual_reporting_line(cr, uid, line, general_information, parent_line_id, context=context)   
        return
    
    def _create_nonactual_lines(self, cr, uid, contract_id, context=None):
        contract = self.browse(cr, uid, contract_id, context=context)
        report_line_obj = self.pool.get('financing.contract.donor.reporting.line')
        if contract.report_line:
            # retrieve parent reporting line
            parent_line_id = contract.report_line.id
            # create overhead line
            overhead_line_vals = {}
            if contract.overhead_type != 'amount' and contract.overhead_percentage > 0.0:
                # create overhead line
                overhead_line_vals = {
                    'name': 'Overheads',
                    'code': 'OH',
                    'parent_id': parent_line_id,
                    'computation_type': contract.overhead_type,
                    'overhead_percentage': contract.overhead_percentage,
                }
                report_line_obj.create(cr, uid, overhead_line_vals, context=context)
            elif contract.budget_allocated_overhead > 0.0 \
              or contract.budget_project_overhead > 0.0 \
              or contract.allocated_overhead > 0.0 \
              or contract.project_overhead > 0.0:
                overhead_line_vals = {
                    'name': 'Overheads',
                    'code': 'OH',
                    'parent_id': parent_line_id,
                    'computation_type': contract.overhead_type,
                    'allocated_budget_value': contract.budget_allocated_overhead,
                    'project_budget_value': contract.budget_project_overhead,
                    'allocated_real_value': contract.allocated_overhead,
                    'project_real_value': contract.project_overhead,
                }
                report_line_obj.create(cr, uid, overhead_line_vals, context=context)
            # Lump sum line
            if contract.budget_allocated_lump_sum > 0.0 \
              or contract.budget_project_lump_sum > 0.0 \
              or contract.allocated_lump_sum > 0.0 \
              or contract.project_lump_sum > 0.0:
                lump_sum_line_vals = {
                    'name': 'Lump sum',
                    'code': 'LS',
                    'parent_id': parent_line_id,
                    'computation_type': 'amount',
                    'allocated_budget_value': contract.budget_allocated_lump_sum,
                    'project_budget_value': contract.budget_project_lump_sum,
                    'allocated_real_value': contract.allocated_lump_sum,
                    'project_real_value': contract.project_lump_sum,
                }
                report_line_obj.create(cr, uid, lump_sum_line_vals, context=context)
            # Consumption line
            if contract.budget_allocated_consumption > 0.0 \
              or contract.budget_project_consumption > 0.0 \
              or contract.allocated_consumption > 0.0 \
              or contract.project_consumption > 0.0:
                consumption_line_vals = {
                    'name': 'Consumption',
                    'code': 'CSP',
                    'parent_id': parent_line_id,
                    'computation_type': 'amount',
                    'allocated_budget_value': contract.budget_allocated_consumption,
                    'project_budget_value': contract.budget_project_consumption,
                    'allocated_real_value': contract.allocated_consumption,
                    'project_real_value': contract.project_consumption,
                }
                report_line_obj.create(cr, uid, consumption_line_vals, context=context)
        return
    
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'code': fields.char('Code', size=16, required=True),
        'donor_id': fields.many2one('financing.contract.donor', 'Donor', required=True),
        'grant_name': fields.char('Grant name', size=64, required=True),
        'donor_grant_reference': fields.char('Donor grant reference', size=64),
        'hq_grant_reference': fields.char('HQ grant reference', size=64),
        'contract_type': fields.selection([('', ''), ('ear_marked','Ear-marked'), ('global_contribution','Global Contribution')], 'Financing contract type', required=True),
        'eligibility_from_date': fields.date('Eligibility date from', required=True),
        'eligibility_to_date': fields.date('Eligibility date to', required=True),
        'grant_amount': fields.float('Grant amount', size=64, required=True),
        'reporting_currency': fields.many2one('res.currency', 'Reporting currency', required=True),
        'notes': fields.text('Notes'),
        'funding_pool_ids': fields.many2many('account.analytic.account', 'financing_contract_funding_pool', 'contract_id', 'funding_pool_id', string='Funding Pools'),
        'open_date': fields.date('Open date'),
        'soft_closed_date': fields.date('Soft-closed date'),
        'hard_closed_date': fields.date('Hard-closed date'),
        'state': fields.selection([('draft','Draft'),
                                    ('open','Open'),
                                    ('soft_closed', 'Soft-closed'),
                                    ('hard_closed', 'Hard-closed')], 'State'),
        'report_line': fields.many2one('financing.contract.donor.reporting.line', 'Parent Report Line')
    }
    
    _defaults = {
        'state': 'draft',
        'reporting_currency': lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
        'format_id': lambda self,cr,uid,context: self.pool.get('financing.contract.format').create(cr, uid, {}, context=context)
    }
    
    def onchange_donor_id(self, cr, uid, ids, donor_id, format_id, actual_line_ids, context={}):
        res = {}
        if donor_id and format_id:
            donor = self.pool.get('financing.contract.donor').browse(cr, uid, donor_id, context=context)
            if donor.format_id:
                source_format = donor.format_id
                format_vals = {
                    'format_name': source_format.format_name,
                    'reporting_type': source_format.reporting_type,
                    'overhead_type': source_format.overhead_type,
                    'overhead_percentage': source_format.overhead_percentage,
                }
                self.pool.get('financing.contract.format').copy_format_lines(cr, uid, donor.format_id.id, format_id, context=context)
        return {'value': format_vals}
    
    def create(self, cr, uid, vals, context=None):
        if not context:
            context={}
        contract_id = super(financing_contract_contract, self).create(cr, uid, vals, context=context)
        # write actual lines
        self._create_parent_line(cr, uid, contract_id, context=context)
        self._create_actual_lines(cr, uid, contract_id, context=context)
        self._create_nonactual_lines(cr, uid, contract_id, context=context)
        return contract_id
    
    def write(self, cr, uid, ids, vals, context=None):
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]
        result = super(financing_contract_contract, self).write(cr, uid, ids, vals, context=context)
        for contract in self.browse(cr, uid, ids, context=context):
            # delete existing parent reporting line (representing the contract in the tree view)
            self._create_parent_line(cr, uid, contract.id, context=context)
            self._create_actual_lines(cr, uid, contract.id, context=context)
            self._create_nonactual_lines(cr, uid, contract.id, context=context)
        return result
    
    def unlink(self, cr, uid, ids, context=None):
        if not context:
            context={}
        report_line_obj = self.pool.get('financing.contract.donor.reporting.line')
        for contract in self.browse(cr, uid, ids, context=context):
            # delete existing parent reporting line (representing the contract in the tree view)
            report_line_obj.unlink(cr, uid, contract.report_line.id, context=context)
        return super(financing_contract_contract, self).unlink(cr, uid, ids, context=context)
    
    
financing_contract_contract()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
