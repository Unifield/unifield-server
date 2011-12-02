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

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
