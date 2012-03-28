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

from time import strftime
from account_tools import get_period_from_date
from account_tools import get_date_in_period

from collections import defaultdict

class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit = 'purchase.order'

    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
        'commitment_ids': fields.one2many('account.commitment', 'purchase_id', string="Commitment Vouchers", readonly=True),
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
        for po in self.browse(cr, uid, ids):
            # Copy analytic_distribution
            self.pool.get('account.invoice').fetch_analytic_distribution(cr, uid, [x.id for x in po.invoice_ids])
        return res

    def button_analytic_distribution(self, cr, uid, ids, context=None):
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

    def copy_data(self, cr, uid, id, default=None, context=None):
        """
        Copy global distribution and give it to new purchase.
        Delete commitment_ids link.
        """
        # Some verifications
        if not context:
            context = {}
        if not default:
            default = {}
        # Update default
        default.update({'commitment_ids': False,})
        # Default method
        res = super(purchase_order, self).copy_data(cr, uid, id, default=default, context=context)
        # Update analytic distribution
        if res:
            po = self.browse(cr, uid, res, context=context)
        if res and po.analytic_distribution_id:
            new_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, po.analytic_distribution_id.id, {}, context=context)
            if new_distrib_id:
                self.write(cr, uid, [res], {'analytic_distribution_id': new_distrib_id}, context=context)
        return res

    def action_create_commitment(self, cr, uid, ids, type=False, context=None):
        """
        Create commitment from given PO, but only for external and esc partner_types
        """
        # Some verifications
        if not type or type not in ['external', 'esc']:
            return False
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        commit_obj = self.pool.get('account.commitment')
        eng_ids = self.pool.get('account.analytic.journal').search(cr, uid, [('type', '=', 'engagement')], context=context)
        for po in self.browse(cr, uid, ids, context=context):
            # fetch analytic distribution, period from delivery date, currency, etc.
            vals = {
                'journal_id': eng_ids and eng_ids[0] or False,
                'currency_id': po.currency_id and po.currency_id.id or False,
                'partner_id': po.partner_id and po.partner_id.id or False,
                'purchase_id': po.id or False,
                'type': po.partner_id and po.partner_id.partner_type or 'manual',
            }
            # prepare some values
            today = strftime('%Y-%m-%d')
            period_ids = get_period_from_date(self, cr, uid, po.delivery_confirmed_date or today, context=context)
            period_id = period_ids and period_ids[0] or False
            if not period_id:
                raise osv.except_osv(_('Error'), _('No period found for given date: %s.') % (po.delivery_confirmed_date or today))
            date = get_date_in_period(self, cr, uid, po.delivery_confirmed_date or today, period_id, context=context)
            po_lines = defaultdict(list)
            # update period and date
            vals.update({
                'date': date,
                'period_id': period_id,
            })
            # Create commitment
            commit_id = commit_obj.create(cr, uid, vals, context=context)
            # Add analytic distribution from purchase
            if po.analytic_distribution_id:
                new_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, po.analytic_distribution_id.id, {}, context=context)
                # Update this distribution not to have a link with purchase but with new commitment
                if new_distrib_id:
                    self.pool.get('analytic.distribution').write(cr, uid, [new_distrib_id], {'purchase_id': False, 'commitment_id': commit_id}, context=context)
                    # Create funding pool lines if needed
                    self.pool.get('analytic.distribution').create_funding_pool_lines(cr, uid, [new_distrib_id], context=context)
                    # Update commitment with new analytic distribution
                    self.pool.get('account.commitment').write(cr, uid, [commit_id], {'analytic_distribution_id': new_distrib_id}, context=context)
            # Browse purchase order lines and group by them by account_id
            for pol in po.order_line:
                # Search product account_id
                if pol.product_id:
                    a = pol.product_id.product_tmpl_id.property_account_expense.id
                    if not a:
                        a = pol.product_id.categ_id.property_account_expense_categ.id
                    if not a:
                        raise osv.except_osv(_('Error !'), _('There is no expense account defined for this product: "%s" (id:%d)') % (pol.product_id.name, pol.product_id.id,))
                else:
                    a = self.pool.get('ir.property').get(cr, uid, 'property_account_expense_categ', 'product.category').id
                fpos = po.fiscal_position or False
                a = self.pool.get('account.fiscal.position').map_account(cr, uid, fpos, a)
                # Write
                po_lines[a].append(pol)
            # Commitment lines process
            created_commitment_lines = []
            for account_id in po_lines:
                total_amount = 0.0
                for line in po_lines[account_id]:
                    total_amount += line.price_subtotal
                # Create commitment lines
                line_id = self.pool.get('account.commitment.line').create(cr, uid, {'commit_id': commit_id, 'amount': total_amount, 'initial_amount': total_amount, 'account_id': account_id, 'purchase_order_line_ids': [(6,0,[x.id for x in po_lines[account_id]])]}, context=context)
                created_commitment_lines.append(line_id)
            # Create analytic distribution on this commitment line
            self.pool.get('account.commitment.line').create_distribution_from_order_line(cr, uid, created_commitment_lines, context=context)
            # Display a message to inform that a commitment was created
            commit_data = self.pool.get('account.commitment').read(cr, uid, commit_id, ['name'], context=context)
            commit_name = commit_data and commit_data.get('name') or ''
            message = _("Commitment Voucher %s has been created.") % commit_name
            view_ids = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'account_commitment_form')
            view_id = view_ids and view_ids[1] or False
            self.pool.get('account.commitment').log(cr, uid, commit_id, message, context={'view_id': view_id})
        return True

    def wkf_approve_order(self, cr, uid, ids, context=None):
        """
        Checks:
        1/ if all purchase line could take an analytic distribution
        2/ if a commitment voucher should be created after PO approbation
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Analytic distribution verification
        ana_obj = self.pool.get('analytic.distribution')
        for po in self.browse(cr, uid, ids, context=context):
            if not po.analytic_distribution_id:
                for line in po.order_line:
                    if not line.analytic_distribution_id:
                        dummy_cc = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_project_dummy')
                        ana_id = ana_obj.create(cr, uid, {'purchase_ids': [(4,po.id)], 'cost_center_lines': [(0, 0, {'analytic_id': dummy_cc[1] , 'percentage':'100', 'currency_id': po.currency_id.id})]})
                        break
        # Default behaviour
        res = super(purchase_order, self).wkf_approve_order(cr, uid, ids, context=context)
        # Create commitments for each PO only if po is "from picking"
        for po in self.browse(cr, uid, ids, context=context):
            if po.invoice_method in ['picking', 'order']:
                self.action_create_commitment(cr, uid, [po.id], po.partner_id and po.partner_id.partner_type, context=context)
        return res

    def _finish_commitment(self, cr, uid, ids, context=None):
        """
        Change commitment(s) to Done state from given Purchase Order.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Browse PO
        for po in self.browse(cr, uid, ids, context=context):
            # Change commitment state if exists
            if po.commitment_ids:
                self.pool.get('account.commitment').action_commitment_done(cr, uid, [x.id for x in po.commitment_ids], context=context)
        return True

    def action_cancel(self, cr, uid, ids, context=None):
        """
        Delete commitment from purchase before 'cancel' state.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Change commitments state if exists
        self._finish_commitment(cr, uid, ids, context=context)
        return super(purchase_order, self).action_cancel(cr, uid, ids, context=context)

    def action_done(self, cr, uid, ids, context=None):
        """
        Delete commitment from purchase before 'done' state.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Change commitments state if all shipments have been invoiced (not in "to be invoiced" state)
        to_process = []
        for po in self.browse(cr, uid, ids, context=context):
            is_totally_done = True
            # If one shipment (stock.picking) is '2binvoiced', we shouldn't change commitments ' state
            for pick in po.picking_ids:
                if pick.invoice_state == '2binvoiced':
                    is_totally_done = False
            # Else shipment is fully done. We could change commitments ' state to Done.
            if is_totally_done:
                to_process.append(po.id)
        self._finish_commitment(cr, uid, to_process, context=context)
        return super(purchase_order, self).action_done(cr, uid, ids, context=context)

purchase_order()

class purchase_order_line(osv.osv):
    _name = 'purchase.order.line'
    _inherit = 'purchase.order.line'

    def create(self, cr, uid, vals, context=None):
        if (not 'price_unit' in vals or vals['price_unit'] == 0.00) and 'order_id' in vals and self.pool.get('purchase.order').browse(cr, uid, vals['order_id'], context=context).from_yml_test:
            vals['price_unit'] = 1.00

        return super(purchase_order_line, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]

        line = self.browse(cr, uid, ids, context=context)[0]
        if 'price_unit' in vals and vals['price_unit'] == 0.00 and self.pool.get('purchase.order').browse(cr, uid, vals.get('order_id', line.order_id.id), context=context).from_yml_test:
            vals['price_unit'] = 1.00

        return super(purchase_order_line, self).write(cr, uid, ids, vals, context=context)

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

    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
        'have_analytic_distribution_from_header': fields.function(_have_analytic_distribution_from_header, method=True, type='boolean', string='Header Distrib.?'),
        'commitment_line_ids': fields.many2many('account.commitment.line', 'purchase_line_commitment_rel', 'purchase_id', 'commitment_id', 
            string="Commitment Voucher Lines", readonly=True),
    }

    _defaults = {
        'have_analytic_distribution_from_header': lambda *a: True,
    }
    def button_analytic_distribution(self, cr, uid, ids, context=None):
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

    def copy_data(self, cr, uid, id, default=None, context=None):
        """
        Copy global distribution and give it to new purchase line
        Copy global distribution and give it to new purchase line.
        """
        # Some verifications
        if not context:
            context = {}
        if not default:
            default = {}
        # Update default
        default.update({'commitment_line_ids': [(6, 0, [])],})
        # Copy analytic distribution
        pol = self.browse(cr, uid, [id], context=context)[0]
        if pol.analytic_distribution_id:
            new_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, pol.analytic_distribution_id.id, {}, context=context)
            if new_distrib_id:
                default.update({'analytic_distribution_id': new_distrib_id})
        return super(purchase_order_line, self).copy_data(cr, uid, id, default, context)

purchase_order_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
