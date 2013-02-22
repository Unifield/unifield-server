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
import datetime
from osv import fields, osv
from tools.translate import _

class financing_contract_funding_pool_line(osv.osv):
    # 
    _name = "financing.contract.funding.pool.line"
    _description = "Funding pool line"
    
    _columns = {
        'contract_id': fields.many2one('financing.contract.format', 'Contract', required=True),
        'funding_pool_id': fields.many2one('account.analytic.account', 'Funding pool name', required=True),
        'funded': fields.boolean('Earmarked'),
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
    _trace = True

    def contract_open(self, cr, uid, ids, *args):
        self.write(cr, uid, ids, {
            'state': 'open',
            'open_date': datetime.date.today().strftime('%Y-%m-%d'),
            'soft_closed_date': None
        })
        return True

    def search_draft_or_temp_posted_register_lines(self, cr, uid, ids, context=None):
        """
        Search all draft/temp posted register lines that have an analytic distribution in which funding pool lines have an analytic account set to those given in contract.
        """
        res = []
        for c in self.browse(cr, uid, ids):
            # Create domain to find analytic lines
            domain = []
            for actual in c.actual_line_ids:
                domain += self.pool.get('financing.contract.format.line')._get_analytic_domain(cr, uid, actual, 'allocated_real')
            # Find analytic lines
            al_ids = self.pool.get('account.analytic.line').search(cr, uid, domain)
            move_ids = [x.get('move_id')[0] for x in self.pool.get('account.analytic.line').read(cr, uid, al_ids, ['move_id']) if x.get('move_id')]
            # Search statement lines that are draft/temp and which have a move id compatible
            absl_ids = self.pool.get('account.bank.statement.line').search(cr, uid, [('state', '=', 'temp'), ('move_ids', 'in', move_ids)])
            if absl_ids:
                res = absl_ids
            # Search draft posted statement lines
            fp_ids = [x and x.funding_pool_id and x.funding_pool_id.id for x in c.funding_pool_ids]
            sql = """SELECT absl.id
            FROM account_bank_statement_line AS absl, funding_pool_distribution_line AS fp
            WHERE distribution_id = analytic_distribution_id
            AND fp.analytic_id in %s
            AND absl.id in (
                SELECT st.id
                FROM account_bank_statement_line st
                    LEFT JOIN account_bank_statement_line_move_rel rel ON rel.move_id = st.id
                    LEFT JOIN account_move am ON am.id = rel.statement_id
                WHERE (rel.statement_id is null OR am.state != 'posted')
                ORDER BY st.id
            ) ORDER BY absl.id"""
            cr.execute(sql, (tuple(fp_ids),))
            sql_res = cr.fetchall()
            if sql_res:
                res += [x and x[0] for x in sql_res]
        return res

    def contract_soft_closed(self, cr, uid, ids, *args):
        """
        If some draft/temp posted register lines that have an analytic distribution in which funding pool lines have an analytic account set to those given in contract, then raise an error.
        Otherwise set contract as soft closed.
        """
        # Search draft/temp posted register lines
        reg_lines = self.search_draft_or_temp_posted_register_lines(cr, uid, ids)
        if reg_lines:
            msg= ''
            for i, st in enumerate(self.pool.get('account.bank.statement.line').browse(cr, uid, reg_lines)):
                if i > 0:
                    msg += ' - '
                msg += (st.name or '') + (st.statement_id and st.statement_id.name and (' in (' + st.statement_id.name + ')') or '')
            raise osv.except_osv(_('Error'), _("Some register lines linked to contract's funding pools are not hard posted: %s") % (msg,))
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
    
    def get_contract_domain(self, cr, uid, browse_contract, reporting_type=None, context=None):
        # we update the context with the contract reporting type and currency
        format_line_obj = self.pool.get('financing.contract.format.line')
        # Values to be set
        account_destination_ids = []
        if reporting_type is None:
            reporting_type = browse_contract.reporting_type
        # general domain
        general_domain = format_line_obj._get_general_domain(cr,
                                                             uid,
                                                             browse_contract.format_id,
                                                             reporting_type,
                                                             context=context)
        
        # parse parent lines (either value or sum of children's values)
        for line in browse_contract.actual_line_ids:
            if not line.parent_id:
                account_destination_ids += format_line_obj._get_account_destination_ids(line, general_domain['funding_pool_account_destination_ids'])
                
        # create the domain
        analytic_domain = []
        account_domain = format_line_obj._create_account_destination_domain(account_destination_ids)
        date_domain = eval(general_domain['date_domain'])
        if reporting_type == 'allocated':
            analytic_domain = [date_domain[0],
                               date_domain[1],
                               ('is_reallocated', '=', False),
                               ('is_reversal', '=', False),
                               eval(general_domain['funding_pool_domain'])]
        else: 
            analytic_domain = [date_domain[0],
                               date_domain[1],
                               ('is_reallocated', '=', False),
                               ('is_reversal', '=', False),
                               eval(general_domain['funding_pool_domain']),
                               eval(general_domain['cost_center_domain'])]
        analytic_domain += account_domain
            
        return analytic_domain

    def _get_overhead_amount(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
            Method to compute the overhead amount
        """
        res = {}
        for budget in self.browse(cr, uid, ids, context=context):
            # default value
            res[budget.id] = 0.0
            if budget.overhead_type == 'cost_percentage':
                res[budget.id] = round(budget.grant_amount * budget.overhead_percentage / (100.0 + budget.overhead_percentage))
            elif budget.overhead_type == 'grant_percentage':
                res[budget.id] = round(budget.grant_amount * budget.overhead_percentage / 100.0)
        return res
    
    _columns = {
        'name': fields.char('Financing contract name', size=64, required=True),
        'code': fields.char('Financing contract code', size=16, required=True),
        'donor_id': fields.many2one('financing.contract.donor', 'Donor', required=True),
        'donor_grant_reference': fields.char('Donor grant reference', size=64),
        'hq_grant_reference': fields.char('HQ grant reference', size=64),
        'grant_amount': fields.float('Grant amount', required=True),
        'overhead_amount': fields.function(_get_overhead_amount, method=True, store=False, string="Overhead amount", type="float", readonly=True),
        'reporting_currency': fields.many2one('res.currency', 'Reporting currency', required=True),
        'notes': fields.text('Notes'),
        'open_date': fields.date('Open date'),
        'soft_closed_date': fields.date('Soft-closed date'),
        'hard_closed_date': fields.date('Hard-closed date'),
        'state': fields.selection([('draft','Draft'),
                                    ('open','Open'),
                                    ('soft_closed', 'Soft-closed'),
                                    ('hard_closed', 'Hard-closed')], 'State'),
        'currency_table_id': fields.many2one('res.currency.table', 'Currency Table'),
        # Define for _inherits
        'format_id': fields.many2one('financing.contract.format', 'Format', ondelete="cascade", required=True),
    }
    
    _defaults = {
        'state': 'draft',
        'reporting_currency': lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
        'format_id': lambda self,cr,uid,context: self.pool.get('financing.contract.format').create(cr, uid, {}, context=context)
    }

    def _check_unicity(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        for contract in self.browse(cr, uid, ids, context=context):
            bad_ids = self.search(cr, uid, [('|'),('name', '=ilike', contract.name),('code', '=ilike', contract.code)])
            if len(bad_ids) and len(bad_ids) > 1:
                return False
        return True

    _constraints = [
        (_check_unicity, 'You cannot have the same code or name between contracts!', ['code', 'name']),
    ]

    def copy(self, cr, uid, id, default=None, context=None, done_list=[], local=False):
        contract = self.browse(cr, uid, id, context=context)
        if not default:
            default = {}
        default = default.copy()
        default['code'] = (contract['code'] or '') + '(copy)'
        default['name'] = (contract['name'] or '') + '(copy)'
        # Copy lines manually
        default['actual_line_ids'] = []
        copy_id = super(financing_contract_contract, self).copy(cr, uid, id, default, context=context)
        copy = self.browse(cr, uid, copy_id, context=context)
        self.pool.get('financing.contract.format').copy_format_lines(cr, uid, contract.format_id.id, copy.format_id.id, context=context)
        return copy_id
    
    def onchange_donor_id(self, cr, uid, ids, donor_id, format_id, actual_line_ids, context=None):
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
                res = {'value': format_vals}
        return res
    
    def onchange_currency_table(self, cr, uid, ids, currency_table_id, reporting_currency_id, context=None):
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

    def onchange_date(self, cr, uid, ids, eligibility_from_date, eligibility_to_date):
        """ This function will be called on the change of dates of the financing contract"""
        if eligibility_from_date and eligibility_to_date:
            if eligibility_from_date >= eligibility_to_date:
                warning = {
                    'title': _('Error'), 
                    'message': _("The 'Eligibility Date From' should be sooner than the 'Eligibility Date To'.")
                }
                return {'warning': warning}
        return {}

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
                'line_type': browse_format_line.line_type,
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
    
    def menu_interactive_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        # we update the context with the contract reporting type
        contract = self.browse(cr, uid, ids[0], context=context)
        context.update({'reporting_currency': contract.reporting_currency.id,
                        'reporting_type': contract.reporting_type,
                        'currency_table_id': contract.currency_table_id.id,
                        'active_id': ids[0],
                        'active_ids': ids,
                        'display_fp': True})
        ## INFO: display_fp in context permits to display Funding Pool column and its attached cost center.
        reporting_line_obj = self.pool.get('financing.contract.donor.reporting.line')
        # Create reporting lines
        # Contract line first (we'll fill it later)
        contract_line_id = reporting_line_obj.create(cr,
                                                     uid,
                                                     vals = {'name': contract.name,
                                                             'code': contract.code,
                                                             'line_type': 'view'},
                                                     context=context)
        
        # Values to be set
        allocated_budget = 0
        project_budget = 0
        allocated_real = 0
        project_real = 0
        
        # create "real" lines
        for line in contract.actual_line_ids:
            if not line.parent_id:
                allocated_budget += line.allocated_budget
                project_budget += line.project_budget
                allocated_real += line.allocated_real
                project_real += line.project_real
                reporting_line_id = self.create_reporting_line(cr, uid, contract, line, contract_line_id, context=context)
        
        # Refresh contract line with general infos
        analytic_domain = self.get_contract_domain(cr, uid, contract, context=context)
        contract_values = {'allocated_budget': allocated_budget,
                           'project_budget': project_budget,
                           'allocated_real': allocated_real,
                           'project_real': project_real,
                           'analytic_domain': analytic_domain}
        reporting_line_obj.write(cr, uid, [contract_line_id], vals=contract_values, context=context)
        
        # retrieve the corresponding_view
        model_data_obj = self.pool.get('ir.model.data')
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
        
    def menu_allocated_expense_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        wiz_obj = self.pool.get('wizard.expense.report')
        wiz_id = wiz_obj.create(cr, uid, {'reporting_type': 'allocated',
                                          'filename': 'allocated_expenses.csv',
                                          'contract_id': ids[0]}, context=context)
        # we open a wizard
        return {
                'type': 'ir.actions.act_window',
                'res_model': 'wizard.expense.report',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [wiz_id],
                'context': context,
        }
        
    def menu_project_expense_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        wiz_obj = self.pool.get('wizard.expense.report')
        wiz_id = wiz_obj.create(cr, uid, {'reporting_type': 'project',
                                          'filename': 'project_expenses.csv',
                                          'contract_id': ids[0]}, context=context)
        # we open a wizard
        return {
                'type': 'ir.actions.act_window',
                'res_model': 'wizard.expense.report',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [wiz_id],
                'context': context,
        }
        
    def menu_csv_interactive_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        wiz_obj = self.pool.get('wizard.interactive.report')
        wiz_id = wiz_obj.create(cr, uid, {'filename': 'interactive_report.csv',
                                          'contract_id': ids[0]}, context=context)
        # we open a wizard
        return {
                'type': 'ir.actions.act_window',
                'res_model': 'wizard.interactive.report',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [wiz_id],
                'context': context,
        }
    
financing_contract_contract()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
