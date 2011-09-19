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
        ana_obj = self.pool.get('analytic.distribution')
        purchase = self.browse(cr, uid, ids[0], context=context)
        amount = purchase.amount_total or 0.0
        child_distributions = []
        # Get analytic_distribution_id
        distrib_id = purchase.analytic_distribution_id and purchase.analytic_distribution_id.id
        # Create an analaytic_distribution_id if no one exists
        if not distrib_id:
            res_id = ana_obj.create(cr, uid, {}, context=context)
            super(purchase_order, self).write(cr, uid, ids, {'analytic_distribution_id': res_id}, context=context)
            distrib_id = res_id
        # Search analytic distribution to renew if necessary
        for pl in purchase.order_line:
            amount = pl.price_subtotal or 0.0
            if pl.analaytic_distribution_id:
                if pl.analaytic_distribution_id.global_distribution or context.get('reset_all', False):
                    child_distributions.append((pl.analaytic_distribution_id.id, amount))
            else:
                child_distrib_id = ana_obj.create(cr, uid, {'global_distribution': True}, context=context)
                self.pool.get('purchase.order.line').write(cr, uid, [pl.id], {'analytic_distribution_id': child_distrib_id}, context=context)
                child_distributions.append((child_distrib_id, amount))
        # Create the wizard
        wiz_obj = self.pool.get('wizard.costcenter.distribution')
        wiz_id = wiz_obj.create(cr, uid, {'total_amount': amount, 'distribution_id': distrib_id}, context=context)
        # Update some context values
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
            'wizard_ids': {'cost_center': wiz_id},
            'child_distributions': child_distributions
        })
        # Open it!
        return {
                'type': 'ir.actions.act_window',
                'res_model': 'wizard.costcenter.distribution',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [wiz_id],
                'context': context,
        }

purchase_order()

class purchase_order_line(osv.osv):
    _name = 'purchase.order.line'
    _inherit = 'purchase.order.line'

    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', string="Analytic Distribution"),
    }

    def button_analytic_distribution(self, cr, uid, ids, context={}):
        """
        Launch the analytic distribution wizard on the first given id (from ids)
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        pl = self.browse(cr, uid, ids[0], context=context) # purchase line
        amount = pl.price_subtotal or 0.0
        child_distributions = []
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = pl.order_id.currency_id and pl.order_id.currency_id.id or company_currency
        # Get analytic distribution
        distrib_id = pl.analaytic_distribution_id and pl.analaytic_distribution_id.id or False
        if not distrib_id:
            raise osv.except_osv(_('No Analytic Distribution !'),_("You have to define an analytic distribution for the whole purchase order first!"))
        # Create the wizard
        wiz_obj = self.pool.get('wizard.costcenter.distribution')
        wiz_id = wiz_obj.create(cr, uid, {'total_amount': amount, 'distribution_id': distrib_id}, context=context)
        # Add some values in context
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
            'wizard_ids': {'cost_center': wiz_id},
            'child_distributions': child_distributions
        })
        # Open it!
        return {
                'type': 'ir.actions.act_window',
                'res_model': 'wizard.costcenter.distribution',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [wiz_id],
                'context': context,
        }

purchase_order_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
