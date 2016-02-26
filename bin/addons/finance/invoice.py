#-*- coding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 TeMPO Consulting, MSF. All Rights Reserved
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

class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    _columns = {
        'supplier_reference': fields.char('Supplier reference', size=128),
        'picking_id': fields.many2one('stock.picking', string="Picking"),
        'purchase_ids': fields.many2many('purchase.order', 'purchase_invoice_rel', 'invoice_id', 'purchase_id', 'Purchase Order',
            help="Purchase Order from which invoice have been generated"),
    }

account_invoice()

class account_invoice_line(osv.osv):
    _name = 'account.invoice.line'
    _inherit = 'account.invoice.line'

    _columns = {
        'order_line_id': fields.many2one('purchase.order.line', string="Purchase Order Line", readonly=True,
            help="Purchase Order Line from which this invoice line has been generated (when coming from a purchase order)."),
    }

account_invoice_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
