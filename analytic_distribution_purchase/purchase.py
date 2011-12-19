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
        for po in self.browse(cr, uid, ids, context=context):
            tmp = po.analytic_distribution_id and po.analytic_distribution_id.lines_count or ''
            # Transform result with just CC line count
            if tmp != '':
                res[po.id] = tmp.split(';')[0]
        return res

    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
        'analytic_distribution_line_count': fields.function(_get_distribution_line_count, method=True, type='char', size=256,
            string="Analytic distribution count", readonly=True, store=False),
    }

    def inv_line_create(self, cr, uid, account_id, order_line):
        """
        Add a link between the new invoice line and the order line that it come from
        """
        # Retrieve data
        res = super(purchase_order, self).inv_line_create(cr, uid, account_id, order_line)
        # Add order_line_id to data
        if res and res[2]:
            res[2].update({'order_line_id': order_line.id,})
        # Return result
        return res

    def action_invoice_create(self, cr, uid, ids, *args):
        """
        Take all new invoice lines and give them analytic distribution that was linked on each purchase order line (if exists)
        """
        # Retrieve some data
        res = super(purchase_order, self).action_invoice_create(cr, uid, ids, *args) # invoice_id
        # Set analytic distribution from purchase order to invoice
        invl_obj = self.pool.get('account.invoice.line') # invoice line object
        ana_obj = self.pool.get('analytic.distribution')
        for po in self.browse(cr, uid, ids):
            if po.from_yml_test:
                continue
            if not po.analytic_distribution_id:
                for line in po.order_line:
                    if not line.analytic_distribution_id:
                        dummy_cc = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_project_dummy')
                        ana_id = ana_obj.create(cr, uid, {'purchase_ids': [(4,po.id)], 'cost_center_lines': [(0, 0, {'analytic_id': dummy_cc[1] , 'percentage':'100', 'currency_id': po.currency_id.id})]})
                        po.analytic_distribution_id = ana_obj.browse(cr, uid, ana_id)
                        #raise osv.except_osv(_('Error'), _("No analytic distribution found on purchase order '%s'.") % po.name)
                        break
            inv_ids = po.invoice_ids
            for inv in inv_ids:
                # First set invoice global distribution
                if po.analytic_distribution_id:
                    new_distrib_id = ana_obj.copy(cr, uid, po.analytic_distribution_id.id, {})
                    if not new_distrib_id:
                        raise osv.except_osv(_('Error'), _('An error occured for analytic distribution copy for invoice.'))
                    # create default funding pool lines
                    ana_obj.create_funding_pool_lines(cr, uid, [new_distrib_id])
                    self.pool.get('account.invoice').write(cr, uid, [inv.id], {'analytic_distribution_id': new_distrib_id,})
                # Search all invoice lines
                invl_ids = invl_obj.search(cr, uid, [('invoice_id', '=', inv.id)])
                # Then set distribution on invoice line regarding purchase order line distribution
                for invl in invl_obj.browse(cr, uid, invl_ids):
                    if invl.order_line_id and invl.order_line_id.analytic_distribution_id:
                        new_invl_distrib_id = ana_obj.copy(cr, uid, invl.order_line_id.analytic_distribution_id.id, {})
                        if not new_invl_distrib_id:
                            raise osv.except_osv(_('Error'), _('An error occured for analytic distribution copy for invoice.'))
                        # create default funding pool lines
                        ana_obj.create_funding_pool_lines(cr, uid, [new_invl_distrib_id])
                        invl_obj.write(cr, uid, [invl.id], {'analytic_distribution_id': new_invl_distrib_id})
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
        purchase = self.browse(cr, uid, ids[0], context=context)
        amount = purchase.amount_total or 0.0
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = purchase.currency_id and purchase.currency_id.id or company_currency
        # Get analytic_distribution_id
        distrib_id = purchase.analytic_distribution_id and purchase.analytic_distribution_id.id
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'purchase_id': purchase.id,
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
        Copy global distribution and give it to new purchase
        """
        # Some verifications
        if not context:
            context = {}
        # Default method
        res = super(purchase_order, self).copy(cr, uid, id, default, context)
        # Update analytic distribution
        if res:
            po = self.browse(cr, uid, res, context=context)
        if res and po.analytic_distribution_id:
            new_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, po.analytic_distribution_id.id, {}, context=context)
            if new_distrib_id:
                self.write(cr, uid, [res], {'analytic_distribution_id': new_distrib_id}, context=context)
        return res

purchase_order()

class purchase_order_line(osv.osv):
    _name = 'purchase.order.line'
    _inherit = 'purchase.order.line'

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
        for pol in self.browse(cr, uid, ids, context=context):
            tmp = pol.analytic_distribution_id and pol.analytic_distribution_id.lines_count or ''
            # Transform result with just CC line count
            if tmp != '':
                res[pol.id] = tmp.split(';')[0]
        return res

    def _have_analytic_distribution_from_header(self, cr, uid, ids, name, arg, context={}):
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for line in self.read(cr, uid, ids, ['analytic_distribution_id']):
            if line['analytic_distribution_id']:
                res[line['id']] = False
            else:
                res[line['id']] = True
        return res

    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
        'analytic_distribution_line_count': fields.function(_get_distribution_line_count, method=True, type='char', size=256,
            string="Analytic distribution count", readonly=True, store=False),
        'have_analytic_distribution_from_header': fields.function(_have_analytic_distribution_from_header, method=True, type='boolean', string='Header Distrib.?'),
    }

    _defaults = {
        'have_analytic_distribution_from_header': lambda *a: True,
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
        purchase_line = self.browse(cr, uid, ids[0], context=context)
        amount = purchase_line.price_subtotal or 0.0
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = purchase_line.order_id.currency_id and purchase_line.order_id.currency_id.id or company_currency
        # Get analytic_distribution_id
        distrib_id = purchase_line.analytic_distribution_id and purchase_line.analytic_distribution_id.id
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'purchase_line_id': purchase_line.id,
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

    def copy_data(self, cr, uid, id, default={}, context={}):
        """
        Copy global distribution and give it to new purchase line
        """
        # Some verifications
        if not context:
            context = {}
        # Copy analytic distribution
        pol = self.browse(cr, uid, [id], context=context)[0]
        if pol.analytic_distribution_id:
            new_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, pol.analytic_distribution_id.id, {}, context=context)
            if new_distrib_id:
                default.update({'analytic_distribution_id': new_distrib_id})
        return super(purchase_order_line, self).copy_data(cr, uid, id, default, context)

purchase_order_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
