#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Olivier DOSSMANN
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

class analytic_distribution(osv.osv):
    _name = 'analytic.distribution'
    _inherit = 'analytic.distribution'

    _columns = {
        'purchase_ids': fields.one2many('purchase.order', 'analytic_distribution_id', string="Purchases"),
        'purchase_line_ids': fields.one2many('purchase.order.line', 'analytic_distribution_id', string="Purchase Lines"),
        'sale_order_ids': fields.one2many('sale.order', 'analytic_distribution_id', string="Sales"),
        'sale_order_line_ids': fields.one2many('sale.order.line', 'analytic_distribution_id', string="Sale Order Lines"),
        'partner_type': fields.text(string='Partner Type of FO/PO', required=False, readonly=True),#UF-2138: added the ref to partner type of FO/PO
    }

    def copy(self, cr, uid, d_id, default=None, context=None):
        """
        Delete one2many fields
        """
        # Some verifications
        if not context:
            context = {}
        if not default:
            default = {}
        # Delete purchase_ids and purchase_line_ids links
        default.update({
            'purchase_ids': False,
            'purchase_line_ids': False,
            'sale_order_ids': False,
            'sale_order_line_ids': False,
        })
        if default.get('partner_type'):
            context['set_copy_partner_type'] = default.get('partner_type')
        new_id = super(analytic_distribution, self).copy(cr, uid, d_id, default, context)
        if context.get('set_copy_partner_type'):
            del context['set_copy_partner_type']
        return new_id

analytic_distribution()

class cost_center_distribution_line(osv.osv):
    _name = 'cost.center.distribution.line'
    _inherit = 'cost.center.distribution.line'

    def copy_data(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        if context is None:
            context = {}
        if context.get('set_copy_partner_type'):
            default['partner_type'] = context.get('set_copy_partner_type')
        return super(cost_center_distribution_line, self).copy_data(cr, uid, id, default=default, context=None)

cost_center_distribution_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
