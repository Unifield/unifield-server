#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
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

class sale_order(osv.osv):
    _name = 'sale.order'
    _inherit = 'sale.order'

    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', string="Analytic distribution"),
    }

    def button_analytic_distribution(self, cr, uid, ids, context={}):
        """
        Launch analytic distribution wizard on a sale order
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        so = self.browse(cr, uid, ids[0], context=context)
        amount = so.amount_total or 0.0
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = so.currency_id and so.currency_id.id or company_currency
        # Get analytic_distribution_id
        distrib_id = so.analytic_distribution_id and so.analytic_distribution_id.id
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'sale_order_id': so.id,
            'currency_id': currency or False,
            'state': 'cc',
        }
        if distrib_id:
            vals.update({'distribution_id': distrib_id,})
        # Create the wizard
        wiz_obj = self.pool.get('analytic.distribution.wizard')
        wiz_id = wiz_obj.create(cr, uid, vals, context=context)
        # Update some context values
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        # Open it!
        return {
                'type': 'ir.actions.act_window',
                'res_model': 'analytic.distribution.wizard',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [wiz_id],
                'context': context,
        }

    def copy(self, cr, uid, id, default={}, context={}):
        """
        Copy global distribution and give it to new sale order.
        """
        # Some verifications
        if not context:
            context = {}
        # Default method
        res = super(sale_order, self).copy(cr, uid, id, default=default, context=context)
        # Update analytic distribution
        if res:
            so = self.browse(cr, uid, res, context=context)
        if res and so.analytic_distribution_id:
            new_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, so.analytic_distribution_id.id, {}, context=context)
            if new_distrib_id:
                self.write(cr, uid, [res], {'analytic_distribution_id': new_distrib_id}, context=context)
        return res

sale_order()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
