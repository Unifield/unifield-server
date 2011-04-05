#!/usr/bin/env python
#-*- encoding:utf-8 -*-
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

class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    def _get_virtual_fields(self, cr, uid, ids, field_name=None, arg=None, context={}):
        """
        Get fields in order to transform them into 'virtual fields" (kind of field duplicity):
         - currency_id
         - account_id
         - supplier
        """
        res = {}
        for inv in self.browse(cr, uid, ids, context=context):
            res[inv.id] = {'virtual_currency_id': inv.currency_id.id or False, 'virtual_account_id': inv.account_id.id or False, 
            'virtual_partner_id': inv.partner_id.id or False}
        return res

    _columns = {
        'register_line_ids': fields.one2many('account.bank.statement.line', 'invoice_id', string="Register Lines"),
        'address_invoice_id': fields.many2one('res.partner.address', 'Invoice Address', readonly=True, required=False, 
            states={'draft':[('readonly',False)]}),
        'virtual_currency_id': fields.function(_get_virtual_fields, method=True, store=False, multi='virtual_fields', string="Currency", 
            type='many2one', relation="res.currency", readonly=True),
        'virtual_account_id': fields.function(_get_virtual_fields, method=True, store=False, multi='virtual_fields', string="Account",
            type='many2one', relation="account.account", readonly=True),
        'virtual_partner_id': fields.function(_get_virtual_fields, method=True, store=False, multi='virtual_fields', string="Supplier",
            type='many2one', relation="res.partner", readonly=True),
    }

account_invoice()

class account_invoice_line(osv.osv):
    _name = 'account.invoice.line'
    _inherit = 'account.invoice.line'

    def _get_product_code(self, cr, uid, ids, field_name=None, arg=None, context={}):
        """
        Give product code for each invoice line
        """
        res = {}
        for inv_line in self.browse(cr, uid, ids, context=context):
            if inv_line.product_id:
                res[inv_line.id] = inv_line.product_id.default_code
        return res

    _columns = {
        'product_code': fields.function(_get_product_code, method=True, store=False, string="Product Code", type='string'),
    }

account_invoice_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
