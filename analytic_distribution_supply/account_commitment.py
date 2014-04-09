#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
from collections import defaultdict

class account_commitment(osv.osv):
    _name = 'account.commitment'
    _inherit = 'account.commitment'

    _columns = {
        'purchase_id': fields.many2one('purchase.order', string="Source document", readonly=True),
    }

account_commitment()

class account_commitment_line(osv.osv):
    _name = 'account.commitment.line'
    _inherit = 'account.commitment.line'

    _columns = {
        'purchase_order_line_ids': fields.many2many('purchase.order.line', 'purchase_line_commitment_rel', 'commitment_id', 'purchase_id',
            string="Purchase Order Lines", readonly=True),
    }

    def create_distribution_from_order_line(self, cr, uid, ids, context=None):
        """
        Create an analytic distribution regarding those from attached PO lines (if exists).
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Browse commitment lines
        for line in self.browse(cr, uid, ids, context=context):
            cc_lines = defaultdict(list) # a dict that permits to show all amount for a specific cost_center (regarding analytic_id from cost_center_line)
            # browse purchase order lines attached to this commitment line
            for pol in line.purchase_order_line_ids:
                # browse cost_center line if an analytic distribution exists for this purchase order line
                if pol.analytic_distribution_id:
                    origin_cc_lines = pol.analytic_distribution_id.cost_center_lines
                # else retrieve CC lines from PO
                else:
                    origin_cc_lines = pol.order_id.analytic_distribution_id.cost_center_lines
                # Compute CC lines amounts
                for aline in origin_cc_lines:
                    if aline.analytic_id:
                        # Compute amount regarding pol subtotal and cost_center_line percentage
                        amount = (pol.price_subtotal * aline.percentage) / 100
                        cc_lines[(aline.analytic_id.id, aline.destination_id and aline.destination_id.id or False)].append(amount)
            # Browse result and create corresponding analytic lines
            if cc_lines:
                # create distribution an link it to commitment line
                distrib_id = self.pool.get('analytic.distribution').create(cr, uid, {}, context=context)
                self.write(cr, uid, [line.id], {'analytic_distribution_id': distrib_id}, context=context)
                for el in cc_lines:
                    analytic_id = el[0] or False
                    vals = {
                            'distribution_id': distrib_id,
                            'analytic_id': analytic_id,
                            'currency_id': line.commit_id.currency_id.id,
                            'destination_id': el[1] or False,
                    }
                    total_amount = 0.0
                    # fetch total amount
                    for amount in cc_lines[el]:
                        total_amount += amount
                    if not total_amount:
                        continue
                    # compute percentage
                    percentage = (total_amount / line.amount) * 100 or 0.0
                    vals.update({'percentage': percentage})
                    # create cost_center_line
                    self.pool.get('cost.center.distribution.line').create(cr, uid, vals, context=context)
                # Create funding pool lines if needed
                self.pool.get('analytic.distribution').create_funding_pool_lines(cr, uid, [distrib_id], line.account_id.id, context=context)
        return True

account_commitment_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
