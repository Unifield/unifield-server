#!/usr/bin/env python
# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF
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

from osv import osv
from osv import fields


class product_supplierinfo(osv.osv):
    _name = 'product.supplierinfo'
    _inherit = 'product.supplierinfo'

    _columns = {
        'manufacturer_id': fields.many2one('res.partner', string='Manufacturer', domain=[('manufacturer', '=', 1)]),
        'second_manufacturer_id': fields.many2one('res.partner', string='Second Manufacturer', domain=[('manufacturer', '=', 1)]),
        'third_manufacturer_id': fields.many2one('res.partner', string='Third Manufacturer', domain=[('manufacturer', '=', 1)]),
        'company_id': fields.many2one('res.company','Company',select=1),
    }
    
    _defaults = {
        'company_id': lambda obj, cr, uid, context: obj.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id,
    }

product_supplierinfo()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

