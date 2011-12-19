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
        'overhead_type': fields.selection([('cost_percentage','Percentage of total costs'),
                                           ('grant_percentage','Percentage of direct costs'),
                                           ('amount', 'Lump sum')], 'Overhead type', required=True),
        'overhead_percentage': fields.float('Percentage overhead'),
        'budget_allocated_overhead': fields.float('Funded overhead - Budget'),
        'budget_project_overhead': fields.float('Total project overhead - Budget'),
        'allocated_overhead': fields.float('Funded overhead - Actuals'),
        'project_overhead': fields.float('Total project overhead - Actuals'),
        'budget_allocated_lump_sum': fields.float('Funded lump sum - Budget'),
        'budget_project_lump_sum': fields.float('Total project lump sum - Budget'),
        'allocated_lump_sum': fields.float('Funded lump sum - Actuals'),
        'project_lump_sum': fields.float('Total project lump sum - Actuals'),
        'budget_allocated_consumption': fields.float('Funded consumption - Budget'),
        'budget_project_consumption': fields.float('Total project consumption - Budget'),
        'allocated_consumption': fields.float('Funded consumption - Actuals'),
        'project_consumption': fields.float('Total project consumption - Actuals'),
    }
    
    _defaults = {
        'format_name': 'Format',
        'reporting_type': 'all',
        'overhead_type': 'cost_percentage',
        'overhead_percentage': 0.0,
        'budget_allocated_overhead': 0.0,
        'budget_project_overhead': 0.0,
        'allocated_overhead': 0.0,
        'project_overhead': 0.0,
        'budget_allocated_lump_sum': 0.0,
        'budget_project_lump_sum': 0.0,
        'allocated_lump_sum': 0.0,
        'project_lump_sum': 0.0,
        'budget_allocated_consumption': 0.0,
        'budget_project_consumption': 0.0,
        'allocated_consumption': 0.0,
        'project_consumption': 0.0,
    }
    
    def name_get(self, cr, uid, ids, context=None):
        result = self.browse(cr, uid, ids, context=context)
        res = []
        for rs in result:
            format_name = rs.format_name
            res += [(rs.id, format_name)]
        return res
    
financing_contract_format()

class financing_contract_actual_line(osv.osv):
    
    _name = "financing.contract.actual.line"

    def _get_number_of_childs(self, cr, uid, ids, field_name=None, arg=None, context={}):
        # Verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
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
    
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'code': fields.char('Code', size=16, required=True),
        'format_id': fields.many2one('financing.contract.format', 'Format'),
        'account_ids': fields.many2many('account.account', 'financing_contract_actual_accounts', 'actual_line_id', 'account_id', string='Accounts'),
        'parent_id': fields.many2one('financing.contract.actual.line', 'Parent line'),
        'child_ids': fields.one2many('financing.contract.actual.line', 'parent_id', 'Child lines'),
        'line_type': fields.selection([('view','View'),
                                       ('normal','Normal')], 'Line type', required=True),
        'allocated_amount': fields.float('Funded amount - Budget'),
        'project_amount': fields.float('Total project amount - Budget'),
    }
    
    _defaults = {
        'line_type': 'normal',
    }

    def _check_unicity(self, cr, uid, ids, context={}):
        if not context:
            context={}
        for reporting_line in self.browse(cr, uid, ids, context=context):
            bad_ids = self.search(cr, uid, [('format_id', '=', reporting_line.format_id.id),('|'),('name', '=ilike', reporting_line.name),('code', '=ilike', reporting_line.code)])
            if len(bad_ids) and len(bad_ids) > 1:
                return False
        return True

    _constraints = [
        (_check_unicity, 'You cannot have the same code or name between reporting lines!', ['code', 'name']),
    ]
    
    def create(self, cr, uid, vals, context=None):
        if not context:
            context={}
        # if the account is set as view, remove budget and account values
        if 'line_type' in vals and vals['line_type'] == 'view':
            vals['allocated_amount'] = 0.0
            vals['project_amount'] = 0.0
            vals['account_ids'] = []
        return super(financing_contract_actual_line, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # if the account is set as view, remove budget and account values
        if 'line_type' in vals and vals['line_type'] == 'view':
            vals['allocated_amount'] = 0.0
            vals['project_amount'] = 0.0
            vals['account_ids'] = [(6, 0, [])]
        return super(financing_contract_actual_line, self).write(cr, uid, ids, vals, context=context)
    
    def copy_format_line(self, cr, uid, browse_source_line, destination_format_id, parent_id=None, context=None):
        if destination_format_id:
            format_line_vals = {
                'name': browse_source_line.name,
                'code': browse_source_line.code,
                'format_id': destination_format_id,
                'parent_id': parent_id,
                'line_type': browse_source_line.line_type,
                'allocated_amount': browse_source_line.allocated_amount,
                'project_amount': browse_source_line.project_amount,
            }
            account_ids = []
            for account in browse_source_line.account_ids:
                account_ids.append(account.id)
            format_line_vals['account_ids'] = [(6, 0, account_ids)]
            parent_line_id = self.pool.get('financing.contract.actual.line').create(cr, uid, format_line_vals, context=context)
            for child_line in browse_source_line.child_ids:
                self.copy_format_line(cr, uid, child_line, destination_format_id, parent_line_id, context=context)
        return
            
financing_contract_actual_line()

class financing_contract_format(osv.osv):
    
    _name = "financing.contract.format"
    _inherit = "financing.contract.format"
    
    _columns = {
        'actual_line_ids': fields.one2many('financing.contract.actual.line', 'format_id', 'Actual lines'),
    }
    
    def copy_format_lines(self, cr, uid, source_id, destination_id, context=None):
        # remove all old report lines
        destination_obj = self.browse(cr, uid, destination_id, context=context)
        for to_remove_line in destination_obj.actual_line_ids:
            self.pool.get('financing.contract.actual.line').unlink(cr, uid, to_remove_line.id, context=context)
        source_obj = self.browse(cr, uid, source_id, context=context)
        # Method to copy a format
        # copy format lines
        for source_line in source_obj.actual_line_ids:
            if not source_line.parent_id:
                self.pool.get('financing.contract.actual.line').copy_format_line(cr,
                                                                                 uid,
                                                                                 source_line,
                                                                                 destination_id,
                                                                                 parent_id=None,
                                                                                 context=context)
        return
        
financing_contract_format()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
