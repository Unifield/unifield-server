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
import datetime

class financing_contract_funding_pool_line(osv.osv):
    # 
    _name = "financing.contract.funding.pool.line"
    
    _columns = {
        'contract_id': fields.many2one('financing.contract.format', 'Contract', required=True),
        'funding_pool_id': fields.many2one('account.analytic.account', 'Funding pool name', required=True),
        'funded': fields.boolean('Funded'),
        'total_project': fields.boolean('Total project'),
    }
        
    _defaults = {
        'funded': False,
        'total_project': True,
    }
    
financing_contract_funding_pool_line()

class financing_contract_contract(osv.osv):
    
    _name = "financing.contract.contract"
    _inherits = {"financing.contract.format": "format_id"}

    def contract_open(self, cr, uid, ids, *args):
        self.write(cr, uid, ids, {
            'state': 'open',
            'open_date': datetime.date.today().strftime('%Y-%m-%d'),
            'soft_closed_date': None
        })
        return True

    def contract_soft_closed(self, cr, uid, ids, *args):
        self.write(cr, uid, ids, {
            'state': 'soft_closed',
            'soft_closed_date': datetime.date.today().strftime('%Y-%m-%d')
        })
        return True

    def contract_hard_closed(self, cr, uid, ids, *args):
        self.write(cr, uid, ids, {
            'state': 'hard_closed',
            'hard_closed_date': datetime.date.today().strftime('%Y-%m-%d')
        })
        return True
    
    _columns = {
        'name': fields.char('Financing contract name', size=64, required=True),
        'code': fields.char('Financing contract code', size=16, required=True),
        'donor_id': fields.many2one('financing.contract.donor', 'Donor', required=True),
        'donor_grant_reference': fields.char('Donor grant reference', size=64),
        'hq_grant_reference': fields.char('HQ grant reference', size=64),
        'eligibility_from_date': fields.date('Eligibility date from'),
        'eligibility_to_date': fields.date('Eligibility date to'),
        'grant_amount': fields.float('Grant amount', size=64, required=True),
        'reporting_currency': fields.many2one('res.currency', 'Reporting currency', required=True),
        'notes': fields.text('Notes'),
        'open_date': fields.date('Open date'),
        'soft_closed_date': fields.date('Soft-closed date'),
        'hard_closed_date': fields.date('Hard-closed date'),
        'state': fields.selection([('draft','Draft'),
                                    ('open','Open'),
                                    ('soft_closed', 'Soft-closed'),
                                    ('hard_closed', 'Hard-closed')], 'State'),
        'currency_table_id': fields.many2one('res.currency.table', 'Currency Table')
    }
    
    _defaults = {
        'state': 'draft',
        'reporting_currency': lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
        'format_id': lambda self,cr,uid,context: self.pool.get('financing.contract.format').create(cr, uid, {}, context=context)
    }

    def _check_unicity(self, cr, uid, ids, context={}):
        if not context:
            context={}
        for contract in self.browse(cr, uid, ids, context=context):
            bad_ids = self.search(cr, uid, [('|'),('name', '=ilike', contract.name),('code', '=ilike', contract.code)])
            if len(bad_ids) and len(bad_ids) > 1:
                return False
        return True

    _constraints = [
        (_check_unicity, 'You cannot have the same code or name between contracts!', ['code', 'name']),
    ]

    def copy(self, cr, uid, id, default={}, context=None, done_list=[], local=False):
        contract = self.browse(cr, uid, id, context=context)
        if not default:
            default = {}
        default = default.copy()
        default['code'] = (contract['code'] or '') + '(copy)'
        default['name'] = (contract['name'] or '') + '(copy)'
        return super(financing_contract_contract, self).copy(cr, uid, id, default, context=context)
    
    def onchange_donor_id(self, cr, uid, ids, donor_id, format_id, actual_line_ids, context={}):
        res = {}
        if donor_id and format_id:
            donor = self.pool.get('financing.contract.donor').browse(cr, uid, donor_id, context=context)
            if donor.format_id:
                source_format = donor.format_id
                format_vals = {
                    'format_name': source_format.format_name,
                    'reporting_type': source_format.reporting_type,
                }
                self.pool.get('financing.contract.format').copy_format_lines(cr, uid, donor.format_id.id, format_id, context=context)
        return {'value': format_vals}
    
    def onchange_currency_table(self, cr, uid, ids, currency_table_id, reporting_currency_id, context={}):
        values = {'reporting_currency': False}
        if reporting_currency_id:
            # it can be a currency from another table
            reporting_currency = self.pool.get('res.currency').browse(cr, uid, reporting_currency_id, context=context)
            # Search if the currency is in the table, and active
            if reporting_currency.reference_currency_id:
                currency_results = self.pool.get('res.currency').search(cr, uid, [('reference_currency_id', '=', reporting_currency.reference_currency_id.id),
                                                                                  ('currency_table_id', '=', currency_table_id),
                                                                                  ('active', '=', True)], context=context)
            else:
                currency_results = self.pool.get('res.currency').search(cr, uid, [('reference_currency_id', '=', reporting_currency_id),
                                                                                  ('currency_table_id', '=', currency_table_id),
                                                                                  ('active', '=', True)], context=context)
            if len(currency_results) > 0:
                # it's here, we keep the currency
                values['reporting_currency'] = reporting_currency_id
        # Restrain domain to selected table (or None if none selected
        domains = {'reporting_currency': [('currency_table_id', '=', currency_table_id)]}
        return {'value': values, 'domain': domains}
    
    def create_reporting_line(self, cr, uid, browse_contract, browse_format_line, parent_report_line_id=None, context=None):
        format_line_obj = self.pool.get('financing.contract.format.line')
        reporting_line_obj = self.pool.get('financing.contract.donor.reporting.line')
        analytic_domain = format_line_obj._get_analytic_domain(cr,
                                                               uid,
                                                               browse_format_line,
                                                               browse_contract.reporting_type,
                                                               context=context)
        vals = {'name': browse_format_line.name,
                'code': browse_format_line.code,
                'allocated_budget': round(browse_format_line.allocated_budget),
                'project_budget': round(browse_format_line.project_budget),
                'allocated_real': round(browse_format_line.allocated_real),
                'project_real': round(browse_format_line.project_real),
                'analytic_domain': analytic_domain,
                'parent_id': parent_report_line_id}
        reporting_line_id = reporting_line_obj.create(cr,
                                                      uid,
                                                      vals,
                                                      context=context)
        # create child lines
        for child_line in browse_format_line.child_ids:
            self.create_reporting_line(cr, uid, browse_contract, child_line, reporting_line_id, context=context)
        return reporting_line_id
            
    
    def menu_interactive_report(self, cr, uid, ids, context={}):
        # we update the context with the contract reporting type
        contract = self.browse(cr, uid, ids[0], context=context)
        context.update({'reporting_currency': contract.reporting_currency.id,
                        'reporting_type': contract.reporting_type,
                        'currency_table_id': contract.currency_table_id.id,
                        'active_id': ids[0],
                        'active_ids': ids})
        reporting_line_obj = self.pool.get('financing.contract.donor.reporting.line')
        format_line_obj = self.pool.get('financing.contract.format.line')
        # Create reporting lines
        # Contract line first (we'll fill it later)
        contract_line_id = reporting_line_obj.create(cr,
                                                     uid,
                                                     vals = {'name': contract.name,
                                                             'code': contract.code},
                                                     context=context)
        # Then the main reporting ones (we keep values for later)
        contract_account_ids = []
        contract_allocated_budget = 0
        contract_project_budget = 0
        contract_allocated_real = 0
        contract_project_real = 0
        contract_general_domain = format_line_obj._get_general_domain(cr,
                                                                      uid,
                                                                      contract.format_id,
                                                                      contract.reporting_type,
                                                                      context=context)
        for line in contract.actual_line_ids:
            if not line.parent_id:
                reporting_line_id = self.create_reporting_line(cr, uid, contract, line, contract_line_id, context=context)
                contract_allocated_budget += line.allocated_budget
                contract_project_budget += line.project_budget
                contract_allocated_real += line.allocated_real
                contract_project_real += line.project_real
                contract_account_ids += format_line_obj._get_account_ids(line, contract_general_domain['funding_pool_account_ids'])
        # create the final domain
        contract_analytic_domain = []
        contract_account_domain = format_line_obj._create_domain('general_account_id', contract_account_ids)
        contract_date_domain = eval(contract_general_domain['date_domain'])
        if contract.reporting_type == 'allocated':
            contract_analytic_domain = [contract_date_domain[0],
                                        contract_date_domain[1],
                                        eval(contract_account_domain),
                                        eval(contract_general_domain['funding_pool_domain'])]
        else: 
            contract_analytic_domain = [contract_date_domain[0],
                                        contract_date_domain[1],
                                        eval(contract_account_domain),
                                        eval(contract_general_domain['funding_pool_domain']),
                                        eval(contract_general_domain['cost_center_domain'])]
        # Refresh contract line with infos
        reporting_line_obj.write(cr, uid, [contract_line_id], vals={'allocated_budget': contract_allocated_budget,
                                                                    'project_budget': contract_project_budget,
                                                                    'allocated_real': contract_allocated_real,
                                                                    'project_real': contract_project_real,
                                                                    'analytic_domain': contract_analytic_domain}, context = context)
        model_data_obj = self.pool.get('ir.model.data')
        # retrieve the corresponding_view
        view_id = False
        view_ids = model_data_obj.search(cr, uid, 
                                        [('module', '=', 'financing_contract'), 
                                         ('name', '=', 'view_donor_reporting_line_tree_%s' % str(contract.reporting_type))],
                                        offset=0, limit=1)
        if len(view_ids) > 0:
            view_id = model_data_obj.browse(cr, uid, view_ids[0]).res_id
        return {
               'type': 'ir.actions.act_window',
               'res_model': 'financing.contract.donor.reporting.line',
               'view_type': 'tree',
               'view_id': [view_id],
               'target': 'current',
               'domain': [('id', '=', contract_line_id)],
               'context': context
        }
    
financing_contract_contract()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
