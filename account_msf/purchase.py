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

class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit = 'purchase.order'

    def create(self, cr, uid, vals, context=None):
        '''
        Change invoice method for in-kind donation PO to 'order' after its creation
        '''
        if not context:
            context = {}
        res = super(purchase_order, self).create(cr, uid, vals, context)
        if vals.get('order_type', False) and vals.get('order_type') == 'in_kind':
          vals.update({'invoice_method': 'order'})

        return res

    def write(self, cr, uid, ids, vals, context=None):
        """
        Change invoice method for in-kind donation PO after a write
        """
        if not context:
            context = {}
        res = super(purchase_order, self).write(cr, uid, ids, vals, context)
        if vals.get('order_type', False) and vals.get('order_type') == 'in_kind':
          cr.execute("UPDATE purchase_order SET invoice_method = 'order' WHERE id in %s", (tuple(ids),))
        return res

    def onchange_internal_type(self, cr, uid, ids, order_type, partner_id, dest_partner_id=False, warehouse_id=False):
        """
        Change invoice method for in-kind donation
        """
        res = super(purchase_order, self).onchange_internal_type(cr, uid, ids, order_type, partner_id, dest_partner_id, warehouse_id)
        if order_type in ['in_kind']:
            v = res.get('value', {})
            v.update({'invoice_method': 'order'})
            res.update({'value': v})
        return res

    def action_invoice_create(self, cr, uid, ids, *args):
        """
        Change some data on invoice resulting from a Donation PO
        """
        # Retrieve some data
        res = super(purchase_order, self).action_invoice_create(cr, uid, ids, *args) # invoice_id
        journal_inkind_ids = self.pool.get('account.journal').search(cr, uid, [('type', '=', 'inkind')])
        
        for po in self.browse(cr, uid, ids):
            if po.order_type == 'in_kind':
                if not journal_inkind_ids:
                    raise osv.except_osv(_('Error'), _('No In-kind donation journal found!'))
                account_id = po.partner_id and po.partner_id.donation_payable_account and po.partner_id.donation_payable_account.id or False
                if not account_id:
                    raise osv.except_osv(_('Error'), _('No Donation Payable account for this partner: %s') % (po.partner_id.name or '',))
                self.pool.get('account.invoice').write(cr, uid, [x.id for x in po.invoice_ids], {'journal_id': journal_inkind_ids[0], 'account_id': account_id})
        return res

    def inv_line_create(self, cr, uid, account_id, order_line):
        """
        Change account_id regarding product if the order line come from a In-kind Donation PO
        """
        # Retrieve data
        res = super(purchase_order, self).inv_line_create(cr, uid, account_id, order_line)
        # Change account_id regarding Donation expense account in Product first, then in Product Category
        if res and res[2] and order_line.order_id and order_line.order_id.order_type == 'in_kind':
            account_id = (order_line.product_id and order_line.product_id.donation_expense_account and order_line.product_id.donation_expense_account.id) \
                or (order_line.product_id.categ_id and order_line.product_id.categ_id.donation_expense_account and order_line.product_id.categ_id.donation_expense_account.id) \
                or False
            if not account_id:
                raise osv.except_osv(_('Error'), _('No donation expense account defined for this PO Line: %s') % (order_line.name or '',))
            res[2].update({'account_id': account_id,})
        # Return result
        return res

purchase_order()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
