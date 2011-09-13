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

class financing_contract_donor(osv.osv):
    
    _name = "financing.contract.donor"
    _inherits = {"financing.contract.format": "format_id"}
    
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'code': fields.char('Code', size=16, required=True),
        'active': fields.boolean('Active'),
    }
    
    _defaults = {
        'active': True,
        'format_id': lambda self,cr,uid,context: self.pool.get('financing.contract.format').create(cr, uid, {}, context=context)
    }
    
    
financing_contract_donor()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
