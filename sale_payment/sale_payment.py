# -*- encoding: utf-8 -*-
##############################################################################
#
# OpenERP, Open Source Management Solution
# Copyright (c) 2009 Zikzakmedia S.L. (http://zikzakmedia.com) All Rights Reserved.
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

import netsvc
from osv import fields, osv

class sale_order(osv.osv):
    _inherit='sale.order'
    _columns={
        'payment_type': fields.many2one('payment.type', 'Payment type', help='The type of payment. It will be transferred to the invoice'),
        'partner_bank': fields.many2one('res.partner.bank','Bank Account', select=True, help='The bank account to pay to or to be paid from. It will be transferred to the invoice'),
    }

    def onchange_partner_id(self, cr, uid, ids, part):
        """Copy partner data in the sale order, including payment_type and acc_number"""
        result = super(sale_order, self).onchange_partner_id(cr, uid, ids, part)
        paytype_id = False
        if part:
            partner = self.pool.get('res.partner').browse(cr, uid, part)
            if partner:
                paytype_id = partner.payment_type_customer.id
                result['value']['payment_type'] = paytype_id

        return self.onchange_paytype_id(cr, uid, ids, paytype_id, part, result)

    def onchange_paytype_id(self, cr, uid, ids, paytype_id, partner_id, result = {'value': {}}):
        if paytype_id and partner_id:
            paytype = self.pool.get('payment.type').browse(cr, uid, paytype_id)
            if paytype.suitable_bank_types and paytype.active:
                # if the payment type is related to a bank account
                partner_bank_obj = self.pool.get('res.partner.bank')
                args = [('partner_id', '=', partner_id), ('default_bank', '=', 1)]
                bank_account_id = partner_bank_obj.search(cr, uid, args)
                if bank_account_id:
                    result['value']['partner_bank'] = bank_account_id[0]
                    return result
        result['value']['partner_bank'] = False
        return result

    def _make_invoice(self, cr, uid, order, lines, context={}):
        """ Redefines _make_invoice to create invoice with payment_type and acc_number from the sale order"""
        inv_id = super(sale_order, self)._make_invoice(cr, uid, order, lines, context)
        inv_obj = self.pool.get('account.invoice')
        inv_obj.write(cr, uid, [inv_id], {'payment_type':order.payment_type.id, 'partner_bank':order.partner_bank.id}, context=context)
        return inv_id

sale_order()
