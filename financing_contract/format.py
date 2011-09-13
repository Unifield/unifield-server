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
        'overhead_type': fields.selection([('total_costs','Total costs percentage'),
                                           ('total_grant','Total grant percentage'),
                                           ('lump_sum', 'Lump sum amount')], 'Overhead type', required=True),
        'overhead_value': fields.float('Overhead', required=True),
        'lump_sum': fields.float('Lump sum'),
        'consumption': fields.float('Consumption'),
    }
    
    _defaults = {
        'format_name': 'Format',
        'overhead_type': 'total_costs',
        'overhead_value': 0.0,
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
        'account_ids': fields.many2many('account.account', 'financing_contract_actual_accounts', 'actual_line_id', 'account_id', string='Accounts', required=True),
        'parent_id': fields.many2one('financing.contract.actual.line', 'Parent line'),
        'child_ids': fields.one2many('financing.contract.actual.line', 'parent_id', 'Child lines'),
        'number_of_childs': fields.function(_get_number_of_childs, method=True, store={'financing.contract.actual.line': (_get_parent_ids, ['parent_id'], 10)}, string="Number of child lines", type="integer", readonly="True"),
        'allocated_amount': fields.float('Budget allocated amount'),
        'total_amount': fields.float('Budget total amount'),
    }
    
financing_contract_actual_line()

class financing_contract_format(osv.osv):
    
    _name = "financing.contract.format"
    _inherit = "financing.contract.format"
    
    _columns = {
        'actual_line_ids': fields.one2many('financing.contract.actual.line', 'format_id', 'Actual lines'),
    }
    
financing_contract_format()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
