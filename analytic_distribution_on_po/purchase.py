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

class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit = 'purchase.order'

    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
    }

    def button_analytic_distribution(self, cr, uid, ids, context={}):
        """
        Launch analytic distribution wizard on a purchase order
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        purchase = self.browse(cr, uid, ids[0], context=context)
        amount = purchase.amount_total or 0.0
        child_distributions = []
        # Get analytic_distribution_id
        distrib_id = purchase.analytic_distribution_id and purchase.analytic_distribution_id.id
        # Create an analaytic_distribution_id if no one exists
        if not distrib_id:
            res_id = self.pool.get('analytic.distribution').create(cr, uid, {}, context=context)
            super(purchase_order, self).write(cr, uid, ids, {'analytic_distribution_id': res_id}, context=context)
            distrib_id = res_id
        # Search analytic distribution to renew if necessary
        # FIXME
#        for invoice_line in invoice_obj.invoice_line:
#            amount = invoice_line.price_subtotal
#            if negative_inv:
#                amount = -1 * amount
#            if invoice_line.analytic_distribution_id:
#                if invoice_line.analytic_distribution_id.global_distribution \
#                or ('reset_all' in context and context['reset_all']):
#                    child_distributions.append((invoice_line.analytic_distribution_id.id, amount))
#            else:
#                child_distrib_id = self.pool.get('analytic.distribution').create(cr, uid, {'global_distribution': True}, context=context)
#                child_vals = {'analytic_distribution_id': child_distrib_id}
#                self.pool.get('account.invoice.line').write(cr, uid, [invoice_line.id], child_vals, context=context)
#                child_distributions.append((child_distrib_id, amount))
        # Create the wizard
        wiz_obj = self.pool.get('wizard.costcenter.distribution')
        wiz_id = wiz_obj.create(cr, uid, {'total_amount': amount, 'distribution_id': distrib_id}, context=context)
        # Open it!
        return {
                'type': 'ir.actions.act_window',
                'res_model': 'wizard.costcenter.distribution',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [wiz_id],
                'context': {
                    'active_id': ids[0],
                    'active_ids': ids,
                    'wizard_ids': {'cost_center': wiz_id},
                    'child_distributions': child_distributions
               }
        }

    def action_invoice_create(self, cr, uid, ids, *args):
        """
        Give the invoice and invoice_line the analytic distribution
        """
        return super(purchase_order, self).action_invoice_create(cr, uid, ids, args)

purchase_order()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
