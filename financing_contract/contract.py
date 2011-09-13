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
                new_format_id = self.pool.get('financing.contract.format').copy(cr, uid, donor.format_id.id, {}, context=context)
                res = {'format_id': new_format_id}
                
        return {'value': res}
    
    
financing_contract_contract()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
