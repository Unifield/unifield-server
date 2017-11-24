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


class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit = 'purchase.order'

    def _get_fake(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Return fake data for down_payment_filter field
        """
        res = {}
        for i in ids:
            res[i] = False
        return res

    def _search_po_for_down_payment(self, cr, uid, obj, name, args, context=None):
        """
        Search PO available for down payments regarding these criteria:
        - the PO should not be 100% invoiced (invoice_rate field)
        - the PO state should be:
           confirm waiting ('confirm_wait' state),
           confirmed ('approved' state),
           but could be in done state and not completly invoiced
        - the currency should be the same as given currency in args
        - the partner should be the same as given partner in args

        To be 100% invoiced, a PO should have some linked invoiced that are validated ('open' state or 'paid' state) and that sum of amount is greater or equal to PO total amount. So to find PO that are not 100% invoiced, you should find those from which all invoice are not created or which amount is inferior to PO total amount.
        
        BKLG-51: new filters
        1) On PO state: only allow "confirmed" or "confirmed (waiting)" POs to be selected in the wizard
        (keeping 'done' for not completly invoiced)
        2) On PO type: only allow regular, purchase list and direct purchase order PO types
        3) Make sure that RFQs or tenders can not be linked to down payments
        1) state 'confirm_waiting' + 'approved' + 'done' (done tolerated if partially invoiced)
        2) order_type 'regular', 'purchase_list', 'direct'
        3) rfq_ok != True

        US-1064: new rule: as soon as all goods are received on a PO (state 'done') no new Down Payment is possible
        """
        # Create default result
        res = [('id', 'in', [])]
        # Only parse args that are composed of 3 element (field, operator, value)
        if args and args[0] and len(args[0]) == 3:
            # This method don't support operators except "="
            if args[0][1] != '=':
                raise osv.except_osv(_('Error'), _('Operator not supported yet!'))
            # Create SQL request
            c_id = args[0][2].get('currency_id', False)
            p_id = args[0][2].get('partner_id', False)
            sql = """SELECT po.id
            FROM purchase_order as po
            LEFT JOIN purchase_invoice_rel as pir ON (po.id = pir.purchase_id)
            LEFT JOIN account_invoice as inv ON (pir.invoice_id = inv.id AND inv.state not in ('draft', 'cancel'))
            LEFT JOIN product_pricelist as prod ON (po.pricelist_id = prod.id AND prod.currency_id = %s)
            LEFT JOIN purchase_order_line as pol ON (po.id = pol.order_id)
            WHERE po.pricelist_id = prod.id
            AND NOT (po.order_type = 'regular' AND po.partner_type in ('internal', 'esc'))
            AND po.order_type in ('regular', 'purchase_list')
            AND po.partner_id = %s
            AND po.rfq_ok != TRUE
            AND pol.state in ('confirmed', 'done')
            GROUP BY po.id, po.amount_total
            HAVING COALESCE(sum(pol.price_unit * pol.product_qty) - sum(inv.amount_total), 10) != 0;"""
            cr.execute(sql, (c_id, p_id))
            sql_res = cr.fetchall()
            # Transform result
            res = [('id', 'in', [x and x[0] for x in sql_res])]
        return res

    _columns = {
        'down_payment_ids': fields.one2many('account.move.line', 'down_payment_id', string="Down Payments", readonly=True),
        'down_payment_filter': fields.function(_get_fake, fnct_search=_search_po_for_down_payment, type="many2one", relation='purchase.order', method=True, string="PO for Down Payment"),
    }

    def copy(self, cr, uid, p_id, default=None, context=None):
        """
        Remove down_payment_ids field on new purchase.order
        """
        if not default:
            default = {}
        default.update({'down_payment_ids': False})
        return super(purchase_order, self).copy(cr, uid, p_id, default, context=context)

purchase_order()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
