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
from tools.translate import _

class sale_order(osv.osv):
    _name = 'sale.order'
    _inherit = 'sale.order'

    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', string="Analytic distribution"),
    }

    def button_analytic_distribution(self, cr, uid, ids, context=None):
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
                'name': 'Global analytic distribution',
                'type': 'ir.actions.act_window',
                'res_model': 'analytic.distribution.wizard',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [wiz_id],
                'context': context,
        }

    def copy_data(self, cr, uid, id, default=None, context=None):
        """
        Copy global distribution and give it to new sale order.
        """
        # Some verifications
        if not context:
            context = {}
        if default is None:
            default = {}
        # Default method
        if 'analytic_distribution_id' not in default:
            default['analytic_distribution_id'] = False
        return super(sale_order, self).copy_data(cr, uid, id, default=default, context=context)

    def wkf_validated(self, cr, uid, ids, context=None):
        """
        Check analytic distribution for each sale order line if partner type is 'internal'
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Analytic distribution verification if partner_type is 'internal'
        ana_obj = self.pool.get('analytic.distribution')
        for so in self.browse(cr, uid, ids, context=context):
            if so.partner_id.partner_type == 'section' and not so.analytic_distribution_id:
                for line in so.order_line:
                    if not line.analytic_distribution_id:
                        dummy_cc = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 
                            'analytic_account_project_dummy')
                        ana_id = ana_obj.create(cr, uid, {'sale_order_ids': [(4,so.id)], 
                            'cost_center_lines': [(0, 0, {'analytic_id': dummy_cc[1] , 'percentage':'100', 'currency_id': so.currency_id.id})]})
                        break
        # Default behaviour
        res = super(sale_order, self).wkf_validated(cr, uid, ids, context=context)
        return res

    def action_invoice_create(self, cr, uid, ids, *args):
        """
        Add analytic distribution from SO to invoice
        """
        # Retrieve some data
        res = super(sale_order, self).action_invoice_create(cr, uid, ids, *args) # invoice_id
        # Set analytic distribution from sale order to invoice
        ana_obj = self.pool.get('analytic.distribution')
        for so in self.browse(cr, uid, ids):
            # Code to retrieve DISTRO from SO have been removed because of impossibility to retrieve some DESTINATION AXIS from FO
            # Copy analytic distribution from sale order line to invoice lines
            for sol in so.order_line:
                if sol.analytic_distribution_id and sol.invoice_lines:
                    sol_distrib_id = sol.analytic_distribution_id and sol.analytic_distribution_id.id or False
                    if sol_distrib_id:
                        for invl in sol.invoice_lines:
                            new_sol_distrib_id = ana_obj.copy(cr, uid, sol_distrib_id, {})
                            if not new_sol_distrib_id:
                                raise osv.except_osv(_('Error'), _('An error occured for analytic distribution copy for invoice line.'))
                            # create default funding pool lines
                            ana_obj.create_funding_pool_lines(cr, uid, [new_sol_distrib_id])
                            self.pool.get('account.invoice.line').write(cr, uid, [invl.id], {'analytic_distribution_id': new_sol_distrib_id,})
        return res

sale_order()

class sale_order_line(osv.osv):
    _name = 'sale.order.line'
    _inherit = 'sale.order.line'

    def _have_analytic_distribution_from_header(self, cr, uid, ids, name, arg, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for line in self.read(cr, uid, ids, ['analytic_distribution_id']):
            if line['analytic_distribution_id']:
                res[line['id']] = False
            else:
                res[line['id']] = True
        return res

    def _get_analytic_distribution_available(self, cr, uid, ids, name, arg, context=None):
        """
        Return true if analytic distribution must be available (which means partner is inter-section)
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for sol in self.browse(cr, uid, ids):
            res[sol.id] = False
            if sol.order_id and sol.order_id.partner_id and sol.order_id.partner_id.partner_type == 'section':
                res[sol.id] = True
        return res

    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
        'have_analytic_distribution_from_header': fields.function(_have_analytic_distribution_from_header, method=True, type='boolean', 
            string='Header Distrib.?'),
        'analytic_distribution_available': fields.function(_get_analytic_distribution_available, string='Is analytic distribution available?', method=True, type='boolean'),
    }

    _defaults = {
        'have_analytic_distribution_from_header': lambda *a: True,
    }

    def button_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Launch analytic distribution wizard on a sale order line
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        sol = self.browse(cr, uid, ids[0], context=context)
        amount = sol.price_subtotal or 0.0
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = sol.order_id.currency_id and sol.order_id.currency_id.id or company_currency
        # Get analytic_distribution_id
        distrib_id = sol.analytic_distribution_id and sol.analytic_distribution_id.id
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'sale_order_line_id': sol.id,
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
                'name': 'Analytic distribution',
                'type': 'ir.actions.act_window',
                'res_model': 'analytic.distribution.wizard',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [wiz_id],
                'context': context,
        }

    def copy_data(self, cr, uid, id, default=None, context=None):
        """
        Copy global distribution and give it to new sale order line
        """
        # Some verifications
        if not context:
            context = {}
        if default is None:
            default = {}
        # Copy analytic distribution
        if 'analytic_distribution_id' not in default and not context.get('keepDateAndDistrib'):
            default['analytic_distribution_id'] = False
        new_data = super(sale_order_line, self).copy_data(cr, uid, id, default, context)
        if new_data and new_data.get('analytic_distribution_id'):
            new_data['analytic_distribution_id'] = self.pool.get('analytic.distribution').copy(cr, uid, new_data['analytic_distribution_id'], {}, context=context)
        return new_data

sale_order_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
