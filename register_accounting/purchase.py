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

class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit = 'purchase.order'

    def _get_fake(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Return fake data for down_payment_filter field
        """
        res = {}
        for id in ids:
            res[id] = False
        return res

    def _search_po_for_down_payment(self, cr, uid, obj, name, args, context=None):
        """
        Search PO available for down payments
        """
        res = [('id', 'in', [])]
        if args and args[0] and len(args[0]) == 3:
            if args[0][1] != '=':
                raise osv.except_osv(_('Error'), _('Operator not supported yet!'))
            c_id = args[0][2].get('currency_id', False)
            p_id = args[0][2].get('partner_id', False)
            sql = """
            SELECT po.id
            FROM purchase_order as po
            WHERE po.pricelist_id = %s
            AND po.partner_id = %s""" % (c_id, p_id)
            sql2 = """
            SELECT res.purchase_id FROM (
                SELECT pir.purchase_id, po.amount_untaxed - SUM(inv.amount_total) as diff
                FROM purchase_invoice_rel as pir, account_invoice as inv, purchase_order as po
                WHERE pir.purchase_id = po.id AND pir.invoice_id = inv.id
                AND po.pricelist_id = %s AND po.partner_id = %s
                AND po.state in %s
                GROUP BY pir.purchase_id, po.amount_untaxed
                ) as res
            WHERE diff >= 0""" % (c_id, p_id, ('approved', 'done'))
            cr.execute(sql2)
            sql_res = cr.fetchall()
            po_ids = []
            res = [('id', 'in', [x and x.get('purchase_id') for x in sql_res])]
        return res

    _columns = {
        'down_payment_ids': fields.one2many('account.move.line', 'down_payment_id', string="Down Payments", readonly=True),
        'down_payment_filter': fields.function(_get_fake, fnct_search=_search_po_for_down_payment, type="many2one", method=True, string="PO for Down Payment"),
    }

    def copy(self, cr, uid, id, default=None, context=None):
        """
        Remove down_payment_ids field on new purchase.order
        """
        if not default:
            default = {}
        default.update({'down_payment_ids': False})
        return super(purchase_order, self).copy(cr, uid, id, default, context=context)

purchase_order()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
