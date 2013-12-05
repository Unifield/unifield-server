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
from time import strftime

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
            'posting_date': strftime('%Y-%m-%d'),
            'document_date': strftime('%Y-%m-%d'),
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
        if 'analytic_distribution_id' not in default and not context.get('keepDateAndDistrib'):
            default['analytic_distribution_id'] = False
        new_data = super(sale_order, self).copy_data(cr, uid, id, default=default, context=context)
        if new_data and new_data.get('analytic_distribution_id'):
            new_data['analytic_distribution_id'] = self.pool.get('analytic.distribution').copy(cr, uid, new_data['analytic_distribution_id'], {}, context=context)
        return new_data

    def _get_destination_ok(self, cr, uid, lines, context):
        dest_ok = False
        for line in lines:
            dest_ok = line.account_4_distribution and line.account_4_distribution.destination_ids or False
            if not dest_ok:
                raise osv.except_osv(_('Error'), _('No destination found for this line: %s.') % (line.name or '',))
        return dest_ok

    def analytic_distribution_checks(self, cr, uid, ids, context=None):
        """
        Check analytic distribution for each sale order line (except if we come from YAML tests)
        Get a default analytic distribution if intermission.
        Change analytic distribution if intermission.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Analytic distribution verification
        ana_obj = self.pool.get('analytic.distribution')
        for so in self.browse(cr, uid, ids, context=context):
            for line in so.order_line:
                # Search intermission
                intermission_cc = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 
                    'analytic_account_project_intermission')
                # check distribution presence
                distrib_id = (line.analytic_distribution_id and line.analytic_distribution_id.id) or (so.analytic_distribution_id and so.analytic_distribution_id.id) or False
                if not distrib_id and so.partner_id.partner_type == 'intermission':
                    account_id = line.account_4_distribution and line.account_4_distribution.id or False
                    # Search default destination_id
                    destination_id = self.pool.get('account.account').read(cr, uid, account_id, ['default_destination_id']).get('default_destination_id', False)
                    distrib_id = ana_obj.create(cr, uid, {'sale_order_line_ids': [(4,line.id)], 
                        'cost_center_lines': [(0, 0, {'destination_id': destination_id[0], 'analytic_id': intermission_cc[1] , 'percentage':'100', 'currency_id': so.currency_id.id})]})
                    self.pool.get('sale.order.line').write(cr, uid, [line.id], {'analytic_distribution_id': distrib_id})
                    line = self.pool.get('sale.order.line').browse(cr, uid, line.id)
                elif distrib_id and so.partner_id.partner_type == 'intermission':
                    # Change CC lines
                    for cc_line in ana_obj.browse(cr, uid, distrib_id).cost_center_lines:
                        # UTP-952: remove the default intermission cc
                        # self.pool.get('cost.center.distribution.line').write(cr, uid, cc_line.id, {'analytic_id': intermission_cc[1]})
                        pass
                        
                if not distrib_id and not so.from_yml_test and not so.order_type in ('loan', 'donation_st', 'donation_exp'):
                    raise osv.except_osv(_('Warning'), _('Analytic distribution is mandatory for this line: %s!') % (line.name or '',))
                # check distribution state
                if distrib_id and line.analytic_distribution_state != 'valid' and not so.from_yml_test:
                    # raise an error if no analytic distribution on line and NONE on header (because no possibility to change anything)
                    if (not line.analytic_distribution_id or line.analytic_distribution_state == 'none') and not so.analytic_distribution_id:
                        # we don't raise an error for these types
                        if not so.order_type in ('loan', 'donation_st', 'donation_exp'):
                            raise osv.except_osv(_('Warning'), _('Analytic distribution is mandatory for this line: %s') % (line.name or '',))
                        else:
                            continue
                    # Change distribution to be valid if needed by using those from header
                    id_ad = self.pool.get('analytic.distribution').create(cr,uid,{})
                    for x in line.analytic_distribution_id and line.analytic_distribution_id.cost_center_lines or so.analytic_distribution_id.cost_center_lines:
                        # fetch compatible destinations then use one of them:
                        # - destination if compatible
                        # - else default destination of given account
                        bro_dests = self._get_destination_ok(cr, uid, [line], context=context)
                        if x.destination_id in bro_dests:
                            bro_dest_ok = x.destination_id
                        else:
                            bro_dest_ok = line.account_4_distribution.default_destination_id
                        # Copy cost center line to the new distribution
                        self.pool.get('cost.center.distribution.line').copy(cr, uid, x.id, {'distribution_id': id_ad, 'destination_id': bro_dest_ok.id})
                        # Write new distribution and link it to the line
                        self.pool.get('sale.order.line').write(cr, uid, [line.id], {'analytic_distribution_id': id_ad})
        return True

    def action_ship_proc_create(self, cr, uid, ids, context=None):
        """
        Do some analytic distribution checks for SO confirmation.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Launch some checks
        self.analytic_distribution_checks(cr, uid, ids)
        # Default behaviour
        res = super(sale_order, self).action_ship_proc_create(cr, uid, ids, context=context)
        return res

    def wkf_validated(self, cr, uid, ids, context=None):
        """
        Do some analytic distribution checks for SO validation.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.analytic_distribution_checks(cr, uid, ids)
        # Default behaviour
        return super(sale_order, self).wkf_validated(cr, uid, ids, context=context)

    # action_invoice_create have been deleted because of no wizard_sale_invoice since 2.0b2
#    def action_invoice_create(self, cr, uid, ids, *args):
#        """
#        Add analytic distribution from SO to invoice
#        """
#        # Retrieve some data
#        res = super(sale_order, self).action_invoice_create(cr, uid, ids, *args) # invoice_id
#        # Set analytic distribution from sale order to invoice
#        ana_obj = self.pool.get('analytic.distribution')
#        for so in self.browse(cr, uid, ids):
#            # Create analytic distribution on invoices regarding FO
#            if so.analytic_distribution_id and so.invoice_ids:
#                invoice_ids = so.invoice_ids
#                if isinstance(invoice_ids, (int, long)):
#                    invoice_ids = [invoice_ids]
#                distrib_id = so.analytic_distribution_id and so.analytic_distribution_id.id or False
#                if distrib_id:
#                    new_distrib_id = ana_obj.copy(cr, uid, distrib_id, {})
#                    if not new_distrib_id:
#                        raise osv.except_osv(_('Error'), _('An error occured for analytic distribution copy for invoice.'))
#                    # create default funding pool lines
#                    ana_obj.create_funding_pool_lines(cr, uid, [new_distrib_id])
#                    self.pool.get('account.invoice').write(cr, uid, [invoice_ids], {'analytic_distribution_id': new_distrib_id,})
#            # Copy analytic distribution from sale order line to invoice lines
#            for sol in so.order_line:
#                if sol.analytic_distribution_id and sol.invoice_lines:
#                    sol_distrib_id = sol.analytic_distribution_id and sol.analytic_distribution_id.id or False
#                    if sol_distrib_id:
#                        for invl in sol.invoice_lines:
#                            new_sol_distrib_id = ana_obj.copy(cr, uid, sol_distrib_id, {})
#                            if not new_sol_distrib_id:
#                                raise osv.except_osv(_('Error'), _('An error occured for analytic distribution copy for invoice line.'))
#                            # create default funding pool lines
#                            ana_obj.create_funding_pool_lines(cr, uid, [new_sol_distrib_id])
#                            self.pool.get('account.invoice.line').write(cr, uid, [invl.id], {'analytic_distribution_id': new_sol_distrib_id,})
#        return res

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

    # METHOD _get_analytic_distribution_available removed (become useless since analytic distribution is mandatory on ALL FO)

    def _get_distribution_state(self, cr, uid, ids, name, args, context=None):
        """
        Get state of distribution:
         - if compatible with the sale order line, then "valid"
         - if no distribution, take a tour of sale order distribution, if compatible, then "valid"
         - if no distribution on sale order line and sale order, then "none"
         - all other case are "invalid"
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        # Browse all given lines
        for line in self.browse(cr, uid, ids, context=context):
            if line.order_id and line.order_id.from_yml_test:
                res[line.id] = 'valid'
            elif line.order_id and ( not line.order_id.analytic_distribution_id or not line.order_id.analytic_distribution_id.cost_center_lines ) and ( not line.analytic_distribution_id or not line.analytic_distribution_id.cost_center_lines ) :
                res[line.id] = 'none'
            else:
                so_distrib_id = line.order_id and line.order_id.analytic_distribution_id and line.order_id.analytic_distribution_id.id or False
                distrib_id = line.analytic_distribution_id and line.analytic_distribution_id.id or False
                account_id = line.account_4_distribution and line.account_4_distribution.id or False
                if not account_id:
                    res[line.id] = 'invalid'
                    continue
                res[line.id] = self.pool.get('analytic.distribution')._get_distribution_state(cr, uid, distrib_id, so_distrib_id, account_id)
        return res

    def _get_distribution_state_recap(self, cr, uid, ids, name, arg, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        get_sel = self.pool.get('ir.model.fields').get_selection
        for sol in self.read(cr, uid, ids, ['analytic_distribution_state', 'have_analytic_distribution_from_header']):
            d_state = get_sel(cr, uid, self._name, 'analytic_distribution_state', sol['analytic_distribution_state'], context)
            res[sol['id']] = "%s%s"%(d_state, sol['have_analytic_distribution_from_header'] and _(" (from header)") or "")
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
            # Fetch account
            if line.product_id:
                a = line.product_id.product_tmpl_id.property_account_income.id or False
                if not a:
                    a = line.product_id.categ_id.property_account_income_categ.id or False
            else:
                a = line.nomen_manda_2 and line.nomen_manda_2.category_id and line.nomen_manda_2.category_id.property_account_income_categ and line.nomen_manda_2.category_id.property_account_income_categ.id or False
            res[line.id] = a
        return res

    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
        'have_analytic_distribution_from_header': fields.function(_have_analytic_distribution_from_header, method=True, type='boolean', 
            string='Header Distrib.?'),
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
        # Search account_id
        account_id = sol.account_4_distribution and sol.account_4_distribution.id or False
        if not account_id:
            raise osv.except_osv(_('Error !'), _('There is no income account defined for this product: "%s" (id:%d)') % \
                (sol.product_id.name, sol.product_id.id,))
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'sale_order_line_id': sol.id,
            'currency_id': currency or False,
            'state': 'cc',
            'account_id': account_id or False,
            'posting_date': strftime('%Y-%m-%d'),
            'document_date': strftime('%Y-%m-%d'),
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
