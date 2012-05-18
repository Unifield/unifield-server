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

    def _get_virtual_fields(self, cr, uid, ids, field_name=None, arg=None, context=None):
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

    def action_reconcile_direct_invoice(self, cr, uid, ids, context=None):
        """
        Reconcile move line if invoice is a Direct Invoice
        NB: In order to define that an invoice is a Direct Invoice, we need to have register_line_ids not null
        """
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

    def create_down_payments(self, cr, uid, ids, amount, context=None):
        """
        Create down payments for given invoices
        """
        # Some verifications
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not amount:
            raise osv.except_osv(_('Warning'), _('Amount for Down Payment is missing!'))
        # Prepare some values
        res = []
        # Browse all elements
        for inv in self.browse(cr, uid, ids):
            # some verification
            if amount > inv.amount_total:
                raise osv.except_osv(_('Error'), _('Given down payment amount is superior to given invoice. Please check both.'))
            # prepare some values
            total = 0.0
            to_use = [] # should contains tuple with: down payment line id, amount
            
            # Create down payment until given amount is reached
            # browse all invoice purchase, then all down payment attached to purchases
            for po in inv.purchase_ids:
                # Order by id all down payment in order to have them in creation order
                dp_ids = self.pool.get('account.move.line').search(cr, uid, [('down_payment_id', '=', po.id)], order='date ASC, id ASC')
                for dp in self.pool.get('account.move.line').browse(cr, uid, dp_ids):
                    # verify that total is not superior to demanded amount
                    if total >= amount:
                        continue
                    diff = 0.0
                    # Take only line that have a down_payment_amount not superior or equal to line amount
                    if not dp.down_payment_amount > dp.amount_currency:
                        if amount > (abs(dp.amount_currency) - abs(dp.down_payment_amount)):
                            diff = (abs(dp.amount_currency) - abs(dp.down_payment_amount))
                        else:
                            diff = amount
                        # Have a tuple containing line id and amount to use for create a payment on invoice
                        to_use.append((dp.id, diff))
                    # Increment processed total
                    total += diff
            # Create counterparts and reconcile them
            for el in to_use:
                # create down payment counterpart on dp account
                # first create the move
                vals = {
                    'journal_id': inv.journal_id.id,
                    'period_id': inv.period_id.id,
                    'date': inv.date_invoice,
                    'partner_id': inv.partner_id.id,
                    'ref': ':'.join(['%s' % (x.name or '') for x in inv.purchase_ids]),
                }
                move_id = self.pool.get('account.move').create(cr, uid, vals)
                # then 2 lines for this move
                vals.update({
                    'move_id': move_id,
                    'partner_type_mandatory': True,
                    'currency_id': inv.currency_id.id,
                    'name': 'Down payment for ' + ':'.join(['%s' % (x.name or '') for x in inv.purchase_ids]),
                })
                # create dp counterpart line
                dp_account = self.pool.get('account.move.line').read(cr, uid, el[0], ['account_id']).get('account_id', False)
                debit = 0.0
                credit = el[1]
                if amount < 0:
                    credit = 0.0
                    debit = el[1]
                vals.update({
                    'account_id': dp_account and dp_account[0] or False,
                    'debit_currency': debit,
                    'credit_currency': credit,
                })
                dp_counterpart_id = self.pool.get('account.move.line').create(cr, uid, vals)
                # create supplier line
                vals.update({
                    'account_id': inv.account_id.id,
                    'debit_currency': credit, # opposite of dp counterpart line
                    'credit_currency': debit, # opposite of dp counterpart line
                })
                supplier_line_id = self.pool.get('account.move.line').create(cr, uid, vals)
                # post move
                self.pool.get('account.move').post(cr, uid, [move_id])
                # and reconcile down payment counterpart
                self.pool.get('account.move.line').reconcile_partial(cr, uid, [el[0], dp_counterpart_id], type='manual')
                # and reconcile invoice and supplier_line
                to_reconcile = [supplier_line_id]
                for line in inv.move_id.line_id:
                    if line.account_id.id == inv.account_id.id:
                        to_reconcile.append(line.id)
                if not len(to_reconcile) > 1:
                    raise osv.except_osv(_('Error'), _('Did not achieve invoice reconciliation with down payment.'))
                self.pool.get('account.move.line').reconcile_partial(cr, uid, to_reconcile)
                # add amount of invoice down_payment line on purchase order to keep used amount
                current_amount = self.pool.get('account.move.line').read(cr, uid, el[0], ['down_payment_amount']).get('down_payment_amount')
                self.pool.get('account.move.line').write(cr, uid, [el[0]], {'down_payment_amount': current_amount + el[1]})
                # add payment to result
                res.append(dp_counterpart_id)
        return res

    def check_down_payments(self, cr, uid, ids, context=None):
        """
        Verify that PO have down payments. If yes, launch down payment creation and attach it to invoice
        """
        # Some verification
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Browse all invoice and check PO
        for inv in self.browse(cr, uid, ids):
            total_payments = 0.0
            for po in inv.purchase_ids:
                for dp in po.down_payment_ids:
                    if abs(dp.down_payment_amount) < abs(dp.amount_currency):
                        total_payments += (dp.amount_currency - dp.down_payment_amount)
            if total_payments == 0.0:
                continue
            elif (inv.amount_total - total_payments) > 0.0:
                # Attach a down payment to this invoice
                self.create_down_payments(cr, uid, inv.id, total_payments)
            elif (inv.amount_total - total_payments) <= 0.0:
                # In this case, down payment permits to pay entirely invoice, that's why the down payment equals invoice total
                self.create_down_payments(cr, uid, inv.id, inv.amount_total)
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

    def action_open_invoice(self, cr, uid, ids, context=None, *args):
        """
        Add down payment check after others verifications
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = super(account_invoice, self).action_open_invoice(cr, uid, ids, context)
        for inv in self.browse(cr, uid, ids):
            # Create down payments for invoice that come from a purchase
            if inv.purchase_ids:
                self.check_down_payments(cr, uid, inv.id)
        return res

account_invoice()

class account_invoice_line(osv.osv):
    _name = 'account.invoice.line'
    _inherit = 'account.invoice.line'

    def _get_product_code(self, cr, uid, ids, field_name=None, arg=None, context=None):
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
