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
from tools.translate import _

class wizard_down_payment(osv.osv_memory):
    _name = 'wizard.down.payment'
    _description = 'Down payment'

    _columns = {
        'register_line_id': fields.many2one('account.bank.statement.line', string="Register line", readonly=True, required=True),
        'purchase_id': fields.many2one('purchase.order', string="Purchase Order", readonly=True, required=False, 
            states={'draft': [('readonly', False), ('required', True)]}),
        'state': fields.selection([('draft', 'Draft'), ('closed', 'Closed')], string="State", required=True),
        'currency_id': fields.many2one('res.currency', string="Register line currency", required=True, readonly=True),
        'partner_id': fields.many2one('res.partner', string="Register line 3rd party", required=True, readonly=True),
    }

    _defaults = {
        'state': lambda *a: 'closed',
    }

    def check_register_line_and_po(self, cr, uid, absl_id, po_id, context=None):
        """
        Verify that register line amount is not superior to (PO total_amount - all down payments).
        Check partner on register line AND PO (should be equal)
        """
        # Some verifications
        if not absl_id or not po_id:
            return False
        if not context:
            context = {}
        if isinstance(absl_id, list):
            absl_id = absl_id[0]
        if isinstance(po_id, list):
            po_id = po_id[0]
        # Prepare some values
        po = self.pool.get('purchase.order').browse(cr, uid, po_id)
        absl = self.pool.get('account.bank.statement.line').browse(cr, uid, absl_id)
        # Verify that PO partner is the same as down payment partner
        if not absl.partner_id:
            raise osv.except_osv(_('Warning'), _('Third Party is mandatory for down payments!'))
        if po.partner_id.id != absl.partner_id.id:
            raise osv.except_osv(_('Error'), _('Third party from Down payment and Purchase Order are different!'))
        total = po.amount_total
        for dp in po.down_payment_ids:
            move_ids = [x.id or None for x in absl.move_ids]
            operator = 'in'
            if len(move_ids) == 1:
                operator = '='
            move_line_ids = self.pool.get('account.move.line').search(cr, uid, [('account_id', '=', absl.account_id.id), 
                ('move_id', operator, move_ids)])
            if dp.id not in move_line_ids:
                total -= dp.amount_currency
        if (-1 * absl.amount) > total:
            raise osv.except_osv(_('Warning'), 
                _('Register line amount is superior to (PO total amount - down payments). Maximum amount should be: %s') % (total))
        return True

    def button_validate(self, cr, uid, ids, context=None):
        """
        Validate the wizard to remember which PO have been selected from this register line.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Browse all wizards
        for wiz in self.browse(cr, uid, ids, context=context):
            # Some verifications
            if not wiz.register_line_id:
                raise osv.except_osv(_('Warning'), _('Please select a Register Line before.'))
            if not wiz.purchase_id:
                raise osv.except_osv(_('Warning'), _('Please choose a Purchase Order.'))
            # Verify that the PO is not invoiced
            if wiz.purchase_id.invoiced:
                raise osv.except_osv(_('Error'), _('You cannot add Down Payment on an invoiced PO.'))
            # Verify that the register line amount is not superior to (PO amount - all its down_payments (draft, temp and hard posted))
            self.check_register_line_and_po(cr, uid, wiz.register_line_id.id, wiz.purchase_id.id, context=context)
            # Write result to register line
            self.pool.get('account.bank.statement.line').write(cr, uid, [wiz.register_line_id.id], {'down_payment_id': wiz.purchase_id.id}, context=context)
        return {'type' : 'ir.actions.act_window_close'}

wizard_down_payment()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
