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


class stock_move(osv.osv):
    _name = 'stock.move'
    _inherit = 'stock.move'

    def action_cancel(self, cr, uid, ids, context=None):
        """
        Update commitment voucher line for the given moves
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        inv_obj = self.pool.get('account.invoice')
        account_amount = {}
        cvl_amount = {}
        po_ids = {}
        for move in self.browse(cr, uid, ids, context=context):
            # Fetch all necessary elements
            qty = move.product_uos_qty or move.product_qty or 0.0
            picking = move.picking_id or False
            if not picking or not move.purchase_line_id or picking.type !='in' or move.state == 'cancel':
                # If no picking then no PO have generated this stock move
                continue
            # fetch invoice type in order to retrieve price unit
            inv_type = self.pool.get('stock.picking')._get_invoice_type(picking) or 'out_invoice'
            price_unit = self.pool.get('stock.picking')._get_price_unit_invoice(cr, uid, move, inv_type)
            if not price_unit:
                # If no price_unit, so no impact on commitments because no price unit have been taken for commitment calculation
                continue

            po_ids[move.purchase_line_id.order_id.id] = True
            cv_line = move.purchase_line_id.cv_line_ids and move.purchase_line_id.cv_line_ids[0] or False
            cv_version = cv_line and cv_line.commit_id and cv_line.commit_id.version or 1
            if cv_version > 1:
                if cv_line.id not in cvl_amount:
                    cvl_amount[cv_line.id] = 0
                cvl_amount[cv_line.id] += round(qty * price_unit, 2)
            else:
                account_id = inv_obj._get_expense_account(cr, uid, move.purchase_line_id, context=context)
                if account_id:
                    if account_id not in account_amount:
                        account_amount[account_id] = 0
                    account_amount[account_id] += round(qty * price_unit, 2)
        if (account_amount or cvl_amount) and po_ids:
            inv_obj._update_commitments_lines(cr, uid, list(po_ids.keys()), account_amount_dic=account_amount, cvl_amount_dic=cvl_amount,
                                              from_cancel=ids, context=context)

        return super(stock_move, self).action_cancel(cr, uid, ids, context=context)

stock_move()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
