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
from tools.translate import _

class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit = 'purchase.order'

    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
    }

    def action_invoice_create(self, cr, uid, ids, *args):
        """
        Take all new invoice lines and give them analytic distribution that was linked on each purchase order line (if exists)
        """
        # Retrieve some data
        res = super(purchase_order, self).action_invoice_create(cr, uid, ids, *args) # invoice_id
        # Set analytic distribution from purchase order to invoice
        for po in self.browse(cr, uid, ids):
            if not po.analytic_distribution_id:
                raise osv.except_osv(_('Error'), _("No analytic distribution found on purchase order '%s'.") % po.name)
            inv_ids = po.invoice_ids
            for inv in inv_ids:
                # Set invoice global distribution
                self.pool.get('account.invoice').write(cr, uid, [inv.id], {'analytic_distribution_id': po.analytic_distribution_id.id,})
        return res

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
        ana_obj = self.pool.get('analytic.distribution')
        purchase = self.browse(cr, uid, ids[0], context=context)
        amount = purchase.amount_total or 0.0
        # Get analytic_distribution_id
        distrib_id = purchase.analytic_distribution_id and purchase.analytic_distribution_id.id
        # Create an analytic_distribution_id if no one exists
        if not distrib_id:
            res_id = ana_obj.create(cr, uid, {}, context=context)
            super(purchase_order, self).write(cr, uid, ids, {'analytic_distribution_id': res_id}, context=context)
            distrib_id = res_id
        # Create the wizard
        wiz_obj = self.pool.get('analytic.distribution.wizard')
        wiz_id = wiz_obj.create(cr, uid, {'total_amount': amount, 'purchase_id': purchase.id, 'distribution_id': distrib_id,
            'currency_id': purchase.currency_id and purchase.currency_id.id or False}, context=context)
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

purchase_order()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
