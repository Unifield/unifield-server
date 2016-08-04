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
from account_override.period import get_period_from_date
from account_override.period import get_date_in_period

from collections import defaultdict

class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit = 'purchase.order'

    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution', select=1),
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
        res = super(purchase_order, self).action_invoice_create(cr, uid, ids, args) # invoice_id
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
            'posting_date': strftime('%Y-%m-%d'),
            'document_date': strftime('%Y-%m-%d'),
            'partner_type': purchase.partner_type,
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
                'name': _('Global analytic distribution'),
                'type': 'ir.actions.act_window',
                'res_model': 'analytic.distribution.wizard',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [wiz_id],
                'context': context,
        }

    def button_reset_distribution(self, cr, uid, ids, context=None):
        """
        Reset analytic distribution on all purchase order lines.
        To do this, just delete the analytic_distribution id link on each purchase order line.
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        purchase_obj = self.pool.get(self._name + '.line')
        # Search purchase order lines
        to_reset = purchase_obj.search(cr, uid, [('order_id', 'in', ids)])
        purchase_obj.write(cr, uid, to_reset, {'analytic_distribution_id': False})
        return True

    def copy_data(self, cr, uid, p_id, default=None, context=None):
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
        if 'analytic_distribution_id' not in default:
            default['analytic_distribution_id'] = False
        # Default method
        return super(purchase_order, self).copy_data(cr, uid, p_id, default=default, context=context)

    def action_create_commitment(self, cr, uid, ids, ctype=False, context=None):
        """
        Create commitment from given PO, but only for external and esc partner_types
        """
        # Some verifications
        if not ctype or ctype not in ['external', 'esc']:
            return False
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        commit_obj = self.pool.get('account.commitment')
        instance_id = self.pool.get('res.users').browse(cr, uid, uid, context).company_id.instance_id.id
        args = [
            ('type', '=', 'engagement'),
            ('instance_id', '=', instance_id)
        ]
        eng_ids = self.pool.get('account.analytic.journal').search(cr, uid, args, limit=1, context=context)
        for po in self.browse(cr, uid, ids, context=context):
            # fetch analytic distribution, period from delivery date, currency, etc.
            vals = {
                'journal_id': eng_ids and eng_ids[0] or False,
                'currency_id': po.currency_id and po.currency_id.id or False,
                'partner_id': po.partner_id and po.partner_id.id or False,
                'purchase_id': po.id or False,
            }
            if po.partner_id and po.partner_id.partner_type == 'external':
                vals.update({'type': 'external'})
            else:
                vals.update({'type': 'manual'})
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
                    self.pool.get('analytic.distribution').write(cr, uid, [new_distrib_id],
                        {'purchase_id': False, 'commitment_id': commit_id}, context=context)
                    # Create funding pool lines if needed
                    self.pool.get('analytic.distribution').create_funding_pool_lines(cr, uid, [new_distrib_id], context=context)
                    # Update commitment with new analytic distribution
                    self.pool.get('account.commitment').write(cr, uid, [commit_id], {'analytic_distribution_id': new_distrib_id}, context=context)
            # Browse purchase order lines and group by them by account_id
            for pol in po.order_line:
                # Search product account_id
                a = pol.account_4_distribution and pol.account_4_distribution.id or False
                if not a:
                    raise osv.except_osv(_('Error'), _('There is no expense account defined for this line: %s (id:%d)') % (pol.name or '', pol.id))
                # Write
                po_lines[a].append(pol)
            # Commitment lines process
            created_commitment_lines = []
            for account_id in po_lines:
                total_amount = 0.0
                for line in po_lines[account_id]:
                    total_amount += line.price_subtotal
                # Create commitment lines
                line_id = self.pool.get('account.commitment.line').create(cr, uid, {
                    'commit_id': commit_id,
                    'amount': total_amount,
                    'initial_amount': total_amount, 'account_id': account_id,
                    'purchase_order_line_ids': [(6,0,[x.id for x in po_lines[account_id]])]
                }, context=context)
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
                for com in po.commitment_ids:
                    if com.type != 'manual':
                        self.pool.get('account.commitment').action_commitment_done(cr, uid, [x.id for x in po.commitment_ids], context=context)
        return True

    def wkf_action_cancel_po(self, cr, uid, ids, context=None):
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
        return super(purchase_order, self).wkf_action_cancel_po(cr, uid, ids, context=context)

    def action_done(self, cr, uid, ids, context=None):
        """
        Delete commitment from purchase before 'done' state.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Change commitments state
        # Sidestep UF-1183
        # If ONE invoice is in draft state, raise an error!
        to_process = []
        for po in self.browse(cr, uid, ids):
            have_draft_invoice = False
            for inv in po.invoice_ids:
                if inv.state == 'draft':
                    have_draft_invoice = True
                    break
            if not have_draft_invoice or not po.invoice_ids:
                to_process.append(po.id)
        self._finish_commitment(cr, uid, to_process, context=context)
        return super(purchase_order, self).action_done(cr, uid, ids, context=context)

purchase_order()

class purchase_order_line(osv.osv):
    _name = 'purchase.order.line'
    _inherit = 'purchase.order.line'

    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]

        if ids:
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

    def _get_distribution_state(self, cr, uid, ids, name, args, context=None):
        """
        Get state of distribution:
         - if compatible with the purchase line, then "valid"
         - if no distribution, take a tour of purchase distribution, if compatible, then "valid"
         - if no distribution on purchase line and purchase, then "none"
         - all other case are "invalid"
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
#         try:
#             intermission_cc = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution',
#                                     'analytic_account_project_intermission')[1]
#         except ValueError:
#             intermission_cc = 0
        ana_dist_obj = self.pool.get('analytic.distribution')
        # Browse all given lines
        for line in self.browse(cr, uid, ids, context=context):
#             is_intermission = False
#             if line.order_id and line.order_id.partner_id and line.order_id.partner_id.partner_type == 'intermission':
#                 is_intermission = True
            if line.order_id and line.order_id.from_yml_test:
                res[line.id] = 'valid'
            elif line.order_id and not line.order_id.analytic_distribution_id and not line.analytic_distribution_id:
                res[line.id] = 'none'
            else:
                po_distrib_id = line.order_id and line.order_id.analytic_distribution_id and line.order_id.analytic_distribution_id.id or False
                distrib_id = line.analytic_distribution_id and line.analytic_distribution_id.id or False
                account_id = line.account_4_distribution and line.account_4_distribution.id or False
                if not account_id:
                    res[line.id] = 'invalid'
                    continue
                res[line.id] = ana_dist_obj._get_distribution_state(cr, uid, distrib_id, po_distrib_id, account_id)

                # UTP-953: For intersection, the cc_intermission can also be used for all partner types, so the block below is removed
#                if res[line.id] == 'valid' and not is_intermission:
#                    cr.execute('SELECT id FROM cost_center_distribution_line WHERE distribution_id=%s AND analytic_id=%s', (po_distrib_id or distrib_id, intermission_cc))
#                    if cr.rowcount > 0:
#                        res[line.id] = 'invalid'

        return res

    def _get_distribution_state_recap(self, cr, uid, ids, name, arg, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        get_sel = self.pool.get('ir.model.fields').get_selection
        for pol in self.read(cr, uid, ids, ['analytic_distribution_state', 'have_analytic_distribution_from_header']):
            d_state = get_sel(cr, uid, self._name, 'analytic_distribution_state', pol['analytic_distribution_state'], context)
            res[pol['id']] = "%s%s"%(d_state, pol['have_analytic_distribution_from_header'] and _(" (from header)") or "")
        return res

    def _get_distribution_account(self, cr, uid, ids, name, arg, context=None):
        """
        Get account for given lines regarding:
        - product expense account if product_id
        - product category expense account if product_id but no product expense account
        - product category expense account if no product_id (come from family's product category link)
        """
        # Some verifications
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        for line in self.browse(cr, uid, ids):
            # Prepare some values
            res[line.id] = False
            a = False
            # Check if PO is inkind
            is_inkind = False
            if line.order_id and line.order_id.order_type == 'in_kind':
                is_inkind = True
            # To my mind there is 4 cases for a PO line (because of 2 criteria that affect account: "PO is inkind or not" and "line have a product or a nomenclature"):
            # - PO is an inkind donation AND PO line have a product: take donation expense account on product OR on product category, else raise an error
            # - PO is NOT inkind and PO line have a product: take product expense account OR category expense account
            # - PO is inkind but not PO Line product => this should not happens ! Should be raise an error but return False (if not we could'nt write a PO line)
            # - other case: take expense account on family that's attached to nomenclature
            if line.product_id and is_inkind:
                a = line.product_id.donation_expense_account and line.product_id.donation_expense_account.id or False
                if not a:
                    a = line.product_id.categ_id.donation_expense_account and line.product_id.categ_id.donation_expense_account.id or False
            elif line.product_id:
                a = line.product_id.product_tmpl_id.property_account_expense.id or False
                if not a:
                    a = line.product_id.categ_id.property_account_expense_categ.id or False
##### Line delete because we decided that nomenclature is possible in Inkind donations
#            elif is_inkind:
#                a = False # Should be raise an error, but this block view display. So nothing happens.
##### END of Line delete…
            else:
                a = line.nomen_manda_2 and line.nomen_manda_2.category_id and line.nomen_manda_2.category_id.property_account_expense_categ and line.nomen_manda_2.category_id.property_account_expense_categ.id or False
            res[line.id] = a
        return res

    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
        'have_analytic_distribution_from_header': fields.function(_have_analytic_distribution_from_header, method=True, type='boolean', string='Header Distrib.?'),
        'commitment_line_ids': fields.many2many('account.commitment.line', 'purchase_line_commitment_rel', 'purchase_id', 'commitment_id',
            string="Commitment Voucher Lines", readonly=True),
        'analytic_distribution_state': fields.function(_get_distribution_state, method=True, type='selection',
            selection=[('none', 'None'), ('valid', 'Valid'), ('invalid', 'Invalid')],
            string="Distribution state", help="Informs from distribution state among 'none', 'valid', 'invalid."),
        'analytic_distribution_state_recap': fields.function(_get_distribution_state_recap, method=True, type='char', size=30, string="Distribution"),
        'account_4_distribution': fields.function(_get_distribution_account, method=True, type='many2one', relation="account.account", string="Account for analytical distribution", readonly=True),
    }

    _defaults = {
        'have_analytic_distribution_from_header': lambda *a: True,
    }

    def button_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Launch analytic distribution wizard on a purchase order line.
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
        # Get default account
        account_id = purchase_line.account_4_distribution and purchase_line.account_4_distribution.id or False
        # Check if PO is inkind
        is_inkind = False
        if purchase_line.order_id and purchase_line.order_id.order_type == 'in_kind':
            is_inkind = True
        if is_inkind and not account_id:
            raise osv.except_osv(_('Error'), _('No donation account found for this line: %s. (product: %s)') % (purchase_line.name, purchase_line.product_id and purchase_line.product_id.name or ''))
        elif not account_id:
            raise osv.except_osv(_('Error !'),
                    _('There is no expense account defined for this product: "%s" (id:%d)') % (purchase_line.product_id.name, purchase_line.product_id.id))
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'purchase_line_id': purchase_line.id,
            'currency_id': currency or False,
            'state': 'cc',
            'account_id': account_id or False,
            'posting_date': strftime('%Y-%m-%d'),
            'document_date': strftime('%Y-%m-%d'),
            'partner_type': context.get('partner_type'),
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
                'name': _('Analytic distribution'),
                'type': 'ir.actions.act_window',
                'res_model': 'analytic.distribution.wizard',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [wiz_id],
                'context': context,
        }

    def copy_data(self, cr, uid, l_id, default=None, context=None):
        """
        Copy global distribution and give it to new purchase line.
        """
        # Some verifications
        if not context:
            context = {}
        if not default:
            default = {}
        # Update default
        default.update({'commitment_line_ids': [(6, 0, [])],})
        if 'analytic_distribution_id' not in default and not context.get('keepDateAndDistrib'):
            default['analytic_distribution_id'] = False
        new_data = super(purchase_order_line, self).copy_data(cr, uid, l_id, default, context)
        if new_data and new_data.get('analytic_distribution_id'):
            new_data['analytic_distribution_id'] = self.pool.get('analytic.distribution').copy(cr, uid, new_data['analytic_distribution_id'], {}, context=context)
        return new_data

purchase_order_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
