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
        if isinstance(ids, int):
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
            'partner_type': so.partner_type,  # UF-2138: Add partner_type to the analytic distribution
            'currency_id': currency or False,
            'state': 'cc',
            'posting_date': strftime('%Y-%m-%d'),
            'document_date': strftime('%Y-%m-%d'),
        }
        if distrib_id:
            vals.update({'distribution_id': distrib_id, })
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
        Reset analytic distribution on all sale order lines.
        To do this, just delete the analytic_distribution id link on each sale order line.
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Prepare some values
        sale_obj = self.pool.get(self._name + '.line')
        # Search  lines
        to_reset = sale_obj.search(cr, uid, [('order_id', 'in', ids)])
        sale_obj.write(cr, uid, to_reset, {'analytic_distribution_id': False})
        return True

    def copy_data(self, cr, uid, s_id, default=None, context=None):
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
        new_data = super(sale_order, self).copy_data(cr, uid, s_id, default=default, context=context)

        # UFTP-322: After the copy_data above, if successfully, the name should be exactly the same as of the original document, so it must be increased
        # in the next statements. ::::::: One of the case that failed the copy_data call above is due to user right
        seq_obj = self.pool.get('ir.sequence')
        order = self.browse(cr, uid, s_id)
        if new_data and not 'name' in new_data or new_data.get('name', False) == order.name:
            name = (order.procurement_request or context.get('procurement_request', False)) and seq_obj.get(cr, uid, 'procurement.request') or seq_obj.get(cr, uid, 'sale.order')
            new_data.update({'name': name})

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

    def analytic_distribution_checks(self, cr, uid, order_brw_list, context=None):
        """
        Check analytic distribution for each sale order line (except if we come from YAML tests)
        Get a default analytic distribution if intermission.
        Change analytic distribution if intermission.
        """
        # Objects
        ana_obj = self.pool.get('analytic.distribution')
        sol_obj = self.pool.get('sale.order.line')
        distrib_line_obj = self.pool.get('cost.center.distribution.line')

        # Some verifications
        if context is None:
            context = {}

        if not isinstance(order_brw_list, list):
            order_brw_list = [order_brw_list]

        for so in order_brw_list:
            # Do not check analytic distribution on IR
            if so.procurement_request:
                continue

            missing_ad_lines = []
            for line in so.order_line:
                """
                UFTP-336: Do not check AD on FO lines if the lines are
                          created on a tender or a RfQ.
                          The AD must be added on the PO line and update the
                          AD at FO line at PO confirmation.
                """
                if line.created_by_tender or line.created_by_rfq:
                    continue
                # Check distribution presence
                l_ana_dist_id = line.analytic_distribution_id and line.analytic_distribution_id.id
                o_ana_dist_id = so.analytic_distribution_id and so.analytic_distribution_id.id
                distrib_id = l_ana_dist_id or o_ana_dist_id or False

                #US-830 : Remove the definition of a default AD for the inter-mission FO is no AD is defined
                if not distrib_id and not so.order_type in ('loan', 'loan_return', 'donation_st', 'donation_exp'):
                    # To display a single error when multiple lines have no AD
                    ad_sol_tuple = [line.name or '', line.line_number]
                    if ad_sol_tuple not in missing_ad_lines:
                        missing_ad_lines.append(ad_sol_tuple)
                    continue

                # Check distribution state
                if distrib_id and line.analytic_distribution_state != 'valid':
                    # Raise an error if no analytic distribution on line and NONE on header (because no possibility to change anything)
                    if (not line.analytic_distribution_id or line.analytic_distribution_state == 'none') and \
                       not so.analytic_distribution_id:
                        # We don't raise an error for these types
                        if so.order_type not in ('loan', 'loan_return', 'donation_st', 'donation_exp'):
                            # To display a single error when multiple lines have no AD
                            ad_sol_tuple = [line.name or '', line.line_number]
                            if ad_sol_tuple not in missing_ad_lines:
                                missing_ad_lines.append(ad_sol_tuple)
                            continue
                        else:
                            continue

                    # Change distribution to be valid if needed by using those from header
                    id_ad = ana_obj.create(cr, uid, {}, context=context)
                    # Get the CC lines of the FO line if any, or the ones of the order
                    cc_lines = line.analytic_distribution_id and line.analytic_distribution_id.cost_center_lines
                    cc_lines = cc_lines or so.analytic_distribution_id.cost_center_lines
                    for x in cc_lines:
                        # fetch compatible destinations then use one of them:
                        # - destination if compatible
                        # - else default destination of given account
                        bro_dests = self._get_destination_ok(cr, uid, [line], context=context)
                        if x.destination_id in bro_dests:
                            bro_dest_ok = x.destination_id
                        else:
                            bro_dest_ok = line.account_4_distribution.default_destination_id
                        # Copy cost center line to the new distribution
                        distrib_line_obj.copy(cr, uid, x.id, {'distribution_id': id_ad, 'destination_id': bro_dest_ok.id}, context=context)
                        # Write new distribution and link it to the line
                        sol_obj.write(cr, uid, [line.id], {'analytic_distribution_id': id_ad}, context=context)
                    # UFTP-277: Check funding pool lines if missing
                    ana_obj.create_funding_pool_lines(cr, uid, [id_ad], context=context)

            if missing_ad_lines:
                if len(missing_ad_lines) == 1:
                    raise osv.except_osv(_('Warning'), _('Analytic distribution is mandatory for this line: %s') % (missing_ad_lines[0][0],))
                else:
                    raise osv.except_osv(_('Warning'), _('Analytic distribution is missing for the lines %s. It must be added manually')
                                         % (', '.join([str(missing_ad_line[1]) for missing_ad_line in missing_ad_lines]),))

        return True


sale_order()


class sale_order_line(osv.osv):
    _name = 'sale.order.line'
    _inherit = 'sale.order.line'

    def _have_analytic_distribution_from_header(self, cr, uid, ids, name, arg, context=None):
        if isinstance(ids, int):
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
        if isinstance(ids, int):
            ids = [ids]
        # Prepare some values
        res = {}
        # Browse all given lines
        for line in self.browse(cr, uid, ids, context=context):
            if line.order_id and (not line.order_id.analytic_distribution_id or not line.order_id.analytic_distribution_id.cost_center_lines) and (not line.analytic_distribution_id or not line.analytic_distribution_id.cost_center_lines) :
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
        if isinstance(ids, int):
            ids = [ids]
        res = {}
        get_sel = self.pool.get('ir.model.fields').get_selection
        for sol in self.read(cr, uid, ids, ['analytic_distribution_state', 'have_analytic_distribution_from_header']):
            d_state = get_sel(cr, uid, self._name, 'analytic_distribution_state', sol['analytic_distribution_state'], context)
            res[sol['id']] = "%s%s" % (d_state, sol['have_analytic_distribution_from_header'] and _(" (from header)") or "")
        return res

    def _get_distribution_account(self, cr, uid, ids, name, arg, context=None):
        """
        Get account for given lines regarding:
        - product expense account if product_id
        - product category expense account if product_id but no product expense account
        - product category expense account if no product_id (come from family's product category link)
        """
        # Some verifications
        if isinstance(ids, int):
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
        if isinstance(ids, int):
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
            'partner_type': sol.order_id.partner_type,  # UF-2138: Add partner_type to the analytic distribution
            'currency_id': currency or False,
            'state': 'cc',
            'account_id': account_id or False,
            'posting_date': strftime('%Y-%m-%d'),
            'document_date': strftime('%Y-%m-%d'),
        }
        if distrib_id:
            vals.update({'distribution_id': distrib_id, })
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
        new_data = super(sale_order_line, self).copy_data(cr, uid, l_id, default, context)
        if new_data and new_data.get('analytic_distribution_id'):
            new_data['analytic_distribution_id'] = self.pool.get('analytic.distribution').copy(cr, uid, new_data['analytic_distribution_id'], {}, context=context)
        return new_data

sale_order_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
