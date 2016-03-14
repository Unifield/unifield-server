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

class financing_contract_donor_reporting_line(osv.osv_memory):
    _name = "financing.contract.donor.reporting.line"
    
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'code': fields.char('Code', size=16, required=True),
        'line_type': fields.selection([('view','View'),
                                       ('actual','Actual'),
                                       ('consumption','Consumption'),
                                       ('overhead','Overhead')], 'Line type', required=True),

        'allocated_budget': fields.integer("Funded - Budget"),
        'project_budget': fields.integer("Total project - Budget"),

        'allocated_real': fields.integer("Funded - Actuals"),
        'project_real': fields.integer("Total project - Actuals"),

        'allocated_balance': fields.integer("Funded - Balance"),
        'project_balance': fields.integer("Total project - Balance"),

        'analytic_domain': fields.char('Analytic domain', size=256),
        'parent_id': fields.many2one('financing.contract.donor.reporting.line', 'Parent line'),
        'child_ids': fields.one2many('financing.contract.donor.reporting.line', 'parent_id', 'Child lines'),
    }
    
    _defaults = {
        'parent_id': lambda *a: False
    }
        
financing_contract_donor_reporting_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
