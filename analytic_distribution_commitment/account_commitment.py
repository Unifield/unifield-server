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

class account_commitment(osv.osv):
    _name = 'account.commitment'
    _inherit = 'account.commitment'

    def _get_distribution_line_count(self, cr, uid, ids, name, args, context={}):
        """
        Return analytic distribution line count (given by analytic distribution)
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        # Browse given invoices
        for co in self.browse(cr, uid, ids, context=context):
            res[co.id] = co.analytic_distribution_id and co.analytic_distribution_id.lines_count or 'None'
        return res

    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', string="Analytic distribution"),
        'analytic_distribution_line_count': fields.function(_get_distribution_line_count, method=True, type='char', size=256,
            string="Analytic distribution count", readonly=True, store=False),
    }

    def button_analytic_distribution(self, cr, uid, ids, context={}):
        """
        Launch analytic distribution wizard on a commitment
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        commitment = self.browse(cr, uid, ids[0], context=context)
        amount = commitment.total or 0.0
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = commitment.currency_id and commitment.currency_id.id or company_currency
        # Get analytic_distribution_id
        distrib_id = commitment.analytic_distribution_id and commitment.analytic_distribution_id.id
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'commitment_id': commitment.id,
            'currency_id': currency or False,
            'state': 'dispatch',
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

account_commitment()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
