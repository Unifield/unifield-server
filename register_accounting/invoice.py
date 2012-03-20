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
from tools.translate import _
import time

import netsvc

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

    def action_reconcile_direct_invoice(self, cr, uid, ids, context={}):
        """
        Reconcile move line if invoice is a Direct Invoice
        NB: In order to define that an invoice is a Direct Invoice, we need to have register_line_ids not null
        """
#        res = super(account_invoice, self).action_move_create(cr, uid, ids, context)
#        if res:
        for inv in self.browse(cr, uid, ids):
            # Verify that this invoice is linked to a register line and have a move
            if inv.move_id and inv.register_line_ids:
                ml_obj = self.pool.get('account.move.line')
                # First search move line that becomes from invoice
                res_ml_ids = ml_obj.search(cr, uid, [('move_id', '=', inv.move_id.id), ('account_id', '=', inv.account_id.id)])
                if len(res_ml_ids) > 1:
                    raise osv.except_osv(_('Error'), _('More than one journal items found for this invoice.'))
                invoice_move_line_id = res_ml_ids[0]
                # Then search move line that corresponds to the register line
                reg_line = inv.register_line_ids[0]
                reg_ml_ids = ml_obj.search(cr, uid, [('move_id', '=', reg_line.move_ids[0].id), ('account_id', '=', reg_line.account_id.id)])
                if len(reg_ml_ids) > 1:
                    raise osv.except_osv(_('Error'), _('More than one journal items found for this register line.'))
                register_move_line_id = reg_ml_ids[0]
                # Finally do reconciliation
                ml_reconcile_id = ml_obj.reconcile_partial(cr, uid, [invoice_move_line_id, register_move_line_id])
        return True
    
    def invoice_open(self, cr, uid, ids, context=None):
        """
        No longer fills the date automatically, but requires it to be set
        """
        wf_service = netsvc.LocalService("workflow")
        for inv in self.browse(cr, uid, ids):
            values = {}
            if not inv.date_invoice:
                values = {'date': time.strftime('%Y-%m-%d'), 'period_id': inv.period_id and inv.period_id.id or False, 'state': 'date'}
            if inv.type in ('in_invoice', 'in_refund') and abs(inv.check_total - inv.amount_total) >= (inv.currency_id.rounding/2.0):
                state = values and 'both' or 'amount'
                values.update({'check_total': inv.check_total , 'amount_total': inv.amount_total, 'state': state})
            if values:
                values['invoice_id'] = inv.id
                wiz_id = self.pool.get('wizard.invoice.date').create(cr, uid, values)
                return {
                    'name': "Missing Information",
                    'type': 'ir.actions.act_window',
                    'res_model': 'wizard.invoice.date',
                    'target': 'new',
                    'view_mode': 'form',
                    'view_type': 'form',
                    'res_id': wiz_id,
                    }
            
            wf_service.trg_validate(uid, 'account.invoice', inv.id, 'invoice_open', cr)
        return True

account_invoice()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
