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
        'name': fields.char('Donor name', size=64, required=True),
        'code': fields.char('Donor code', size=16, required=True),
        'active': fields.boolean('Active'),
        # Define for _inherits
        'format_id': fields.many2one('financing.contract.format', 'Format', ondelete="cascade"),
        'reporting_currency': fields.many2one('res.currency', 'Reporting currency', required=True),
    }
    
    _defaults = {
        'active': True,
    }

    def _check_unicity(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        for donor in self.browse(cr, uid, ids, context=context):
            bad_ids = self.search(cr, uid, [('|'),('name', '=ilike', donor.name),('code', '=ilike', donor.code)])
            if len(bad_ids) and len(bad_ids) > 1:
                return False
        return True

    _constraints = [
        (_check_unicity, 'You cannot have the same code or name between donors!', ['code', 'name']),
    ]

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        donor = self.browse(cr, uid, id, context=context)
        if not default:
            default = {}
        default = default.copy()
        default['code'] = (donor['code'] or '') + '(copy)'
        default['name'] = (donor['name'] or '') + '(copy)'
        # Copy lines manually
        default['actual_line_ids'] = []
        copy_id = super(financing_contract_donor, self).copy(cr, uid, id, default, context=context)
        copy = self.browse(cr, uid, copy_id, context=context)
        self.pool.get('financing.contract.format').copy_format_lines(cr, uid, donor.format_id.id, copy.format_id.id, context=context)
        return copy_id
    
    
financing_contract_donor()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
