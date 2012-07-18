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
from tools.translate import _

class stock_picking(osv.osv):
    _name = 'stock.picking'
    _inherit = 'stock.picking'

    def _invoice_line_hook(self, cr, uid, move_line, invoice_line_id):
        """
        """
        res = super(stock_picking, self)._invoice_line_hook(cr, uid, move_line, invoice_line_id)
        if move_line.picking_id and move_line.picking_id.purchase_id and move_line.picking_id.purchase_id.order_type == 'in_kind':
            order_line = move_line.purchase_line_id or False
            account_id = (order_line.product_id and order_line.product_id.donation_expense_account and order_line.product_id.donation_expense_account.id) \
                or (order_line.product_id.categ_id and order_line.product_id.categ_id.donation_expense_account and order_line.product_id.categ_id.donation_expense_account.id) \
                or False
            if not account_id:
                raise osv.except_osv(_('Error'), _('No donation expense account defined for this PO Line: %s') % (order_line.name or '',))
            self.pool.get('account.invoice.line').write(cr, uid, [invoice_line_id], {'account_id': account_id,})
        return res

    def _hook_invoice_vals_before_invoice_creation(self, cr, uid, ids, invoice_vals, picking):
        """
        Update journal by an inkind journal if we come from an inkind donation PO.
        Update partner account
        """
        res = super(stock_picking, self)._hook_invoice_vals_before_invoice_creation(cr, uid, ids, invoice_vals, picking)
        journal_ids = self.pool.get('account.journal').search(cr, uid, [('type', '=', 'inkind')])
        if picking and picking.purchase_id and picking.purchase_id.order_type == "in_kind":
            if not journal_ids:
                raise osv.except_osv(_('Error'), _('No In-kind donation journal found!'))
            account_id = picking.partner_id and picking.partner_id.donation_payable_account and picking.partner_id.donation_payable_account.id or False
            if not account_id:
                raise osv.except_osv(_('Error'), _('No Donation Payable account for this partner: %s') % (picking.partner_id.name or '',))
            invoice_vals.update({'journal_id': journal_ids[0], 'account_id': account_id, 'is_inkind_donation': True,})
        return invoice_vals

    def action_invoice_create(self, cr, uid, ids, journal_id=False, group=False, type='out_invoice', context=None):
        """
        Fetch old analytic distribution on each purchase line (if exists)
        """
        distrib_obj = self.pool.get('analytic.distribution')
        res = {}
        res = super(stock_picking, self).action_invoice_create(cr, uid, ids, journal_id, group, type, context)
        for sp in self.browse(cr, uid, ids):
            if res.get(sp.id):
                inv = res[sp.id] or False
                if inv:
                    if sp.purchase_id and sp.purchase_id.analytic_distribution_id:
                        new_distrib_id = distrib_obj.copy(cr, uid, sp.purchase_id.analytic_distribution_id.id)
                        distrib_obj.create_funding_pool_lines(cr, uid, [new_distrib_id])
                        self.pool.get('account.invoice').write(cr, uid, [inv], {'analytic_distribution_id': new_distrib_id or False,})
                    for invl in self.pool.get('account.invoice').browse(cr, uid, inv).invoice_line:
                        if invl.order_line_id and invl.order_line_id.analytic_distribution_id:
                            new_distrib_id = distrib_obj.copy(cr, uid, invl.order_line_id.analytic_distribution_id.id)
                            distrib_obj.create_funding_pool_lines(cr, uid, [new_distrib_id], account_id=invl.account_id.id)
                            self.pool.get('account.invoice.line').write(cr, uid, invl.id, {'analytic_distribution_id': new_distrib_id or False})
        return res

stock_picking()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
