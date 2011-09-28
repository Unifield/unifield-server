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
        # Create an analytic_distribution_id if no one exists
        if not distrib_id:
            res_id = ana_obj.create(cr, uid, {}, context=context)
            super(purchase_order, self).write(cr, uid, ids, {'analytic_distribution_id': res_id}, context=context)
            distrib_id = res_id
        # Search analytic distribution to renew if necessary
        for pl in purchase.order_line:
            pl_amount = pl.price_subtotal or 0.0
            if pl.analytic_distribution_id:
                if pl.analytic_distribution_id.global_distribution or context.get('reset_all', False):
                    child_distributions.append((pl.analytic_distribution_id.id, pl_amount))
            else:
                child_distrib_id = ana_obj.create(cr, uid, {'global_distribution': True}, context=context)
                self.pool.get('purchase.order.line').write(cr, uid, [pl.id], {'analytic_distribution_id': child_distrib_id}, context=context)
                child_distributions.append((child_distrib_id, pl_amount))
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
        distrib_id = pl.analytic_distribution_id and pl.analytic_distribution_id.id or False
        if not distrib_id:
            raise osv.except_osv(_('No Analytic Distribution !'),_("You have to define an analytic distribution for the whole purchase order first!"))
        # Create the wizard
        wiz_obj = self.pool.get('wizard.costcenter.distribution')
        wiz_id = wiz_obj.create(cr, uid, {'total_amount': amount, 'distribution_id': distrib_id, 'currency_id': currency}, context=context)
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

    def create(self, cr, uid, vals, context={}):
        """
        Link analytic distribution on purchase order line after its creation
        """
        if not context:
            context = {}
        if not vals:
            vals = {}
        if vals.get('order_id', False):
            # Search global distribution (those from purchase order)
            po = self.pool.get('purchase.order').browse(cr, uid, vals.get('order_id'), context=context)
            if po.analytic_distribution_id:
                # Create a new global analytic distribution
                ana_obj = self.pool.get('analytic.distribution')
                child_distrib_id = ana_obj.create(cr, uid, {'global_distribution': True}, context=context)
                vals.update({'analytic_distribution_id': child_distrib_id,})
                res = super(purchase_order_line, self).create(cr, uid, vals, context=context)
                total_amount = self._amount_line(cr, uid, [res], None, None, context=context)[res]
                amount = total_amount or 0.0
                # Search currency (by default those of company)
                company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
                currency = po.currency_id and po.currency_id.id or company_currency
                ana_obj.copy_from_global_distribution(cr, uid, po.analytic_distribution_id.id, child_distrib_id, amount, currency, context=context)
                return res
        return super(purchase_order_line, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context={}):
        """
        Update analytic lines if an analytic distribution exists
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Write first new purchase order line
        res = super(purchase_order_line, self).write(cr, uid, ids, vals, context=context)
        for pl in self.browse(cr, uid, ids, context=context):
            # do something only if analytic_distribution_id field is filled in
            if pl.order_id.analytic_distribution_id:
                # prepare some values
                po_distrib = pl.order_id.analytic_distribution_id
                company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
                currency = pl.order_id.currency_id and pl.order_id.currency_id.id or company_currency
                if 'price_unit' in vals or 'product_qty' in vals or context.get('reset_all', False) or pl.analytic_distribution_id.global_distribution:
                    amount = pl.price_subtotal or 0.0
                    self.pool.get('analytic.distribution').copy_from_global_distribution(cr, uid, po_distrib.id, pl.analytic_distribution_id.id, amount, currency, context=context)
        return res

purchase_order_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
