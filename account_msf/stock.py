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

    def action_invoice_create(self, cr, uid, ids, *args):
        """
        Change some data on invoice resulting from a Donation PO
        """
        # Retrieve some data
        res = super(stock_picking, self).action_invoice_create(cr, uid, ids, *args) # invoice_id
        journal_ids = self.pool.get('account.journal').search(cr, uid, [('type', '=', 'inkind')])
        for sp in self.browse(cr, uid, ids):
            if sp.purchase_id and sp.purchase_id.order_type == 'in_kind':
                if not journal_ids:
                    raise osv.except_osv(_('Error'), _('No In-kind donation journal found!'))
                account_id = sp.partner_id and sp.partner_id.donation_payable_account and sp.partner_id.donation_payable_account.id or False
                if not account_id:
                    raise osv.except_osv(_('Error'), _('No Donation Payable account for this partner: %s') % (sp.partner_id.name or '',))
                self.pool.get('account.invoice').write(cr, uid, [x.id for x in sp.purchase_id.invoice_ids], 
                    {'journal_id': journal_ids[0], 'account_id': account_id, 'is_inkind_donation': True,})
        return res

stock_picking()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
